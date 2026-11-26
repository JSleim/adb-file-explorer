import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from handler import FileItem
from ui.device_panel import DevicePanel


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class FileSortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.panel = DevicePanel(None, DisconnectedHandler())
        self.panel.show()
        self.panel.populate_view([
            FileItem("Z folder", "/Z folder", True, 0, "drwxr-xr-x", ""),
            FileItem("older.txt", "/older.txt", False, 200, "-rw-r--r--", "2026-10-15 08:00"),
            FileItem("newer.txt", "/newer.txt", False, 10, "-rw-r--r--", "2026-10-16 08:00"),
        ])
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def _click_header(self, column):
        header = self.panel.tree_view.header()
        x = header.sectionViewportPosition(column) + header.sectionSize(column) // 2
        QTest.mouseClick(
            header.viewport(),
            Qt.MouseButton.LeftButton,
            pos=QPoint(x, header.height() // 2),
        )

    def _names(self):
        return [
            self.panel.tree_model.item(row, 0).text()
            for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 1).text() == "File"
        ]

    def test_default_name_order_keeps_folders_before_files(self):
        rows = [
            self.panel.tree_model.item(row, 1).text()
            for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 0).text() != ".."
        ]

        self.assertEqual(rows, ["Directory", "File", "File"])

    def test_modified_column_sorts_newest_files_first_on_second_click(self):
        self.assertFalse(self.panel.tree_view.isColumnHidden(4))

        self._click_header(4)
        self._click_header(4)

        self.assertEqual(self._names(), ["newer.txt", "older.txt"])

    def test_size_column_sorts_numerically(self):
        self._click_header(2)

        self.assertEqual(self._names(), ["newer.txt", "older.txt"])

    def test_name_column_sorts_numeric_segments_naturally(self):
        names = ["101", "11", "10"]
        self.panel.populate_view([
            FileItem(name, f"/{name}", is_dir, 0, "", "")
            for is_dir in (True, False)
            for name in names
        ])
        self.panel.tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.app.processEvents()

        directories = [
            self.panel.tree_model.item(row, 0).text()
            for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 1).text() == "Directory"
            and self.panel.tree_model.item(row, 0).text() != ".."
        ]
        files = [
            self.panel.tree_model.item(row, 0).text()
            for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 1).text() == "File"
        ]

        self.assertEqual(directories, ["10", "11", "101"])
        self.assertEqual(files, ["10", "11", "101"])

    def test_typing_selects_by_name_after_clicking_another_column(self):
        names = ["alpha.txt", "report.txt"]
        self.panel.populate_view([
            FileItem(name, f"/{name}", False, 0, "", "") for name in names
        ])
        self.panel.tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.app.processEvents()

        row = next(
            row for row in range(self.panel.tree_model.rowCount())
            if self.panel.tree_model.item(row, 0).text() == "alpha.txt"
        )
        clicked_index = self.panel.tree_model.index(row, 1)
        QTest.mouseClick(
            self.panel.tree_view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=self.panel.tree_view.visualRect(clicked_index).center(),
        )
        QTest.keyClicks(self.panel.tree_view, "report")

        self.assertEqual(
            self.panel.tree_view.currentIndex().siblingAtColumn(0).data(),
            "report.txt",
        )


if __name__ == "__main__":
    unittest.main()
