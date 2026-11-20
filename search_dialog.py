from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


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

    def cancel(self):
        self._cancelled = True

    def run(self):
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


class DeviceSearchDialog(QDialog):
    # Передает (serial_устройства, полный_путь)
    file_selected = pyqtSignal(str, str)

    def __init__(
        self,
        adb_handler,
        default_serial=None,
        start_path="/",
        use_root=False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Global Search on Device"))
        self.setObjectName("device_search_dialog")
        self.resize(720, 500)
        self.adb_handler = adb_handler
        self.worker = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.device_combo = QComboBox()
        devices = self.adb_handler.get_unique_devices()
        target_serial = default_serial or self.adb_handler.device_serial
        for serial, model in devices.items():
            self.device_combo.addItem(f"{model} ({serial})", serial)
            if serial == target_serial:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)

        self.path_edit = QLineEdit(start_path or "/")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            self.tr("File or folder name (e.g. photo or .pdf)")
        )
        self.content_edit = QLineEdit()
        self.content_edit.setPlaceholderText(self.tr("Text inside file (optional)"))

        self.root_checkbox = QCheckBox(self.tr("Search with Root (su)"))
        self.root_checkbox.setChecked(use_root)

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
        btn_row.addWidget(self.search_btn)
        btn_row.addWidget(self.stop_btn)
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
        self.name_edit.returnPressed.connect(self.start_search)
        self.content_edit.returnPressed.connect(self.start_search)
        self.results_tree.itemDoubleClicked.connect(self.on_double_click)
        self.name_edit.setFocus()

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

        self.adb_handler.device_serial = serial
        self.results_tree.clear()
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(self.tr("Searching..."))

        self.worker = DeviceSearchWorker(
            adb_handler=self.adb_handler,
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

    def on_item_found(self, item):
        row = QTreeWidgetItem([item["name"], item["path"]])
        row.setData(0, Qt.ItemDataRole.UserRole, item["path"])
        self.results_tree.addTopLevelItem(row)
        self.status_label.setText(
            self.tr("Searching... Found: {0}").format(
                self.results_tree.topLevelItemCount()
            )
        )

    def on_finished(self, count):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(self.tr("Done. Found: {0}").format(count))

    def on_double_click(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        serial = self.device_combo.currentData()
        if path and serial:
            self.file_selected.emit(serial, path)
            self.accept()

    def closeEvent(self, event):
        self.stop_search()
        if self.worker:
            self.worker.wait(1000)
        super().closeEvent(event)
