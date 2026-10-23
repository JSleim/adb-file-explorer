import subprocess
import socket
import struct
from dataclasses import dataclass
from typing import List
import re
import time
import zipfile
import os
import shutil
import tempfile
import json
from operation_control import (
    is_cancelled,
    register_process,
    register_socket,
    unregister_process,
    unregister_socket,
)

@dataclass
class FileItem:
    name: str
    path: str
    is_dir: bool
    size: int
    permissions: str
    date_modified: str

class ADBHandler:
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
    def _shell_quote(path):
        return "'" + path.replace("'", "'\\''") + "'"

    def _remote_path_exists(self, path, device_serial=None, use_root=False):
        quoted_path = self._shell_quote(path)
        stat_command = f"stat -c '%s %Y' {quoted_path}"
        command = (
            ['shell', 'su', '-c', stat_command]
            if use_root and self.root_mode == "su"
            else ['shell', stat_command]
        )
        try:
            result = self._run_adb_command(
                command,
                timeout=10,
                device_serial=device_serial,
            )
        except Exception as error:
            self.logger.error("Could not check remote destination %s: %s", path, error)
            self.last_error = str(error)
            return None
        if result.returncode != 0:
            error = (result.stderr or result.stdout or "").strip()
            if "no such file or directory" in error.lower():
                self.last_error = None
                return False
            self.logger.error(
                "Could not check remote destination %s: %s",
                path,
                error or "ADB command failed",
            )
            self.last_error = error or "ADB command failed"
            return None
        fields = (result.stdout or "").split()
        if len(fields) == 2 and fields[0].isdigit():
            try:
                int(fields[1])
            except ValueError:
                pass
            else:
                self.last_error = None
                return True
        self.logger.error("Unexpected result checking remote destination %s", path)
        self.last_error = "Unexpected output checking remote path"
        return None

    def _remove_remote_partial(self, path, device_serial=None):
        normalized_path = path.rstrip("/")
        if normalized_path in {"", "/"}:
            self.logger.error("Refusing to remove unsafe partial destination %r", path)
            return
        command = f'rm -rf {self._shell_quote(normalized_path)}'
        try:
            result = subprocess.run(
                self._build_adb_cmd(
                    ['shell', command], device_serial=device_serial
                ),
                capture_output=True,
                text=True,
                timeout=15,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            if result.returncode != 0:
                self.logger.error(
                    "Could not remove partial remote destination %s: %s",
                    normalized_path,
                    (result.stderr or "").strip() or "ADB command failed",
                )
        except Exception:
            self.logger.exception(
                "Could not remove partial remote destination %s", normalized_path
            )

    def _move_remote_path_for_recovery(self, source, destination):
        try:
            result = subprocess.run(
                self._build_adb_cmd(
                    [
                        'shell',
                        f'mv {self._shell_quote(source)} '
                        f'{self._shell_quote(destination)}',
                    ]
                ),
                capture_output=True,
                text=True,
                timeout=15,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            if result.returncode == 0:
                return True
            self.logger.error(
                "Could not restore remote destination %s: %s",
                destination,
                (result.stderr or "").strip() or "ADB command failed",
            )
        except Exception:
            self.logger.exception(
                "Could not restore remote destination %s", destination
            )
        return False

    def _remove_local_partial(self, path):
        try:
            if os.path.islink(path) or not os.path.isdir(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
        except FileNotFoundError:
            return
        except Exception:
            self.logger.exception("Could not remove partial local destination %s", path)

    @staticmethod
    def _exec_mkdir(serial, remote_dir):
        try:
            process = subprocess.Popen(
                ['adb', '-s', serial, 'exec-out', 'mkdir', '-p', remote_dir],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=ADBHandler._make_startupinfo(),
                creationflags=ADBHandler._WIN_FLAGS,
            )
            register_process(process)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            finally:
                unregister_process(process)
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
            self.logger.debug(f"ADB Devices output: {result.stdout.strip()}")
            if result.returncode != 0:
                self.logger.error(
                    f"ADB connection check failed: {result.stderr.strip()}"
                )
                return False

            for line in result.stdout.splitlines():
                fields = line.split()
                if len(fields) < 2 or fields[1] != "device":
                    continue
                if self.device_serial is None or fields[0] == self.device_serial:
                    return True
            return False
        except FileNotFoundError:
            self.logger.error("ADB command not found. Please ensure ADB is installed and in PATH")
            return False
        except Exception as e:
            self.logger.error(f"ADB Connection error: {e}")
            return False

    def _escape_path(self, path: str) -> str:
        path = path.replace('"', '\\"').replace("'", "\\'")
        return f'"{path}"'

    def _run_adb_command(
        self, command: list, use_shell=False, timeout=30, device_serial=None
    ) -> subprocess.CompletedProcess:
        cmd = ['adb']
        serial = device_serial or self.device_serial
        if serial:
            cmd.extend(['-s', serial])
        cmd.extend(command)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            register_process(process)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(
                    cmd, timeout, output=stdout, stderr=stderr
                )
            finally:
                unregister_process(process)
            return subprocess.CompletedProcess(
                cmd, process.returncode, stdout, stderr
            )
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {' '.join(cmd)}")
            raise

    def _adb_push_sync(self, dst_serial, dst_path, data_iter, cancel_check=None):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            register_socket(sock)
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
                if is_cancelled() or (cancel_check and cancel_check()):
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
                unregister_socket(sock)
                try: sock.close()
                except Exception: pass

    def stream_file(self, src_serial: str, src_path: str, dst_serial: str, dst_path: str,
                    chunk_callback=None, cancel_check=None) -> bool:
        destination_existed = self._remote_path_exists(dst_path, dst_serial)
        transfer_succeeded = False
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
            register_process(src_proc)

            def data_iter():
                buf = 262144
                while True:
                    if is_cancelled() or (cancel_check and cancel_check()):
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

            unregister_process(src_proc)

            if not ok:
                self.logger.error(f"Stream push failed: {err}")
                self.last_error = err
                return False
            if src_proc.returncode != 0:
                self.last_error = f"source cat exited {src_proc.returncode}"
                return False
            transfer_succeeded = True
            return True

        except Exception as e:
            self.logger.error(f"Stream file error: {e}")
            self.last_error = str(e)
            return False
        finally:
            if src_proc:
                unregister_process(src_proc)
                if src_proc.returncode is None:
                    try: src_proc.kill()
                    except Exception: pass
            if (
                is_cancelled()
                and not transfer_succeeded
                and destination_existed is False
            ):
                self._remove_remote_partial(dst_path, dst_serial)

    def stream_directory(self, src_serial: str, src_path: str, dst_serial: str, dst_path: str,
                         line_callback=None, cancel_check=None) -> bool:
        parent = '/'.join(dst_path.rstrip('/').split('/')[:-1])
        base_name = src_path.rstrip('/').split('/')[-1]
        target = f"{parent}/{base_name}" if parent else base_name
        ADBHandler._exec_mkdir(dst_serial, parent)

        try:
            r = self._run_adb_command(
                ['exec-out', 'find', src_path, '-type', 'f'],
                timeout=30,
                device_serial=src_serial,
            )
            if r.returncode != 0:
                return False
            files = [path for path in r.stdout.splitlines() if path.strip()]
            if not files:
                return True
            for fpath in files:
                if is_cancelled() or (cancel_check and cancel_check()):
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
            self.last_error = "No ADB device connected"
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
                name = match.group(5).replace('\\ ', ' ')
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
            self.last_error = f"Timeout listing directory: {path}"
            return []
        except Exception as e:
            self.logger.error(f"Error listing directory: {e}")
            self.last_error = str(e)
            return []

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        destination_existed = os.path.lexists(local_path)
        transfer_succeeded = False
        try:
            cmd = self._build_adb_cmd(['pull', remote_path, local_path])
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            register_process(process)
            stdout, stderr = process.communicate()
            transfer_succeeded = process.returncode == 0
            return transfer_succeeded
        except Exception as e:
            self.logger.error(f"Error pulling file/folder: {e}")
            return False
        finally:
            if 'process' in locals():
                unregister_process(process)
                if process.poll() is None:
                    process.kill()
                process.wait()
            if is_cancelled() and not transfer_succeeded and not destination_existed:
                self._remove_local_partial(local_path)

    def _run_transfer_streaming(self, command, progress_callback=None, line_callback=None):
        if not self.device_connected:
            return False

        destination = command[2]
        destination_existed = (
            os.path.lexists(destination)
            if command[0] == 'pull'
            else self._remote_path_exists(destination)
        )
        transfer_succeeded = False
        cmd = self._build_adb_cmd(command)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            register_process(process)

            for raw_line in iter(process.stdout.readline, b''):
                if is_cancelled():
                    process.kill()
                    return False
                line = raw_line.decode('utf-8', errors='replace').rstrip('\r\n')
                if line_callback:
                    line_callback(line)

            process.wait()
            transfer_succeeded = process.returncode == 0
            return transfer_succeeded
        except Exception as e:
            self.logger.error(f"Error during streaming transfer: {e}")
            return False
        finally:
            if 'process' in locals():
                unregister_process(process)
                if process.poll() is None:
                    process.kill()
                process.wait()
            if (
                is_cancelled()
                and not transfer_succeeded
                and destination_existed is False
            ):
                if command[0] == 'pull':
                    self._remove_local_partial(destination)
                else:
                    self._remove_remote_partial(destination)

    def pull_file_streaming(self, remote_path, local_path, line_callback=None):
        return self._run_transfer_streaming(
            ['pull', remote_path, local_path], line_callback=line_callback
        )

    def push_file_streaming(self, local_path, remote_path, line_callback=None):
        return self._run_transfer_streaming(
            ['push', local_path, remote_path], line_callback=line_callback
        )

    def rename_item(self, old_path: str, new_path: str, use_root: bool = False) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        try:
            escaped_old = self._escape_path(old_path)
            escaped_new = self._escape_path(new_path)
            rename_command = (
                f'mv -n {escaped_old} {escaped_new} && test ! -e {escaped_old}'
            )
            command = (
                ['shell', 'su', '-c', rename_command]
                if use_root and self.root_mode == "su"
                else ['shell', rename_command]
            )
            result = self._run_adb_command(command)
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

        destination_existed = self._remote_path_exists(remote_path)
        transfer_succeeded = False
        try:
            cmd = self._build_adb_cmd(['push', local_path, remote_path])
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            register_process(process)
            stdout, stderr = process.communicate()
            transfer_succeeded = process.returncode == 0
            return transfer_succeeded
        except Exception as e:
            self.logger.error(f"Error pushing file: {e}")
            return False
        finally:
            if 'process' in locals():
                unregister_process(process)
                if process.poll() is None:
                    process.kill()
                process.wait()
            if (
                is_cancelled()
                and not transfer_succeeded
                and destination_existed is False
            ):
                self._remove_remote_partial(remote_path)

    def copy_on_device(self, src_path: str, dest_path: str) -> bool:
        if not self.device_connected:
            self.logger.error("No ADB device connected")
            return False

        destination_existed = self._remote_path_exists(dest_path)
        transfer_succeeded = False
        try:
            escaped_src = self._escape_path(src_path)
            escaped_dest = self._escape_path(dest_path)

            parent_dir = '/'.join(dest_path.split('/')[:-1])
            if parent_dir:
                self.create_folder(parent_dir)

            result = self._run_adb_command(['shell', f'cp -r {escaped_src} {escaped_dest}'])
            transfer_succeeded = result.returncode == 0
            return transfer_succeeded
        except subprocess.TimeoutExpired:
            print(f"Timeout copying: {src_path} to {dest_path}")
            return False
        except Exception as e:
            print(f"Error copying: {e}")
            return False
        finally:
            if (
                is_cancelled()
                and not transfer_succeeded
                and destination_existed is False
            ):
                self._remove_remote_partial(dest_path)

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