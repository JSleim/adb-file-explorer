import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication

from handler import FileItem
from ui.multi_device_window import MultiDeviceWindow


class ClipboardHandler:
    device_connected = False

    def __init__(self, device_serial, transfers):
        self.device_serial = device_serial or "primary"
        self.devices = {}
        self.transfers = transfers

    def get_unique_devices(self):
        return {}

    def path_exists(self, _path):
        return False

    def stream_file(self, src_serial, src_path, dst_serial, dst_path):
        self.transfers.append(("file", src_serial, src_path, dst_serial, dst_path))
        return True

    def stream_directory(self, src_serial, src_path, dst_serial, dst_path):
        self.transfers.append(("directory", src_serial, src_path, dst_serial, dst_path))
        return True


class SharedClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _select_items(self, view, items):
        view.populate_view(items)
        self.app.processEvents()
        selection = view.tree_view.selectionModel()
        for item in items:
            row = next(
                row
                for row in range(view.tree_model.rowCount())
                if view.tree_model.item(row, 0).text() == item.name
            )
            selection.select(
                view.tree_model.index(row, 0),
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _make_window(self, transfers):
        with patch(
            "ui.multi_device_window.ADBHandler",
            side_effect=lambda device_serial=None: ClipboardHandler(
                device_serial, transfers
            ),
        ):
            window = MultiDeviceWindow()
            source = window._add_panel_for_device("source", "Source")
            destination = window._add_panel_for_device(
                "destination", "Destination"
            )
        window.connection_timer.stop()
        self.addCleanup(window.close)
        return window, source, destination

    def test_copy_can_stream_files_and_folders_between_panels(self):
        transfers = []
        _, source_panel, destination_panel = self._make_window(transfers)
        source_view = source_panel.active_view
        self._select_items(
            source_view,
            [
                FileItem("report.txt", "/report.txt", False, 12, "", ""),
                FileItem("logs", "/logs", True, 0, "", ""),
            ],
        )
        source_view.copy_selected()
        destination_view = destination_panel.add_tab("/storage/destination")
        destination_view.refresh_files = lambda: None

        self.assertIs(source_panel.clipboard, destination_panel.clipboard)
        self.assertEqual(
            destination_panel.clipboard["source_device_serial"], "source"
        )
        with patch.object(
            destination_view,
            "_run_modal",
            side_effect=lambda _title, run, *args, on_done=None, **_kwargs: (
                on_done(run(*args))
            ),
        ):
            destination_view.paste_items()

        self.assertEqual(
            transfers,
            [
                (
                    "file",
                    "source",
                    "/storage/emulated/0/report.txt",
                    "destination",
                    "/storage/destination/report.txt",
                ),
                (
                    "directory",
                    "source",
                    "/storage/emulated/0/logs",
                    "destination",
                    "/storage/destination/logs",
                ),
            ],
        )

    def test_cross_device_cut_is_rejected_without_transfer(self):
        transfers = []
        _, source_panel, destination_panel = self._make_window(transfers)
        source_view = source_panel.active_view
        self._select_items(
            source_view,
            [FileItem("report.txt", "/report.txt", False, 12, "", "")],
        )
        source_view.cut_selected()

        destination_view = destination_panel.active_view
        destination_view.paste_items()

        self.assertIn("not supported", destination_view.status_label.text())
        self.assertEqual(transfers, [])


if __name__ == "__main__":
    unittest.main()
