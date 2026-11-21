import ctypes
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_native_dll = None


@dataclass
class DragManifestItem:
    remote_path: str
    relative_path: str
    size: int
    modified_unix_seconds: int
    is_directory: bool


class NativeDragItem(ctypes.Structure):
    _fields_ = [
        ("remote_path", ctypes.c_wchar_p),
        ("relative_path", ctypes.c_wchar_p),
        ("size", ctypes.c_uint64),
        ("modified_unix_seconds", ctypes.c_int64),
        ("is_directory", ctypes.c_uint32),
    ]


def _validate_windows_name(name):
    A = name
    if (
        not A
        or A in {".", ".."}
        or any(B in A for B in '<>:"/\\|?*\x00\r\n')
        or A.endswith((" ", "."))
    ):
        raise ValueError(f"'{A}' cannot be represented as a Windows file name.")
    D = A.split(".", 1)[0].upper()
    B = {"CON", "PRN", "AUX", "NUL"}
    B.update(f"COM{A}" for A in range(1, 10))
    B.update(f"LPT{A}" for A in range(1, 10))
    if D in B:
        raise ValueError(f"'{A}' is reserved as a Windows file name.")


def _make_manifest_item(file_item, relative_path):
    B = relative_path
    A = file_item
    _validate_windows_name(A.name)
    if len(B.encode("utf-16-le")) // 2 >= 260:
        raise ValueError(f"'{B}' exceeds the Windows drag path limit.")
    C = int(datetime.strptime(A.date_modified, "%Y-%m-%d %H:%M").timestamp())
    return DragManifestItem(
        remote_path=A.path,
        relative_path=B,
        size=A.size,
        modified_unix_seconds=C,
        is_directory=A.is_dir,
    )


def build_drag_manifest(adb_handler, selected_items, use_root=False):
    A = adb_handler
    C = []

    def D(file_item, relative_path):
        E = relative_path
        B = file_item
        C.append(_make_manifest_item(B, E))
        if not B.is_dir:
            return
        if not A.device_connected:
            raise RuntimeError("ADB device disconnected while preparing the drag.")
        A.last_error = None
        F = A.list_directory(B.path, use_root=use_root)
        if F is None or A.last_error:
            H = A.last_error or "Directory listing failed."
            raise RuntimeError(f"Failed to list directory '{B.path}': {H}")
        for G in F:
            I = f"{E}\\{G.name}"
            D(G, I)

    for B in selected_items:
        D(B, B.name)
    return C


def _get_native_dll_path():
    if getattr(sys, "frozen", False):
        B = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return B / "adb_drag_source.dll"
    return (
        Path(__file__).resolve().parents[1]
        / "cpp"
        / "build"
        / "Release"
        / "adb_drag_source.dll"
    )


def native_drag_available():
    return os.name == "nt" and _get_native_dll_path().is_file()


def _load_native_dll():
    global _native_dll
    if _native_dll is None:
        _native_dll = ctypes.WinDLL(str(_get_native_dll_path()))
        A = _native_dll.start_drag
        A.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(NativeDragItem),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_wchar),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint64),
        ]
        A.restype = ctypes.c_int32
        _native_dll.cancel_drag.argtypes = [ctypes.c_uint64]
        _native_dll.cancel_drag.restype = ctypes.c_int32
        _native_dll.wait_for_drag.argtypes = [ctypes.c_uint64]
        _native_dll.wait_for_drag.restype = ctypes.c_int32
    return _native_dll


def start_windows_drag(serial, manifest, use_su=False):
    A = manifest
    if os.name != "nt":
        raise OSError("Native Windows file dragging is only available on Windows.")
    F = _get_native_dll_path()
    if not F.is_file():
        return False
    if not A:
        return False
    if len(A) > 4294967295:
        raise ValueError("Too many items to drag in one operation.")
    C = shutil.which("adb")
    if not C:
        raise FileNotFoundError("ADB was not found on PATH.")
    G = (NativeDragItem * len(A))(
        *(
            NativeDragItem(
                A.remote_path,
                A.relative_path,
                A.size,
                A.modified_unix_seconds,
                int(A.is_directory),
            )
            for A in A
        )
    )
    B = ctypes.create_unicode_buffer(512)
    H = _load_native_dll()
    I = H.start_drag
    D = ctypes.c_uint64()
    E = I(C, serial, int(use_su), G, len(A), B, len(B), ctypes.byref(D))
    if E == -1:
        raise RuntimeError(B.value or "The Windows drag operation failed.")
    if E == 0:
        return
    return D.value


def wait_for_windows_drag(operation_id):
    return bool(_load_native_dll().wait_for_drag(operation_id))


def cancel_windows_drag(operation_id):
    return bool(_load_native_dll().cancel_drag(operation_id))


def build_manifest_for_paths(adb_handler, all_files, paths, use_root=False):
    D = {A.path: A for A in all_files}
    A = []
    for B in paths:
        C = D.get(B)
        if C is None:
            raise RuntimeError(f"Selected item is no longer available: {B}")
        A.append(C)
    return build_drag_manifest(adb_handler, A, use_root=use_root)
