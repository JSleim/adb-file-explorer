from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from handler import ADBHandler
from operation_control import (
    OperationControl,
    clear_current_operation,
    set_current_operation,
)


class DeviceScanThread(QThread):
    devices_scanned = pyqtSignal(dict)

    def run(self):
        try:
            devices = ADBHandler().get_unique_devices()
        except Exception:
            devices = {}
        self.devices_scanned.emit(devices)


class DeviceSearchWorker(QThread):
    item_found = pyqtSignal(dict)
    search_finished = pyqtSignal(int)

    def __init__(self, adb_handler, root_path, name_query, content_query, use_root):
        super().__init__()
        self.adb_handler = adb_handler
        self.device_serial = adb_handler.device_serial
        self.root_path = root_path
        self.name_query = name_query
        self.content_query = content_query
        self.use_root = use_root
        self._cancelled = False
        self._operation = OperationControl()

    def cancel(self):
        self._cancelled = True
        self._operation.cancel()

    def run(self):
        set_current_operation(self._operation)
        try:
            if self.use_root and self.adb_handler.root_mode is None:
                try:
                    self.adb_handler.enable_root()
                except Exception:
                    pass
            count = 0
            for item in self.adb_handler.search_device_files(
                root_path=self.root_path,
                name_query=self.name_query,
                content_query=self.content_query,
                use_root=self.use_root,
                cancel_check=lambda: self._cancelled,
            ):
                if self._cancelled:
                    break
                count += 1
                self.item_found.emit(item)
            self.search_finished.emit(count)
        finally:
            clear_current_operation()


