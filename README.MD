
# ADB Explorer
A graphical file manager for Android devices connected via ADB (Android Debug Bridge). Provides an intuitive interface for managing files on Android devices without needing to use command-line ADB commands or navigate through the device's UI.
## Features
- **Multi-device support** - Select from multiple connected Android devices
- **Full file operations** - Push, pull, delete, rename, and copy/paste files
- **GUI interface** - Clean, intuitive file explorer built with PyQt6
- **Two-way sync** - Transfer files between computer and device easily
- **Fast navigation** - Browse device storage like a desktop file manager
- **File search** - Quickly find files on your device
- **Batch operations** - Perform actions on multiple files at once
- **Drag-and-drop support** - Intuitive file transfers
- **Progress indicators** - Visual feedback for large file transfers
- **Wireless ADB** - Connect to devices over network (no USB required)
## Installation
### Option 1: Download Executable (Windows)
Download the latest release from the [Releases](../../releases) page and run the `.exe` file.
### Option 2: Run from Source
**Requirements:**
- Python 3.7+
- PyQt6
- ADB installed and in system PATH
**Install dependencies:**
```bash
pip install PyQt6
```
**Run:**
```bash
python main.py
```
## Usage
1. **Connect your Android device** via USB with USB debugging enabled
2. **Launch the application**
3. **Select your device** from the device chooser (if multiple devices connected)
4. **Navigate and manage files** using the GUI:
   - **Push files**: Transfer files from computer to device
   - **Pull files**: Download files from device to computer
   - **Delete**: Remove files from device
   - **Rename**: Rename files on device
   - **Copy/Paste**: Copy files within the device
   - **Search**: Find files quickly using the search function
   - **Drag-and-drop**: Drop files directly into the application to transfer
   - **Batch operations**: Select multiple files for simultaneous operations
## Prerequisites
- ADB (Android Debug Bridge) must be installed and accessible from command line
- For USB connections: Android device with USB debugging enabled
- For wireless connections: Device and computer on the same network
### Installing ADB
**Windows:**
- Download [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools)
- Extract and add to system PATH
**macOS:**
```bash
brew install android-platform-tools
```
**Linux:**
```bash
sudo apt-get install adb  # Ubuntu/Debian
```
### Enabling USB Debugging on Android
1. Go to **Settings** > **About Phone**
2. Tap **Build Number** 7 times to enable Developer Options
3. Go to **Settings** > **Developer Options**
4. Enable **USB Debugging**
## Technical Details
Built with:
- **Python** - Core application logic
- **PyQt6** - GUI framework
- **ADB** - Android Debug Bridge for device communication
The application uses subprocess calls to ADB commands and presents them through a familiar file explorer interface, making Android file management accessible without command-line knowledge.
## Known Limitations
- Some system directories may require root access
- File permissions depend on device settings
## License
MIT License