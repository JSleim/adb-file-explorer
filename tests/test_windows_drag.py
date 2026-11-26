import unittest

from PyQt6.QtCore import QMimeData

from handler import FileItem
from ui.widgets import ADB_MIME, DropTreeView
from ui.windows_drag import build_drag_manifest


def file_item(name, path, is_dir, size=0):
    return FileItem(
        name=name,
        path=path,
        is_dir=is_dir,
        size=size,
        permissions="drwxr-xr-x" if is_dir else "-rw-r--r--",
        date_modified="2026-10-15 08:00",
    )


class FakeADBHandler:
    def __init__(self, listings):
        self.listings = listings
        self.list_calls = []
        self.device_connected = True
        self.last_error = None

    def list_directory(self, path, use_root=False):
        self.list_calls.append((path, use_root))
        result = self.listings[path]
        if result is None:
            self.last_error = "Permission denied"
        return result


class WindowsDragManifestTests(unittest.TestCase):
    def test_recursively_flattens_directory_with_relative_paths(self):
        root = file_item("Camera Roll", "/storage/Camera Roll", True)
        album = file_item("2026", "/storage/Camera Roll/2026", True)
        image = file_item("photo.jpg", "/storage/Camera Roll/2026/photo.jpg", False, 1234)
        handler = FakeADBHandler({
            root.path: [album],
            album.path: [image],
        })

        manifest = build_drag_manifest(handler, [root], use_root=True)

        self.assertEqual(
            [(item.relative_path, item.is_directory) for item in manifest],
            [
                ("Camera Roll", True),
                ("Camera Roll\\2026", True),
                ("Camera Roll\\2026\\photo.jpg", False),
            ],
        )
        self.assertEqual(manifest[-1].remote_path, image.path)
        self.assertEqual(manifest[-1].size, 1234)
        self.assertEqual(handler.list_calls, [
            (root.path, True),
            (album.path, True),
        ])

    def test_fails_explicitly_if_directory_listing_fails(self):
        root = file_item("Pictures", "/storage/Pictures", True)
        handler = FakeADBHandler({root.path: None})

        with self.assertRaisesRegex(RuntimeError, "Failed to list directory"):
            build_drag_manifest(handler, [root])

    def test_rejects_names_that_cannot_be_created_on_windows(self):
        invalid_file = file_item("bad:name.txt", "/storage/bad:name.txt", False)

        with self.assertRaisesRegex(ValueError, "Windows file name"):
            build_drag_manifest(FakeADBHandler({}), [invalid_file])

    def test_reads_the_native_windows_mime_alias_for_in_app_drags(self):
        mime_data = QMimeData()
        windows_mime_type = (
            'application/x-qt-windows-mime;value="application/x-adb-paths"'
        )
        payload = b"device-1\n/storage/folder\n"
        mime_data.setData(windows_mime_type, payload)

        self.assertEqual(
            DropTreeView._adb_paths_payload(mime_data),
            payload,
        )


if __name__ == "__main__":
    unittest.main()
