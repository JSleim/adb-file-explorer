# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyQt6.QtCore import QLibraryInfo

is_windows = sys.platform.startswith('win')
qt_translations_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)

# Определяем нативную библиотеку в зависимости от ОС
binaries_list = []
if is_windows:
    dll_path = Path('cpp/build/Release/adb_drag_source.dll')
    if dll_path.exists():
        binaries_list.append((str(dll_path), '.'))
else:
    # Укажите точный путь, который выдаст команда find, если он отличается
    so_candidates = [
        Path('cpp/build/libadb_drag_source.so'),
        Path('cpp/build/adb_drag_source.so'),
    ]
    for so_path in so_candidates:
        if so_path.exists():
            binaries_list.append((str(so_path), '.'))
            break

# Иконка (для Linux лучше использовать .png, если есть в папке assets)
icon_path = 'assets/adb-explorer.ico' if is_windows else 'assets/adb-explorer.png'
if not Path(icon_path).exists():
    icon_path = 'assets/adb-explorer.ico'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_list,
    datas=[
        ('logging_config.py', '.'),
        ('assets', 'assets'),
        ('i18n', 'i18n'),
        (f"{qt_translations_dir}/qtbase_ru.qm", "PyQt6/Qt6/translations"),
    ],
    hiddenimports=['PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'logging.handlers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ADB Explorer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
