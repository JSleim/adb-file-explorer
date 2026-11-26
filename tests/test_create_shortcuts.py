import os
import sys
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from ui.device_panel import DevicePanel


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class CreateShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.refresh_files = Mock()
        self.panel.show()
        self.panel.adb_handler.device_connected = True
        self.panel.adb_handler.create_folder = Mock(return_value=True)
        self.panel.adb_handler.create_file = Mock(return_value=True)
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_shortcuts_prompt_and_create_folders_and_text_files(self):
        keys = {shortcut.key().toString() for shortcut in self.panel._shortcuts}
        self.assertIn("Ctrl+Shift+N", keys)
        self.assertIn("Ctrl+Shift+T", keys)
        self.panel.tree_view.setFocus()

        def run_modal(_title, operation, *args, on_done=None, **_kwargs):
            result = operation(*args)
            if on_done:
                on_done(result)

        with patch(
            "ui.device_panel.QInputDialog.getText",
            side_effect=[("New Folder", True), ("notes.txt", True)],
        ) as prompt, patch.object(
            self.panel, "_run_modal", side_effect=run_modal
        ) as run:
            QTest.keyClick(
                self.panel.tree_view,
                Qt.Key.Key_N,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            )
            QTest.keyClick(
                self.panel.tree_view,
                Qt.Key.Key_T,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            )

        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(
            [call.args for call in prompt.call_args_list],
            [
                (self.panel, "New Folder", "Folder name:"),
                (self.panel, "New File", "File name:"),
            ],
        )
        self.panel.adb_handler.create_folder.assert_called_once_with(
            "/storage/emulated/0/New Folder"
        )
        self.panel.adb_handler.create_file.assert_called_once_with(
            "/storage/emulated/0/notes.txt"
        )
        self.assertEqual(run.call_count, 2)

    def test_cancelled_name_prompt_does_not_start_creation(self):
        self.panel.tree_view.setFocus()
        with patch(
            "ui.device_panel.QInputDialog.getText", return_value=("", False)
        ), patch.object(self.panel, "_run_modal") as run:
            QTest.keyClick(
                self.panel.tree_view,
                Qt.Key.Key_N,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            )

        run.assert_not_called()
        self.panel.adb_handler.create_folder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
