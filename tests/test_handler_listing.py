import logging
import unittest
from types import SimpleNamespace

from handler import ADBHandler


class DirectoryListingTests(unittest.TestCase):
    def test_browses_directory_with_escaped_space_in_ls_output(self):
        handler = object.__new__(ADBHandler)
        handler.device_connected = True
        handler.device_serial = "test-device"
        handler.logger = logging.getLogger("test.ADBHandler")

        listing_with_escaped_space = SimpleNamespace(
            returncode=0,
            stdout="drwxr-xr-x 2 root root 4096 2026-10-15 08:00 My\\ Folder\n",
            stderr="",
        )
        child_listing = SimpleNamespace(
            returncode=0,
            stdout="total 0\n",
            stderr="",
        )

        def run_adb_command(command):
            if command[-1].startswith("ls -la '/storage' "):
                return listing_with_escaped_space
            return child_listing

        handler._run_adb_command = run_adb_command

        folders = handler.list_directory("/storage")
        child_items = handler.list_directory(folders[0].path)

        self.assertIsNotNone(child_items, "Entering the listed directory should succeed")
        self.assertEqual(folders[0].name, "My Folder")
        self.assertEqual(folders[0].path, "/storage/My Folder")


if __name__ == "__main__":
    unittest.main()
