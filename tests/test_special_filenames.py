import logging
import shlex
import subprocess
import unittest
from unittest.mock import Mock

from handler import ADBHandler


class SpecialFilenameTests(unittest.TestCase):
    def test_shell_path_escaping_preserves_special_filename(self):
        handler = object.__new__(ADBHandler)
        path = "/storage/emulated/0/space 'quote\" $HOME `cmd` &; ([]) café.txt"

        escaped = handler._escape_path(path)

        self.assertEqual(shlex.split(escaped), [path])
        self.assertTrue(escaped.startswith("'"))

    def test_create_file_passes_special_path_as_one_shell_argument(self):
        handler = object.__new__(ADBHandler)
        handler.device_connected = True
        handler.logger = logging.getLogger("test.ADBHandler")
        handler._run_adb_command = Mock(
            return_value=subprocess.CompletedProcess(["adb"], 0, "", "")
        )
        path = "/storage/emulated/0/test'test & [1].txt"

        self.assertTrue(handler.create_file(path))

        command = handler._run_adb_command.call_args.args[0][-1]
        self.assertEqual(shlex.split(command)[1:], [path])


if __name__ == "__main__":
    unittest.main()
