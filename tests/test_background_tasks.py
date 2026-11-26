import os
import sys
import threading
import time
import unittest
import logging
import tempfile
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QMainWindow,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QWidget,
    QVBoxLayout,
)

from operation_control import register_process
from handler import ADBHandler, FileItem
from ui.device_panel import ApplyToAllCheckBox, DevicePanel
from ui.task_manager import BackgroundTaskManager, WorkerThread
from ui.theme import DARK, LIGHT


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class ConnectedHandler(DisconnectedHandler):
    device_connected = True

    def __init__(self):
        self.uploaded = []
        self.created_folders = []
        self.existing_remote_dirs = set()
        self.remote_listing = {}
        self.renamed = []

    def _remote_path_exists(self, remote_path, use_root=False):
        return remote_path in self.existing_remote_dirs

    def create_folder(self, remote_path):
        self.created_folders.append(remote_path)
        return True

    def push_file(self, local_path, remote_path):
        self.uploaded.append((local_path, remote_path))
        return True

    def rename_item(self, old_path, new_path, use_root=False):
        self.renamed.append((old_path, new_path, use_root))
        return True

    def list_directory(self, path, use_root=False):
        return self.remote_listing.get(path, [])


class BackgroundTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_panel_operation_dialog_has_background_action(self):
        window = QMainWindow()
        central = QWidget(window)
        layout = QVBoxLayout(central)
        task_manager = BackgroundTaskManager(central)
        window.task_manager = task_manager
        layout.addWidget(task_manager)
        panel = DevicePanel(central, DisconnectedHandler())
        layout.addWidget(panel)
        window.setCentralWidget(central)

        task = panel._run_modal("Test operation", lambda: True)
        dialog = panel.findChild(QDialog)
        buttons = dialog.findChildren(QPushButton)

        self.assertIn("Background", [button.text() for button in buttons])
        self.assertFalse(
            dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint
        )
        next(button for button in buttons if button.text() == "Background").click()
        self.assertEqual(len(task_manager._tasks), 1)

        task.wait()
        self.app.processEvents()
        window.close()

    def test_rebackgrounding_reopened_operation_does_not_duplicate_task(self):
        window = QMainWindow()
        central = QWidget(window)
        layout = QVBoxLayout(central)
        task_manager = BackgroundTaskManager(central)
        window.task_manager = task_manager
        layout.addWidget(task_manager)
        panel = DevicePanel(central, DisconnectedHandler())
        layout.addWidget(panel)
        window.setCentralWidget(central)

        started = threading.Event()
        release = threading.Event()

        def wait_until_released():
            started.set()
            release.wait(2)
            return True

        task = panel._run_modal("Test operation", wait_until_released)
        self.assertTrue(started.wait(1))
        dialog = panel.findChild(QDialog)
        background_button = next(
            button for button in dialog.findChildren(QPushButton)
            if button.text() == "Background"
        )
        background_button.click()
        self.assertEqual(len(task_manager._tasks), 1)

        row = task_manager._tasks[0]
        row._on_reopen()
        self.app.processEvents()
        self.assertTrue(dialog.isVisible())
        background_button.click()
        self.app.processEvents()

        self.assertFalse(dialog.isVisible())
        self.assertEqual(len(task_manager._tasks), 1)
        self.assertIs(task_manager._tasks[0], row)

        release.set()
        task.wait()
        self.app.processEvents()
        window.close()

    def test_pc_folder_import_runs_as_a_background_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            nested_file = source / "Nested" / "photo.jpg"
            nested_file.parent.mkdir()
            nested_file.write_bytes(b"image")
            (source / "Empty").mkdir()

            window = QMainWindow()
            central = QWidget(window)
            layout = QVBoxLayout(central)
            task_manager = BackgroundTaskManager(central)
            window.task_manager = task_manager
            layout.addWidget(task_manager)
            handler = ConnectedHandler()
            panel = DevicePanel(central, handler)
            initial_refresh_task = panel._refresh_task
            panel.refresh_files = lambda: None
            layout.addWidget(panel)
            window.setCentralWidget(central)

            modal_tasks = []
            original_run_modal = panel._run_modal

            def track_modal_task(*args, **kwargs):
                task = original_run_modal(*args, **kwargs)
                modal_tasks.append(task)
                return task

            panel._run_modal = track_modal_task
            panel.upload_files_and_folders([str(source)])
            dialog = panel.findChild(QDialog)
            next(button for button in dialog.findChildren(QPushButton)
                 if button.text() == "Background").click()
            task = task_manager._tasks[0].task
            task.wait()
            deadline = time.monotonic() + 2
            while len(modal_tasks) < 2 and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            if len(modal_tasks) == 2:
                modal_tasks[1].wait()
                self.app.processEvents()
            if initial_refresh_task is not None:
                initial_refresh_task.wait()
                self.app.processEvents()

            self.assertEqual(set(handler.created_folders), {
                f"/storage/emulated/0/{source.name}",
                f"/storage/emulated/0/{source.name}/Nested",
                f"/storage/emulated/0/{source.name}/Empty",
            })
            self.assertEqual(handler.uploaded, [(
                str(nested_file),
                f"/storage/emulated/0/{source.name}/Nested/photo.jpg",
            )])
            window.close()

    def test_existing_upload_is_skipped_without_modifying_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "same.txt"
            source.write_text("source")
            handler = ConnectedHandler()
            remote_dir = "/storage/emulated/0"
            handler.existing_remote_dirs.add(remote_dir)
            handler.remote_listing[remote_dir] = [
                FileItem("same.txt", f"{remote_dir}/same.txt", False, 83,
                         "rw-r--r--", "2026-10-16 13:13")
            ]
            panel = SimpleNamespace(
                adb_handler=handler,
                status_label=QLabel(),
                refresh_files=lambda: None,
                use_root=False,
            )
            plan = DevicePanel._build_upload_plan(
                [str(source)], "/storage/emulated/0"
            )
            conflicts, = DevicePanel._inspect_upload_conflicts(panel, plan)
            ran_upload = []

            def run_modal(_title, fn, *args, on_done=None, **_kwargs):
                result = fn(*args)
                ran_upload.append(result)
                on_done(result)

            panel._confirm_upload_conflict = lambda *_args: ("skip", False)
            panel._run_modal = run_modal
            DevicePanel._resolve_upload_conflicts(panel, plan, conflicts)

            self.assertEqual(handler.uploaded, [])
            self.assertEqual(ran_upload, [(0, 1, 0)])
            self.assertEqual(
                panel.status_label.text(),
                "Uploaded 0 files; skipped 1; preserved 0 existing files",
            )

    def test_overwrite_conflict_uploads_to_original_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "same.txt"
            source.write_text("replacement")
            handler = ConnectedHandler()
            remote_dir = "/storage/emulated/0"
            handler.existing_remote_dirs.add(remote_dir)
            handler.remote_listing[remote_dir] = [
                FileItem("same.txt", f"{remote_dir}/same.txt", False, 83,
                         "rw-r--r--", "2026-10-16 13:13")
            ]
            panel = SimpleNamespace(
                adb_handler=handler,
                status_label=QLabel(),
                refresh_files=lambda: None,
                use_root=False,
            )
            plan = DevicePanel._build_upload_plan([str(source)], remote_dir)
            conflicts, = DevicePanel._inspect_upload_conflicts(panel, plan)

            def run_modal(_title, fn, *args, on_done=None, **_kwargs):
                result = fn(*args)
                on_done(result)

            panel._confirm_upload_conflict = lambda *_args: ("overwrite", False)
            panel._run_modal = run_modal
            DevicePanel._resolve_upload_conflicts(panel, plan, conflicts)

            self.assertEqual(
                handler.uploaded,
                [(str(source), f"{remote_dir}/same.txt")],
            )
            self.assertEqual(
                panel.status_label.text(),
                "Uploaded 1 files; skipped 0; preserved 0 existing files",
            )

    def test_rename_destination_preserves_file_with_next_numbered_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "test.log"
            source.write_text("replacement")
            handler = ConnectedHandler()
            remote_dir = "/storage/emulated/0"
            handler.existing_remote_dirs.add(remote_dir)
            handler.remote_listing[remote_dir] = [
                FileItem("test.log", f"{remote_dir}/test.log", False, 83,
                         "rw-r--r--", "2026-10-16 13:13"),
                FileItem("test (1).log", f"{remote_dir}/test (1).log", False, 10,
                         "rw-r--r--", "2026-10-15 13:13"),
            ]
            panel = SimpleNamespace(
                adb_handler=handler,
                status_label=QLabel(),
                refresh_files=lambda: None,
                use_root=False,
            )
            plan = DevicePanel._build_upload_plan([str(source)], remote_dir)
            conflicts, = DevicePanel._inspect_upload_conflicts(panel, plan)

            def run_modal(_title, fn, *args, on_done=None, **_kwargs):
                result = fn(*args)
                on_done(result)

            panel._confirm_upload_conflict = lambda *_args: ("rename", False)
            panel._run_modal = run_modal
            DevicePanel._resolve_upload_conflicts(panel, plan, conflicts)

            self.assertEqual(
                handler.renamed,
                [(
                    f"{remote_dir}/test.log",
                    f"{remote_dir}/test (2).log",
                    False,
                )],
            )
            self.assertEqual(
                handler.uploaded,
                [(str(source), f"{remote_dir}/test.log")],
            )
            self.assertIn("preserved 1 existing files", panel.status_label.text())

    def test_upload_preflight_aborts_when_destination_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "same.txt"
            source.write_text("source")
            handler = ConnectedHandler()
            def inaccessible(_path, use_root=False):
                handler.last_error = "Permission denied"
                return None

            handler._remote_path_exists = inaccessible
            panel = SimpleNamespace(
                adb_handler=handler,
                use_root=False,
            )
            plan = DevicePanel._build_upload_plan(
                [str(source)], "/data/user/0"
            )

            with self.assertRaisesRegex(RuntimeError, "Permission denied"):
                DevicePanel._inspect_upload_conflicts(panel, plan)

    def test_apply_to_all_skips_each_conflicting_upload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = []
            remote_dir = "/storage/emulated/0"
            handler = ConnectedHandler()
            handler.existing_remote_dirs.add(remote_dir)
            handler.remote_listing[remote_dir] = []
            for filename in ("first.txt", "second.txt"):
                source = Path(temp_dir) / filename
                source.write_text(filename)
                sources.append(str(source))
                handler.remote_listing[remote_dir].append(
                    FileItem(filename, f"{remote_dir}/{filename}", False, 8,
                             "rw-r--r--", "2026-10-16 13:13")
                )
            panel = SimpleNamespace(
                adb_handler=handler,
                status_label=QLabel(),
                refresh_files=lambda: None,
                use_root=False,
            )
            plan = DevicePanel._build_upload_plan(sources, remote_dir)
            conflicts, = DevicePanel._inspect_upload_conflicts(panel, plan)
            ran_upload = []

            def run_modal(_title, fn, *args, on_done=None, **_kwargs):
                result = fn(*args)
                ran_upload.append(result)
                on_done(result)

            confirms = []
            panel._confirm_upload_conflict = lambda *_args: (
                confirms.append(True) or ("skip", True)
            )
            panel._run_modal = run_modal
            DevicePanel._resolve_upload_conflicts(panel, plan, conflicts)

            self.assertEqual(len(confirms), 1)
            self.assertEqual(handler.uploaded, [])
            self.assertEqual(ran_upload, [(0, 2, 0)])

    def test_cancelled_upload_conflict_does_not_start_transfer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "same.txt"
            source.write_text("source")
            handler = ConnectedHandler()
            remote_dir = "/storage/emulated/0"
            handler.existing_remote_dirs.add(remote_dir)
            handler.remote_listing[remote_dir] = [
                FileItem("same.txt", f"{remote_dir}/same.txt", False, 83,
                         "rw-r--r--", "2026-10-16 13:13")
            ]
            panel = SimpleNamespace(
                adb_handler=handler,
                status_label=QLabel(),
                refresh_files=lambda: None,
                use_root=False,
            )
            plan = DevicePanel._build_upload_plan(
                [str(source)], remote_dir
            )
            conflicts, = DevicePanel._inspect_upload_conflicts(panel, plan)
            run_modal_calls = []

            panel._confirm_upload_conflict = lambda *_args: ("cancel", False)
            panel._run_modal = lambda *args, **kwargs: run_modal_calls.append(args)
            DevicePanel._resolve_upload_conflicts(panel, plan, conflicts)

            self.assertEqual(run_modal_calls, [])
            self.assertEqual(handler.uploaded, [])
            self.assertIn("no files were uploaded", panel.status_label.text())

    def test_conflict_dialog_shows_file_details_and_apply_to_all(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "test.log"
            source.write_bytes(b"x" * 98)
            panel = DevicePanel(None, DisconnectedHandler())
            existing = FileItem(
                "test.log",
                "/data/user/0/test.log",
                False,
                83,
                "rw-r--r--",
                "2026-10-16 13:13",
            )
            dialog_text = []
            checkmark_pixels = []

            def click_overwrite():
                box = next(
                    widget
                    for widget in QApplication.topLevelWidgets()
                    if isinstance(widget, QMessageBox)
                )
                dialog_text.append(box.informativeText())
                checkbox = box.findChild(QCheckBox, "apply_to_all_conflicts")
                self.assertEqual(checkbox.text(), "Apply to all conflicts")
                self.assertIsInstance(checkbox, ApplyToAllCheckBox)
                self.assertEqual(
                    checkbox.accessibleName(), "Apply to all file conflicts"
                )
                self.assertTrue(checkbox.toolTip())
                checkbox.setChecked(True)
                checkbox.repaint()
                image = checkbox.grab().toImage()
                option = QStyleOptionButton()
                checkbox.initStyleOption(option)
                indicator = checkbox.style().subElementRect(
                    QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox
                )
                bright_pixels = 0
                for x in range(indicator.left(), indicator.right() + 1):
                    for y in range(indicator.top(), indicator.bottom() + 1):
                        color = image.pixelColor(x, y)
                        if (
                            color.red() > 230
                            and color.green() > 230
                            and color.blue() > 230
                        ):
                            bright_pixels += 1
                checkmark_pixels.append(bright_pixels)
                next(
                    button
                    for button in box.findChildren(QPushButton)
                    if button.text() == "Overwrite"
                ).click()

            original_stylesheet = self.app.styleSheet()
            try:
                for theme in (LIGHT, DARK):
                    self.app.setStyleSheet(theme)
                    QTimer.singleShot(0, click_overwrite)
                    choice, apply_to_all = panel._confirm_upload_conflict(
                        "/data/user/0/test.log", str(source), existing
                    )
                    self.assertEqual(choice, "overwrite")
                    self.assertTrue(apply_to_all)
            finally:
                self.app.setStyleSheet(original_stylesheet)

            self.assertIn("98 Bytes", dialog_text[0])
            self.assertIn("83 Bytes", dialog_text[0])
            self.assertIn("/data/user/0/test.log", dialog_text[0])
            self.assertEqual(len(checkmark_pixels), 2)
            self.assertTrue(all(pixel_count > 0 for pixel_count in checkmark_pixels))
            panel.close()

    def test_conflict_dialog_uses_short_rename_button_label(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "test.log"
            source.write_text("source")
            panel = DevicePanel(None, DisconnectedHandler())
            existing = FileItem(
                "test.log", "/data/user/0/test.log", False, 83,
                "rw-r--r--", "2026-10-16 13:13",
            )
            button_labels = []

            def click_rename():
                box = next(
                    widget
                    for widget in QApplication.topLevelWidgets()
                    if isinstance(widget, QMessageBox)
                )
                buttons = box.findChildren(QPushButton)
                button_labels.extend(button.text() for button in buttons)
                next(button for button in buttons if button.text() == "Rename").click()

            QTimer.singleShot(0, click_rename)
            choice, _apply_to_all = panel._confirm_upload_conflict(
                "/data/user/0/test.log", str(source), existing
            )

            self.assertEqual(choice, "rename")
            self.assertIn("Rename", button_labels)
            self.assertNotIn("Rename Destination", button_labels)
            panel.close()

    def test_import_folder_uses_selected_pc_directory(self):
        panel = DevicePanel(None, ConnectedHandler())
        with (
            patch.object(QFileDialog, "getExistingDirectory", return_value="C:\\Photos"),
            patch.object(panel, "upload_files_and_folders") as upload,
        ):
            panel.import_folder_from_pc()

        upload.assert_called_once_with(["C:\\Photos"])
        panel.close()

    def test_panel_operation_error_callback_runs_once(self):
        panel = DevicePanel(None, DisconnectedHandler())
        errors = []

        def fail():
            raise RuntimeError("expected failure")

        task = panel._run_modal(
            "Failing operation",
            fail,
            on_error=lambda: errors.append("failed"),
        )
        task.wait()
        self.app.processEvents()

        self.assertEqual(errors, ["failed"])
        panel.close()

    def test_panel_operation_cancel_callback_runs(self):
        panel = DevicePanel(None, DisconnectedHandler())
        started = threading.Event()
        release = threading.Event()
        cancelled = []

        def wait_for_cancel():
            started.set()
            release.wait(1)
            return False

        task = panel._run_modal(
            "Cancellable operation",
            wait_for_cancel,
            on_cancel=lambda: cancelled.append(True),
        )
        dialog = panel.findChild(QDialog)
        self.assertTrue(started.wait(1))
        next(button for button in dialog.findChildren(QPushButton)
             if button.text() == "Cancel").click()
        release.set()
        task.wait()
        self.app.processEvents()

        self.assertEqual(cancelled, [True])
        panel.close()

    def test_cancel_does_not_kill_an_unrelated_task_process(self):
        class FakeProcess:
            def __init__(self):
                self.killed = False

            def poll(self):
                return None

            def kill(self):
                self.killed = True

        process = FakeProcess()
        entered = threading.Event()
        release = threading.Event()

        def wait_with_process():
            register_process(process)
            entered.set()
            release.wait(1)

        unrelated_task = WorkerThread("Active transfer", wait_with_process)
        unrelated_task.start()
        self.assertTrue(entered.wait(1))
        cancelled_task = WorkerThread("Unrelated task", lambda: time.sleep(0.05))
        try:
            cancelled_task.start()
            cancelled_task.cancel()
            cancelled_task.wait()
        finally:
            release.set()
            unrelated_task.wait()

        self.assertFalse(process.killed)

    def test_cancel_stops_resources_owned_by_the_task(self):
        class FakeProcess:
            def __init__(self):
                self.killed = False

            def poll(self):
                return None

            def kill(self):
                self.killed = True

        process = FakeProcess()
        entered = threading.Event()
        release = threading.Event()

        def wait_with_process():
            register_process(process)
            entered.set()
            release.wait(1)

        task = WorkerThread("Cancellable task", wait_with_process)
        task.start()
        self.assertTrue(entered.wait(1))
        try:
            task.cancel()
            self.assertTrue(process.killed)
        finally:
            release.set()
            task.wait()

        self.assertTrue(task.is_cancelled())

    def test_worker_cancel_runs_native_cancel_callback(self):
        called = []
        task = WorkerThread("Native drag", lambda: time.sleep(0.05))
        task.add_cancel_callback(lambda: called.append("cancelled"))
        task.start()
        task.cancel()
        task.wait()
        self.assertEqual(called, ["cancelled"])

    def test_cancel_terminates_the_adb_command_owned_by_the_task(self):
        class BlockingProcess:
            def __init__(self):
                self.started = threading.Event()
                self.stopped = threading.Event()
                self.returncode = None

            def communicate(self, timeout=None):
                self.started.set()
                self.stopped.wait(timeout)
                return "", ""

            def poll(self):
                return self.returncode

            def kill(self):
                self.returncode = -9
                self.stopped.set()

        process = BlockingProcess()
        handler = ADBHandler.__new__(ADBHandler)
        handler.device_serial = "test-device"
        handler.logger = logging.getLogger("test-adb-handler")
        with patch("handler.subprocess.Popen", return_value=process):
            task = WorkerThread("ADB command", handler._run_adb_command, ["shell", "long-op"])
            task.start()
            self.assertTrue(process.started.wait(1))
            task.cancel()
            task.wait()

        self.assertEqual(process.returncode, -9)
        self.assertTrue(task.is_cancelled())


if __name__ == "__main__":
    unittest.main()
