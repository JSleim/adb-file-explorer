import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication

from handler import FileItem
from ui.device_panel import DevicePanel


class CopyHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}

    def __init__(self):
        self.existing = set()
        self.copies = []

    def path_exists(self, path):
        return path in self.existing

    def copy_on_device(self, source, destination):
        self.copies.append((source, destination))
        self.existing.add(destination)
        return True


class SameDirectoryCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.handler = CopyHandler()
        self.panel = DevicePanel(None, self.handler)
        self.panel.refresh_files = lambda: None
        self.panel.populate_view(
            [FileItem("report.txt", "/report.txt", False, 12, "", "")]
        )
        self.app.processEvents()
        row = next(
            row
            for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 0).text() == "report.txt"
        )
        self.panel.tree_view.selectionModel().select(
            self.panel.tree_model.index(row, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.panel.copy_selected()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def _paste(self):
        def run_modal(_title, operation, *args, on_done=None, **_kwargs):
            result = operation(*args)
            if on_done:
                on_done(result)

        with patch.object(self.panel, "_run_modal", side_effect=run_modal):
            self.panel.paste_items()

    def test_file_copies_get_incrementing_suffixes_before_extension(self):
        self.handler.existing.add("/storage/emulated/0/report.txt")
        with patch("ui.device_panel.QMessageBox.question") as question:
            self._paste()
            self._paste()

        self.assertEqual(
            self.handler.copies,
            [
                (
                    "/storage/emulated/0/report.txt",
                    "/storage/emulated/0/report (copy).txt",
                ),
                (
                    "/storage/emulated/0/report.txt",
                    "/storage/emulated/0/report (copy 2).txt",
                ),
            ],
        )
        question.assert_not_called()

    def test_directory_copy_keeps_dotted_name_intact(self):
        self.panel.populate_view(
            [FileItem("archive.tar", "/archive.tar", True, 0, "", "")]
        )
        self.app.processEvents()
        row = next(
            row
            for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 0).text() == "archive.tar"
        )
        self.panel.tree_view.selectionModel().clearSelection()
        self.panel.tree_view.selectionModel().select(
            self.panel.tree_model.index(row, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.panel.copy_selected()
        self.handler.existing.add("/storage/emulated/0/archive.tar")

        with patch("ui.device_panel.QMessageBox.question") as question:
            self._paste()

        self.assertEqual(
            self.handler.copies[-1],
            (
                "/storage/emulated/0/archive.tar",
                "/storage/emulated/0/archive.tar (copy)",
            ),
        )
        question.assert_not_called()


if __name__ == "__main__":
    unittest.main()
