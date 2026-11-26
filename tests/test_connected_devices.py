import unittest
import subprocess
from unittest.mock import Mock

from handler import ADBHandler


class ConnectedDeviceTests(unittest.TestCase):
    def test_connection_check_ignores_header_and_offline_device(self):
        handler = object.__new__(ADBHandler)
        handler.device_serial = "device-1"
        handler.logger = Mock()
        handler._run_adb_command = lambda *_args: subprocess.CompletedProcess(
            ["adb", "devices"],
            0,
            "List of devices attached\ndevice-1\toffline\n",
            "",
        )

        self.assertFalse(handler.check_adb_connection())

    def test_connection_check_only_matches_this_device(self):
        handler = object.__new__(ADBHandler)
        handler.device_serial = "device-1"
        handler.logger = Mock()
        handler._run_adb_command = lambda *_args: subprocess.CompletedProcess(
            ["adb", "devices"],
            0,
            "List of devices attached\ndevice-1\toffline\ndevice-2\tdevice\n",
            "",
        )

        self.assertFalse(handler.check_adb_connection())

    def test_connection_check_accepts_this_device_in_device_state(self):
        handler = object.__new__(ADBHandler)
        handler.device_serial = "device-1"
        handler.logger = Mock()
        handler._run_adb_command = lambda *_args: subprocess.CompletedProcess(
            ["adb", "devices"],
            0,
            "List of devices attached\ndevice-1\tdevice product:phone\n",
            "",
        )

        self.assertTrue(handler.check_adb_connection())

    def test_remote_path_check_distinguishes_missing_from_unknown(self):
        handler = object.__new__(ADBHandler)
        handler.logger = Mock()

        handler._run_adb_command = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["adb", "shell", "stat"],
            1,
            "stat: '/missing' : No such file or directory",
            "",
        )
        self.assertFalse(handler._remote_path_exists("/missing"))

        handler._run_adb_command = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["adb", "shell", "stat"],
            1,
            "",
            "stat: '/private' : Permission denied",
        )
        self.assertIsNone(handler._remote_path_exists("/private"))
        self.assertEqual(handler.last_error, "stat: '/private' : Permission denied")

    def test_remote_path_check_accepts_stat_output(self):
        handler = object.__new__(ADBHandler)
        handler.logger = Mock()
        handler._run_adb_command = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["adb", "shell", "stat"],
            0,
            "83 1792156390\n",
            "",
        )

        self.assertTrue(handler._remote_path_exists("/existing"))

    def test_rename_item_uses_no_clobber_and_root_mode(self):
        handler = object.__new__(ADBHandler)
        handler.device_connected = True
        handler.root_mode = "su"
        handler.logger = Mock()
        commands = []

        def run_adb_command(command):
            commands.append(command)
            return subprocess.CompletedProcess(["adb"], 0, "", "")

        handler._run_adb_command = run_adb_command

        self.assertTrue(
            handler.rename_item(
                "/data/user/0/test.log",
                "/data/user/0/test (1).log",
                use_root=True,
            )
        )
        self.assertEqual(commands[0][:3], ["shell", "su", "-c"])
        self.assertIn("mv -n", commands[0][3])
        self.assertIn("test ! -e", commands[0][3])

    def test_unique_devices_prefers_usb_endpoint_for_same_physical_device(self):
        handler = object.__new__(ADBHandler)
        handler.get_connected_devices = lambda: {
            "R58M123USB": "Pixel_8",
            "192.168.1.44:5555": "Pixel_8",
            "R58M987USB": "Pixel_7",
        }
        identities = {
            "R58M123USB": "physical-pixel-8",
            "192.168.1.44:5555": "physical-pixel-8",
            "R58M987USB": "physical-pixel-7",
        }
        handler.get_device_identity = identities.__getitem__

        devices = handler.get_unique_devices()

        self.assertEqual(devices, {
            "R58M123USB": "Pixel_8",
            "R58M987USB": "Pixel_7",
        })


if __name__ == "__main__":
    unittest.main()
