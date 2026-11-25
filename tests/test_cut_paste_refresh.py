import os
import sys
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.device_panel import DevicePanelGroup


class CutPasteHandler:
    device_connected = True
    device_serial = "test-device"
    devices = {}

    def __init__(self):
        self.moved = []

    def list_directory(self, *_args, **_kwargs):
        return []

    def path_exists(self, _path):
        return False

    def move_on_device(self, source, destination):
        self.moved.append((source, destination))
        return True


class CutPasteRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_cut_paste_refreshes_source_tab(self):
        handler = CutPasteHandler()
        panel = DevicePanelGroup(None, handler)
        source_view = panel.active_view
        destination_view = panel.add_tab("/storage/destination")
        source_view.refresh_files = Mock()
        destination_view.refresh_files = Mock()
        panel.clipboard.update(
            {
                "items": [
                    {
                        "path": "/storage/emulated/0/report.txt",
                        "name": "report.txt",
                        "is_dir": False,
                    }
                ],
                "operation": "cut",
            }
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
            handler.moved,
            [
                (
                    "/storage/emulated/0/report.txt",
                    "/storage/destination/report.txt",
                )
            ],
        )
        source_view.refresh_files.assert_called_once()
        destination_view.refresh_files.assert_called_once()
        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
