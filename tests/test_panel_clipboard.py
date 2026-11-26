import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication

from handler import FileItem
from ui.device_panel import DevicePanelGroup


class ClipboardHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}

    def __init__(self):
        self.copied = []

    def copy_on_device(self, source, destination):
        self.copied.append((source, destination))
        return True

    def path_exists(self, _path):
        return False


class PanelClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_copy_in_one_tab_can_be_pasted_in_another(self):
        handler = ClipboardHandler()
        panel = DevicePanelGroup(None, handler)
        first_view = panel.active_view
        first_view.populate_view([
            FileItem("report.txt", "/report.txt", False, 12, "", ""),
        ])
        self.app.processEvents()
        file_row = next(
            row for row in range(first_view.tree_model.rowCount())
            if first_view.tree_model.item(row, 0).text() == "report.txt"
        )
        first_view.tree_view.selectionModel().select(
            first_view.tree_model.index(file_row, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        first_view.copy_selected()

        second_view = panel.add_tab("/storage/destination")
        second_view.refresh_files = lambda: None
        handler.device_connected = True
        self.assertIs(first_view.clipboard, second_view.clipboard)

        with patch.object(
            second_view,
            "_run_modal",
            side_effect=lambda _title, run, *args, on_done=None, **_kwargs: (
                on_done(run(*args))
            ),
        ):
            second_view.paste_items()

        self.assertEqual(
            handler.copied,
            [("/storage/emulated/0/report.txt", "/storage/destination/report.txt")],
        )
        self.assertEqual(second_view.clipboard["operation"], "copy")
        self.assertEqual(len(second_view.clipboard["items"]), 1)

        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
