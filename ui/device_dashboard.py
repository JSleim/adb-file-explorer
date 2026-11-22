import logging
import re

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from handler import ADBHandler
from operation_control import (
    OperationControl,
    clear_current_operation,
    set_current_operation,
)

_logger = logging.getLogger(__name__)

BATTERY_STATUS = {
    1: "Unknown",
    2: "Charging",
    3: "Discharging",
    4: "Not charging",
    5: "Full",
}

BATTERY_HEALTH = {
    1: "Unknown",
    2: "Good",
    3: "Overheat",
    4: "Dead",
    5: "Over voltage",
    6: "Failure",
    7: "Cold",
}


def _first_int(pattern, text):
    match = re.search(pattern, text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


class DeviceInfoWorker(QThread):
    info_ready = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, serial):
        super().__init__()
        self.serial = serial
        self._operation = OperationControl()

    def cancel(self):
        self._operation.cancel()

    def run(self):
        set_current_operation(self._operation)
        try:
            handler = ADBHandler(device_serial=self.serial)
            info = {
                "props": self._collect_props(handler),
                "battery": self._collect_battery(handler),
                "storage": self._collect_storage(handler),
                "memory": self._collect_memory(handler),
            }
            if not self._operation.cancelled:
                self.info_ready.emit(info)
        except Exception as error:
            if not self._operation.cancelled:
                _logger.exception("Device dashboard refresh failed")
                self.failed.emit(str(error))
        finally:
            clear_current_operation()

    def _call(self, handler, args, timeout=20):
        try:
            result = handler._run_adb_command(
                args, timeout=timeout, device_serial=handler.device_serial
            )
        except Exception as error:
            _logger.warning("Dashboard command failed: %s", error)
            return ""
        if result is None or result.returncode != 0:
            return ""
        return result.stdout or ""

    def _collect_props(self, handler):
        wanted = (
            "ro.product.model",
            "ro.product.device",
            "ro.serialno",
            "ro.build.version.release",
            "ro.build.version.sdk",
            "ro.product.cpu.abi",
            "ro.build.version.security_patch",
        )
        output = self._call(handler, ["shell", "getprop"])
        props = {}
        for match in re.finditer(r"^\[(.+?)\]: \[(.*)\]$", output, re.MULTILINE):
            props[match.group(1)] = match.group(2)
        return {key: props.get(key, "") for key in wanted}

    def _collect_battery(self, handler):
        text = self._call(handler, ["shell", "dumpsys battery"])
        technology_match = re.search(r"technology:\s*(\S+)", text)
        return {
            "level": _first_int(r"level:\s*(\d+)", text),
            "status": _first_int(r"status:\s*(\d+)", text),
            "health": _first_int(r"health:\s*(\d+)", text),
            "temperature": _first_int(r"temperature:\s*(\d+)", text),
            "technology": technology_match.group(1) if technology_match else "",
        }

    def _collect_storage(self, handler):
        mounts = []
        for target in ("/data", "/storage/emulated/0"):
            output = self._call(handler, ["shell", "df", "-h", target])
            for line in output.splitlines():
                fields = line.strip().split()
                if len(fields) < 6 or fields[-1] != target:
                    continue
                mounts.append(
                    {
                        "mount": target,
                        "total": fields[-5],
                        "used": fields[-4],
                        "available": fields[-3],
                        "percent": fields[-2],
                    }
                )
        return mounts

    def _collect_memory(self, handler):
        text = self._call(handler, ["shell", "cat", "/proc/meminfo"])
        return {
            "total_kb": _first_int(r"MemTotal:\s+(\d+)", text),
            "available_kb": _first_int(r"MemAvailable:\s+(\d+)", text),
        }


