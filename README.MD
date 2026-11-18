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
- **Protect existing files during PC uploads** with overwrite, rename,
  skip, cancel, file details, and an apply-to-all option
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
1. Connect the device and computer to the same network.
2. On the device, enable **Wireless debugging** and tap **Pair device with pairing code**.
3. On your computer, run:
   ```bash
   adb pair <ip>:<pairing-port>
   ```
   and enter the pairing code shown on the device.
4. Then connect using the IP and port shown on the main Wireless debugging screen:
   ```bash
   adb connect <ip>:<port>
   ```
5. Launch ADB Explorer.

## Using ADB Explorer

### Working with files

Select files and use the toolbar or right-click menu to copy, move, rename,
delete, or transfer them. You can drag and drop files and folders in from your
PC.

Long-running tasks can be sent to the background and cancelled at any time.
Cancelling a transfer removes any partial file it created at the destination.

### Panels and tabs

- Click **+ Add Panel** to open another connected device panel. You can open a
  second panel for the same device.
- Click **+ Add Tab** or press **Ctrl+T** to open a new path tab in the active
  panel. Press **Ctrl+W** to close it.

### Address bar

The address bar shows clickable breadcrumbs. Click any segment to jump to that
folder. Long paths scroll to keep the current folder in view, so they never
widen the window or the device panels.

To type a path instead, press **Ctrl+L** or click the edit icon. Start typing
and press **Tab** or **Right Arrow** to accept the suggested folder completion.
Suggestions update as you move into nested folders. Press **Esc** to go back to
the breadcrumbs.

### Sidebar and favorites

The left pane lists **Favorites** first, followed by common folders under
**Internal storage**: Downloads, Documents, Pictures, Music, Videos, and Camera.

- Click a folder once to navigate. Collapse groups to keep the sidebar tidy.
- The sidebar selection follows the active tab.
- Right-click a folder in the file list to **add it to Favorites**.
- Right-click a favorite to **edit** (including an optional note) or **remove** it.
- Right-click a built-in folder in the sidebar to **pin** it.
- Favorites persist between launches.

When multiple device panels are open, the pane collapses automatically. Use the
navigation-pane button in a panel header to show it again.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+T | New tab |
| Ctrl+W | Close active tab |
| Ctrl+L | Edit path |
| Esc | Return to breadcrumbs |
| Tab / Right Arrow | Accept path completion |

### Where settings are stored

Favorites (`bookmarks.json`) and theme settings (`config.ini`) are saved per
user in:

- **Windows:** `%APPDATA%\ADB Explorer`
- **macOS:** `~/Library/Application Support/ADB Explorer`
- **Linux:** `$XDG_DATA_HOME/ADB Explorer`, or `~/.local/share/ADB Explorer` when
  `XDG_DATA_HOME` is not set

## License

GPL-3.0. See [LICENSE](LICENSE).
