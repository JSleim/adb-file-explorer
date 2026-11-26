import os
import sys
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from ui.multi_device_window import MultiDeviceWindow


class NoDeviceHandler:
    def __init__(self, device_serial=None):
        self.device_serial = device_serial

    def get_connected_devices(self):
        return {}

    def get_unique_devices(self):
        return {}


class ClosablePanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.close_prepared = False

    def prepare_for_close(self):
        self.close_prepared = True


class MultiDeviceWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_close_removes_the_requested_panel(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        panel = ClosablePanel(window.splitter)
        window.splitter.addWidget(panel)
        window.device_panels.append(panel)

        window._close_panel(panel)

        self.assertEqual(window.device_panels, [])
        self.assertIsNone(panel.parentWidget())
        self.assertTrue(panel.isHidden())
        self.assertTrue(panel.close_prepared)
        window.close()

    def test_add_panel_allows_a_device_that_already_has_a_panel(self):
        with patch("ui.multi_device_window.ADBHandler", NoDeviceHandler):
            window = MultiDeviceWindow()
        window.connection_timer.stop()
        existing_panel = QWidget(window.splitter)
        existing_panel.device_serial = "device-1"
        window.device_panels.append(existing_panel)

        devices = {"device-1": "Pixel"}
        dialog = Mock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.selected_devices.return_value = ["device-1"]
        with patch("ui.multi_device_window.ADBHandler") as handler_class, patch(
            "ui.multi_device_window.DeviceChooser", return_value=dialog
        ) as chooser_class, patch.object(window, "_add_panel_for_device") as add_panel:
            handler_class.return_value.get_unique_devices.return_value = devices

            window._add_panel()

        chooser_class.assert_called_once_with(devices, window)
        add_panel.assert_called_once_with("device-1", "Pixel")
        window.close()

if __name__ == "__main__":
    unittest.main()
