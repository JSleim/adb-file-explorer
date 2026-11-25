import logging
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLineEdit

from handler import ADBHandler
from ui.device_panel import DevicePanel


class RenamePanelHandler:
    device_connected = True
    device_serial = "test-device"
    devices = {}

    def list_directory(self, *_args, **_kwargs):
        return []


class CaseOnlyRenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_case_only_rename_uses_a_temporary_path(self):
        handler = object.__new__(ADBHandler)
        handler.device_connected = True
        handler.root_mode = None
        handler.logger = logging.getLogger("test.ADBHandler")
        handler._run_adb_command = Mock(
            return_value=subprocess.CompletedProcess(["adb"], 0, "", "")
        )
        old_path = "/storage/emulated/0/MyFile.txt"
        new_path = "/storage/emulated/0/myfile.txt"

        self.assertTrue(handler.rename_item(old_path, new_path))

        command = handler._run_adb_command.call_args.args[0][-1]
        self.assertIn(old_path, command)
        self.assertIn(new_path, command)
        self.assertIn("adb-explorer-rename-", command)
        self.assertGreaterEqual(command.count("mv -n"), 3)

    def test_rename_dialog_selects_name_without_extension(self):
        panel = DevicePanel(None, RenamePanelHandler())
        selection = []

        def inspect_dialog():
            dialog = self.app.activeModalWidget()
            line_edit = dialog.findChild(QLineEdit)
            selection.append(line_edit.selectedText())
            dialog.accept()

        QTimer.singleShot(10, inspect_dialog)
        panel.rename_item("photo.jpg")

        self.assertEqual(selection, ["photo"])
        panel.close()
        panel.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
