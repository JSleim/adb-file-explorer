import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QListWidget

from device_chooser import DeviceChooser


class DeviceChooserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_allows_selecting_multiple_devices(self):
        chooser = DeviceChooser({"usb-1": "Pixel 8", "usb-2": "Pixel 7"})
        chooser.device_list.selectAll()

        self.assertEqual(chooser.device_list.selectionMode(), QListWidget.SelectionMode.MultiSelection)
        self.assertEqual(chooser.selected_devices(), ["usb-1", "usb-2"])


if __name__ == "__main__":
    unittest.main()