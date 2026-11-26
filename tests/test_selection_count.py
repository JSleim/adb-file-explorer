import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication

from handler import FileItem
from ui.device_panel import DevicePanel


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class SelectionCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.populate_view([
            FileItem("Documents", "/Documents", True, 0, "", ""),
            FileItem("report.txt", "/report.txt", False, 12, "", ""),
        ])
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def _row_for_name(self, name):
        return next(
            row for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 0).text() == name
        )

    def _select_row(self, name, command):
        self.panel.tree_view.selectionModel().select(
            self.panel.tree_model.index(self._row_for_name(name), 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
            | command,
        )

    def test_selection_count_updates_for_files_and_folders(self):
        self.assertEqual(self.panel.selection_count_label.text(), "0 items selected")

        self._select_row("Documents", QItemSelectionModel.SelectionFlag.NoUpdate)
        self.assertEqual(self.panel.selection_count_label.text(), "1 item selected")

        self._select_row("report.txt", QItemSelectionModel.SelectionFlag.NoUpdate)
        self.assertEqual(self.panel.selection_count_label.text(), "2 items selected")

        self.panel.tree_view.selectionModel().clearSelection()
        self.assertEqual(self.panel.selection_count_label.text(), "0 items selected")

    def test_navigation_parent_is_not_counted_as_a_selected_item(self):
        self._select_row("..", QItemSelectionModel.SelectionFlag.NoUpdate)
        self.assertEqual(self.panel.selection_count_label.text(), "0 items selected")

    def test_repopulating_the_view_resets_selection_count(self):
        self._select_row("report.txt", QItemSelectionModel.SelectionFlag.NoUpdate)
        self.panel.populate_view([
            FileItem("new.txt", "/new.txt", False, 8, "", ""),
        ])

        self.assertEqual(self.panel.selection_count_label.text(), "0 items selected")


if __name__ == "__main__":
    unittest.main()
