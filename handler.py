import subprocess
import socket
import struct
from dataclasses import dataclass
from typing import List
import re
import time
import zipfile
import os
import tempfile
import json

@dataclass
class FileItem:
    name: str
    path: str
    is_dir: bool
    size: int
    permissions: str
    date_modified: str

class ADBHandler:
    _active_streams = {}

    _WIN_FLAGS: int = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    def __init__(self, device_serial=None):
        import logging
        self.logger = logging.getLogger('ADBHandler')

        self._ensure_server_started()

        self.device_serial = device_serial
        self.devices = self.get_connected_devices()
        self.device_connected = bool(self.devices)
        self.root_mode = None
        self.last_error = None
        self._active_process = None

        if not self.device_connected:
            self.logger.warning("No ADB device connected")
        elif not device_serial and len(self.devices) == 1:
            self.device_serial = next(iter(self.devices.keys()))

    def _build_adb_cmd(self, command: list, device_serial: str = None) -> list:
        cmd = ['adb']
        serial = device_serial or self.device_serial
        if serial:
            cmd.extend(['-s', serial])
        cmd.extend(command)
        return cmd

    @staticmethod
    def _make_startupinfo():
        startupinfo = None
        if hasattr(subprocess, 'STARTUPINFO'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo

    @staticmethod
    def _exec_mkdir(serial, remote_dir):
        try:
            subprocess.run(
                ['adb', '-s', serial, 'exec-out', 'mkdir', '-p', remote_dir],
                capture_output=True, timeout=10,
                startupinfo=ADBHandler._make_startupinfo(),
                creationflags=ADBHandler._WIN_FLAGS,
            )
        except Exception:
            pass

    def _ensure_server_started(self):
        try:
            subprocess.run(
                ['adb', 'start-server'],
                capture_output=True,
                timeout=15,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
        except Exception:
            pass

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

    def get_device_identity(self, serial: str) -> str:
        """Return the physical device serial reported by a specific ADB endpoint."""
        try:
            result = subprocess.run(
                ['adb', '-s', serial, 'get-serialno'],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            identity = result.stdout.strip()
            if result.returncode == 0 and identity and identity != 'unknown':
                return identity
        except Exception:
            pass
        return serial

    def get_unique_devices(self):
        """Return one preferred ADB endpoint per physical device, preferring USB."""
        unique = {}
        for serial, model in self.get_connected_devices().items():
            identity = self.get_device_identity(serial)
            candidate = (serial, model)
            current = unique.get(identity)
            if current is None or self._endpoint_priority(serial) < self._endpoint_priority(current[0]):
                unique[identity] = candidate
        return {serial: model for serial, model in unique.values()}

    @staticmethod
    def _endpoint_priority(serial: str):
        return (':' in serial, serial)
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

    def _run_adb_command(self, command: list, use_shell=False, timeout=30) -> subprocess.CompletedProcess:
        cmd = ['adb']
        if self.device_serial:
            cmd.extend(['-s', self.device_serial])
        cmd.extend(command)

        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=use_shell,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {' '.join(cmd)}")
            raise

    def _adb_push_sync(self, dst_serial, dst_path, data_iter, cancel_check=None):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect(('127.0.0.1', 5037))

            def sexact(d):
                t = 0
                while t < len(d):
                    n = sock.send(d[t:])
                    if n == 0: raise ConnectionError("ADB disconnected")
                    t += n

            def rexact(n):
                buf = b''
                while len(buf) < n:
                    c = sock.recv(n - len(buf))
                    if not c: raise ConnectionError("ADB disconnected")
                    buf += c
                return buf

            def adb_cmd(c):
                sexact(b'%04x' % len(c) + c)
                r = rexact(4)
                if r != b'OKAY':
                    raise RuntimeError(f"ADB cmd failed: {r!r}")

            adb_cmd(b'host:transport:' + dst_serial.encode())
            adb_cmd(b'sync:')
            sock.settimeout(None)

            path_b = dst_path.rstrip('/').encode()
            mode_str = b'644'
            send_data = path_b + b',' + mode_str
            while len(send_data) % 4 != 0:
                send_data += b'\x00'
            sexact(b'SEND' + struct.pack('<I', len(send_data)) + send_data)

            for chunk in data_iter:
                if cancel_check and cancel_check():
                    return False, "cancelled"
                sexact(b'DATA' + struct.pack('<I', len(chunk)) + chunk)

            sexact(b'DONE' + struct.pack('<I', int(time.time())))

            resp = rexact(4)
            if resp == b'OKAY':
                return True, ""
            elif resp == b'FAIL':
                elen = struct.unpack('<I', rexact(4))[0]
                return False, rexact(elen).decode('utf-8', errors='replace')
            else:
                return False, f"unexpected sync response: {resp!r}"
        except Exception as e:
            return False, str(e)
        finally:
            if sock:
                try: sock.close()
                except Exception: pass

    def stream_file(self, src_serial: str, src_path: str, dst_serial: str, dst_path: str,
                    chunk_callback=None, cancel_check=None) -> bool:
        si_dir = '/'.join(dst_path.rstrip('/').split('/')[:-1])
        if si_dir:
            ADBHandler._exec_mkdir(dst_serial, si_dir)

        src_proc = None
        try:
            src_proc = subprocess.Popen(
                ['adb', '-s', src_serial, 'exec-out', 'cat', src_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            self._active_process = src_proc
            stream_id = id(src_proc)
            ADBHandler._active_streams[stream_id] = (src_proc, None)

            def data_iter():
                buf = 262144
                while True:
                    if cancel_check and cancel_check():
                        return
                    chunk = src_proc.stdout.read(buf)
                    if not chunk:
                        break
                    if chunk_callback:
                        chunk_callback(len(chunk))
                    yield chunk

            ok, err = self._adb_push_sync(dst_serial, dst_path, data_iter(), cancel_check=cancel_check)
            src_proc.wait()

            src_err = (src_proc.stderr.read() or b'').decode('utf-8', errors='replace').strip()
            if src_err:
                self.logger.error(f"Stream src stderr: {src_err[:300]}")

            ADBHandler._active_streams.pop(stream_id, None)
            self._active_process = None

            if not ok:
                self.logger.error(f"Stream push failed: {err}")
                self.last_error = err
                return False
            if src_proc.returncode != 0:
                self.last_error = f"source cat exited {src_proc.returncode}"
                return False
            return True

        except Exception as e:
            self.logger.error(f"Stream file error: {e}")
            self.last_error = str(e)
            return False
        finally:
            if src_proc:
                ADBHandler._active_streams.pop(id(src_proc), None)
                if src_proc.returncode is None:
                    try: src_proc.kill()
                    except Exception: pass
            self._active_process = None

    def stream_directory(self, src_serial: str, src_path: str, dst_serial: str, dst_path: str,
                         line_callback=None, cancel_check=None) -> bool:
        parent = '/'.join(dst_path.rstrip('/').split('/')[:-1])
        base_name = src_path.rstrip('/').split('/')[-1]
        target = f"{parent}/{base_name}" if parent else base_name
        ADBHandler._exec_mkdir(dst_serial, parent)

        try:
            r = subprocess.run(
                ['adb', '-s', src_serial, 'exec-out', 'find', src_path, '-type', 'f'],
                capture_output=True, timeout=30,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            if r.returncode != 0:
                return False
            files = [f.strip() for f in r.stdout.decode('utf-8', errors='replace').split('\n') if f.strip()]
            if not files:
                return True
            for fpath in files:
                if cancel_check and cancel_check():
                    return False
                rel = fpath[len(src_path.rstrip('/')):].lstrip('/')
                dest = f"{target}/{rel}" if rel else target
                si_dir = '/'.join(dest.rstrip('/').split('/')[:-1])
                ADBHandler._exec_mkdir(dst_serial, si_dir)
                if line_callback:
                    line_callback(f"Streaming {fpath}")
                ok = self.stream_file(src_serial, fpath, dst_serial, dest, cancel_check=cancel_check)
                if not ok:
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Directory streaming error: {e}")
            return False

    def enable_root(self) -> bool:
        self.last_error = None
        try:
            result = self._run_adb_command(['root'])
            out = (result.stdout or "") + (result.stderr or "")
            if "restarting adbd as root" in out or "adbd is already running as root" in out:
                time.sleep(1)
                self.root_mode = "adb"
                return True
            if "cannot run as root" not in out:
                if result.returncode == 0:
                    time.sleep(1)
                    self.root_mode = "adb"
                    return True
        except Exception:
            pass

        try:
            result = self._run_adb_command(['shell', 'su', '-c', 'id'])
            if result.returncode == 0 and "uid=0" in (result.stdout or ""):
                self.root_mode = "su"
                return True
            self.last_error = (result.stderr or result.stdout or "").strip()
        except Exception as e:
            self.last_error = str(e)

        self.root_mode = None
        return False

    def list_directory(self, path: str, use_root: bool = False) -> List[FileItem]:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return []

        try:
            self.logger.debug(f"Listing directory: {path}")
            escaped_path = self._escape_path(path)
            if use_root and self.root_mode == "su":
                result = self._run_adb_command(
                    ['shell', 'su', '-c', f'ls -la {escaped_path} 2>/dev/null || echo "error"']
                )
            else:
                result = self._run_adb_command(
                    ['shell', f'ls -la {escaped_path} 2>/dev/null || echo "error"']
                )

            stdout = (result.stdout or "").strip()
            if result.returncode != 0 or stdout == "error" or stdout.startswith("error\n"):
                self.logger.error(f"ADB Error: {result.stderr or result.stdout}")
                self.last_error = (result.stderr or result.stdout or "").strip()
                return None

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

    def is_remote_dir(self, path: str) -> bool:
        if not self.device_connected:
            return False
        try:
            escaped_path = self._escape_path(path)
            result = self._run_adb_command(['shell', f'test -d {escaped_path}'])
            return result.returncode == 0
        except Exception:
            return False

    def get_remote_file_size(self, remote_path: str):
        """Return size in bytes of a remote file, or None if unknown."""
        if not self.device_connected:
            return None
        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command(['shell', f'stat -c %s {escaped_path}'])
            out = (result.stdout or "").strip().split()
            if result.returncode == 0 and out and out[0].isdigit():
                return int(out[0])
        except Exception:
            pass
        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command(['shell', f'wc -c < {escaped_path}'])
            out = (result.stdout or "").strip().split()
            if result.returncode == 0 and out and out[0].isdigit():
                return int(out[0])
        except Exception:
            pass
        return None

    def get_remote_dir_size(self, remote_path: str):
        """Return recursive size in bytes of a remote directory, or None if unknown."""
        if not self.device_connected:
            return None
        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command(['shell', f'du -sb {escaped_path}'])
            out = (result.stdout or "").strip().split()
            if result.returncode == 0 and out and out[0].isdigit():
                return int(out[0])
        except Exception:
            pass
        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command(['shell', f'du -sk {escaped_path}'])
            out = (result.stdout or "").strip().split()
            if result.returncode == 0 and out and out[0].isdigit():
                return int(out[0]) * 1024
        except Exception:
            pass
        return None

    def list_remote_files(self, remote_dir: str):
        """List all files under remote_dir recursively."""
        if not self.device_connected:
            return []
        try:
            escaped_path = self._escape_path(remote_dir.rstrip('/') or '/')
            result = self._run_adb_command(['shell', f'find {escaped_path} -type f'])
            if result.returncode != 0:
                return []
            files = [
                line.strip()
                for line in (result.stdout or "").splitlines()
                if line.strip()
            ]
            return files
        except Exception as e:
            self.logger.error(f"Error listing remote files: {e}")
            return []

    def list_remote_dirs(self, remote_dir: str):
        """List all directories under remote_dir recursively (including itself)."""
        if not self.device_connected:
            return []
        try:
            escaped_path = self._escape_path(remote_dir.rstrip('/') or '/')
            result = self._run_adb_command(['shell', f'find {escaped_path} -type d'])
            if result.returncode != 0:
                return []
            dirs = [
                line.strip()
                for line in (result.stdout or "").splitlines()
                if line.strip()
            ]
            return dirs
        except Exception as e:
            self.logger.error(f"Error listing remote dirs: {e}")
            return []

    def _stream_single_remote_file(self, remote_path: str, local_path: str,
                                   on_chunk=None, cancel_check=None):
        """Stream one remote file to local path via `adb exec-out cat`.

        Returns (success: bool, bytes_written: int).
        """
        cmd = self._build_adb_cmd(['exec-out', 'cat', remote_path])
        proc = None
        bytes_written = 0
        cancelled = False
        try:
            parent = os.path.dirname(local_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            self._active_process = proc
            with open(local_path, 'wb') as f:
                while True:
                    if cancel_check and cancel_check():
                        cancelled = True
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        break
                    try:
                        chunk = proc.stdout.read(262144)
                    except Exception:
                        if cancel_check and cancel_check():
                            cancelled = True
                        break
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)
                    if on_chunk:
                        try:
                            on_chunk(len(chunk))
                        except Exception:
                            pass
            if cancelled:
                try:
                    os.remove(local_path)
                except Exception:
                    pass
                return False, bytes_written
            proc.wait()
            if proc.returncode != 0:
                try:
                    err = (proc.stderr.read() or b'').decode('utf-8', errors='replace').strip()
                except Exception:
                    err = ""
                if err:
                    self.logger.error(f"Pull src stderr: {err[:300]}")
                    self.last_error = err[:500]
                else:
                    self.last_error = f"cat exited {proc.returncode}"
                try:
                    os.remove(local_path)
                except Exception:
                    pass
                return False, bytes_written
            return True, bytes_written
        except Exception as e:
            self.logger.error(f"Error streaming remote file: {e}")
            self.last_error = str(e)
            try:
                if proc and proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
            try:
                os.remove(local_path)
            except Exception:
                pass
            return False, bytes_written
        finally:
            self._active_process = None
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    def pull_file_with_progress(self, remote_path: str, local_path: str,
                                progress_callback=None, cancel_check=None) -> bool:
        """Pull a single remote file with percentage progress.

        progress_callback(transferred: int, total: int, name: str) is invoked
        from the worker thread; total is 0 when the size is unknown.
        """
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False
        total = self.get_remote_file_size(remote_path)
        if total is None:
            total = 0
        name = remote_path.rstrip('/').split('/')[-1] or remote_path
        if progress_callback:
            try:
                progress_callback(0, total, name)
            except Exception:
                pass
        transferred = [0]

        def on_chunk(n):
            transferred[0] += n
            if progress_callback:
                try:
                    progress_callback(transferred[0], total, name)
                except Exception:
                    pass

        ok, _ = self._stream_single_remote_file(
            remote_path, local_path, on_chunk=on_chunk, cancel_check=cancel_check
        )
        if ok and progress_callback and total > 0:
            try:
                progress_callback(total, total, name)
            except Exception:
                pass
        return ok

    def pull_dir_with_progress(self, remote_path: str, local_path: str,
                               progress_callback=None, cancel_check=None) -> bool:
        """Pull a remote directory recursively with overall percentage progress."""
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False
        remote_dir = remote_path.rstrip('/') or '/'
        base = remote_dir.split('/')[-1] or "folder"
        total = self.get_remote_dir_size(remote_dir)
        if total is None:
            total = 0
        if progress_callback:
            try:
                progress_callback(0, total, base)
            except Exception:
                pass
        files = self.list_remote_files(remote_dir)
        dirs = self.list_remote_dirs(remote_dir)
        try:
            os.makedirs(local_path, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Cannot create local dir: {e}")
            return False
        for d in dirs:
            if cancel_check and cancel_check():
                return False
            rel = d[len(remote_dir):].lstrip('/')
            if not rel:
                continue
            try:
                os.makedirs(os.path.join(local_path, rel), exist_ok=True)
            except Exception:
                pass
        if not files:
            if progress_callback and total > 0:
                try:
                    progress_callback(total, total, base)
                except Exception:
                    pass
            return True
        transferred = [0]

        for remote_file in files:
            if cancel_check and cancel_check():
                return False
            rel = remote_file[len(remote_dir):].lstrip('/')
            if not rel:
                continue
            local_file = os.path.join(local_path, rel)
            fname = remote_file.split('/')[-1]

            def on_chunk(n, _fname=fname):
                transferred[0] += n
                if progress_callback:
                    try:
                        progress_callback(transferred[0], total, _fname)
                    except Exception:
                        pass

            ok, _ = self._stream_single_remote_file(
                remote_file, local_file, on_chunk=on_chunk, cancel_check=cancel_check
            )
            if not ok:
                return False
        if progress_callback and total > 0:
            try:
                progress_callback(total, total, base)
            except Exception:
                pass
        elif progress_callback:
            try:
                progress_callback(transferred[0], 0, base)
            except Exception:
                pass
        return True

    def pull_with_progress(self, remote_path: str, local_path: str,
                           progress_callback=None, cancel_check=None) -> bool:
        """Pull a remote file or folder with percentage progress."""
        if not self.device_connected:
            return False
        try:
            if self.is_remote_dir(remote_path):
                return self.pull_dir_with_progress(
                    remote_path, local_path,
                    progress_callback=progress_callback, cancel_check=cancel_check,
                )
            return self.pull_file_with_progress(
                remote_path, local_path,
                progress_callback=progress_callback, cancel_check=cancel_check,
            )
        except Exception as e:
            self.logger.error(f"Error pulling with progress: {e}")
            self.last_error = str(e)
            return False

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            cmd = self._build_adb_cmd(['pull', remote_path, local_path])
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            self._active_process = process
            stdout, stderr = process.communicate()
            self._active_process = None
            return process.returncode == 0
        except Exception as e:
            self.logger.error(f"Error pulling file/folder: {e}")
            return False

    def _run_transfer_streaming(self, command, progress_callback=None, line_callback=None):
        if not self.device_connected:
            return False

        cmd = self._build_adb_cmd(command)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            self._active_process = process

            for raw_line in iter(process.stdout.readline, b''):
                line = raw_line.decode('utf-8', errors='replace').rstrip('\r\n')
                if line_callback:
                    line_callback(line)

            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.logger.error(f"Error during streaming transfer: {e}")
            return False

    def pull_file_streaming(self, remote_path, local_path, line_callback=None):
        return self._run_transfer_streaming(['pull', remote_path, local_path], line_callback=line_callback)

    def push_file_streaming(self, local_path, remote_path, line_callback=None):
        return self._run_transfer_streaming(['push', local_path, remote_path], line_callback=line_callback)

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
            cmd = f'rm -r {escaped_path}' if is_dir else f'rm {escaped_path}'
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
            cmd = self._build_adb_cmd(['push', local_path, remote_path])
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            self._active_process = process
            stdout, stderr = process.communicate()
            self._active_process = None
            return process.returncode == 0
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

    def path_exists(self, path: str) -> bool:
        if not self.device_connected:
            return False
        try:
            escaped_path = self._escape_path(path)
            result = self._run_adb_command(['shell', f'test -e {escaped_path} && echo "yes" || echo "no"'])
            return result.returncode == 0 and "yes" in (result.stdout or "")
        except Exception as e:
            self.logger.error(f"Error checking path existence: {e}")
            return False

    def install_apk(self, apk_path: str) -> bool:
        if not self.device_connected:
            raise ConnectionError("No ADB device connected")
        result = self._run_adb_command(["install", "-r", apk_path], timeout=120)
        output = (result.stdout or "") + (result.stderr or "")
        self.last_error = None if result.returncode == 0 else output.strip()
        return result.returncode == 0 and "Success" in output

    def install_xapk(self, xapk_path: str, callback=None) -> int:
        if not self.device_connected:
            raise ConnectionError("No ADB device connected")

        self.last_error = None
        try:
            with tempfile.TemporaryDirectory(prefix="xapk_") as tmp:
                with zipfile.ZipFile(xapk_path, 'r') as zf:
                    self._extract_zip_safely(zf, tmp)

                apks = self._find_files(tmp, ".apk")
                if not apks:
                    raise ValueError("No APK files found in XAPK archive")

                for apk in apks:
                    if callback:
                        callback(os.path.basename(apk))

                if len(apks) == 1:
                    command = ["install", "-r", apks[0]]
                else:
                    command = ["install-multiple", "-r", *apks]

                result = self._run_adb_command(command, timeout=max(300, 90 * len(apks)))
                output = (result.stdout or "") + (result.stderr or "")
                if result.returncode != 0 or "Success" not in output:
                    self.last_error = output.strip()
                    raise RuntimeError(self.last_error or "XAPK installation failed")

                self._install_xapk_obb_files(tmp, callback=callback)
                self.last_error = None
                return len(apks)
        except Exception as e:
            if not self.last_error:
                self.last_error = str(e)
            raise

    def _extract_zip_safely(self, zf: zipfile.ZipFile, target_dir: str):
        target_dir = os.path.abspath(target_dir)
        for member in zf.infolist():
            target_path = os.path.abspath(os.path.join(target_dir, member.filename))
            if target_path != target_dir and not target_path.startswith(target_dir + os.sep):
                raise ValueError(f"Unsafe path in archive: {member.filename}")
            zf.extract(member, target_dir)

    def _find_files(self, root: str, suffix: str):
        matches = []
        suffix = suffix.lower()
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for filename in files:
                if filename.lower().endswith(suffix):
                    matches.append(os.path.join(current, filename))
        return sorted(matches, key=lambda p: (os.path.basename(p).lower() != "base.apk", p.lower()))

    def _install_xapk_obb_files(self, extracted_dir: str, callback=None):
        obbs = self._find_files(extracted_dir, ".obb")
        if not obbs:
            return

        package_name = self._read_xapk_package_name(extracted_dir)
        if not package_name:
            self.logger.warning("XAPK contains OBB files but no package_name was found in manifest.json")
            return

        remote_dir = f"/sdcard/Android/obb/{package_name}"
        self.create_folder(remote_dir)
        for obb in obbs:
            if callback:
                callback(os.path.basename(obb))
            remote_path = f"{remote_dir}/{os.path.basename(obb)}"
            if not self.push_file(obb, remote_path):
                raise RuntimeError(f"Failed to push OBB file: {os.path.basename(obb)}")

    def _read_xapk_package_name(self, extracted_dir: str):
        manifest_path = os.path.join(extracted_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            return manifest.get("package_name") or manifest.get("package")
        except Exception as e:
            self.logger.warning(f"Could not read XAPK manifest: {e}")
            return None