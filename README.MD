# ADB Explorer

ADB Explorer is a desktop file manager for Android devices connected through
Android Debug Bridge (ADB).

## Features

- Browse and manage files on Android devices
- Transfer files between your PC and devices, or between devices
- Work with multiple devices and side-by-side panels
- Search files, install APKs, and run tasks in the background
- Drag and drop files

## Install

### Windows executable

Download the latest `.exe` from [Releases](../../releases) and run it.

### Run from source

Install Python 3.10 or newer and [ADB](https://developer.android.com/tools/adb),
then run:

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

## Use

Connect a device with USB debugging enabled, then launch ADB Explorer. For
wireless connections, connect the device to the same network and use ADB's
wireless debugging.

Select files to copy, move, rename, delete, or transfer. Long-running tasks can
be moved to the background and cancelled. Cancelling an ADB Explorer transfer
removes a newly created partial destination.

## License

MIT
