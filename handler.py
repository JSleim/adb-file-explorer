import subprocess
import shlex
from dataclasses import dataclass
from typing import List, Optional
import re

@dataclass
class FileItem:
    name: str
    path: str
    is_dir: bool
    size: int
    permissions: str
    date_modified: str

class ADBHandler:
    def __init__(self, device_serial=None):
        import logging
        self.logger = logging.getLogger('ADBHandler')

        self.device_serial = device_serial
        self.devices = self.get_connected_devices()
        self.device_connected = bool(self.devices)

        if not self.device_connected:
            self.logger.warning("No ADB device connected")
        elif not device_serial and len(self.devices) == 1:
            self.device_serial = next(iter(self.devices.keys()))
        
    def get_connected_devices(self):
        try:
            result = self._run_adb_command(['devices', '-l'])

            if result.returncode != 0:
                self.logger.error(f"Error getting devices: {result.stderr}")
                return {}

            devices = {}
            for line in result.stdout.splitlines():
                if 'device ' in line and 'devices' not in line:
                    parts = line.split()
                    serial = parts[0]
                    model = next((p.split(':')[1] for p in parts[1:] if p.startswith('model:')), 'Unknown')
                    devices[serial] = model

            return devices

        except Exception as e:
            self.logger.error(f"Error listing devices: {e}")
            return {}
    
    def check_adb_connection(self) -> bool:
        try:
            result = self._run_adb_command(['devices'])
            devices = result.stdout.strip()
            self.logger.debug(f"ADB Devices output: {devices}")
            return "device" in devices
        except FileNotFoundError:
            self.logger.error("ADB command not found. Please ensure ADB is installed and in PATH")
            return False
        except Exception as e:
            self.logger.error(f"ADB Connection error: {e}")
            return False
    
    def _escape_path(self, path: str) -> str:

        path = path.replace('"', '\\"').replace("'", "\\'")
        return f'"{path}"'
    
    def _run_adb_command(self, command: list, use_shell=False) -> subprocess.CompletedProcess:
        startupinfo = None
        if hasattr(subprocess, 'STARTUPINFO'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        cmd = ['adb']
        if self.device_serial:
            cmd.extend(['-s', self.device_serial])
        cmd.extend(command)

        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                shell=use_shell,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {' '.join(cmd)}")
            raise
            
    def list_directory(self, path: str) -> List[FileItem]:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return []

        try:
            self.logger.debug(f"Listing directory: {path}")
            escaped_path = self._escape_path(path)
            result = self._run_adb_command(
                ['shell', f'ls -la {escaped_path} 2>/dev/null || echo "error"']
            )

            if result.returncode != 0:
                self.logger.error(f"ADB Error: {result.stderr}")
                return []

            items = []
            lines = result.stdout.split('\n')

            pattern = re.compile(
                r'^([\-dlcbpsrwxStT]+)\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.+)$'
            )
            for line in lines:
                self.logger.debug(f"Raw line: '{line}'")
                line = line.strip()
                if not line or line.startswith('total'):
                    continue
                match = pattern.match(line)
                if not match:
                    self.logger.debug(f"Skipping line (no regex match): '{line}'")
                    continue
                perms = match.group(1)
                size = match.group(2)
                date = f"{match.group(3)} {match.group(4)}"
                name = match.group(5)
                if name in ['.', '..']:
                    continue
                self.logger.debug(f"Parsed: perms={perms}, size={size}, date={date}, name={name}")
                items.append(FileItem(
                    name=name,
                    path=f"{path.rstrip('/')}/{name}",
                    is_dir=perms.startswith('d'),
                    size=int(size),
                    permissions=perms,
                    date_modified=date
                ))
            self.logger.debug(f"Successfully parsed {len(items)} items")
            return items
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout listing directory: {path}")
            return []
        except Exception as e:
            self.logger.error(f"Error listing directory: {e}")
            return []

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            result = self._run_adb_command(['pull', remote_path, local_path])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout pulling file: {remote_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error pulling file/folder: {e}")
            return False

    def rename_item(self, old_path: str, new_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_old = self._escape_path(old_path)
            escaped_new = self._escape_path(new_path)
            result = self._run_adb_command(['shell', f'mv {escaped_old} {escaped_new}'])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout renaming: {old_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error renaming: {e}")
            return False

    def delete_item(self, path: str, is_dir: bool = False) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_path = self._escape_path(path)
            if is_dir:
                cmd = f'rm -r {escaped_path}'
            else:
                cmd = f'rm {escaped_path}'
            result = self._run_adb_command(['shell', cmd])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout deleting: {path}")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting: {e}")
            return False

    def create_file(self, remote_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command(['shell', f'touch {escaped_path}'])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout creating file: {remote_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error creating file: {e}")
            return False

    def create_folder(self, remote_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command(['shell', f'mkdir -p {escaped_path}'])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout creating folder: {remote_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error creating folder: {e}")
            return False

    def push_file(self, local_path: str, remote_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            result = self._run_adb_command(['push', local_path, remote_path])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout pushing file: {local_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error pushing file: {e}")
            return False
            
    def copy_on_device(self, src_path: str, dest_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_src = self._escape_path(src_path)
            escaped_dest = self._escape_path(dest_path)

            parent_dir = '/'.join(dest_path.split('/')[:-1])
            if parent_dir:
                self.create_folder(parent_dir)

            result = self._run_adb_command(['shell', f'cp -r {escaped_src} {escaped_dest}'])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"Timeout copying: {src_path} to {dest_path}")
            return False
        except Exception as e:
            print(f"Error copying: {e}")
            return False
            
    def move_on_device(self, src_path: str, dest_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_src = self._escape_path(src_path)
            escaped_dest = self._escape_path(dest_path)

            parent_dir = '/'.join(dest_path.split('/')[:-1])
            if parent_dir:
                self.create_folder(parent_dir)

            result = self._run_adb_command(['shell', f'mv {escaped_src} {escaped_dest}'])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"Timeout moving: {src_path} to {dest_path}")
            return False
        except Exception as e:
            print(f"Error moving: {e}")
            return False
            
