# ADB Explorer: Android File Manager for Windows, macOS & Linux

[![Release](https://img.shields.io/github/v/release/JSleim/adb-file-explorer)](https://github.com/JSleim/adb-file-explorer/releases)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)

**ADB Explorer is a free, open-source desktop file manager for Android.** It uses
Android Debug Bridge (ADB) to browse, copy, move, and manage files on your phone
or tablet over USB or Wi-Fi, with side-by-side panels, drag and drop, and
device-to-device transfers.

## Features

- **Browse and manage files** on Android devices: copy, move, rename, delete
- **Transfer files** between PC and device, or directly between two devices
- **Multiple devices, side-by-side panels**, with multiple path tabs per panel
- **Search files**, **install APKs**, and run tasks in the background
- **Import files and folders** while preserving folder structure
- **Protect existing files during PC uploads** with overwrite, skip, cancel,
  file details, and an apply-to-all option
- **Drag and drop** files and folders from your PC
- **Safe cancellation**: cancelled transfers remove partial destination files

## Download and install

| Platform | How |
|---|---|
| Windows | Download the `.exe` from [Releases](../../releases) |
| macOS / Linux | [Run from source](#run-from-source) (Python 3.10+) |

> **Requires [ADB](https://developer.android.com/tools/adb) installed and in your PATH.** This applies to both the `.exe` and running from source.

### Run from source

Install Python 3.10 or newer, then run:

```bash
pip install -r requirements.txt
python main.py
```

To drag files from a device into Windows apps when running from source, build
the native helper with CMake and a C++ compiler:

```bash
cmake -S cpp -B cpp/build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build --config Release
```

## How to connect your Android device

### USB
1. Enable **Developer options** and **USB debugging** on your device.
2. Connect it to your computer and accept the debugging prompt.
3. Launch ADB Explorer.

### Wi-Fi (wireless debugging)
Connect the device and computer to the same network, enable **Wireless debugging**
on the device, and pair it using ADB. Then launch ADB Explorer.

## Using ADB Explorer

Select files to copy, move, rename, delete, or transfer. Long-running tasks can
be moved to the background and cancelled. Cancelling an ADB Explorer transfer
removes a newly created partial destination.

Use **+ Add Panel** to open another connected device panel, including another
panel for the same device. Use **+ Add Tab** or press **Ctrl+T** to open a new
path tab in the active panel. Press **Ctrl+W** to close the active tab.

## License

GPL-3.0. See [LICENSE](LICENSE).
