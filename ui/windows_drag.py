import ctypes
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from handler import FileItem

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
    if (
        not name
        or name in {".", ".."}
        or any(character in name for character in '<>:"/\\|?*\0\r\n')
        or name.endswith((" ", "."))
    ):
        raise ValueError(f"'{name}' cannot be represented as a Windows file name.")

    stem = name.split(".", 1)[0].upper()
    reserved_names = {"CON", "PRN", "AUX", "NUL"}
    reserved_names.update(f"COM{number}" for number in range(1, 10))
    reserved_names.update(f"LPT{number}" for number in range(1, 10))
    if stem in reserved_names:
        raise ValueError(f"'{name}' is reserved as a Windows file name.")


def _make_manifest_item(file_item, relative_path):
    _validate_windows_name(file_item.name)
    if len(relative_path.encode("utf-16-le")) // 2 >= 260:
        raise ValueError(f"'{relative_path}' exceeds the Windows drag path limit.")

    modified = int(datetime.strptime(
        file_item.date_modified, "%Y-%m-%d %H:%M"
    ).timestamp())
    return DragManifestItem(
        remote_path=file_item.path,
        relative_path=relative_path,
        size=file_item.size,
        modified_unix_seconds=modified,
        is_directory=file_item.is_dir,
    )


def build_drag_manifest(adb_handler, selected_items, use_root=False):
    manifest = []

    def add_item(file_item, relative_path):
        manifest.append(_make_manifest_item(file_item, relative_path))
        if not file_item.is_dir:
            return

        if not adb_handler.device_connected:
            raise RuntimeError("ADB device disconnected while preparing the drag.")
        adb_handler.last_error = None
        children = adb_handler.list_directory(file_item.path, use_root=use_root)
        if children is None or adb_handler.last_error:
            error = adb_handler.last_error or "Directory listing failed."
            raise RuntimeError(f"Failed to list directory '{file_item.path}': {error}")
        for child in children:
            child_relative_path = f"{relative_path}\\{child.name}"
            add_item(child, child_relative_path)

    for item in selected_items:
        add_item(item, item.name)

    return manifest


def _get_native_dll_path():
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base_path / "adb_drag_source.dll"
    return Path(__file__).resolve().parents[1] / "cpp" / "build" / "Release" / "adb_drag_source.dll"


def native_drag_available():
    return os.name == "nt" and _get_native_dll_path().is_file()


def _load_native_dll():
    global _native_dll
    if _native_dll is None:
        _native_dll = ctypes.WinDLL(str(_get_native_dll_path()))
        start_drag = _native_dll.start_drag
        start_drag.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(NativeDragItem),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_wchar),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint64),
        ]
        start_drag.restype = ctypes.c_int32
        _native_dll.cancel_drag.argtypes = [ctypes.c_uint64]
        _native_dll.cancel_drag.restype = ctypes.c_int32
        _native_dll.wait_for_drag.argtypes = [ctypes.c_uint64]
        _native_dll.wait_for_drag.restype = ctypes.c_int32
    return _native_dll


def start_windows_drag(serial, manifest, use_su=False):
    if os.name != "nt":
        raise OSError("Native Windows file dragging is only available on Windows.")

    dll_path = _get_native_dll_path()
    if not dll_path.is_file():
        return False
    if not manifest:
        return False
    if len(manifest) > 0xFFFFFFFF:
        raise ValueError("Too many items to drag in one operation.")

    adb_path = shutil.which("adb")
    if not adb_path:
        raise FileNotFoundError("ADB was not found on PATH.")

    items = (NativeDragItem * len(manifest))(
        *(
            NativeDragItem(
                item.remote_path,
                item.relative_path,
                item.size,
                item.modified_unix_seconds,
                int(item.is_directory),
            )
            for item in manifest
        )
    )
    error_buffer = ctypes.create_unicode_buffer(512)
    native_dll = _load_native_dll()
    start_drag = native_dll.start_drag
    async_operation_id = ctypes.c_uint64()
    result = start_drag(
        adb_path,
        serial,
        int(use_su),
        items,
        len(manifest),
        error_buffer,
        len(error_buffer),
        ctypes.byref(async_operation_id),
    )

    if result == -1:
        raise RuntimeError(error_buffer.value or "The Windows drag operation failed.")
    if result == 0:
        return None
    return async_operation_id.value


def wait_for_windows_drag(operation_id):
    return bool(_load_native_dll().wait_for_drag(operation_id))


def cancel_windows_drag(operation_id):
    return bool(_load_native_dll().cancel_drag(operation_id))


def build_manifest_for_paths(adb_handler, all_files, paths, use_root=False):
    files_by_path = {file_item.path: file_item for file_item in all_files}
    selected = []
    for path in paths:
        file_item = files_by_path.get(path)
        if file_item is None:
            raise RuntimeError(f"Selected item is no longer available: {path}")
        selected.append(file_item)
    return build_drag_manifest(adb_handler, selected, use_root=use_root)
