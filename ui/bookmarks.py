_C = "version"
_B = "devices"
_A = None
import json, os, tempfile
from pathlib import Path
from PyQt6.QtCore import QObject, QStandardPaths, pyqtSignal


def get_app_data_directory():
    A = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(A) if A else Path.home() / ".adb-explorer"


class BookmarkStore(QObject):
    bookmarks_changed = pyqtSignal(str)

    def __init__(B, path=_A):
        A = path
        super().__init__()
        if A is _A:
            A = get_app_data_directory() / "bookmarks.json"
        B.path = Path(A)

    def load(A, device_id):
        C = A._read()
        B = C[_B].get(A._device_key(device_id), [])
        if not isinstance(B, list):
            raise ValueError("Bookmark list must be a JSON array")
        for D in B:
            A._validate_bookmark(D)
        return B

    def save(A, device_id, bookmarks):
        G = False
        F = bookmarks
        E = device_id
        for H in F:
            A._validate_bookmark(H)
        D = A._read()
        D[_C] = 1
        D[_B][A._device_key(E)] = F
        A.path.parent.mkdir(parents=True, exist_ok=True)
        B = _A
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=A.path.parent,
                prefix=f"{A.path.name}.",
                suffix=".tmp",
                delete=G,
            ) as C:
                B = Path(C.name)
                json.dump(D, C, ensure_ascii=G, indent=2)
                C.write("\n")
                C.flush()
                os.fsync(C.fileno())
            os.replace(B, A.path)
        finally:
            if B is not _A and B.exists():
                B.unlink()
        A.bookmarks_changed.emit(A._device_key(E))

    def _read(B):
        if not B.path.exists():
            return {_C: 1, _B: {}}
        with B.path.open(encoding="utf-8") as C:
            A = json.load(C)
        if not isinstance(A, dict) or not isinstance(A.get(_B), dict):
            raise ValueError("Bookmark file must contain a devices object")
        return A

    @staticmethod
    def _device_key(device_id):
        return str(device_id or "unknown")

    @staticmethod
    def _validate_bookmark(bookmark):
        C = "path"
        B = "name"
        A = bookmark
        if (
            not isinstance(A, dict)
            or not isinstance(A.get(B), str)
            or not A[B].strip()
            or not isinstance(A.get(C), str)
            or not A[C].startswith("/")
            or not isinstance(A.get("note", ""), str)
        ):
            raise ValueError("Bookmark requires a name and absolute device path")
