import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QStandardItem
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.device_panel import DevicePanel


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class NavigationShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.refresh_files = lambda: None
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_navigation_history_supports_back_forward_and_branches(self):
        self.panel.navigate_to("/storage/first")
        self.panel.navigate_to("/storage/second")
        self.panel.go_back()

        self.assertEqual(self.panel.current_path, "/storage/first")

        self.panel.go_forward()
        self.assertEqual(self.panel.current_path, "/storage/second")

        self.panel.go_back()
        self.panel.navigate_to("/storage/third")
        self.panel.go_forward()

        self.assertEqual(self.panel.current_path, "/storage/third")
        self.assertEqual(
            self.panel.path_history,
            ["/storage/emulated/0", "/storage/first", "/storage/third"],
        )

    def test_up_navigation_is_added_to_history(self):
        self.panel.navigate_to("/storage/emulated/0/DCIM")
        self.panel.go_up()
        self.panel.go_back()

        self.assertEqual(self.panel.current_path, "/storage/emulated/0/DCIM")

    def test_enter_activates_selected_directory(self):
        self.panel.tree_model.appendRow([
            QStandardItem("Pictures"),
            QStandardItem("Directory"),
            QStandardItem(""),
            QStandardItem(""),
            QStandardItem(""),
        ])

        self.panel.tree_view.setCurrentIndex(self.panel.tree_model.index(0, 0))
        self.panel.tree_view.setFocus()
        QTest.keyClick(self.panel.tree_view, Qt.Key.Key_Return)

        self.assertEqual(
            self.panel.current_path,
            "/storage/emulated/0/Pictures",
        )

    def test_mouse_back_button_navigates_to_previous_directory(self):
        self.panel.navigate_to("/storage/first")
        self.panel.navigate_to("/storage/second")

        QTest.mouseClick(
            self.panel.tree_view.viewport(),
            Qt.MouseButton.BackButton,
        )

        self.assertEqual(self.panel.current_path, "/storage/first")

        QTest.mouseClick(
            self.panel.tree_view.viewport(),
            Qt.MouseButton.ForwardButton,
        )

        self.assertEqual(self.panel.current_path, "/storage/second")

    def test_navigation_and_focus_shortcuts_are_registered(self):
        keys = {
            shortcut.key().toString()
            for shortcut in self.panel._shortcuts
        }

        self.assertTrue({
            "Alt+Left",
            "Alt+Right",
            "Alt+Up",
            "Backspace",
            "F5",
            "Ctrl+F",
            "Ctrl+L",
        }.issubset(keys))
        self.assertEqual(self.panel.search_bar.placeholderText(), "Filter files")

    def test_navigation_and_focus_keys_trigger_their_actions(self):
        refresh_calls = []
        self.panel.refresh_files = lambda: refresh_calls.append(True)
        self.panel.navigate_to("/storage/first")
        self.panel.navigate_to("/storage/second")
        self.panel.tree_view.setFocus()

        QTest.keyClick(
            self.panel.tree_view,
            Qt.Key.Key_Left,
            Qt.KeyboardModifier.AltModifier,
        )
        self.assertEqual(self.panel.current_path, "/storage/first")

        QTest.keyClick(
            self.panel.tree_view,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.AltModifier,
        )
        self.assertEqual(self.panel.current_path, "/storage/second")

        QTest.keyClick(self.panel.tree_view, Qt.Key.Key_Backspace)
        self.assertEqual(self.panel.current_path, "/storage/first")

        QTest.keyClick(
            self.panel.tree_view,
            Qt.Key.Key_Up,
            Qt.KeyboardModifier.AltModifier,
        )
        self.assertEqual(self.panel.current_path, "/storage")

        QTest.keyClick(self.panel.tree_view, Qt.Key.Key_F5)
        self.assertTrue(refresh_calls)

        QTest.keyClick(
            self.panel.tree_view,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertIs(QApplication.focusWidget(), self.panel.search_bar)

        QTest.keyClick(
            self.panel.search_bar,
            Qt.Key.Key_L,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertIs(QApplication.focusWidget(), self.panel.path_display)

    def test_delete_shortcut_warns_about_folder_contents(self):
        self.panel.adb_handler.device_connected = True
        self.panel.tree_model.appendRow([
            QStandardItem("Pictures"),
            QStandardItem("Directory"),
            QStandardItem(""),
            QStandardItem(""),
            QStandardItem(""),
        ])
        self.panel.tree_view.setCurrentIndex(self.panel.tree_model.index(0, 0))
        self.panel.tree_view.setFocus()

        with patch(
            "ui.device_panel.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question, patch.object(
            self.panel.adb_handler, "delete_item", create=True
        ) as delete_item:
            QTest.keyClick(self.panel.tree_view, Qt.Key.Key_Delete)

        self.assertIn("all of its contents", question.call_args.args[2])
        self.assertIn("subfolders", question.call_args.args[2])
        delete_item.assert_not_called()

if __name__ == "__main__":
    unittest.main()
