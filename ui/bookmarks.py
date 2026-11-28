import json
import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, pyqtSignal


def get_app_data_directory() -> Path:
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(location) if location else Path.home() / ".adb-explorer"


class BookmarkStore(QObject):
    bookmarks_changed = pyqtSignal(str)
    common_bookmarks_changed = pyqtSignal()

    def __init__(self, path=None):
        super().__init__()
        if path is None:
            path = get_app_data_directory() / "bookmarks.json"
        self.path = Path(path)

    def load(self, device_id: str) -> list:
        data = self._read()
        bookmarks = data["devices"].get(self._device_key(device_id), [])
        if not isinstance(bookmarks, list):
            raise ValueError("Bookmark list must be a JSON array")
        for item in bookmarks:
            self._validate_bookmark(item)
        return bookmarks

    def load_common(self) -> list:
        bookmarks = self._read().get("common", [])
        if not isinstance(bookmarks, list):
            raise ValueError("Common favorites must be a JSON array")
        for item in bookmarks:
            self._validate_bookmark(item)
        return bookmarks

    def save(self, device_id: str, bookmarks: list) -> None:
        for item in bookmarks:
            self._validate_bookmark(item)
        data = self._read()
        data["version"] = 3
        key = self._device_key(device_id)
        data["devices"][key] = bookmarks
        self._write(data)
        self.bookmarks_changed.emit(key)

    def save_common(self, bookmarks: list) -> None:
        for item in bookmarks:
            self._validate_bookmark(item)
        data = self._read()
        data["version"] = 3
        data["common"] = bookmarks
        self._write(data)
        self.common_bookmarks_changed.emit()

    def save_device_and_common(
        self, device_id: str, device_bookmarks: list, common_bookmarks: list
    ) -> None:
        for item in (*device_bookmarks, *common_bookmarks):
            self._validate_bookmark(item)
        data = self._read()
        data["version"] = 3
        key = self._device_key(device_id)
        data["devices"][key] = device_bookmarks
        data["common"] = common_bookmarks
        self._write(data)
        self.bookmarks_changed.emit(key)
        self.common_bookmarks_changed.emit()

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f"{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                json.dump(data, tmp_file, ensure_ascii=False, indent=2)
                tmp_file.write("\n")
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()

    def _read(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "devices": {}}
        with self.path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("devices"), dict):
            raise ValueError("Bookmark file must contain a devices object")
        return data

    @staticmethod
    def _device_key(device_id) -> str:
        return str(device_id or "unknown")

    @staticmethod
    def _validate_bookmark(bookmark) -> None:
        if (
            not isinstance(bookmark, dict)
            or not isinstance(bookmark.get("name"), str)
            or not bookmark["name"].strip()
        ):
            raise ValueError("Favorites entries require a name")
        if bookmark.get("kind") == "folder":
            children = bookmark.get("children")
            if (
                not isinstance(bookmark.get("id"), str)
                or not bookmark["id"]
                or not isinstance(children, list)
            ):
                raise ValueError("Favorites folders require an id and children list")
            for child in children:
                BookmarkStore._validate_bookmark(child)
            return
        if bookmark.get("kind") not in (None, "favorite") or (
            not isinstance(bookmark.get("path"), str)
            or not bookmark["path"].startswith("/")
            or not isinstance(bookmark.get("note", ""), str)
        ):
            raise ValueError("Bookmark requires a name and absolute device path")
