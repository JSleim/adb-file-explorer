import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from ui.device_panel import DevicePanelGroup
from ui.multi_device_window import MultiDeviceWindow
from PyQt6.QtWidgets import QTabBar, QToolButton
from ui.theme import DARK, LIGHT


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}

    def __init__(self, device_serial="test-device"):
        self.device_serial = device_serial

    def rename_item(self, *_args):
        return True

    def get_unique_devices(self):
        return {}

    def list_directory(self, *_args):
        return []


class NoDeviceHandler:
    def __init__(self, device_serial=None):
        self.device_serial = device_serial

    def get_unique_devices(self):
        return {}


class PanelTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_added_tab_starts_at_same_path_and_navigates_independently(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())
        first_view = panel.active_view
        first_view.navigate_to("/storage/first")

        second_view = panel.add_tab()

        self.assertEqual(panel.tabs.count(), 2)
        self.assertEqual(second_view.current_path, "/storage/first")
        second_view.navigate_to("/storage/second")
        self.assertEqual(first_view.current_path, "/storage/first")
        self.assertEqual(panel.tabs.tabText(1), "second")

        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_closing_last_tab_keeps_panel_open_and_add_tab_available(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())
        self.assertEqual(panel.close_btn.text(), "X")
        self.assertEqual(panel.add_tab_btn.text(), "+")
        close_requests = []
        panel.close_requested.connect(lambda: close_requests.append(True))
        first_view = panel.active_view
        first_view.navigate_to("/storage/custom")

        close_tab = panel.tabs.tabBar().tabButton(
            0, QTabBar.ButtonPosition.RightSide
        )
        self.assertIsInstance(close_tab, QToolButton)
        self.assertEqual(close_tab.text(), "x")
        close_tab.click()
        self.assertEqual(panel.tabs.count(), 0)
        self.assertEqual(close_requests, [])
        self.assertFalse(panel.add_tab_btn.isHidden())
        self.assertFalse(panel.close_btn.isHidden())

        QTest.mouseClick(panel.add_tab_btn, Qt.MouseButton.LeftButton)
        new_view = panel.active_view
        self.assertEqual(new_view.current_path, "/storage/custom")
        self.assertEqual(panel.tabs.count(), 1)

        panel.close_btn.click()
        self.assertEqual(close_requests, [True])
        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_ctrl_w_closes_active_tab_and_keeps_panel_when_last_closes(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        panel = DevicePanelGroup(window.splitter, DisconnectedHandler())
        window.splitter.addWidget(panel)
        window.device_panels.append(panel)
        window._last_active_panel = panel
        first_view = panel.active_view
        second_view = panel.add_tab("/storage/second")
        close_requests = []
        panel.close_requested.connect(lambda: close_requests.append(True))
        window.show()
        second_view.tree_view.setFocus()
        self.app.processEvents()

        QTest.keyClick(
            second_view.tree_view,
            Qt.Key.Key_W,
            Qt.KeyboardModifier.ControlModifier,
        )

        self.assertEqual(panel.tabs.count(), 1)
        self.assertIs(panel.active_view, first_view)
        self.assertEqual(close_requests, [])

        first_view.tree_view.setFocus()
        self.app.processEvents()
        QTest.keyClick(
            first_view.tree_view,
            Qt.Key.Key_W,
            Qt.KeyboardModifier.ControlModifier,
        )

        self.assertEqual(panel.tabs.count(), 0)
        self.assertEqual(close_requests, [])
        self.assertFalse(panel.close_btn.isHidden())
        self.assertFalse(panel.add_tab_btn.isHidden())
        window.close()

    def test_ctrl_w_works_when_focus_is_on_window_toolbar(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        panel = DevicePanelGroup(window.splitter, DisconnectedHandler())
        window.splitter.addWidget(panel)
        window.device_panels.append(panel)
        window._last_active_panel = panel
        first_view = panel.active_view
        panel.add_tab("/storage/second")
        window.show()
        window.add_tab_btn.setFocus()
        self.app.processEvents()

        QTest.keyClick(
            window.add_tab_btn,
            Qt.Key.Key_W,
            Qt.KeyboardModifier.ControlModifier,
        )

        self.assertEqual(panel.tabs.count(), 1)
        self.assertIs(panel.active_view, first_view)
        window.close()

    def test_clicking_a_tab_activates_its_panel_for_window_shortcuts(self):
        with patch(
            "ui.multi_device_window.ADBHandler",
            side_effect=lambda device_serial=None: DisconnectedHandler(device_serial),
        ):
            window = MultiDeviceWindow()
            first_panel = window._add_panel_for_device("first", "First")
            second_panel = window._add_panel_for_device("second", "Second")
        window.connection_timer.stop()
        second_panel.add_tab("/storage/second")
        window.show()
        first_panel.active_view.tree_view.setFocus()
        self.app.processEvents()

        second_panel.tabs.tabBar().tabBarClicked.emit(0)

        self.assertIs(window._active_panel(), second_panel)
        window._close_active_tab()

        self.assertEqual(first_panel.tabs.count(), 1)
        self.assertEqual(second_panel.tabs.count(), 1)
        window.close()

    def test_clicking_empty_panel_activates_it_for_ctrl_t(self):
        with patch(
            "ui.multi_device_window.ADBHandler",
            side_effect=lambda device_serial=None: DisconnectedHandler(device_serial),
        ):
            window = MultiDeviceWindow()
            first_panel = window._add_panel_for_device("first", "First")
            second_panel = window._add_panel_for_device("second", "Second")
        window.connection_timer.stop()
        second_panel.close_active_tab()
        window.show()
        first_panel.active_view.tree_view.setFocus()
        self.app.processEvents()

        QTest.mouseClick(
            second_panel.device_header, Qt.MouseButton.LeftButton
        )
        QTest.keyClick(
            second_panel.device_header,
            Qt.Key.Key_T,
            Qt.KeyboardModifier.ControlModifier,
        )

        self.assertEqual(first_panel.tabs.count(), 1)
        self.assertEqual(second_panel.tabs.count(), 1)
        self.assertIs(window._active_panel(), second_panel)
        window.close()

    def test_connection_poll_updates_panel_to_disconnected(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        handler = DisconnectedHandler()
        handler.check_adb_connection = lambda: False
        panel = DevicePanelGroup(window.splitter, handler)
        window.splitter.addWidget(panel)
        window.device_panels.append(panel)
        handler.device_connected = True
        panel.update_connection_status()
        self.assertEqual(panel.conn_label.text(), "🟢 Connected")

        window._check_connections()

        self.assertEqual(panel.conn_label.text(), "🔴 Disconnected")
        window.close()

    def test_tab_overflow_controls_have_visible_labels(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())
        panel.resize(240, 320)
        panel.show()
        for index in range(12):
            panel.add_tab(f"/storage/folder-{index}")
        self.app.processEvents()

        for width in (240, 320, 480):
            panel.resize(width, 320)
            self.app.processEvents()

            for stylesheet in (LIGHT, DARK):
                self.app.setStyleSheet(stylesheet)
                self.app.processEvents()
                panel._style_tab_scroll_buttons()
                self.app.processEvents()

                buttons = {
                    button.objectName(): button
                    for button in panel.tabs.tabBar().findChildren(QToolButton)
                    if button.objectName() in {"ScrollLeftButton", "ScrollRightButton"}
                }

                self.assertEqual(buttons["ScrollLeftButton"].text(), "<")
                self.assertEqual(buttons["ScrollRightButton"].text(), ">")
                self.assertEqual(
                    buttons["ScrollLeftButton"].accessibleName(), "Scroll tabs left"
                )
                self.assertEqual(
                    buttons["ScrollRightButton"].accessibleName(), "Scroll tabs right"
                )
                self.assertFalse(
                    buttons["ScrollLeftButton"].geometry().intersects(
                        buttons["ScrollRightButton"].geometry()
                    )
                )
                tab_bar = panel.tabs.tabBar()
                for button in buttons.values():
                    self.assertTrue(tab_bar.rect().contains(button.geometry()))
                scroll_area = (
                    buttons["ScrollLeftButton"].geometry()
                    .united(buttons["ScrollRightButton"].geometry())
                )
                for index in range(tab_bar.count()):
                    tab_rect = tab_bar.tabRect(index)
                    if tab_rect.isValid():
                        self.assertFalse(tab_rect.intersects(scroll_area))

        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_ctrl_t_adds_tab_to_focused_panel(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        panel = DevicePanelGroup(window.splitter, DisconnectedHandler())
        window.splitter.addWidget(panel)
        window.device_panels.append(panel)
        window.show()
        panel.active_view.tree_view.setFocus()
        self.app.processEvents()

        QTest.keyClick(
            panel.active_view.tree_view,
            Qt.Key.Key_T,
            Qt.KeyboardModifier.ControlModifier,
        )

        self.assertEqual(panel.tabs.count(), 2)
        self.assertEqual(panel.current_path, "/storage/emulated/0")
        window.close()

    def test_add_tab_button_targets_the_last_focused_panel(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        first_panel = DevicePanelGroup(window.splitter, DisconnectedHandler())
        second_panel = DevicePanelGroup(window.splitter, DisconnectedHandler())
        window.splitter.addWidget(first_panel)
        window.splitter.addWidget(second_panel)
        window.device_panels.extend([first_panel, second_panel])
        window.show()
        second_panel.active_view.tree_view.setFocus()
        self.app.processEvents()

        QTest.mouseClick(window.add_tab_btn, Qt.MouseButton.LeftButton)

        self.assertEqual(first_panel.tabs.count(), 1)
        self.assertEqual(second_panel.tabs.count(), 2)
        window.close()

    def test_panel_close_button_removes_panel_from_splitter(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        panel = DevicePanelGroup(window.splitter, DisconnectedHandler())
        window.splitter.addWidget(panel)
        window.device_panels.append(panel)
        panel.close_requested.connect(lambda p=panel: window._close_panel(p))
        window.show()
        self.app.processEvents()

        self.assertTrue(panel.close_btn.isVisible())
        self.assertEqual(panel.close_btn.text(), "X")
        self.assertGreater(panel.close_btn.width(), 0)
        self.assertGreater(panel.close_btn.height(), 0)
        panel.close_btn.click()
        self.app.processEvents()

        self.assertNotIn(panel, window.device_panels)
        self.assertTrue(panel.isHidden())
        self.assertEqual(window.splitter.indexOf(panel), -1)
        window.close()


if __name__ == "__main__":
    unittest.main()
