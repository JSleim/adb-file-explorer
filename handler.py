_S = "Success"
_R = "install"
_Q = "process"
_P = "replace"
_O = "devices"
_N = "exec-out"
_M = "pull"
_L = "utf-8"
_K = "ADB command failed"
_J = "-c"
_I = "-s"
_H = "su"
_G = "adb"
_F = "No ADB device connected"
_E = "shell"
_D = True
_C = "/"
_B = None
_A = False
import json, os, re, shutil, socket, struct, subprocess, tempfile, time, zipfile
from dataclasses import dataclass
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
    _WIN_FLAGS: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def __init__(self, device_serial=_B):
        import logging

        self.logger = logging.getLogger("ADBHandler")
        self._ensure_server_started()
        self.device_serial = device_serial
        self.devices = self.get_connected_devices()
        self.device_connected = bool(self.devices)
        self.root_mode = _B
        self.last_error = _B
        if not self.device_connected:
            self.logger.warning(_F)
        elif not device_serial and len(self.devices) == 1:
            self.device_serial = next(iter(self.devices.keys()))

    def _build_adb_cmd(self, command, device_serial=_B):
        cmd = [_G]
        serial = device_serial or self.device_serial
        if serial:
            cmd.extend([_I, serial])
        cmd.extend(command)
        return cmd

    @staticmethod
    def _make_startupinfo():
        startupinfo = _B
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo

    @staticmethod
    def _shell_quote(path):
        return "'" + path.replace("'", "'\\''") + "'"

    def _remote_path_exists(self, path, device_serial=_B, use_root=_A):
        A = "Could not check remote destination %s: %s"
        quoted_path = self._shell_quote(path)
        stat_command = f"stat -c '%s %Y' {quoted_path}"
        command = (
            [_E, _H, _J, stat_command]
            if use_root and self.root_mode == _H
            else [_E, stat_command]
        )
        try:
            result = self._run_adb_command(
                command, timeout=10, device_serial=device_serial
            )
        except Exception as error:
            self.logger.error(A, path, error)
            self.last_error = str(error)
            return
        if result.returncode != 0:
            error = (result.stderr or result.stdout or "").strip()
            if "no such file or directory" in error.lower():
                self.last_error = _B
                return _A
            self.logger.error(A, path, error or _K)
            self.last_error = error or _K
            return
        fields = (result.stdout or "").split()
        if len(fields) == 2 and fields[0].isdigit():
            try:
                int(fields[1])
            except ValueError:
                0
            else:
                self.last_error = _B
                return _D
        self.logger.error("Unexpected result checking remote destination %s", path)
        self.last_error = "Unexpected output checking remote path"

    def _remove_remote_partial(self, path, device_serial=_B):
        normalized_path = path.rstrip(_C)
        if normalized_path in {"", _C}:
            self.logger.error("Refusing to remove unsafe partial destination %r", path)
            return
        command = f"rm -rf {self._shell_quote(normalized_path)}"
        try:
            result = subprocess.run(
                self._build_adb_cmd([_E, command], device_serial=device_serial),
                capture_output=_D,
                text=_D,
                timeout=15,
                check=_A,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            if result.returncode != 0:
                self.logger.error(
                    "Could not remove partial remote destination %s: %s",
                    normalized_path,
                    (result.stderr or "").strip() or _K,
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
                        _E,
                        f"mv {self._shell_quote(source)} {self._shell_quote(destination)}",
                    ]
                ),
                capture_output=_D,
                text=_D,
                timeout=15,
                check=_A,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            if result.returncode == 0:
                return _D
            self.logger.error(
                "Could not restore remote destination %s: %s",
                destination,
                (result.stderr or "").strip() or _K,
            )
        except Exception:
            self.logger.exception(
                "Could not restore remote destination %s", destination
            )
        return _A

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
                [_G, _I, serial, _N, "mkdir", "-p", remote_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
        except (subprocess.SubprocessError, OSError):
            0

    def _ensure_server_started(self):
        try:
            subprocess.run(
                [_G, "start-server"],
                capture_output=_D,
                timeout=15,
                check=_A,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
        except (subprocess.SubprocessError, OSError):
            0

    def get_connected_devices(self):
        try:
            result = self._run_adb_command([_O, "-l"])
            if result.returncode != 0:
                self.logger.error(f"Error getting devices: {result.stderr}")
                return {}
            devices = {}
            for line in result.stdout.splitlines():
                if "device " in line and _O not in line:
                    parts = line.split()
                    serial = parts[0]
                    model = next(
                        (p.split(":")[1] for p in parts[1:] if p.startswith("model:")),
                        "Unknown",
                    )
                    devices[serial] = model
            return devices
        except Exception as e:
            self.logger.error(f"Error listing devices: {e}")
            return {}

    def get_device_identity(self, serial):
        "Return the physical device serial reported by a specific ADB endpoint."
        try:
            result = subprocess.run(
                [_G, _I, serial, "get-serialno"],
                capture_output=_D,
                text=_D,
                timeout=10,
                check=_A,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            identity = result.stdout.strip()
            if result.returncode == 0 and identity and identity != "unknown":
                return identity
        except Exception:
            0
        return serial

    def get_unique_devices(self):
        "Return one preferred ADB endpoint per physical device, preferring USB."
        unique = {}
        for serial, model in self.get_connected_devices().items():
            identity = self.get_device_identity(serial)
            candidate = serial, model
            current = unique.get(identity)
            if current is _B or self._endpoint_priority(
                serial
            ) < self._endpoint_priority(current[0]):
                unique[identity] = candidate
        return {serial: model for (serial, model) in unique.values()}

    @staticmethod
    def _endpoint_priority(serial):
        return ":" in serial, serial

    def check_adb_connection(self):
        try:
            result = self._run_adb_command([_O])
            self.logger.debug(f"ADB Devices output: {result.stdout.strip()}")
            if result.returncode != 0:
                self.logger.error(
                    f"ADB connection check failed: {result.stderr.strip()}"
                )
                return _A
            for line in result.stdout.splitlines():
                fields = line.split()
                if len(fields) < 2 or fields[1] != "device":
                    continue
                if self.device_serial is _B or fields[0] == self.device_serial:
                    return _D
            return _A
        except FileNotFoundError:
            self.logger.error(
                "ADB command not found. Please ensure ADB is installed and in PATH"
            )
            return _A
        except Exception as e:
            self.logger.error(f"ADB Connection error: {e}")
            return _A

    def _escape_path(self, path):
        path = path.replace('"', '\\"').replace("'", "\\'")
        return f'"{path}"'

    def _run_adb_command(self, command, use_shell=_A, timeout=30, device_serial=_B):
        cmd = [_G]
        serial = device_serial or self.device_serial
        if serial:
            cmd.extend([_I, serial])
        cmd.extend(command)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=_D,
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
            return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {" ".join(cmd)}")
            raise

    def _adb_push_sync(self, dst_serial, dst_path, data_iter, cancel_check=_B):
        C = b"OKAY"
        B = "ADB disconnected"
        A = "<I"
        sock = _B
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            register_socket(sock)
            sock.settimeout(30)
            sock.connect(("127.0.0.1", 5037))

            def sexact(d):
                t = 0
                while t < len(d):
                    n = sock.send(d[t:])
                    if n == 0:
                        raise ConnectionError(B)
                    t += n

            def rexact(n):
                buf = b""
                while len(buf) < n:
                    c = sock.recv(n - len(buf))
                    if not c:
                        raise ConnectionError(B)
                    buf += c
                return buf

            def adb_cmd(c):
                sexact(b"%04x" % len(c) + c)
                r = rexact(4)
                if r != C:
                    raise RuntimeError(f"ADB cmd failed: {r!r}")

            adb_cmd(b"host:transport:" + dst_serial.encode())
            adb_cmd(b"sync:")
            sock.settimeout(_B)
            path_b = dst_path.rstrip(_C).encode()
            mode_str = b"644"
            send_data = path_b + b"," + mode_str
            while len(send_data) % 4 != 0:
                send_data += b"\x00"
            sexact(b"SEND" + struct.pack(A, len(send_data)) + send_data)
            for chunk in data_iter:
                if is_cancelled() or cancel_check and cancel_check():
                    return _A, "cancelled"
                sexact(b"DATA" + struct.pack(A, len(chunk)) + chunk)
            sexact(b"DONE" + struct.pack(A, int(time.time())))
            resp = rexact(4)
            if resp == C:
                return _D, ""
            elif resp == b"FAIL":
                elen = struct.unpack(A, rexact(4))[0]
                return _A, rexact(elen).decode(_L, errors=_P)
            else:
                return _A, f"unexpected sync response: {resp!r}"
        except Exception as e:
            return _A, str(e)
        finally:
            if sock:
                unregister_socket(sock)
                try:
                    sock.close()
                except Exception:
                    0

    def stream_file(
        self,
        src_serial,
        src_path,
        dst_serial,
        dst_path,
        chunk_callback=_B,
        cancel_check=_B,
    ):
        destination_existed = self._remote_path_exists(dst_path, dst_serial)
        transfer_succeeded = _A
        si_dir = _C.join(dst_path.rstrip(_C).split(_C)[:-1])
        if si_dir:
            ADBHandler._exec_mkdir(dst_serial, si_dir)
        src_proc = _B
        try:
            src_proc = subprocess.Popen(
                [_G, _I, src_serial, _N, "cat", src_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._make_startupinfo(),
                creationflags=self._WIN_FLAGS,
            )
            register_process(src_proc)

            def data_iter():
                buf = 262144
                while _D:
                    if is_cancelled() or cancel_check and cancel_check():
                        return
                    chunk = src_proc.stdout.read(buf)
                    if not chunk:
                        break
                    if chunk_callback:
                        chunk_callback(len(chunk))
                    yield chunk

            ok, err = self._adb_push_sync(
                dst_serial, dst_path, data_iter(), cancel_check=cancel_check
            )
            src_proc.wait()
            src_err = (src_proc.stderr.read() or b"").decode(_L, errors=_P).strip()
            if src_err:
                self.logger.error(f"Stream src stderr: {src_err[:300]}")
            unregister_process(src_proc)
            if not ok:
                self.logger.error(f"Stream push failed: {err}")
                self.last_error = err
                return _A
            if src_proc.returncode != 0:
                self.last_error = f"source cat exited {src_proc.returncode}"
                return _A
            transfer_succeeded = _D
            return _D
        except Exception as e:
            self.logger.error(f"Stream file error: {e}")
            self.last_error = str(e)
            return _A
        finally:
            if src_proc:
                unregister_process(src_proc)
                if src_proc.returncode is _B:
                    try:
                        src_proc.kill()
                    except Exception:
                        0
            if is_cancelled() and not transfer_succeeded and destination_existed is _A:
                self._remove_remote_partial(dst_path, dst_serial)

    def stream_directory(
        self,
        src_serial,
        src_path,
        dst_serial,
        dst_path,
        line_callback=_B,
        cancel_check=_B,
    ):
        parent = _C.join(dst_path.rstrip(_C).split(_C)[:-1])
        base_name = src_path.rstrip(_C).split(_C)[-1]
        target = f"{parent}/{base_name}" if parent else base_name
        ADBHandler._exec_mkdir(dst_serial, parent)
        try:
            r = self._run_adb_command(
                [_N, "find", src_path, "-type", "f"],
                timeout=30,
                device_serial=src_serial,
            )
            if r.returncode != 0:
                return _A
            files = [path for path in r.stdout.splitlines() if path.strip()]
            if not files:
                return _D
            for fpath in files:
                if is_cancelled() or cancel_check and cancel_check():
                    return _A
                rel = fpath[len(src_path.rstrip(_C)) :].lstrip(_C)
                dest = f"{target}/{rel}" if rel else target
                si_dir = _C.join(dest.rstrip(_C).split(_C)[:-1])
                ADBHandler._exec_mkdir(dst_serial, si_dir)
                if line_callback:
                    line_callback(f"Streaming {fpath}")
                ok = self.stream_file(
                    src_serial, fpath, dst_serial, dest, cancel_check=cancel_check
                )
                if not ok:
                    return _A
            return _D
        except Exception as e:
            self.logger.error(f"Directory streaming error: {e}")
            return _A

    def enable_root(self):
        self.last_error = _B
        try:
            result = self._run_adb_command(["root"])
            out = (result.stdout or "") + (result.stderr or "")
            if (
                "restarting adbd as root" in out
                or "adbd is already running as root" in out
            ):
                time.sleep(1)
                self.root_mode = _G
                return _D
            if "cannot run as root" not in out:
                if result.returncode == 0:
                    time.sleep(1)
                    self.root_mode = _G
                    return _D
        except Exception:
            0
        try:
            result = self._run_adb_command([_E, _H, _J, "id"])
            if result.returncode == 0 and "uid=0" in (result.stdout or ""):
                self.root_mode = _H
                return _D
            self.last_error = (result.stderr or result.stdout or "").strip()
        except Exception as e:
            self.last_error = str(e)
        self.root_mode = _B
        return _A

    def list_directory(self, path, use_root=_A):
        if not self.device_connected:
            self.logger.error(_F)
            self.last_error = _F
            return []
        try:
            self.logger.debug(f"Listing directory: {path}")
            escaped_path = self._escape_path(path)
            if use_root and self.root_mode == _H:
                result = self._run_adb_command(
                    [_E, _H, _J, f'ls -la {escaped_path} 2>/dev/null || echo "error"']
                )
            else:
                result = self._run_adb_command(
                    [_E, f'ls -la {escaped_path} 2>/dev/null || echo "error"']
                )
            stdout = (result.stdout or "").strip()
            if (
                result.returncode != 0
                or stdout == "error"
                or stdout.startswith("error\n")
            ):
                self.logger.error(f"ADB Error: {result.stderr or result.stdout}")
                self.last_error = (result.stderr or result.stdout or "").strip()
                return
            items = []
            lines = result.stdout.split("\n")
            pattern = re.compile(
                "^([\\-dlcbpsrwxStT]+)\\s+\\d+\\s+\\S+\\s+\\S+\\s+(\\d+)\\s+(\\d{4}-\\d{2}-\\d{2})\\s+(\\d{2}:\\d{2})\\s+(.+)$"
            )
            for line in lines:
                self.logger.debug(f"Raw line: '{line}'")
                line = line.strip()
                if not line or line.startswith("total"):
                    continue
                match = pattern.match(line)
                if not match:
                    self.logger.debug(f"Skipping line (no regex match): '{line}'")
                    continue
                perms = match.group(1)
                size = match.group(2)
                date = f"{match.group(3)} {match.group(4)}"
                name = match.group(5).replace("\\ ", " ")
                if name in [".", ".."]:
                    continue
                self.logger.debug(
                    f"Parsed: perms={perms}, size={size}, date={date}, name={name}"
                )
                items.append(
                    FileItem(
                        name=name,
                        path=f"{path.rstrip(_C)}/{name}",
                        is_dir=perms.startswith("d"),
                        size=int(size),
                        permissions=perms,
                        date_modified=date,
                    )
                )
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

    def pull_file(self, remote_path, local_path):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        destination_existed = os.path.lexists(local_path)
        transfer_succeeded = _A
        try:
            cmd = self._build_adb_cmd([_M, remote_path, local_path])
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
            return _A
        finally:
            if _Q in locals():
                unregister_process(process)
                if process.poll() is _B:
                    process.kill()
                process.wait()
            if is_cancelled() and not transfer_succeeded and not destination_existed:
                self._remove_local_partial(local_path)

    def _run_transfer_streaming(self, command, progress_callback=_B, line_callback=_B):
        if not self.device_connected:
            return _A
        destination = command[2]
        destination_existed = (
            os.path.lexists(destination)
            if command[0] == _M
            else self._remote_path_exists(destination)
        )
        transfer_succeeded = _A
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
            for raw_line in iter(process.stdout.readline, b""):
                if is_cancelled():
                    process.kill()
                    return _A
                line = raw_line.decode(_L, errors=_P).rstrip("\r\n")
                if line_callback:
                    line_callback(line)
            process.wait()
            transfer_succeeded = process.returncode == 0
            return transfer_succeeded
        except Exception as e:
            self.logger.error(f"Error during streaming transfer: {e}")
            return _A
        finally:
            if _Q in locals():
                unregister_process(process)
                if process.poll() is _B:
                    process.kill()
                process.wait()
            if is_cancelled() and not transfer_succeeded and destination_existed is _A:
                if command[0] == _M:
                    self._remove_local_partial(destination)
                else:
                    self._remove_remote_partial(destination)

    def pull_file_streaming(self, remote_path, local_path, line_callback=_B):
        return self._run_transfer_streaming(
            [_M, remote_path, local_path], line_callback=line_callback
        )

    def push_file_streaming(self, local_path, remote_path, line_callback=_B):
        return self._run_transfer_streaming(
            ["push", local_path, remote_path], line_callback=line_callback
        )

    def rename_item(self, old_path, new_path, use_root=_A):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        try:
            escaped_old = self._escape_path(old_path)
            escaped_new = self._escape_path(new_path)
            rename_command = (
                f"mv -n {escaped_old} {escaped_new} && test ! -e {escaped_old}"
            )
            command = (
                [_E, _H, _J, rename_command]
                if use_root and self.root_mode == _H
                else [_E, rename_command]
            )
            result = self._run_adb_command(command)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout renaming: {old_path}")
            return _A
        except Exception as e:
            self.logger.error(f"Error renaming: {e}")
            return _A

    def delete_item(self, path, is_dir=_A):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        try:
            escaped_path = self._escape_path(path)
            cmd = f"rm -r {escaped_path}" if is_dir else f"rm {escaped_path}"
            result = self._run_adb_command([_E, cmd])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout deleting: {path}")
            return _A
        except Exception as e:
            self.logger.error(f"Error deleting: {e}")
            return _A

    def create_file(self, remote_path):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command([_E, f"touch {escaped_path}"])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout creating file: {remote_path}")
            return _A
        except Exception as e:
            self.logger.error(f"Error creating file: {e}")
            return _A

    def create_folder(self, remote_path):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        try:
            escaped_path = self._escape_path(remote_path)
            result = self._run_adb_command([_E, f"mkdir -p {escaped_path}"])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout creating folder: {remote_path}")
            return _A
        except Exception as e:
            self.logger.error(f"Error creating folder: {e}")
            return _A

    def push_file(self, local_path, remote_path):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        destination_existed = self._remote_path_exists(remote_path)
        transfer_succeeded = _A
        try:
            cmd = self._build_adb_cmd(["push", local_path, remote_path])
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
            return _A
        finally:
            if _Q in locals():
                unregister_process(process)
                if process.poll() is _B:
                    process.kill()
                process.wait()
            if is_cancelled() and not transfer_succeeded and destination_existed is _A:
                self._remove_remote_partial(remote_path)

    def copy_on_device(self, src_path, dest_path):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        destination_existed = self._remote_path_exists(dest_path)
        transfer_succeeded = _A
        try:
            escaped_src = self._escape_path(src_path)
            escaped_dest = self._escape_path(dest_path)
            parent_dir = _C.join(dest_path.split(_C)[:-1])
            if parent_dir:
                self.create_folder(parent_dir)
            result = self._run_adb_command([_E, f"cp -r {escaped_src} {escaped_dest}"])
            transfer_succeeded = result.returncode == 0
            return transfer_succeeded
        except subprocess.TimeoutExpired:
            print(f"Timeout copying: {src_path} to {dest_path}")
            return _A
        except Exception as e:
            print(f"Error copying: {e}")
            return _A
        finally:
            if is_cancelled() and not transfer_succeeded and destination_existed is _A:
                self._remove_remote_partial(dest_path)

    def move_on_device(self, src_path, dest_path):
        if not self.device_connected:
            self.logger.error(_F)
            return _A
        try:
            escaped_src = self._escape_path(src_path)
            escaped_dest = self._escape_path(dest_path)
            parent_dir = _C.join(dest_path.split(_C)[:-1])
            if parent_dir:
                self.create_folder(parent_dir)
            result = self._run_adb_command([_E, f"mv {escaped_src} {escaped_dest}"])
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"Timeout moving: {src_path} to {dest_path}")
            return _A
        except Exception as e:
            print(f"Error moving: {e}")
            return _A

    def path_exists(self, path):
        if not self.device_connected:
            return _A
        try:
            escaped_path = self._escape_path(path)
            result = self._run_adb_command(
                [_E, f'test -e {escaped_path} && echo "yes" || echo "no"']
            )
            return result.returncode == 0 and "yes" in (result.stdout or "")
        except Exception as e:
            self.logger.error(f"Error checking path existence: {e}")
            return _A

    def install_apk(self, apk_path):
        if not self.device_connected:
            raise ConnectionError(_F)
        result = self._run_adb_command([_R, "-r", apk_path], timeout=120)
        output = (result.stdout or "") + (result.stderr or "")
        self.last_error = _B if result.returncode == 0 else output.strip()
        return result.returncode == 0 and _S in output

    def install_xapk(self, xapk_path, callback=_B):
        if not self.device_connected:
            raise ConnectionError(_F)
        self.last_error = _B
        try:
            with tempfile.TemporaryDirectory(prefix="xapk_") as tmp:
                with zipfile.ZipFile(xapk_path, "r") as zf:
                    self._extract_zip_safely(zf, tmp)
                apks = self._find_files(tmp, ".apk")
                if not apks:
                    raise ValueError("No APK files found in XAPK archive")
                for apk in apks:
                    if callback:
                        callback(os.path.basename(apk))
                if len(apks) == 1:
                    command = [_R, "-r", apks[0]]
                else:
                    command = ["install-multiple", "-r", *apks]
                result = self._run_adb_command(
                    command, timeout=max(300, 90 * len(apks))
                )
                output = (result.stdout or "") + (result.stderr or "")
                if result.returncode != 0 or _S not in output:
                    self.last_error = output.strip()
                    raise RuntimeError(self.last_error or "XAPK installation failed")
                self._install_xapk_obb_files(tmp, callback=callback)
                self.last_error = _B
                return len(apks)
        except Exception as e:
            if not self.last_error:
                self.last_error = str(e)
            raise

    def _extract_zip_safely(self, zf, target_dir):
        target_dir = os.path.abspath(target_dir)
        for member in zf.infolist():
            target_path = os.path.abspath(os.path.join(target_dir, member.filename))
            if target_path != target_dir and not target_path.startswith(
                target_dir + os.sep
            ):
                raise ValueError(f"Unsafe path in archive: {member.filename}")
            zf.extract(member, target_dir)

    def _find_files(self, root, suffix):
        matches = []
        suffix = suffix.lower()
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for filename in files:
                if filename.lower().endswith(suffix):
                    matches.append(os.path.join(current, filename))
        return sorted(
            matches,
            key=lambda p: (os.path.basename(p).lower() != "base.apk", p.lower()),
        )

    def _install_xapk_obb_files(self, extracted_dir, callback=_B):
        obbs = self._find_files(extracted_dir, ".obb")
        if not obbs:
            return
        package_name = self._read_xapk_package_name(extracted_dir)
        if not package_name:
            self.logger.warning(
                "XAPK contains OBB files but no package_name was found in manifest.json"
            )
            return
        remote_dir = f"/sdcard/Android/obb/{package_name}"
        self.create_folder(remote_dir)
        for obb in obbs:
            if callback:
                callback(os.path.basename(obb))
            remote_path = f"{remote_dir}/{os.path.basename(obb)}"
            if not self.push_file(obb, remote_path):
                raise RuntimeError(f"Failed to push OBB file: {os.path.basename(obb)}")

    def _read_xapk_package_name(self, extracted_dir):
        manifest_path = os.path.join(extracted_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return
        try:
            with open(manifest_path, encoding=_L) as f:
                manifest = json.load(f)
            return manifest.get("package_name") or manifest.get("package")
        except Exception as e:
            self.logger.warning(f"Could not read XAPK manifest: {e}")
            return
