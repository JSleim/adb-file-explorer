import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QItemSelectionModel, Qt
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import QApplication

from ui.bookmarks import BookmarkStore
from ui.device_panel import BookmarkDialog, DevicePanelGroup
from ui.multi_device_window import (
    MultiDeviceWindow, _load_theme, _save_theme,
)
from ui.theme import DARK, LIGHT


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}

    def __init__(self, device_serial="test-device"):
        self.device_serial = device_serial

    def get_unique_devices(self):
        return {}


class BookmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_bookmarks_persist_separately_for_each_device(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bookmarks.json")
            store = BookmarkStore(path)
            store.save("device-a", [
                {"name": "Photos", "path": "/storage/DCIM", "note": "Camera roll"},
            ])
            store.save("device-b", [
                {"name": "Downloads", "path": "/storage/Download", "note": ""},
            ])

            reloaded = BookmarkStore(path)

            self.assertEqual(
                reloaded.load("device-a"),
                [{"name": "Photos", "path": "/storage/DCIM", "note": "Camera roll"}],
            )
            self.assertEqual(
                reloaded.load("device-b"),
                [{"name": "Downloads", "path": "/storage/Download", "note": ""}],
            )

    def test_theme_settings_use_roaming_and_migrate_legacy_config(self):
        with tempfile.TemporaryDirectory() as directory:
            roaming_dir = Path(directory) / "Roaming" / "ADB Explorer"
            legacy_dir = Path(directory) / "old"
            legacy_dir.mkdir()
            (legacy_dir / "config.ini").write_text(
                "[app]\ndark_mode = yes\n",
                encoding="utf-8",
            )

            with (
                patch(
                    "ui.multi_device_window.get_app_data_directory",
                    return_value=roaming_dir,
                ),
                patch(
                    "ui.multi_device_window.get_base_dir",
                    return_value=legacy_dir,
                ),
            ):
                self.assertTrue(_load_theme())
                self.assertTrue((roaming_dir / "config.ini").exists())
                _save_theme(False)
                self.assertFalse(_load_theme())

            with patch(
                "ui.bookmarks.get_app_data_directory",
                return_value=roaming_dir,
            ):
                bookmark_store = BookmarkStore()
            self.assertEqual(
                bookmark_store.path,
                roaming_dir / "bookmarks.json",
            )

    def test_favorite_single_click_navigates_active_tab(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bookmarks.json")
            store = BookmarkStore(path)
            store.save("test-device", [
                {"name": "Photos", "path": "/storage/DCIM", "note": "Camera roll"},
            ])
            panel = DevicePanelGroup(None, DisconnectedHandler(), bookmarks_path=path)
            view = panel.active_view
            favorites_root = panel.navigation_tree.topLevelItem(0)
            item = favorites_root.child(0)

            self.assertEqual(item.text(0), "Photos")
            self.assertIn("Camera roll", item.toolTip(0))

            panel.navigation_tree.itemClicked.emit(item, 0)

            self.assertEqual(view.current_path, "/storage/DCIM")
            self.assertIs(panel.navigation_tree.currentItem(), item)
            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_navigation_tree_groups_device_folders_and_favorites(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = DevicePanelGroup(
                None,
                DisconnectedHandler(),
                bookmarks_path=os.path.join(directory, "bookmarks.json"),
            )
            expected = {
                "Downloads": "/storage/emulated/0/Download",
                "Documents": "/storage/emulated/0/Documents",
                "Pictures": "/storage/emulated/0/Pictures",
                "Music": "/storage/emulated/0/Music",
                "Videos": "/storage/emulated/0/Movies",
                "Camera": "/storage/emulated/0/DCIM",
            }

            favorites_root = panel.navigation_tree.topLevelItem(0)
            storage_root = panel.navigation_tree.topLevelItem(1)
            shortcuts = {
                storage_root.child(index).text(0):
                    storage_root.child(index).data(
                        0, Qt.ItemDataRole.UserRole
                    )["path"]
                for index in range(storage_root.childCount())
            }
            self.assertEqual(shortcuts, expected)
            self.assertEqual(storage_root.text(0), "Internal storage")
            self.assertEqual(favorites_root.text(0), "Favorites")

            item = storage_root.child(0)
            panel.navigation_tree.itemClicked.emit(item, 0)
            self.assertEqual(
                panel.active_view.current_path,
                "/storage/emulated/0/Download",
            )
            self.assertEqual(favorites_root.childCount(), 1)
            self.assertFalse(
                favorites_root.child(0).flags()
                & Qt.ItemFlag.ItemIsEnabled
            )

            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_navigation_tree_selection_tracks_active_tab_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = DevicePanelGroup(
                None,
                DisconnectedHandler(),
                bookmarks_path=os.path.join(directory, "bookmarks.json"),
            )
            view = panel.active_view
            view.navigate_to("/storage/emulated/0/Download/Camera")
            downloads_item = panel.navigation_tree.topLevelItem(1).child(0)
            self.assertIs(panel.navigation_tree.currentItem(), downloads_item)

            panel.add_tab("/storage/emulated/0/Music")
            music_item = panel.navigation_tree.topLevelItem(1).child(3)
            self.assertIs(panel.navigation_tree.currentItem(), music_item)

            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_device_folder_can_be_pinned_without_removing_its_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = DevicePanelGroup(
                None,
                DisconnectedHandler(),
                bookmarks_path=os.path.join(directory, "bookmarks.json"),
            )
            downloads = panel.navigation_tree.topLevelItem(1).child(0)

            panel._pin_navigation_item(downloads)

            favorites = panel.navigation_tree.topLevelItem(0)
            self.assertEqual(favorites.child(0).text(0), "Downloads")
            self.assertEqual(
                favorites.child(0)
                .data(0, Qt.ItemDataRole.UserRole)["path"],
                "/storage/emulated/0/Download",
            )
            self.assertEqual(
                panel.navigation_tree.topLevelItem(1).child(0).text(0),
                "Downloads",
            )
            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_bookmark_refresh_preserves_collapsed_navigation_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = DevicePanelGroup(
                None,
                DisconnectedHandler(),
                bookmarks_path=os.path.join(directory, "bookmarks.json"),
            )
            favorites_root = panel.navigation_tree.topLevelItem(0)
            storage_root = panel.navigation_tree.topLevelItem(1)
            storage_root.setExpanded(False)
            favorites_root.setExpanded(False)

            panel.add_bookmark("Camera", "/storage/emulated/0/DCIM")

            self.assertFalse(panel.navigation_tree.topLevelItem(0).isExpanded())
            self.assertFalse(panel.navigation_tree.topLevelItem(1).isExpanded())
            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_favorites_pane_auto_collapses_for_multiple_panels_and_restores(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())

        self.assertFalse(panel.favorites_pane.isHidden())
        panel.set_multi_panel_mode(True)
        self.assertTrue(panel.favorites_pane.isHidden())
        panel.set_multi_panel_mode(False)
        self.assertFalse(panel.favorites_pane.isHidden())

        panel.set_multi_panel_mode(True)
        panel.toggle_navigation_pane()
        self.assertFalse(panel.favorites_pane.isHidden())
        panel.set_multi_panel_mode(False)
        self.assertFalse(panel.favorites_pane.isHidden())

        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_manual_collapse_remains_collapsed_after_multi_panel_mode(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())
        panel.toggle_navigation_pane()
        self.assertTrue(panel.favorites_pane.isHidden())

        panel.set_multi_panel_mode(True)
        panel.set_multi_panel_mode(False)
        self.assertTrue(panel.favorites_pane.isHidden())

        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_multi_device_window_collapses_pane_when_panel_is_added_and_restores_it(self):
        with patch(
            "ui.multi_device_window.ADBHandler",
            side_effect=lambda device_serial=None: DisconnectedHandler(
                device_serial or "test-device"
            ),
        ):
            window = MultiDeviceWindow()
            window.connection_timer.stop()
            first = window._add_panel_for_device("device-a", "Device A")
            second = window._add_panel_for_device("device-b", "Device B")

        self.assertTrue(first.favorites_pane.isHidden())
        self.assertTrue(second.favorites_pane.isHidden())
        window._close_panel(second)
        self.assertFalse(first.favorites_pane.isHidden())
        window.close()

    def test_add_and_remove_bookmark_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bookmarks.json")
            panel = DevicePanelGroup(
                None, DisconnectedHandler(), bookmarks_path=path
            )

            self.assertTrue(
                panel.add_bookmark("Photos", "/storage/DCIM", "Camera roll")
            )
            self.assertFalse(
                panel.add_bookmark("Other name", "/storage/DCIM")
            )
            panel.navigation_tree.setCurrentItem(
                panel.navigation_tree.topLevelItem(0).child(0)
            )
            panel._remove_bookmark()

            self.assertEqual(BookmarkStore(path).load("test-device"), [])
            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_add_favorite_dialog_saves_custom_name_and_note(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bookmarks.json")
            panel = DevicePanelGroup(
                None, DisconnectedHandler(), bookmarks_path=path
            )
            panel.add_bookmark(
                "Downloads", "/storage/emulated/0/Download"
            )
            panel.navigation_tree.setCurrentItem(
                panel.navigation_tree.topLevelItem(0).child(0)
            )

            def accept(dialog):
                dialog.name_input.setText("Camera roll")
                dialog.note_input.setText("Photos from this device")
                return dialog.DialogCode.Accepted

            with patch.object(BookmarkDialog, "exec", new=accept):
                panel._edit_selected_bookmark()

            self.assertEqual(
                BookmarkStore(path).load("test-device"),
                [{
                    "name": "Camera roll",
                    "path": "/storage/emulated/0/Download",
                    "note": "Photos from this device",
                }],
            )
            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_bookmark_dialog_exposes_current_sharing_scope(self):
        bookmark = {
            "name": "Photos",
            "path": "/storage/DCIM",
            "note": "",
        }
        dialog = BookmarkDialog(
            None, bookmark, "Edit favorite", is_common=True
        )

        self.assertTrue(dialog.is_common())

        dialog.share_across_devices.setChecked(False)
        self.assertFalse(dialog.is_common())

        dialog.deleteLater()

    def test_file_context_menu_adds_the_right_clicked_folder_to_favorites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bookmarks.json")
            panel = DevicePanelGroup(
                None, DisconnectedHandler(), bookmarks_path=path
            )
            view = panel.active_view
            view.tree_model.appendRow([
                QStandardItem("notes.txt"),
                QStandardItem("File"),
                QStandardItem("1"),
                QStandardItem(""),
                QStandardItem(""),
            ])
            view.tree_model.appendRow([
                QStandardItem("Trips"),
                QStandardItem("Directory"),
                QStandardItem(""),
                QStandardItem(""),
                QStandardItem(""),
            ])
            panel.resize(900, 600)
            panel.show()
            self.app.processEvents()

            previous = view.tree_model.index(0, 0)
            target = view.tree_model.index(1, 0)
            selection = view.tree_view.selectionModel()
            selection.select(
                previous,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            position = view.tree_view.visualRect(target).center()
            menus = []
            with patch(
                "ui.device_panel.QMenu.exec",
                new=lambda menu, _position: menus.append(menu),
            ):
                view.show_context_menu(position)

            selected_rows = selection.selectedRows()
            self.assertEqual([row.row() for row in selected_rows], [1])
            action = next(
                action for action in menus[0].actions()
                if action.text() == "Add to favorites"
            )
            action.trigger()

            self.assertEqual(
                BookmarkStore(path).load("test-device"),
                [{
                    "name": "Trips",
                    "path": "/storage/emulated/0/Trips",
                    "note": "",
                }],
            )
            panel.prepare_for_close()
            panel.deleteLater()
            self.app.processEvents()

    def test_same_device_panels_share_bookmark_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BookmarkStore(os.path.join(directory, "bookmarks.json"))
            first = DevicePanelGroup(
                None, DisconnectedHandler("same-device"), bookmark_store=store
            )
            second = DevicePanelGroup(
                None, DisconnectedHandler("same-device"), bookmark_store=store
            )

            first.add_bookmark("Photos", "/storage/DCIM")

            favorites_root = second.navigation_tree.topLevelItem(0)
            self.assertEqual(favorites_root.childCount(), 1)
            self.assertEqual(favorites_root.child(0).text(0), "Photos")
            for panel in (first, second):
                panel.prepare_for_close()
                panel.deleteLater()
            self.app.processEvents()

    def test_favorites_pane_has_light_and_dark_theme_rules(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())

        self.assertIn("QWidget#favorites_pane", LIGHT)
        self.assertIn("QTreeWidget#navigation_tree", LIGHT)
        self.assertIn("QToolButton#navigation_toggle_btn", LIGHT)
        self.assertIn("QSplitter#panel_content_splitter", LIGHT)
        self.assertIn("QWidget#favorites_pane", DARK)
        self.assertIn("QTreeWidget#navigation_tree", DARK)
        self.assertIn("QToolButton#navigation_toggle_btn", DARK)
        self.assertIn("QSplitter#panel_content_splitter", DARK)

        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()

    def test_sidebar_toggle_is_leftmost_and_uses_navigation_icon(self):
        panel = DevicePanelGroup(None, DisconnectedHandler())
        header = panel.layout().itemAt(0).widget()

        self.assertIs(
            header.layout().itemAt(0).widget(),
            panel.navigation_toggle_btn,
        )
        self.assertEqual(panel.navigation_toggle_btn.text(), "◧")
        self.assertEqual(
            panel.navigation_toggle_btn.toolTip(),
            "Hide navigation pane",
        )

        panel.navigation_toggle_btn.click()
        self.assertTrue(panel.favorites_pane.isHidden())
        self.assertEqual(
            panel.navigation_toggle_btn.toolTip(),
            "Show navigation pane",
        )
        panel.prepare_for_close()
        panel.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
