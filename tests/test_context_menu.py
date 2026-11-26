import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import QApplication

from ui.device_panel import DevicePanel


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class ContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.tree_model.appendRow([
            QStandardItem("sample.txt"),
            QStandardItem("File"),
            QStandardItem("1 KB"),
            QStandardItem(""),
            QStandardItem(""),
        ])
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_context_menu_request_opens_menu_only_once(self):
        index = self.panel.tree_model.index(0, 0)
        self.panel.tree_view.setCurrentIndex(index)
        position = self.panel.tree_view.visualRect(index).center()
        menus = []

        def record_menu(*args):
            menus.append(args)

        with patch("ui.device_panel.QMenu.exec", side_effect=record_menu):
            self.panel.tree_view.customContextMenuRequested.emit(position)

        self.assertEqual(len(menus), 1)


if __name__ == "__main__":
    unittest.main()
