import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QToolButton

from handler import FileItem
from ui.device_panel import DevicePanel
from ui.theme import DARK, LIGHT


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class NestedDirectoryHandler(DisconnectedHandler):
    def __init__(self):
        self.listed_paths = []

    def list_directory(self, path, _use_root=False):
        self.listed_paths.append(path)
        if path == "/storage/emulated/0/DCIM":
            return [
                FileItem("Camera", f"{path}/Camera", True, 0, "", ""),
            ]
        if path == "/storage/emulated/0/DCIM/Camera":
            return [
                FileItem("2026", f"{path}/2026", True, 0, "", ""),
            ]
        return []


class PathAutocompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.populate_view([
            FileItem("DCIM", "/storage/emulated/0/DCIM", True, 0, "", ""),
            FileItem("photo.jpg", "/storage/emulated/0/photo.jpg", False, 8, "", ""),
        ])
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def _type_path_prefix(self, prefix):
        self.panel.focus_address_bar()
        self.panel.path_display.selectAll()
        QTest.keyClicks(self.panel.path_display, prefix)
        self.app.processEvents()

    def test_tab_completes_absolute_path_segment_with_trailing_slash(self):
        self._type_path_prefix("/st")
        popup = self.panel.path_display.completer().popup()
        self.assertTrue(popup.isVisible())

        QTest.keyClick(popup, Qt.Key.Key_Tab)

        self.assertEqual(self.panel.path_display.text(), "/storage/")
        self.assertIs(QApplication.focusWidget(), self.panel.path_display)

    def test_tab_without_a_matching_suggestion_keeps_address_bar_focused(self):
        self.panel.focus_address_bar()
        self.panel.path_display.setText("/directory-not-loaded")
        self.panel.path_display._completion_model.setStringList([])
        self.app.processEvents()

        QTest.keyClick(self.panel.path_display, Qt.Key.Key_Tab)
        self.app.processEvents()

        self.assertIs(QApplication.focusWidget(), self.panel.path_display)
        self.assertIs(
            self.panel.path_stack.currentWidget(), self.panel.path_display
        )

    def test_right_arrow_completes_current_directory_child(self):
        self._type_path_prefix("/storage/emulated/0/DC")

        QTest.keyClick(self.panel.path_display, Qt.Key.Key_Right)

        self.assertEqual(self.panel.path_display.text(), "/storage/emulated/0/DCIM/")

    def test_completion_continues_after_each_path_separator(self):
        self._type_path_prefix("/st")
        for expected, typed in (
            ("/storage/", None),
            ("/storage/emulated/", "em"),
            ("/storage/emulated/0/", "0"),
            ("/storage/emulated/0/DCIM/", "DC"),
        ):
            if typed:
                QTest.keyClicks(self.panel.path_display, typed)
            QTest.keyClick(self.panel.path_display, Qt.Key.Key_Tab)
            self.assertEqual(self.panel.path_display.text(), expected)

    def test_typing_separator_loads_suggestions_for_nested_directory(self):
        handler = NestedDirectoryHandler()
        handler.device_connected = True
        self.panel.adb_handler = handler

        self._type_path_prefix("/storage/emulated/0/DCIM/")
        self._wait_for_completion("/storage/emulated/0/DCIM/Camera/")

        QTest.keyClicks(self.panel.path_display, "Cam")
        popup = self.panel.path_display.completer().popup()
        self.assertTrue(popup.isVisible())
        QTest.keyClick(popup, Qt.Key.Key_Tab)
        self.assertEqual(
            self.panel.path_display.text(), "/storage/emulated/0/DCIM/Camera/"
        )
        self._wait_for_completion("/storage/emulated/0/DCIM/Camera/2026/")

        QTest.keyClicks(self.panel.path_display, "20")
        popup = self.panel.path_display.completer().popup()
        self.assertTrue(popup.isVisible())
        QTest.keyClick(popup, Qt.Key.Key_Tab)
        self.assertEqual(
            self.panel.path_display.text(),
            "/storage/emulated/0/DCIM/Camera/2026/",
        )

        self.assertIn("/storage/emulated/0/DCIM", handler.listed_paths)
        self.assertIn("/storage/emulated/0/DCIM/Camera", handler.listed_paths)

    def _wait_for_completion(self, completion):
        for _ in range(50):
            self.app.processEvents()
            if completion in (
                self.panel.path_display._completion_model.stringList()
            ):
                break
            QTest.qWait(10)
        self.assertIn(
            completion, self.panel.path_display._completion_model.stringList()
        )

    def test_completion_popup_has_light_and_dark_theme_rules(self):
        popup = self.panel.path_display.completer().popup()
        self.assertEqual(popup.objectName(), "path_completion_popup")
        breadcrumb_scroll = self.panel.path_breadcrumbs._scroll_area
        self.assertEqual(breadcrumb_scroll.objectName(), "path_breadcrumb_scroll")
        self.assertEqual(
            breadcrumb_scroll.viewport().objectName(),
            "path_breadcrumb_viewport",
        )
        self.assertEqual(
            breadcrumb_scroll.widget().objectName(),
            "path_breadcrumb_content",
        )

        self.assertIn("QListView#path_completion_popup", LIGHT)
        self.assertIn("background-color: #ffffff;", LIGHT)
        self.assertIn("QToolButton#path_breadcrumb_segment", LIGHT)
        self.assertIn("QWidget#path_breadcrumb_viewport", LIGHT)

        self.assertIn("QListView#path_completion_popup", DARK)
        self.assertIn("background-color: #1e1e2e;", DARK)
        self.assertIn("QToolButton#path_breadcrumb_segment", DARK)
        self.assertIn("QWidget#path_breadcrumb_viewport", DARK)
        self.assertIn("background-color: #181825;", DARK)

    def test_clicking_breadcrumb_navigates_to_that_path_segment(self):
        segment = next(
            button
            for button in self.panel.path_breadcrumbs.findChildren(QToolButton)
            if button.text() == "emulated"
        )

        QTest.mouseClick(segment, Qt.MouseButton.LeftButton)

        self.assertEqual(self.panel.current_path, "/storage/emulated")
        self.assertIs(
            self.panel.path_stack.currentWidget(), self.panel.path_breadcrumbs
        )
        self.assertEqual(self.panel.path_display.text(), "/storage/emulated")

    def test_edit_button_keeps_address_bar_typing_and_escape_returns_to_breadcrumbs(self):
        edit_button = self.panel.path_breadcrumbs.findChild(
            QToolButton, "path_breadcrumb_edit"
        )
        QTest.mouseClick(edit_button, Qt.MouseButton.LeftButton)
        self.assertIs(
            self.panel.path_stack.currentWidget(), self.panel.path_display
        )
        self.assertIs(QApplication.focusWidget(), self.panel.path_display)

        QTest.keyClick(self.panel.path_display, Qt.Key.Key_Escape)

        self.assertIs(
            self.panel.path_stack.currentWidget(), self.panel.path_breadcrumbs
        )
        self.assertEqual(self.panel.path_display.text(), self.panel.current_path)

    def test_navigation_bar_does_not_expand_vertically_with_panel(self):
        self.panel.resize(700, 500)
        self.app.processEvents()
        nav_container = self.panel.path_stack.parentWidget()

        self.assertLessEqual(
            nav_container.height(),
            nav_container.sizeHint().height() + 2,
        )

    def test_long_path_does_not_increase_minimum_width_and_current_segment_stays_visible(self):
        short_path_minimum = self.panel.minimumSizeHint().width()
        short_path_hint = self.panel.sizeHint().width()
        long_path = (
            "/storage/emulated/0/Android/data/"
            "com.example.someverylongpackage.name/files/"
            "verylongfoldername/anotherdeepfolder/finaldestination"
        )
        self.panel.current_path = long_path
        self.panel.update_path_display()
        self.panel.resize(420, 500)
        self.app.processEvents()
        QTest.qWait(10)

        self.assertLessEqual(
            self.panel.minimumSizeHint().width(),
            short_path_minimum + 5,
        )
        self.assertLessEqual(self.panel.sizeHint().width(), short_path_hint + 5)

        scroll_area = self.panel.path_breadcrumbs._scroll_area
        current_button = next(
            self.panel.path_breadcrumbs._content_layout.itemAt(index).widget()
            for index in range(
                self.panel.path_breadcrumbs._content_layout.count()
            )
            if self.panel.path_breadcrumbs._content_layout.itemAt(index).widget()
            and self.panel.path_breadcrumbs._content_layout.itemAt(index).widget()
            .objectName() == "path_breadcrumb_current"
        )
        current_position = current_button.mapTo(
            scroll_area.viewport(), QPoint(0, 0)
        )
        self.assertGreater(scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertEqual(
            scroll_area.horizontalScrollBar().value(),
            scroll_area.horizontalScrollBar().maximum(),
        )
        self.assertGreaterEqual(current_position.x(), 0)
        self.assertLessEqual(
            current_position.x() + current_button.width(),
            scroll_area.viewport().width(),
        )
        self.assertTrue(self.panel.path_breadcrumbs._edit_button.isVisible())


if __name__ == "__main__":
    unittest.main()
