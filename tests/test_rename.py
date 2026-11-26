import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from ui.device_panel import DevicePanel


class RenameHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class RenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, RenameHandler())

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_rename_dialog_starts_with_the_current_name(self):
        self.panel.adb_handler.device_connected = True
        with patch(
            "ui.device_panel.QInputDialog.exec",
            return_value=QDialog.DialogCode.Accepted,
        ), patch(
            "ui.device_panel.QInputDialog.textValue",
            return_value="renamed.jpg",
        ), patch.object(
            self.panel, "_run_modal"
        ) as run_modal, patch.object(
            self.panel.adb_handler, "rename_item", create=True
        ):
            self.panel.rename_item("photo.jpg")

        self.assertEqual(run_modal.call_args.args[2:], (
            "/storage/emulated/0/photo.jpg",
            "/storage/emulated/0/renamed.jpg",
        ))


if __name__ == "__main__":
    unittest.main()
