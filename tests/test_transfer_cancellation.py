import logging
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from handler import ADBHandler
from ui.task_manager import WorkerThread


class BlockingProcess:
    def __init__(self, on_communicate=None):
        self.returncode = None
        self.started = threading.Event()
        self.stopped = threading.Event()
        self._on_communicate = on_communicate

    def communicate(self):
        if self._on_communicate:
            self._on_communicate()
        self.started.set()
        self.stopped.wait(2)
        return b"", b""

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9
        self.stopped.set()

    def wait(self):
        self.stopped.wait(2)
        return self.returncode


class TransferCancellationTests(unittest.TestCase):
    def make_handler(self):
        handler = ADBHandler.__new__(ADBHandler)
        handler.device_connected = True
        handler.device_serial = "test-device"
        handler.logger = logging.getLogger("test-transfer-cancellation")
        handler.last_error = None
        return handler

    def test_cancelled_pull_removes_new_local_destination_only(self):
        for destination_exists in (False, True):
            with self.subTest(destination_exists=destination_exists):
                with tempfile.TemporaryDirectory() as temp_dir:
                    destination = Path(temp_dir) / "partial.bin"
                    if destination_exists:
                        destination.write_bytes(b"original")

                    process = BlockingProcess(
                        lambda: destination.write_bytes(b"partial")
                    )
                    handler = self.make_handler()
                    with patch("handler.subprocess.Popen", return_value=process):
                        task = WorkerThread(
                            "Pull", handler.pull_file, "/remote.bin", str(destination)
                        )
                        task.start()
                        self.assertTrue(process.started.wait(1))
                        task.cancel()
                        task.wait()

                    self.assertEqual(destination.exists(), destination_exists)

    def test_cancelled_push_removes_only_new_remote_destination(self):
        for destination_exists in (False, True):
            with self.subTest(destination_exists=destination_exists):
                process = BlockingProcess()
                handler = self.make_handler()
                cleanup = []
                handler._remote_path_exists = lambda _path: destination_exists
                handler._remove_remote_partial = lambda path: cleanup.append(path)

                with patch("handler.subprocess.Popen", return_value=process):
                    task = WorkerThread(
                        "Push", handler.push_file, "local.bin", "/remote.bin"
                    )
                    task.start()
                    self.assertTrue(process.started.wait(1))
                    task.cancel()
                    task.wait()

                self.assertEqual(cleanup, [] if destination_exists else ["/remote.bin"])

    def test_cancelled_stream_removes_new_remote_file(self):
        handler = self.make_handler()
        process = BlockingProcess()
        process.stdout = type("Stdout", (), {"read": lambda self, _size: b""})()
        process.stderr = type("Stderr", (), {"read": lambda self: b""})()
        cleanup = []
        handler._remote_path_exists = lambda _path, _serial: False
        handler._remove_remote_partial = lambda path, _serial: cleanup.append(path)
        sync_started = threading.Event()

        def wait_for_cancellation(*_args, **_kwargs):
            sync_started.set()
            process.stopped.wait(2)
            return False, "cancelled"

        with patch.object(ADBHandler, "_exec_mkdir"), patch(
            "handler.subprocess.Popen", return_value=process
        ), patch.object(handler, "_adb_push_sync", side_effect=wait_for_cancellation):
            task = WorkerThread(
                "Device copy",
                handler.stream_file,
                "source-device",
                "/source.bin",
                "target-device",
                "/target.bin",
            )
            task.start()
            self.assertTrue(sync_started.wait(1))
            task.cancel()
            task.wait()

        self.assertEqual(cleanup, ["/target.bin"])

    def test_cancelled_on_device_copy_removes_new_remote_destination(self):
        handler = self.make_handler()
        handler._remote_path_exists = lambda _path: False
        cleanup = []
        handler._remove_remote_partial = lambda path: cleanup.append(path)
        started = threading.Event()
        release = threading.Event()

        def blocked_copy(*_args, **_kwargs):
            started.set()
            release.wait(2)
            return subprocess.CompletedProcess([], 1, "", "")

        handler.create_folder = lambda _path: True
        with patch.object(handler, "_run_adb_command", side_effect=blocked_copy):
            task = WorkerThread(
                "Device copy", handler.copy_on_device, "/source", "/target"
            )
            task.start()
            self.assertTrue(started.wait(1))
            task.cancel()
            release.set()
            task.wait()

        self.assertEqual(cleanup, ["/target"])


if __name__ == "__main__":
    unittest.main()
