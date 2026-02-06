from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, 
                             QTreeView, QHeaderView, QMessageBox, QLabel, QHBoxLayout)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

class SelectDirectoryDialog(QDialog):
    def __init__(self, parent, adb_handler, start_path="/storage/emulated/0", root_path="/", use_root=False):
        super().__init__(parent)
        self.setWindowTitle("Select Destination Folder")
        self.resize(600, 400)
        self.adb_handler = adb_handler
        self.selected_path = None
        self.root_path = "/" if root_path == "/" else root_path.rstrip("/")
        self.current_path = "/" if start_path == "/" else start_path.rstrip("/")
        self.use_root = use_root

        layout = QVBoxLayout(self)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Path'])
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setHeaderHidden(False)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        layout.addWidget(self.tree_view)

        btn_layout = QHBoxLayout()
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(self.go_up)
        btn_layout.addWidget(up_btn)

        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.accept)
        btn_layout.addWidget(select_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.tree_view.doubleClicked.connect(self.on_double_click)

        if self.adb_handler.device_connected:
            self.refresh()
        else:
            self.status_label.setText("No ADB device connected")
            QMessageBox.warning(self, "Connection Error", "No ADB device connected")

    def refresh(self):
        if not self.adb_handler.device_connected:
            self.status_label.setText("No ADB device connected")
            return
            
        self.status_label.setText("Loading directories...")
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Path'])

        
        if self.current_path != self.root_path:
            parent = "/".join(self.current_path.split("/")[:-1])
            if not parent:
                parent = self.root_path
            item = QStandardItem("..")
            path_item = QStandardItem(parent)
            self.tree_model.appendRow([item, path_item])

        try:
            files = self.adb_handler.list_directory(self.current_path, use_root=self.use_root)
            if files is None:
                self.status_label.setText("Failed to load directories")
                return
                
            dirs = sorted([f for f in files if f.is_dir], key=lambda x: x.name.lower())
            for d in dirs:
                name_item = QStandardItem(d.name)
                path_item = QStandardItem(d.path)
                self.tree_model.appendRow([name_item, path_item])
                
            self.status_label.setText(f"Found {len(dirs)} directories")
        except Exception as e:
            self.status_label.setText(f"Error loading directories: {e}")

        self.tree_view.setColumnHidden(1, True)
        self.tree_view.resizeColumnToContents(0)

    def go_up(self):
        if self.current_path == self.root_path:
            return
        parent = "/".join(self.current_path.split("/")[:-1])
        if not parent:
            parent = self.root_path
        self.current_path = parent
        self.refresh()

    def on_double_click(self, index):
        if not self.adb_handler.device_connected:
            return
            
        item = self.tree_model.itemFromIndex(index)
        path_item = self.tree_model.item(index.row(), 1)
        if path_item and item.text() != "..":
            self.current_path = path_item.text()
            self.refresh()

    def accept(self):
        if not self.adb_handler.device_connected:
            QMessageBox.warning(self, "Connection Error", "No ADB device connected")
            return
            
        selection = self.tree_view.selectionModel().selectedRows()
        if not selection:
            QMessageBox.warning(self, "No Selection", "Please select a folder.")
            return
        index = selection[0]
        path_index = self.tree_model.index(index.row(), 1)
        self.selected_path = self.tree_model.data(path_index)
        super().accept()

    def get_selected_path(self):
        return self.selected_path
