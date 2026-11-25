import logging
import subprocess

from PyQt6.QtCore import QCoreApplication, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from handler import ADBHandler
from operation_control import (
    OperationControl,
    clear_current_operation,
    register_process,
    set_current_operation,
    unregister_process,
)

_logger = logging.getLogger(__name__)

SYSTEM_PREFIXES = ("/system", "/system_ext", "/vendor", "/apex", "/odm", "/product")

# tag, description, find expression (POSIX syntax, works in toybox find)
RULES = (
    ("W", "-type f -perm -0002"),
    ("D", "-type d -perm -0002 ! -perm -1000"),
    ("S", "-type f -perm -4000"),
)

RULE_LABELS = {
    "W": "World-writable file",
    "D": "World-writable directory without sticky bit",
    "S": "SUID binary",
}


class PermissionScanWorker(QThread):
    item_found = pyqtSignal(dict)
    scan_finished = pyqtSignal(int)

    MAX_ITEMS = 2000

    def __init__(self, serial, root_path, use_root, ignore_system):
        super().__init__()
        self.serial = serial
        self.root_path = root_path
        self.use_root = use_root
        self.ignore_system = ignore_system
        self._cancelled = False
        self._operation = OperationControl()

    def cancel(self):
        self._cancelled = True
        # Kills the running adb process instead of waiting for the next line.
        self._operation.cancel()

    def run(self):
        set_current_operation(self._operation)
        count = 0
        try:
            handler = ADBHandler(device_serial=self.serial)
            if self.use_root and handler.root_mode is None:
                try:
                    handler.enable_root()
                except Exception:
                    _logger.debug("Root is not available for permission scan")
            for tag, expr in RULES:
                if self._cancelled or count >= self.MAX_ITEMS:
                    break
                for path in self._scan_rule(handler, expr):
                    if self._cancelled or count >= self.MAX_ITEMS:
                        break
                    if self.ignore_system and path.startswith(SYSTEM_PREFIXES):
                        continue
                    count += 1
                    self.item_found.emit({"path": path, "tag": tag})
        except Exception:
            _logger.exception("Permission scan failed")
        finally:
            self.scan_finished.emit(count)
            clear_current_operation()

    def _scan_rule(self, handler, expr):
        shell_cmd = f"find {handler._shell_quote(self.root_path)} {expr} -print"
        if self.use_root and handler.root_mode == "su":
            cmd = handler._build_adb_cmd(
                ["shell", "su", "-c", shell_cmd], device_serial=self.serial
            )
        else:
            cmd = handler._build_adb_cmd(
                ["shell", shell_cmd], device_serial=self.serial
            )
        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            register_process(process)
            for line in process.stdout:
                if self._cancelled:
                    break
                path = line.rstrip("\n")
                if path:
                    yield path
        finally:
            if process is not None:
                unregister_process(process)
                if process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class PermissionLintDialog(QDialog):
    # Передает (serial_устройства, полный_путь, use_root, is_directory)
    item_selected = pyqtSignal(str, str, bool, bool)

    def _translation_source(self):
        # Вызывается никогда: существует только для pylupdate6.
        return (
            self.tr("World-writable file"),
            self.tr("World-writable directory without sticky bit"),
            self.tr("SUID binary"),
        )

    def __init__(self, adb_handler, start_path="/", use_root=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Permission Lint"))
        self.setObjectName("permission_lint_dialog")
        self.resize(640, 460)
        self.serial = adb_handler.device_serial
        self.worker = None

        layout = QVBoxLayout(self)

        self.path_edit = QLineEdit(start_path or "/")
        layout.addWidget(self.path_edit)

        self.root_checkbox = QCheckBox(self.tr("Scan with Root (su)"))
        self.root_checkbox.setChecked(use_root)
        layout.addWidget(self.root_checkbox)

        self.ignore_system_checkbox = QCheckBox(
            self.tr("Ignore system partitions (/system, /vendor, ...)")
        )
        self.ignore_system_checkbox.setChecked(True)
        layout.addWidget(self.ignore_system_checkbox)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(self.tr("Scan"))
        self.stop_btn = QPushButton(self.tr("Stop"))
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.scan_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels([self.tr("Path"), self.tr("Issue")])
        self.results_tree.setColumnWidth(0, 380)
        self.results_tree.setAlternatingRowColors(True)
        layout.addWidget(self.results_tree)

        self.status_label = QLabel(self.tr("Ready"))
        layout.addWidget(self.status_label)

        self.scan_btn.clicked.connect(self.start_scan)
        self.stop_btn.clicked.connect(self.stop_scan)
        self.path_edit.returnPressed.connect(self.start_scan)
        self.results_tree.itemDoubleClicked.connect(self.on_double_click)
        # Covers accept/reject/Esc: closeEvent is not called for those.
        self.finished.connect(self._shutdown_worker)
        self.path_edit.setFocus()

    def start_scan(self):
        root_path = self.path_edit.text().strip() or "/"
        if self.serial is None:
            self.status_label.setText(self.tr("No device selected."))
            return

        self._shutdown_worker()
        self.results_tree.clear()
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(self.tr("Scanning..."))

        self.worker = PermissionScanWorker(
            serial=self.serial,
            root_path=root_path,
            use_root=self.root_checkbox.isChecked(),
            ignore_system=self.ignore_system_checkbox.isChecked(),
        )
        self.worker.item_found.connect(self.on_item_found)
        self.worker.scan_finished.connect(self.on_finished)
        self.worker.start()

    def stop_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText(self.tr("Stopping..."))

    def _shutdown_worker(self):
        if self.worker is None:
            return
        self.stop_scan()
        self.worker.wait(3000)
        if self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(1000)
        self.worker = None

    def on_item_found(self, item):
        label = QCoreApplication.translate(
            "PermissionLintDialog", RULE_LABELS.get(item["tag"], item["tag"])
        )
        row = QTreeWidgetItem([item["path"], label])
        row.setData(0, Qt.ItemDataRole.UserRole, item["path"])
        row.setData(0, Qt.ItemDataRole.UserRole + 1, self.serial)
        row.setData(0, Qt.ItemDataRole.UserRole + 2, self.root_checkbox.isChecked())
        row.setData(0, Qt.ItemDataRole.UserRole + 3, item["tag"] == "D")
        self.results_tree.addTopLevelItem(row)
        self.status_label.setText(
            self.tr("Scanning... Issues found: {0}").format(
                self.results_tree.topLevelItemCount()
            )
        )

    def on_finished(self, count):
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(self.tr("Done. Issues found: {0}").format(count))

    def on_double_click(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        serial = item.data(0, Qt.ItemDataRole.UserRole + 1)
        use_root = bool(item.data(0, Qt.ItemDataRole.UserRole + 2))
        is_directory = bool(item.data(0, Qt.ItemDataRole.UserRole + 3))
        if path and serial:
            self.item_selected.emit(serial, path, use_root, is_directory)

    def closeEvent(self, event):
        self._shutdown_worker()
        super().closeEvent(event)
