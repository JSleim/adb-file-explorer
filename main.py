import sys
import os
import tempfile
import subprocess
import logging
from logging_config import setup_logging

logger = setup_logging()
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTreeView, 
                            QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
                            QMessageBox, QLineEdit, QMenu, QFileDialog, QProgressDialog,
                            QStatusBar, QLabel, QDialog)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QTimer
from handler import ADBHandler
from device_chooser import DeviceChooser

class DropTreeView(QTreeView):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.main_window.handle_drop_event(event)
            event.acceptProposedAction()
        else:
            event.ignore()

class ADBFileExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADB File Explorer")
        self.setGeometry(100, 100, 800, 600)
        
        self.adb_handler = ADBHandler()
        
        self.setup_ui()
        
        self.select_device()
        
        if self.adb_handler.device_connected:
            self.refresh_files()
            
    def select_device(self):
        if not self.adb_handler.device_connected:
            QMessageBox.critical(self, "No Devices", "No ADB devices found. Please connect a device and try again.")
            return False

        if len(self.adb_handler.devices) > 1:
            dialog = DeviceChooser(self.adb_handler.devices, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_serial = dialog.selected_device()
                if selected_serial:
                    self.adb_handler = ADBHandler(device_serial=selected_serial)
                    self.setWindowTitle(f"ADB File Explorer - {self.adb_handler.devices[selected_serial]} ({selected_serial})")
                    return True
            return False
        elif len(self.adb_handler.devices) == 1:
            serial = next(iter(self.adb_handler.devices.keys()))
            self.setWindowTitle(f"ADB File Explorer - {self.adb_handler.devices[serial]} ({serial})")
            return True

        return False
        
    def setup_ui(self):
        self.clipboard = {
            'items': [],
            'operation': None
        }
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Add status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Add connection status indicator
        self.connection_label = QLabel("")
        self.status_bar.addPermanentWidget(self.connection_label)
        self.update_connection_status()
        
        # Add navigation bar
        nav_layout = QHBoxLayout()
        
        # Back button
        self.back_btn = QPushButton("←")
        self.back_btn.setMaximumWidth(50)
        self.back_btn.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_btn)
        
        # Path display
        self.path_display = QLineEdit()
        self.path_display.setReadOnly(True)
        nav_layout.addWidget(self.path_display)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_files)
        nav_layout.addWidget(refresh_btn)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self.apply_search_filter)
        nav_layout.addWidget(self.search_bar)
        
        layout.addLayout(nav_layout)
        
        # Create tree view
        self.tree_view = DropTreeView(self, self)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        
        # Enable double-click handling
        self.tree_view.doubleClicked.connect(self.handle_double_click)
        
        # Add context menu for copy/cut/delete
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        
        # Add toolbar for copy/cut/paste buttons
        self.toolbar = self.addToolBar("Edit")
        self.copy_action = self.toolbar.addAction("Copy")
        self.copy_action.triggered.connect(self.copy_selected)
        self.cut_action = self.toolbar.addAction("Cut")
        self.cut_action.triggered.connect(self.cut_selected)
        self.paste_action = self.toolbar.addAction("Paste")
        self.paste_action.triggered.connect(self.paste_items)
        
        self.clipboard = {
            'items': [],
            'operation': None
        }
        
        # Add keyboard shortcuts
        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self.copy_shortcut.activated.connect(self.copy_selected)
        self.cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, self)
        self.cut_shortcut.activated.connect(self.cut_selected)
        self.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self.paste_shortcut.activated.connect(self.paste_items)
        
        layout.addWidget(self.tree_view)
        
        self.current_path = "/storage/emulated/0".rstrip("/")
        self.path_history = [self.current_path]
        self.update_path_display()
        
        self.setup_context_menu()

        self.all_files = []

        if self.adb_handler.device_connected:
            self.refresh_files()
        else:
            self.status_label.setText("No ADB device connected")
            self.show_connection_error()

        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connection_periodically)
        self.connection_timer.start(10000)
    
    def update_connection_status(self):
        if self.adb_handler.device_connected:
            self.connection_label.setText("🟢 Connected")
            self.connection_label.setStyleSheet("color: green;")
        else:
            self.connection_label.setText("🔴 Disconnected")
            self.connection_label.setStyleSheet("color: red;")
    
    def check_connection_periodically(self):
        was_connected = self.adb_handler.device_connected
        self.adb_handler.device_connected = self.adb_handler.check_adb_connection()

        if was_connected != self.adb_handler.device_connected:
            self.update_connection_status()
            if not self.adb_handler.device_connected:
                self.show_connection_error()
            else:
                self.status_label.setText("ADB device reconnected")
                self.refresh_files()
    
    def show_connection_error(self):
        QMessageBox.warning(
            self,
            "ADB Connection Error",
            "No Android device connected via ADB.\n\n"
            "Please ensure:\n"
            "1. ADB is installed and in your PATH\n"
            "2. USB debugging is enabled on your device\n"
            "3. Device is connected and authorized\n"
            "4. Run 'adb devices' to verify connection"
        )
    
    def show_status_message(self, message: str, timeout: int = 3000):
        self.status_label.setText(message)
        QTimer.singleShot(timeout, lambda: self.status_label.setText("Ready"))
    
    def show_error_message(self, title: str, message: str):
        QMessageBox.critical(self, title, message)
        self.status_label.setText(f"Error: {title}")
    
    def show_success_message(self, message: str):
        self.status_label.setText(message)
        QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    def setup_context_menu(self):
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        
    def get_file_size_from_row(self, row):
        size_index = self.tree_model.index(row, 2)
        size_text = self.tree_model.data(size_index)
        return int(size_text) if size_text.isdigit() else 0

    def is_dir_from_row(self, row):
        type_index = self.tree_model.index(row, 1)
        return self.tree_model.data(type_index) == "Directory"

    def format_size(self, bytes_size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

    def get_selected_items(self):
        """Get a list of selected file/directory items"""
        selected_items = []
        for index in self.tree_view.selectionModel().selectedRows():
            name = self.tree_model.itemFromIndex(index.siblingAtColumn(0)).text()
            item_type = self.tree_model.itemFromIndex(index.siblingAtColumn(1)).text()
            selected_items.append({
                'name': name,
                'path': f"{self.current_path.rstrip('/')}/{name}",
                'is_dir': item_type.lower() == 'directory'
            })
        return selected_items
        
    def copy_selected(self):
        """Copy selected items to clipboard"""
        selected_items = self.get_selected_items()
        if not selected_items:
            return
            
        self.clipboard = {
            'items': selected_items,
            'operation': 'copy'
        }
        self.status_label.setText(f"Copied {len(selected_items)} item(s) to clipboard")
        
    def cut_selected(self):
        """Cut selected items to clipboard"""
        selected_items = self.get_selected_items()
        if not selected_items:
            return
            
        self.clipboard = {
            'items': selected_items,
            'operation': 'cut'
        }
        self.status_label.setText(f"Cut {len(selected_items)} item(s)")
        
    def paste_items(self):
        """Paste items from clipboard to current directory"""
        if not self.clipboard or not self.clipboard['items']:
            self.status_label.setText("Clipboard is empty")
            return
            
        dest_dir = self.current_path
        success_count = 0
        total = len(self.clipboard['items'])
        
        progress = QProgressDialog("Processing items...", "Cancel", 0, total, self)
        progress.setWindowTitle("Pasting" if self.clipboard['operation'] == 'copy' else "Moving")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        for i, item in enumerate(self.clipboard['items']):
            if progress.wasCanceled():
                break
                
            src_path = item['path']
            dest_path = f"{dest_dir}/{os.path.basename(src_path)}"
            
            progress.setLabelText(f"Processing {os.path.basename(src_path)}...")
            progress.setValue(i)
            
            try:
                if self.clipboard['operation'] == 'copy':
                    success = self.adb_handler.copy_on_device(src_path, dest_path)
                else:  # cut
                    success = self.adb_handler.move_on_device(src_path, dest_path)
                    
                if success:
                    success_count += 1
                    
            except Exception as e:
                print(f"Error during paste operation: {e}")
                
            progress.setValue(i + 1)
            
        progress.close()
        
        if success_count > 0:
            self.refresh_files()
            self.status_label.setText(
                f"Successfully {'pasted' if self.clipboard['operation'] == 'copy' else 'moved'} {success_count} item(s)"
            )
            
            # Clear clipboard if it was a cut operation
            if self.clipboard['operation'] == 'cut':
                self.clipboard = {'items': [], 'operation': None}
        else:
            self.status_label.setText("Paste operation failed or was canceled")
    
    def show_context_menu(self, position):
        indexes = self.tree_view.selectionModel().selectedRows()
        menu = QMenu()
        
        # Add paste option if there are items in the clipboard
        if self.clipboard and self.clipboard['items']:
            paste_action = menu.addAction("Paste")
            paste_action.triggered.connect(self.paste_items)
            menu.addSeparator()
        
        if not indexes:
            # Right-clicked on empty space: show new file/folder/upload options
            new_file_action = menu.addAction("New File")
            new_file_action.triggered.connect(self.create_new_file)
            new_folder_action = menu.addAction("New Folder")
            new_folder_action.triggered.connect(self.create_new_folder)
            upload_file_action = menu.addAction("Upload File")
            upload_file_action.triggered.connect(self.upload_file_to_device)
        elif len(indexes) > 1:
            # Batch actions
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(self.copy_selected)
            
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(self.cut_selected)
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete Selected")
            delete_action.triggered.connect(self.delete_selected_items)

            download_action = menu.addAction("Download Selected")
            download_action.triggered.connect(self.download_selected_items)

            copy_to_action = menu.addAction("Copy Selected To...")
            copy_to_action.triggered.connect(self.copy_selected_to)
            
            batch_rename_action = menu.addAction("Batch Rename...")
            batch_rename_action.triggered.connect(self.batch_rename_selected)

            # Optional: show total size
            total_size = sum(
                self.get_file_size_from_row(index.row()) 
                for index in indexes 
                if not self.is_dir_from_row(index.row())
            )
            menu.addSeparator()
            size_label = menu.addAction(f"Total Size: {self.format_size(total_size)}")
            size_label.setEnabled(False)
        else:
            # Single selection
            index = indexes[0]
            name_index = self.tree_model.index(index.row(), 0)
            type_index = self.tree_model.index(index.row(), 1)
            item_name = self.tree_model.data(name_index)
            item_type = self.tree_model.data(type_index)
            
            # Add copy and cut actions for the selected item
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(self.copy_selected)
            
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(self.cut_selected)
            
            menu.addSeparator()
            
            if item_type == "File":
                open_action = menu.addAction("Open")
                open_action.triggered.connect(lambda: self.open_file_on_host(item_name))
                
                copy_to_action = menu.addAction("Copy to...")
                copy_to_action.triggered.connect(lambda: self.copy_file_to(item_name))
                
                menu.addSeparator()
                
                rename_action = menu.addAction("Rename")
                rename_action.triggered.connect(lambda: self.rename_item(item_name))
                
                delete_action = menu.addAction("Delete")
                delete_action.triggered.connect(lambda: self.delete_item(item_name, is_dir=False))
                
            elif item_type == "Directory":
                copy_to_action = menu.addAction("Copy to...")
                copy_to_action.triggered.connect(lambda: self.copy_folder_to(item_name))
                
                menu.addSeparator()
                
                rename_action = menu.addAction("Rename")
                rename_action.triggered.connect(lambda: self.rename_item(item_name))
                
                delete_action = menu.addAction("Delete")
                delete_action.triggered.connect(lambda: self.delete_item(item_name, is_dir=True))
        menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def copy_file_to(self, filename):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File As", filename)
        if not save_path:
            return
            
        self.show_status_message(f"Copying {filename}...")
        success = self.adb_handler.pull_file(remote_path, save_path)
        if not success:
            self.show_error_message("Copy Error", f"Failed to copy file: {filename}")
        else:
            self.show_success_message(f"File copied to: {save_path}")

    def copy_folder_to(self, foldername):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        remote_path = f"{self.current_path.rstrip('/')}/{foldername}"
        save_dir = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not save_dir:
            return
        # The local destination path for the folder
        local_path = os.path.join(save_dir, foldername)
        
        self.show_status_message(f"Copying folder {foldername}...")
        success = self.adb_handler.pull_file(remote_path, local_path)
        if not success:
            self.show_error_message("Copy Error", f"Failed to copy folder: {foldername}")
        else:
            self.show_success_message(f"Folder copied to: {local_path}")

    def update_path_display(self):
        self.path_display.setText(self.current_path)
        # Enable back button only if we have history
        self.back_btn.setEnabled(len(self.path_history) > 1)
    
    def go_back(self):
        if len(self.path_history) > 1:
            self.path_history.pop()  # Remove current path
            self.current_path = self.path_history[-1]  # Get previous path
            self.update_path_display()
            self.refresh_files()
    
    def handle_double_click(self, index):
        # Get the name from the first column
        name_index = self.tree_model.index(index.row(), 0)
        type_index = self.tree_model.index(index.row(), 1)
        
        item_name = self.tree_model.data(name_index)
        item_type = self.tree_model.data(type_index)
        
        print(f"Clicked on: '{item_name}' (Type: {item_type})")  # Debug print
        
        # Skip if item_name is empty
        if not item_name:
            print("Empty item name, skipping...")
            return
            
        if item_type == "Directory":
            new_path = ""
            if item_name == "..":
                # Go up one directory
                parent_path = "/".join(self.current_path.rstrip("/").split("/")[:-1])
                new_path = parent_path if parent_path else "/storage/emulated/0"
            else:
                # Construct new path properly
                new_path = f"{self.current_path.rstrip('/')}/{item_name}"
            
            print(f"Current path: {self.current_path}")  # Debug print
            print(f"New path: {new_path}")  # Debug print
            
            if new_path != self.current_path:
                self.current_path = new_path
                self.path_history.append(self.current_path)
                self.update_path_display()
                print(f"Refreshing files for path: {self.current_path}")  # Debug print
                self.refresh_files()
        elif item_type == "File":
            self.open_file_on_host(item_name)

    def open_file_on_host(self, filename):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        # Pull file to temp directory
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, filename)
        
        self.show_status_message(f"Opening {filename}...")
        success = self.adb_handler.pull_file(remote_path, local_path)
        if not success:
            self.show_error_message("Open Error", f"Failed to pull file: {filename}")
            return
        # Open file with default application
        try:
            if sys.platform.startswith('win'):
                os.startfile(local_path)
            elif sys.platform.startswith('darwin'):
                subprocess.run(['open', local_path])
            else:
                subprocess.run(['xdg-open', local_path])
            self.show_success_message(f"Opened {filename}")
        except Exception as e:
            self.show_error_message("Open Error", f"Failed to open file: {e}")

    def refresh_files(self):
        if not self.adb_handler.device_connected:
            self.status_label.setText("No ADB device connected")
            return
            
        self.show_status_message(f"Refreshing {self.current_path}...")
        self.all_files = self.adb_handler.list_directory(self.current_path)
        
        if self.all_files is None:
            self.show_error_message("Refresh Error", "Failed to list directory contents")
            return
            
        self.show_status_message(f"Found {len(self.all_files)} items")
        self.apply_search_filter()

    def apply_search_filter(self):
        search_text = self.search_bar.text().lower()
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])
        
        # Check if we have files to display
        if not hasattr(self, 'all_files') or self.all_files is None:
            return
            
        # Add parent directory entry if not in root
        if self.current_path.rstrip("/") != "/storage/emulated/0":
            parent_item = QStandardItem("..")
            type_item = QStandardItem("Directory")
            self.tree_model.appendRow([parent_item, type_item, 
                                     QStandardItem(""), QStandardItem(""), QStandardItem("")])
        # Filter files
        filtered = [f for f in self.all_files if search_text in f.name.lower()]
        # Sort files: directories first, then files, both alphabetically
        dirs = sorted([f for f in filtered if f.is_dir], key=lambda x: x.name.lower())
        regular_files = sorted([f for f in filtered if not f.is_dir], key=lambda x: x.name.lower())
        sorted_files = dirs + regular_files
        for file_item in sorted_files:
            name_item = QStandardItem(file_item.name)
            type_item = QStandardItem("Directory" if file_item.is_dir else "File")
            size = str(file_item.size) if not file_item.is_dir else ""
            size_item = QStandardItem(size)
            perm_item = QStandardItem(file_item.permissions)
            date_item = QStandardItem(file_item.date_modified)
            row = [name_item, type_item, size_item, perm_item, date_item]
            self.tree_model.appendRow(row)
        for i in range(5):
            self.tree_view.resizeColumnToContents(i)

    def rename_item(self, old_name):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename", f"Enter new name for '{old_name}':")
        if ok and new_name and new_name != old_name:
            old_path = f"{self.current_path.rstrip('/')}/{old_name}"
            new_path = f"{self.current_path.rstrip('/')}/{new_name}"
            
            self.show_status_message(f"Renaming {old_name}...")
            success = self.adb_handler.rename_item(old_path, new_path)
            if not success:
                self.show_error_message("Rename Error", f"Failed to rename '{old_name}'")
            else:
                self.show_success_message(f"Renamed '{old_name}' to '{new_name}'")
                self.refresh_files()

    def delete_item(self, name, is_dir=False):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        reply = QMessageBox.question(
            self, "Delete",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            path = f"{self.current_path.rstrip('/')}/{name}"
            
            self.show_status_message(f"Deleting {name}...")
            success = self.adb_handler.delete_item(path, is_dir)
            if not success:
                self.show_error_message("Delete Error", f"Failed to delete '{name}'")
            else:
                self.show_success_message(f"Deleted '{name}'")
                self.refresh_files()

    def delete_selected_items(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return
        names_types = []
        for index in indexes:
            name_index = self.tree_model.index(index.row(), 0)
            type_index = self.tree_model.index(index.row(), 1)
            item_name = self.tree_model.data(name_index)
            item_type = self.tree_model.data(type_index)
            if item_name and item_name != "..":
                names_types.append((item_name, item_type == "Directory"))
        if not names_types:
            return
        reply = QMessageBox.question(
            self, "Delete",
            f"Are you sure you want to delete {len(names_types)} selected items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.show_status_message(f"Deleting {len(names_types)} items...")
            success_count = 0
            for name, is_dir in names_types:
                path = f"{self.current_path.rstrip('/')}/{name}"
                if self.adb_handler.delete_item(path, is_dir):
                    success_count += 1
            if success_count == len(names_types):
                self.show_success_message(f"Successfully deleted {success_count} items")
            else:
                self.show_error_message("Delete Warning", f"Deleted {success_count}/{len(names_types)} items")
            self.refresh_files()

    def create_new_file(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New File", "Enter new file name:")
        if ok and name:
            remote_path = f"{self.current_path.rstrip('/')}/{name}"
            
            self.show_status_message(f"Creating file {name}...")
            success = self.adb_handler.create_file(remote_path)
            if not success:
                self.show_error_message("Create Error", f"Failed to create file: {name}")
            else:
                self.show_success_message(f"Created file '{name}'")
                self.refresh_files()

    def create_new_folder(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Folder", "Enter new folder name:")
        if ok and name:
            remote_path = f"{self.current_path.rstrip('/')}/{name}"
            
            self.show_status_message(f"Creating folder {name}...")
            success = self.adb_handler.create_folder(remote_path)
            if not success:
                self.show_error_message("Create Error", f"Failed to create folder: {name}")
            else:
                self.show_success_message(f"Created folder '{name}'")
                self.refresh_files()

    def upload_file_to_device(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not file_path:
            return
        # Upload to current directory, keep original filename
        filename = os.path.basename(file_path)
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        
        self.show_status_message(f"Uploading {filename}...")
        success = self.adb_handler.push_file(file_path, remote_path)
        if not success:
            self.show_error_message("Upload Error", f"Failed to upload file: {filename}")
        else:
            self.show_success_message(f"File uploaded to: {remote_path}")
            self.refresh_files()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def handle_drop_event(self, event):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        urls = event.mimeData().urls()
        if not urls:
            return
        paths = [u.toLocalFile() for u in urls]
        files_to_upload = []
        for path in paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        abs_file = os.path.join(root, file)
                        rel_dir = os.path.relpath(root, path)
                        files_to_upload.append((abs_file, rel_dir))
            else:
                files_to_upload.append((path, ""))
        self.upload_files_and_folders_with_progress(files_to_upload, base_folder=paths[0] if os.path.isdir(paths[0]) else None)

    def upload_files_and_folders_with_progress(self, files, base_folder=None):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        total = len(files)
        progress = QProgressDialog("Uploading files...", "Cancel", 0, total, self)
        progress.setWindowTitle("Upload Progress")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.show()
        
        success_count = 0
        for i, (file_path, rel_dir) in enumerate(files, 1):
            if progress.wasCanceled():
                break
            filename = os.path.basename(file_path)
            # If uploading a folder, preserve its structure
            if base_folder and rel_dir != ".":
                remote_dir = f"{self.current_path.rstrip('/')}/{os.path.basename(base_folder)}/{rel_dir}".replace("\\", "/")
            elif base_folder:
                remote_dir = f"{self.current_path.rstrip('/')}/{os.path.basename(base_folder)}".replace("\\", "/")
            else:
                remote_dir = self.current_path.rstrip("/")
            # Create remote directory if needed
            if rel_dir:
                self.adb_handler.create_folder(remote_dir)
            remote_path = f"{remote_dir}/{filename}".replace("\\", "/")
            progress.setLabelText(f"Uploading {filename} ({i}/{total})")
            progress.setValue(i - 1)
            QApplication.processEvents()
            success = self.adb_handler.push_file(file_path, remote_path)
            if success:
                success_count += 1
            else:
                self.show_error_message("Upload Error", f"Failed to upload file: {filename}")
                break
        progress.close()
        
        if success_count == total:
            self.show_success_message(f"Successfully uploaded {success_count} files")
        else:
            self.show_error_message("Upload Warning", f"Uploaded {success_count}/{total} files")
        self.refresh_files()

    def download_files_with_progress(self, files):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        total = len(files)
        progress = QProgressDialog("Downloading files...", "Cancel", 0, total, self)
        progress.setWindowTitle("Download Progress")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.show()
        
        success_count = 0
        for i, (remote_path, local_path) in enumerate(files, 1):
            if progress.wasCanceled():
                break
            filename = os.path.basename(remote_path)
            progress.setLabelText(f"Downloading {filename} ({i}/{total})")
            progress.setValue(i - 1)
            QApplication.processEvents()
            success = self.adb_handler.pull_file(remote_path, local_path)
            if success:
                success_count += 1
            else:
                self.show_error_message("Download Error", f"Failed to download file: {filename}")
                break
        progress.close()
        
        if success_count == total:
            self.show_success_message(f"Successfully downloaded {success_count} files")
        else:
            self.show_error_message("Download Warning", f"Downloaded {success_count}/{total} files")
    def download_selected_items(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return

        # Choose destination folder
        save_dir = QFileDialog.getExistingDirectory(self, "Select Download Location")
        if not save_dir:
            return

        # Prepare list of (remote_path, local_path)
        files_to_download = []
        for index in indexes:
            name_index = self.tree_model.index(index.row(), 0)
            type_index = self.tree_model.index(index.row(), 1)
            item_name = self.tree_model.data(name_index)
            item_type = self.tree_model.data(type_index)

            if not item_name or item_name == "..":
                continue

            remote_path = f"{self.current_path.rstrip('/')}/{item_name}"
            local_path = os.path.join(save_dir, item_name)

            files_to_download.append((remote_path, local_path))

        if not files_to_download:
            self.show_error_message("Download Error", "No valid items selected for download")
            return

        # Run with progress
        self.download_files_with_progress(files_to_download)
        
    def copy_selected_to(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return

        names_types = []
        for index in indexes:
            name_index = self.tree_model.index(index.row(), 0)
            type_index = self.tree_model.index(index.row(), 1)
            item_name = self.tree_model.data(name_index)
            is_dir = self.tree_model.data(type_index) == "Directory"
            if item_name and item_name != "..":
                names_types.append((item_name, is_dir))

        if not names_types:
            return

        # Let user pick target directory
        from select_directory_dialog import SelectDirectoryDialog
        dialog = SelectDirectoryDialog(self, self.adb_handler, self.current_path)
        if dialog.exec() == dialog.DialogCode.Accepted:
            target_path = dialog.get_selected_path()
            if not target_path:
                return

            # Confirm
            reply = QMessageBox.question(
                self, "Copy Items",
                f"Copy {len(names_types)} item(s) to '{target_path}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

            # Perform copy
            self.copy_items_to_path(names_types, target_path)
            
    def copy_items_to_path(self, items, target_path):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        progress = QProgressDialog("Copying items...", "Cancel", 0, len(items), self)
        progress.setWindowTitle("Copy Progress")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.show()

        success_count = 0
        for i, (name, is_dir) in enumerate(items):
            if progress.wasCanceled():
                break
            source = f"{self.current_path.rstrip('/')}/{name}"
            dest = f"{target_path.rstrip('/')}/{name}"
            
            # Use the ADB handler for copying
            if is_dir:
                # For directories, we need to create the destination and copy contents
                    try:
                        self.adb_handler.create_folder(dest)
                        cmd = f"cp -r '{source}' '{dest}'"
                        result = self.adb_handler._run_adb_command(['shell', cmd])
                        success = result.returncode == 0
                    except Exception as e:
                        print(f"Error copying directory {name}: {e}")
                        success = False
            else:
                # For files, use the push method
                try:
                    # Pull to temp, then push to destination
                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    temp_file = os.path.join(temp_dir, name)
                    if self.adb_handler.pull_file(source, temp_file):
                        success = self.adb_handler.push_file(temp_file, dest)
                        # Clean up temp file
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    else:
                        success = False
                except Exception as e:
                    print(f"Error copying file {name}: {e}")
                    success = False

            if success:
                success_count += 1

            progress.setLabelText(f"Copying {name} ({i+1}/{len(items)})")
            progress.setValue(i+1)
            QApplication.processEvents()

        progress.close()
        if success_count == len(items):
            self.show_success_message(f"Successfully copied {success_count} items")
        else:
            self.show_error_message("Copy Warning", f"Copied {success_count}/{len(items)} items")
        self.refresh_files()
            
    def batch_rename_selected(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
            
        indexes = self.tree_view.selectionModel().selectedRows()
        if len(indexes) < 2:
            QMessageBox.information(self, "Info", "Select 2 or more items to batch rename.")
            return

        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        base_name, ok = QInputDialog.getText(
            self, "Batch Rename",
            "Enter base name:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if not ok or not base_name:
            return

        padding = len(str(len(indexes)))

        progress = QProgressDialog("Renaming items...", "Cancel", 0, len(indexes), self)
        progress.setWindowTitle("Batch Rename")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.show()

        success_count = 0
        for i, index in enumerate(indexes):
            if progress.wasCanceled():
                break
                
            old_name_index = self.tree_model.index(index.row(), 0)
            old_name = self.tree_model.data(old_name_index)
            new_name = f"{base_name}{str(i+1).zfill(padding)}"
            old_path = f"{self.current_path.rstrip('/')}/{old_name}"
            new_path = f"{self.current_path.rstrip('/')}/{new_name}"
            
            if self.adb_handler.rename_item(old_path, new_name):
                success_count += 1

            progress.setLabelText(f"Renaming {old_name} → {new_name}")
            progress.setValue(i+1)
            QApplication.processEvents()

        progress.close()
        if success_count == len(indexes):
            self.show_success_message(f"Successfully renamed {success_count} items")
        else:
            self.show_error_message("Rename Warning", f"Renamed {success_count}/{len(indexes)} items")
        self.refresh_files()

def main():
    # Configure logging first
    logger = setup_logging()
    
    try:
        # Create application
        app = QApplication(sys.argv)
        
        # Set application attributes
        app.setApplicationName("ADB Explorer")
        app.setApplicationVersion("1.0.0")
        app.setQuitOnLastWindowClosed(True)
        
        # Create and show main window
        window = ADBFileExplorer()
        window.show()
        
        # Start the application
        return app.exec()
        
    except Exception as e:
        logger.exception("Fatal error in application")
        QMessageBox.critical(
            None,
            "Fatal Error",
            f"A fatal error occurred:\n{str(e)}\n\nCheck the log file for more details."
        )
        return 1

if __name__ == "__main__":
    # This ensures proper cleanup when the application is closed
    sys.exit(main())