class DeviceSearchPanel(QWidget):
    file_selected = pyqtSignal(str, str, bool, bool)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("device_search_dialog")
        self._scan_thread = None
        self._preferred_serial = None
        self._searching = False
        self.worker = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.device_combo = QComboBox()
        self.path_edit = QLineEdit("/")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            self.tr("File or folder name (e.g. photo or .pdf)")
        )
        self.content_edit = QLineEdit()
        self.content_edit.setPlaceholderText(self.tr("Text inside file (optional)"))

        self.root_checkbox = QCheckBox(self.tr("Search with Root (su)"))

        form.addRow(self.tr("Device:"), self.device_combo)
        form.addRow(self.tr("Start directory:"), self.path_edit)
        form.addRow(self.tr("Name:"), self.name_edit)
        form.addRow(self.tr("Content:"), self.content_edit)
        form.addRow("", self.root_checkbox)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.search_btn = QPushButton(self.tr("Search"))
        self.stop_btn = QPushButton(self.tr("Stop"))
        self.stop_btn.setEnabled(False)
        self.clear_btn = QPushButton(self.tr("Clear"))
        self.clear_btn.setEnabled(False)
        btn_row.addWidget(self.search_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels([self.tr("Name"), self.tr("Path")])
        self.results_tree.setColumnWidth(0, 240)
        self.results_tree.setAlternatingRowColors(True)
        layout.addWidget(self.results_tree)

        self.status_label = QLabel(self.tr("Ready"))
        layout.addWidget(self.status_label)

        self.search_btn.clicked.connect(self.start_search)
        self.stop_btn.clicked.connect(self.stop_search)
        self.clear_btn.clicked.connect(self.clear_results)
        self.name_edit.returnPressed.connect(self.start_search)
        self.content_edit.returnPressed.connect(self.start_search)
        self.results_tree.itemDoubleClicked.connect(self.on_double_click)

    # -- Thread lifecycle -------------------------------------------------

    def refresh_devices(self, preferred_serial=None):
        self._preferred_serial = preferred_serial
        if self._scan_thread is not None and self._scan_thread.isRunning():
            return
        self._scan_thread = DeviceScanThread()
        self._scan_thread.devices_scanned.connect(self._on_devices_scanned)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.finished.connect(self._clear_scan_thread_ref)
        self.device_combo.setEnabled(False)
        self.status_label.setText(self.tr("Scanning devices..."))
        self._scan_thread.start()

    def _clear_scan_thread_ref(self):
        self._scan_thread = None

    def _on_devices_scanned(self, devices):
        self.device_combo.clear()
        for serial, model in devices.items():
            self.device_combo.addItem(f"{model} ({serial})", serial)
            if serial == self._preferred_serial:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
        if not devices:
            self.status_label.setText(self.tr("No ADB devices connected"))
        elif not self._searching:
            self.status_label.setText(self.tr("Ready"))
        self.device_combo.setEnabled(bool(devices) and not self._searching)

    def start_search(self):
        if self._searching:
            return

        serial = self.device_combo.currentData()
        if not serial:
            self.status_label.setText(self.tr("No device selected."))
            return

        root_path = self.path_edit.text().strip() or "/"
        name_q = self.name_edit.text().strip()
        content_q = self.content_edit.text().strip()

        if not name_q and not content_q:
            self.status_label.setText(self.tr("Enter file name or content text."))
            return

        self._shutdown_worker()
        self.results_tree.clear()
        self._searching = True
        self._set_inputs_enabled(False)
        self.status_label.setText(self.tr("Searching..."))

        self.worker = DeviceSearchWorker(
            adb_handler=ADBHandler(device_serial=serial),
            root_path=root_path,
            name_query=name_q,
            content_query=content_q,
            use_root=self.root_checkbox.isChecked(),
        )
        self.worker.item_found.connect(self.on_item_found)
        self.worker.search_finished.connect(self.on_finished)
        self.worker.finished.connect(self._on_worker_thread_finished)
        self.worker.start()

    def _set_inputs_enabled(self, enabled):
        self.search_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
        self.clear_btn.setEnabled(enabled and self.results_tree.topLevelItemCount() > 0)
        self.device_combo.setEnabled(enabled and self.device_combo.count() > 0)
        self.root_checkbox.setEnabled(enabled)
        self.path_edit.setEnabled(enabled)

    def stop_search(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText(self.tr("Stopping..."))

    def _on_worker_thread_finished(self):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def _shutdown_worker(self):
        if self.worker is None:
            return
        try:
            if self.worker.isRunning():
                self.worker.cancel()
                self.worker.wait(3000)
                if self.worker.isRunning():
                    self.worker.terminate()
                    self.worker.wait(1000)
                    clear_current_operation()
        except RuntimeError:
            pass
        self.worker = None

    def clear_results(self):
        self.results_tree.clear()
        self.clear_btn.setEnabled(False)
        self.status_label.setText(self.tr("Ready"))

    def shutdown(self):
        if self._scan_thread is not None and self._scan_thread.isRunning():
            try:
                self._scan_thread.devices_scanned.disconnect()
            except TypeError:
                pass
            self._scan_thread.wait(2000)
        self._shutdown_worker()

    # -- UI slots ---------------------------------------------------------

    def set_use_root(self, checked):
        self.root_checkbox.setChecked(checked)

    def focus_search(self):
        self.name_edit.setFocus()

    def on_item_found(self, item):
        if not self.worker:
            return
        row = QTreeWidgetItem([item["name"], item["path"]])
        row.setData(0, Qt.ItemDataRole.UserRole, item["path"])
        row.setData(0, Qt.ItemDataRole.UserRole + 1, self.worker.device_serial)
        row.setData(0, Qt.ItemDataRole.UserRole + 2, self.worker.use_root)
        row.setData(0, Qt.ItemDataRole.UserRole + 3, bool(item.get("is_directory", False)))
        self.results_tree.addTopLevelItem(row)
        self.status_label.setText(
            self.tr("Searching... Found: {0}").format(
                self.results_tree.topLevelItemCount()
            )
        )

    def on_finished(self, count):
        self._searching = False
        self._set_inputs_enabled(True)
        self.status_label.setText(self.tr("Done. Found: {0}").format(count))

    def on_double_click(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        serial = item.data(0, Qt.ItemDataRole.UserRole + 1)
        use_root = bool(item.data(0, Qt.ItemDataRole.UserRole + 2))
        is_dir = bool(item.data(0, Qt.ItemDataRole.UserRole + 3))
        if path and serial:
            self.file_selected.emit(serial, path, use_root, is_dir)
