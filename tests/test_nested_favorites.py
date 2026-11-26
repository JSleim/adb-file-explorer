import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMenu

from ui.bookmarks import BookmarkStore
from ui.device_panel import DevicePanelGroup


class DisconnectedHandler:
    device_connected = False
    devices = {}

    def __init__(self, device_serial):
        self.device_serial = device_serial


class NestedFavoritesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _new_panel(self, store, serial="device-a"):
        panel = DevicePanelGroup(
            None, DisconnectedHandler(serial), bookmark_store=store
        )
        self.addCleanup(self._close_panel, panel)
        return panel

    def _close_panel(self, panel):
        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_create_nested_favorites_and_keep_them_per_device(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BookmarkStore(os.path.join(directory, "bookmarks.json"))
            panel = self._new_panel(store)

            with patch(
                "ui.device_panel.QInputDialog.getText",
                side_effect=[("Devices", True), ("Phone", True)],
            ):
                panel._create_bookmark_folder()
                devices = panel._bookmarks[0]
                panel._create_bookmark_folder(devices)

            phone = panel._bookmarks[0]["children"][0]
            self.assertTrue(
                panel.add_bookmark(
                    "Photos",
                    "/storage/DCIM",
                    parent_folder_id=phone["id"],
                )
            )
            root = panel.navigation_tree.topLevelItem(0)
            self.assertEqual(root.child(0).text(0), "Devices")
            self.assertEqual(root.child(0).child(0).text(0), "Phone")
            self.assertEqual(
                root.child(0).child(0).child(0).text(0), "Photos"
            )

            other_device = self._new_panel(store, "device-b")
            other_root = other_device.navigation_tree.topLevelItem(0)
            self.assertEqual(other_root.child(0).text(0), "No favorites yet")

            reloaded = self._new_panel(BookmarkStore(store.path))
            self.assertEqual(
                reloaded.navigation_tree.topLevelItem(0)
                .child(0)
                .child(0)
                .child(0)
                .text(0),
                "Photos",
            )

    def test_favorite_context_menu_moves_existing_favorite_into_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BookmarkStore(os.path.join(directory, "bookmarks.json"))
            panel = self._new_panel(store)
            panel.add_bookmark("Photos", "/storage/DCIM")
            with patch(
                "ui.device_panel.QInputDialog.getText",
                return_value=("Phone", True),
            ):
                panel._create_bookmark_folder()
            panel.show()
            self.app.processEvents()

            root = panel.navigation_tree.topLevelItem(0)
            favorite_item = next(
                root.child(index)
                for index in range(root.childCount())
                if (
                    root.child(index).data(0, Qt.ItemDataRole.UserRole) or {}
                ).get("kind") == "favorite"
            )
            panel.navigation_tree.setCurrentItem(favorite_item)
            position = panel.navigation_tree.visualItemRect(favorite_item).center()

            def move_into_phone(menu, _position):
                move_menu = next(
                    action.menu()
                    for action in menu.actions()
                    if action.text() == "Move to folder"
                )
                next(
                    action
                    for action in move_menu.actions()
                    if action.text() == "Phone"
                ).trigger()

            with patch.object(QMenu, "exec", new=move_into_phone):
                panel._show_bookmark_context_menu(position)

            self.assertEqual(
                panel._bookmarks[0]["children"][0]["path"], "/storage/DCIM"
            )
            reloaded = BookmarkStore(store.path).load("device-a")
            self.assertEqual(
                reloaded[0]["children"][0]["path"], "/storage/DCIM"
            )

    def test_nested_favorite_can_be_edited_and_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BookmarkStore(os.path.join(directory, "bookmarks.json"))
            panel = self._new_panel(store)
            with patch(
                "ui.device_panel.QInputDialog.getText",
                return_value=("Phone", True),
            ):
                panel._create_bookmark_folder()
            folder_id = panel._bookmarks[0]["id"]
            panel.add_bookmark(
                "Photos", "/storage/DCIM", parent_folder_id=folder_id
            )
            bookmark = panel._bookmarks[0]["children"][0]

            with patch("ui.device_panel.BookmarkDialog") as dialog_class:
                dialog = dialog_class.return_value
                dialog.exec.return_value = QDialog.DialogCode.Accepted
                dialog.bookmark.return_value = {
                    "name": "Camera",
                    "path": bookmark["path"],
                    "note": "Edited note",
                }
                panel._edit_bookmark_dialog(bookmark, "Edit favorite")

            self.assertEqual(
                panel._bookmarks[0]["children"][0]["name"], "Camera"
            )
            reloaded = self._new_panel(BookmarkStore(store.path))
            root = reloaded.navigation_tree.topLevelItem(0)
            nested_favorite = root.child(0).child(0)
            reloaded.navigation_tree.setCurrentItem(nested_favorite)
            reloaded._remove_bookmark()
            self.assertEqual(reloaded._bookmarks[0]["children"], [])
            self.assertEqual(
                BookmarkStore(store.path).load("device-a")[0]["children"], []
            )


if __name__ == "__main__":
    unittest.main()
