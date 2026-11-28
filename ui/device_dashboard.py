import logging
import re

from PyQt6.QtCore import QT_TRANSLATE_NOOP, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
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
    1: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Unknown"),
    2: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Charging"),
    3: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Discharging"),
    4: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Not charging"),
    5: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Full"),
}

BATTERY_HEALTH = {
    1: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Unknown"),
    2: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Good"),
    3: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Overheat"),
    4: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Dead"),
    5: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Over voltage"),
    6: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Failure"),
    7: QT_TRANSLATE_NOOP("DeviceDashboardDialog", "Cold"),
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
        output = self._call(handler, ["shell", "df", "-h"])
        if not output:
            output = self._call(handler, ["shell", "df"])

        normalized_lines = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) == 1 and normalized_lines:
                normalized_lines.append(line)
            elif (
                normalized_lines
                and len(normalized_lines[-1].split()) == 1
                and len(parts) >= 5
            ):
                normalized_lines[-1] = f"{normalized_lines[-1]} {line}"
            else:
                normalized_lines.append(line)

        mounts = []
        seen_mounts = set()
        targets = ("/data", "/storage/emulated/0", "/storage/emulated", "/sdcard")

        for line in normalized_lines:
            fields = line.split()
            if len(fields) < 6:
                continue
            mount_point = fields[-1]
            percent_str = fields[-2]

            if mount_point not in targets or not percent_str.endswith("%"):
                continue
            if mount_point in seen_mounts:
                continue

            try:
                percent = int(percent_str.rstrip("%"))
            except ValueError:
                continue

            seen_mounts.add(mount_point)
            mounts.append(
                {
                    "mount": mount_point,
                    "total": fields[-5],
                    "used": fields[-4],
                    "available": fields[-3],
                    "percent": percent,
                }
            )
        return mounts

    def _collect_memory(self, handler):
        text = self._call(handler, ["shell", "cat", "/proc/meminfo"])
        return {
            "total_kb": _first_int(r"MemTotal:\s+(\d+)", text),
            "available_kb": _first_int(r"MemAvailable:\s+(\d+)", text),
        }


class DeviceDashboardDialog(QWidget):
    def __init__(self, adb_handler=None, parent=None):
        super().__init__(parent)
        self.setObjectName("device_dashboard")
        self.serial = adb_handler.device_serial if adb_handler else None
        self._worker = None
        self._build_ui()
        if self.serial:
            self.refresh()
        else:
            self.battery_label.setText(self.tr("No device selected."))

    def set_device(self, adb_handler):
        new_serial = adb_handler.device_serial if adb_handler else None
        if new_serial == self.serial:
            return
        self._shutdown_worker()
        self.serial = new_serial
        self.refresh_btn.setEnabled(True)
        if self.serial:
            self.refresh()
        else:
            for lbl in self._labels.values():
                lbl.setText("-")
            self.battery_bar.setValue(0)
            self.battery_label.setText(self.tr("No device selected."))
            self._set_storage([])
            self.memory_bar.setValue(0)
            self.memory_label.setText("-")

    def _build_ui(self):
        layout = QVBoxLayout(self)

        system_group = QGroupBox(self.tr("System"))
        system_form = QFormLayout(system_group)
        system_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
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
            value_label.setWordWrap(True)
            value_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
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
        self.memory_label.setWordWrap(True)
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
            self._storage_layout.addWidget(self._make_storage_row(mount))
        if (
            len(mounts) == 2
            and mounts[0].get("total") == mounts[1].get("total")
            and mounts[0].get("used") == mounts[1].get("used")
        ):
            note = QLabel(self.tr("Both paths share the same partition."))
            note.setWordWrap(True)
            note.setObjectName("storage_note")
            self._storage_layout.addWidget(note)

    def _make_storage_row(self, mount):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        mount_label = QLabel(mount.get("mount", "-"))
        mount_label.setWordWrap(True)
        mount_label.setObjectName("storage_mount_name")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        percent = mount.get("percent")
        if isinstance(percent, (int, float)):
            bar.setValue(max(0, min(100, int(percent))))
        else:
            try:
                bar.setValue(max(0, min(100, int(str(percent).rstrip("%")))))
            except (ValueError, TypeError):
                pass
        detail_label = QLabel(
            self.tr("{0} used of {1} ({2} free)").format(
                mount.get("used", "-"),
                mount.get("total", "-"),
                mount.get("available", "-"),
            )
        )
        detail_label.setWordWrap(True)
        detail_label.setObjectName("storage_detail")
        row_layout.addWidget(mount_label)
        row_layout.addWidget(bar)
        row_layout.addWidget(detail_label, 1)
        return row

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
