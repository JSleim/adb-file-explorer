import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.multi_device_window import MultiDeviceWindow
from ui.permission_lint import PermissionLintDialog


class PermissionLintNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_file_result_navigates_to_parent_and_selects_file(self):
        path = (
            "/storage/emulated/0/Android/data/com.zy.wqmt.bilibili/"
            "files/tombstone_00"
        )
        dialog = PermissionLintDialog(SimpleNamespace(device_serial="device-1"))
        selected = []
        dialog.item_selected.connect(lambda *args: selected.append(args))
        dialog.on_item_found({"path": path, "tag": "W"})
        dialog.on_double_click(dialog.results_tree.topLevelItem(0), 0)
        dialog.close()

        self.assertEqual(selected, [("device-1", path, False, False)])

        view = SimpleNamespace(use_root=False, tree_model=Mock(), tree_view=Mock())
        view.tree_model.rowCount.return_value = 1
        view.tree_model.index.return_value = 0
        view.tree_model.data.return_value = "tombstone_00"
        panel = SimpleNamespace(
            device_serial="device-1",
            adb_handler=SimpleNamespace(root_mode=None),
            add_tab=Mock(return_value=view),
        )
        window = SimpleNamespace(device_panels=[panel])

        with patch(
            "ui.multi_device_window.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            MultiDeviceWindow._navigate_to_search_result(window, *selected[0])

        panel.add_tab.assert_called_once_with(
            path="/storage/emulated/0/Android/data/com.zy.wqmt.bilibili/files"
        )
        view.tree_view.setCurrentIndex.assert_called_once_with(0)
        view.tree_view.scrollTo.assert_called_once_with(0)

    def test_directory_result_is_marked_as_directory(self):
        dialog = PermissionLintDialog(SimpleNamespace(device_serial="device-1"))
        selected = []
        dialog.item_selected.connect(lambda *args: selected.append(args))
        dialog.on_item_found({"path": "/storage/emulated/0/shared", "tag": "D"})
        dialog.on_double_click(dialog.results_tree.topLevelItem(0), 0)
        dialog.close()

        self.assertEqual(
            selected, [("device-1", "/storage/emulated/0/shared", False, True)]
        )


if __name__ == "__main__":
    unittest.main()
