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
        self.root_path = root_path
        self.name_query = name_query
        self.content_query = content_query
        self.use_root = use_root
        self._cancelled = False
        self._operation = OperationControl()

    def cancel(self):
        self._cancelled = True
        # Kills the search adb process immediately instead of waiting
        # for the next line of find output.
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
    # Передает (serial_устройства, полный_путь, use_root)
    file_selected = pyqtSignal(str, str, bool)

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
        # Only one scan at a time: the previous thread object must never be
        # overwritten while its run() is still executing, otherwise Qt
        # destroys a live QThread and aborts the whole process.
        self._preferred_serial = preferred_serial
        if self._scan_thread is not None and self._scan_thread.isRunning():
            return
        self._scan_thread = DeviceScanThread()
        self._scan_thread.devices_scanned.connect(self._on_devices_scanned)
        self.device_combo.setEnabled(False)
        self.status_label.setText(self.tr("Scanning devices..."))
        self._scan_thread.start()

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
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.clear_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.status_label.setText(self.tr("Searching..."))

        # Dedicated handler: the shared panel handler is never touched,
        # so the panel keeps its own serial and root state.
        self.worker = DeviceSearchWorker(
            adb_handler=ADBHandler(device_serial=serial),
            root_path=root_path,
            name_query=name_q,
            content_query=content_q,
            use_root=self.root_checkbox.isChecked(),
        )
        self.worker.item_found.connect(self.on_item_found)
        self.worker.search_finished.connect(self.on_finished)
        self.worker.start()

    def stop_search(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText(self.tr("Stopping..."))

    def _shutdown_worker(self):
        if self.worker is None:
            return
        if self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
            if self.worker.isRunning():
                # Last resort: the process kill did not unblock the thread.
                self.worker.terminate()
                self.worker.wait(1000)
        self.worker = None

    def clear_results(self):
        self.results_tree.clear()
        self.status_label.setText(self.tr("Ready"))

    def shutdown(self):
        # Called from the main window closeEvent. Waits for both threads
        # before the widgets go away, so nothing is destroyed while running.
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
        row = QTreeWidgetItem([item["name"], item["path"]])
        row.setData(0, Qt.ItemDataRole.UserRole, item["path"])
        row.setData(0, Qt.ItemDataRole.UserRole + 1, self.device_combo.currentData())
        row.setData(0, Qt.ItemDataRole.UserRole + 2, self.root_checkbox.isChecked())
        self.results_tree.addTopLevelItem(row)
        self.status_label.setText(
            self.tr("Searching... Found: {0}").format(
                self.results_tree.topLevelItemCount()
            )
        )

    def on_finished(self, count):
        self._searching = False
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.clear_btn.setEnabled(True)
        self.device_combo.setEnabled(self.device_combo.count() > 0)
        self.status_label.setText(self.tr("Done. Found: {0}").format(count))

    def on_double_click(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        serial = item.data(0, Qt.ItemDataRole.UserRole + 1)
        use_root = bool(item.data(0, Qt.ItemDataRole.UserRole + 2))
        if path and serial:
            self.file_selected.emit(serial, path, use_root)


# Legacy alias: main.py still imports DeviceSearchDialog
DeviceSearchDialog = DeviceSearchPanel
