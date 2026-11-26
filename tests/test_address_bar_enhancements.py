import os
import sys
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMenu, QToolButton

from ui.device_panel import DevicePanel, DevicePanelGroup


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class AddressBarEnhancementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def _current_breadcrumb(self):
        return next(
            button
            for button in self.panel.path_breadcrumbs.findChildren(QToolButton)
            if button.objectName() == "path_breadcrumb_current"
        )

    def test_entering_edit_mode_places_unselected_cursor_at_path_end(self):
        self.panel.focus_address_bar()

        self.assertEqual(
            self.panel.path_display.cursorPosition(),
            len(self.panel.current_path),
        )
        self.assertEqual(self.panel.path_display.selectedText(), "")

    def test_double_clicking_current_breadcrumb_enters_edit_mode(self):
        QTest.mouseDClick(self._current_breadcrumb(), Qt.MouseButton.LeftButton)

        self.assertIs(
            self.panel.path_stack.currentWidget(), self.panel.path_display
        )
        self.assertEqual(
            self.panel.path_display.cursorPosition(),
            len(self.panel.current_path),
        )

    def test_breadcrumb_context_menu_adds_that_path_to_favorites(self):
        self.panel.navigate_to("/storage/emulated")
        favorite_requests = []
        self.panel.favorite_requested.connect(
            lambda name, path: favorite_requests.append((name, path))
        )
        button = next(
            button
            for button in self.panel.path_breadcrumbs.findChildren(QToolButton)
            if button.text() == "storage"
        )

        def trigger_first_action(menu, *_args, **_kwargs):
            self.assertEqual(menu.actions()[0].text(), "Add to favorites")
            menu.actions()[0].trigger()

        with patch.object(QMenu, "exec", new=trigger_first_action):
            position = QPoint(2, 2)
            QApplication.sendEvent(
                button,
                QContextMenuEvent(
                    QContextMenuEvent.Reason.Mouse,
                    position,
                    button.mapToGlobal(position),
                ),
            )

        self.assertEqual(favorite_requests, [("storage", "/storage")])

    def test_tab_context_menu_adds_that_tab_path_to_favorites(self):
        group = DevicePanelGroup(None, DisconnectedHandler())
        group.add_tab("/storage/emulated/0/DCIM")
        group._add_folder_to_favorites = Mock()
        group.show()
        self.app.processEvents()
        tab_bar = group.tabs.tabBar()
        position = tab_bar.tabRect(1).center()

        def trigger_first_action(menu, *_args, **_kwargs):
            self.assertEqual(menu.actions()[0].text(), "Add to favorites")
            menu.actions()[0].trigger()

        with patch.object(QMenu, "exec", new=trigger_first_action):
            QApplication.sendEvent(
                tab_bar,
                QContextMenuEvent(
                    QContextMenuEvent.Reason.Mouse,
                    position,
                    tab_bar.mapToGlobal(position),
                ),
            )

        group._add_folder_to_favorites.assert_called_once_with(
            "DCIM", "/storage/emulated/0/DCIM", group.tabs.widget(1)
        )
        group.prepare_for_close()
        group.deleteLater()
        self.app.processEvents()

    def test_wheel_scrolls_breadcrumbs_horizontally(self):
        self.panel.current_path = (
            "/storage/emulated/0/Android/data/"
            "com.example.long.package/files/a_deep_folder"
        )
        self.panel.update_path_display()
        self.panel.resize(420, 500)
        self.app.processEvents()
        QTest.qWait(10)

        scroll_bar = self.panel.path_breadcrumbs._scroll_area.horizontalScrollBar()
        before = scroll_bar.value()
        self.assertGreater(scroll_bar.maximum(), 0)
        button = self._current_breadcrumb()
        position = QPointF(button.width() // 2, button.height() // 2)
        event = QWheelEvent(
            position,
            QPointF(button.mapToGlobal(position.toPoint())),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

        QApplication.sendEvent(button, event)

        self.assertLess(scroll_bar.value(), before)


if __name__ == "__main__":
    unittest.main()