class DeviceDashboardDialog(QDialog):
    def __init__(self, adb_handler, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Device Dashboard"))
        self.setObjectName("device_dashboard")
        self.resize(520, 520)
        self.serial = adb_handler.device_serial
        self._worker = None
        self._build_ui()
        # Covers accept/reject/Esc: closeEvent is not called for those.
        self.finished.connect(self._shutdown_worker)
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        system_group = QGroupBox(self.tr("System"))
        system_form = QFormLayout(system_group)
        self._labels = {}
        for key, title in (
            ("ro.product.model", "Model"),
            ("ro.product.device", "Device"),
            ("ro.serialno", "Serial"),
            ("ro.build.version.release", "Android"),
            ("ro.build.version.sdk", "API level"),
            ("ro.product.cpu.abi", "ABI"),
            ("ro.build.version.security_patch", "Security patch"),
        ):
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self._labels[key] = value_label
            system_form.addRow(self.tr(title) + ":", value_label)
        layout.addWidget(system_group)

        battery_group = QGroupBox(self.tr("Battery"))
        battery_layout = QVBoxLayout(battery_group)
        self.battery_bar = QProgressBar()
        self.battery_bar.setRange(0, 100)
        battery_layout.addWidget(self.battery_bar)
        self.battery_label = QLabel(self.tr("Refreshing..."))
        self.battery_label.setWordWrap(True)
        battery_layout.addWidget(self.battery_label)
        layout.addWidget(battery_group)

        storage_group = QGroupBox(self.tr("Storage"))
        self._storage_layout = QVBoxLayout(storage_group)
        layout.addWidget(storage_group)

        memory_group = QGroupBox(self.tr("Memory"))
        memory_layout = QVBoxLayout(memory_group)
        self.memory_bar = QProgressBar()
        self.memory_bar.setRange(0, 100)
        memory_layout.addWidget(self.memory_bar)
        self.memory_label = QLabel("-")
        memory_layout.addWidget(self.memory_label)
        layout.addWidget(memory_group)

        button_row = QHBoxLayout()
        self.refresh_btn = QPushButton(self.tr("Refresh"))
        self.refresh_btn.clicked.connect(self.refresh)
        button_row.addWidget(self.refresh_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

    def refresh(self):
        if self._worker is not None and self._worker.isRunning():
            return
        if not self.serial:
            self.battery_label.setText(self.tr("No device selected."))
            return
        self.refresh_btn.setEnabled(False)
        self.battery_label.setText(self.tr("Refreshing..."))
        self._worker = DeviceInfoWorker(self.serial)
        self._worker.info_ready.connect(self._on_info)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_info(self, info):
        self.refresh_btn.setEnabled(True)
        props = info.get("props") or {}

        for key in self._labels:
            value = props.get(key) or "-"
            self._labels[key].setText(value)

        battery = info.get("battery") or {}
        level = battery.get("level")
        if isinstance(level, int):
            self.battery_bar.setValue(max(0, min(100, level)))
        temperature = battery.get("temperature")
        temperature_text = (
            self.tr("{0:.1f} °C").format(temperature / 10.0)
            if isinstance(temperature, int)
            else "-"
        )
        status = BATTERY_STATUS.get(battery.get("status"), "-")
        health = BATTERY_HEALTH.get(battery.get("health"), "-")
        self.battery_label.setText(
            self.tr("{0}% - {1}, {2}, {3}, {4}").format(
                level if isinstance(level, int) else "-",
                self.tr(status),
                temperature_text,
                self.tr(health),
                battery.get("technology") or "-",
            )
        )

        self._set_storage(info.get("storage") or [])

        memory = info.get("memory") or {}
        total_kb = memory.get("total_kb")
        available_kb = memory.get("available_kb")
        if isinstance(total_kb, int) and total_kb > 0:
            total_gb = total_kb / 1024 / 1024
            if isinstance(available_kb, int) and 0 <= available_kb <= total_kb:
                used_gb = (total_kb - available_kb) / 1024 / 1024
                percent = round(used_gb / total_gb * 100)
                self.memory_bar.setValue(percent)
                self.memory_label.setText(
                    self.tr("{0:.1f} GB used of {1:.1f} GB").format(used_gb, total_gb)
                )
            else:
                self.memory_bar.setValue(0)
                self.memory_label.setText(self.tr("{0:.1f} GB total").format(total_gb))
        else:
            self.memory_bar.setValue(0)
            self.memory_label.setText("-")

    def _set_storage(self, mounts):
        while self._storage_layout.count():
            item = self._storage_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not mounts:
            self._storage_layout.addWidget(QLabel(self.tr("No storage information.")))
            return
        for mount in mounts:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            mount_label = QLabel(mount.get("mount", "-"))
            mount_label.setMinimumWidth(190)
            bar = QProgressBar()
            bar.setRange(0, 100)
            percent_text = str(mount.get("percent", "")).rstrip("%")
            try:
                bar.setValue(max(0, min(100, int(percent_text))))
            except ValueError:
                pass
            detail_label = QLabel(
                self.tr("{0} used of {1} ({2} free)").format(
                    mount.get("used", "-"),
                    mount.get("total", "-"),
                    mount.get("available", "-"),
                )
            )
            row_layout.addWidget(mount_label)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(detail_label)
            self._storage_layout.addWidget(row)

    def _on_failed(self, error):
        self.refresh_btn.setEnabled(True)
        self.battery_label.setText(self.tr("Failed to collect info: {0}").format(error))

    def _shutdown_worker(self):
        if self._worker is None:
            return
        self._worker.cancel()
        self._worker.wait(3000)
        if self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(1000)
        self._worker = None

    def closeEvent(self, event):
        self._shutdown_worker()
        super().closeEvent(event)
