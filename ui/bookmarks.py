import json
import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, pyqtSignal


def get_app_data_directory():
    data_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(data_dir) if data_dir else Path.home() / ".adb-explorer"


class BookmarkStore(QObject):
    bookmarks_changed = pyqtSignal(str)

    def __init__(self, path=None):
        super().__init__()
        if path is None:
            path = get_app_data_directory() / "bookmarks.json"
        self.path = Path(path)

    def load(self, device_id):
        data = self._read()
        bookmarks = data["devices"].get(self._device_key(device_id), [])
        if not isinstance(bookmarks, list):
            raise ValueError("Bookmark list must be a JSON array")
        for bookmark in bookmarks:
            self._validate_bookmark(bookmark)
        return bookmarks

    def save(self, device_id, bookmarks):
        for bookmark in bookmarks:
            self._validate_bookmark(bookmark)
        data = self._read()
        data["version"] = 1
        data["devices"][self._device_key(device_id)] = bookmarks

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f"{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        self.bookmarks_changed.emit(self._device_key(device_id))

    def _read(self):
        if not self.path.exists():
            return {"version": 1, "devices": {}}
        with self.path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("devices"), dict):
            raise ValueError("Bookmark file must contain a devices object")
        return data

    @staticmethod
    def _device_key(device_id):
        return str(device_id or "unknown")

    @staticmethod
    def _validate_bookmark(bookmark):
        if (
            not isinstance(bookmark, dict)
            or not isinstance(bookmark.get("name"), str)
            or not bookmark["name"].strip()
            or not isinstance(bookmark.get("path"), str)
            or not bookmark["path"].startswith("/")
            or not isinstance(bookmark.get("note", ""), str)
        ):
            raise ValueError("Bookmark requires a name and absolute device path")
