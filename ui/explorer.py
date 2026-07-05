import os
import sys
import tempfile
import subprocess

from PyQt6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QMessageBox, QLineEdit, QMenu, QFileDialog, QInputDialog,
    QStatusBar, QLabel, QDialog, QCheckBox, QFileIconProvider, QProgressBar,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QTimer, QFileInfo

from handler import ADBHandler
from device_chooser import DeviceChooser
from ui.widgets import DropTreeView
from ui.task_manager import BackgroundTaskManager, WorkerThread


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
                    self.apply_device_root_path()
                    return True
            return False
        elif len(self.adb_handler.devices) == 1:
            serial = next(iter(self.adb_handler.devices.keys()))
            self.setWindowTitle(f"ADB File Explorer - {self.adb_handler.devices[serial]} ({serial})")
            self.apply_device_root_path()
            return True

        return False

    def setup_ui(self):
        self.clipboard = {
            'items': [],
            'operation': None
        }
        self.use_root = False
        self._loading = False
        self._refresh_pending = False
        self._refresh_task = None

        self._icon_provider = QFileIconProvider()
        self._folder_icon = self._icon_provider.icon(QFileIconProvider.IconType.Folder)
        self._file_icon = self._icon_provider.icon(QFileIconProvider.IconType.File)
        self._icon_cache = {}

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.connection_label = QLabel("")
        self.status_bar.addPermanentWidget(self.connection_label)
        self.update_connection_status()

        self.root_checkbox = QCheckBox("Root access")
        self.root_checkbox.setChecked(False)
        self.root_checkbox.stateChanged.connect(self.on_root_toggle)
        self.status_bar.addPermanentWidget(self.root_checkbox)

        nav_layout = QHBoxLayout()

        self.back_btn = QPushButton("←")
        self.back_btn.setMaximumWidth(40)
        self.back_btn.setObjectName("back_btn")
        self.back_btn.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_btn)

        self.path_display = QLineEdit()
        self.path_display.setReadOnly(True)
        self.path_display.setObjectName("path_display")
        nav_layout.addWidget(self.path_display)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_files)
        nav_layout.addWidget(refresh_btn)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.setObjectName("search_bar")
        self.search_bar.textChanged.connect(self.apply_search_filter)
        nav_layout.addWidget(self.search_bar)

        nav_container = QWidget()
        nav_container.setObjectName("nav_container")
        nav_container.setLayout(nav_layout)
        layout.addWidget(nav_container)

        self.tree_view = DropTreeView(self, self)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setColumnHidden(4, True)
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, header.ResizeMode.ResizeToContents)

        self.task_manager = BackgroundTaskManager(main_widget)
        self._position_task_manager()

        self.tree_view.doubleClicked.connect(self.handle_double_click)

        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)

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

        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self.copy_shortcut.activated.connect(self.copy_selected)
        self.cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, self)
        self.cut_shortcut.activated.connect(self.cut_selected)
        self.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self.paste_shortcut.activated.connect(self.paste_items)

        layout.addWidget(self.tree_view)

        self.root_path = self._normalize_root_path("/")
        self.current_path = "/storage/emulated/0"
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'task_manager') and self.task_manager.isVisible():
            self._position_task_manager()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'task_manager'):
            self._position_task_manager()

    def closeEvent(self, event):
        if hasattr(self, 'task_manager'):
            self.task_manager.setParent(None)
        event.accept()

    def _position_task_manager(self):
        if not hasattr(self, 'task_manager'):
            return
        mgr = self.task_manager
        parent = mgr.parentWidget() or self
        margin = 15
        x = max(margin, parent.width() - mgr.width() - margin)
        y = max(margin, parent.height() - mgr.height() - margin)
        mgr.move(x, y)
        mgr.raise_()

    def _normalize_root_path(self, path: str) -> str:
        return "/" if path == "/" else path.rstrip("/")

    def apply_device_root_path(self):
        self.root_path = self._normalize_root_path("/")
        self.current_path = "/storage/emulated/0"
        self.path_history = [self.current_path]
        self.update_path_display()

    def on_root_toggle(self):
        if self.root_checkbox.isChecked():
            has_root = self.adb_handler.enable_root()
            if not has_root:
                QMessageBox.warning(
                    self,
                    "Root Access",
                    "Root access is not available on this device.\n\n"
                    "If rooted, grant superuser permissions on the device.\n"
                    "If not rooted, adb root may not be supported on production builds."
                )
                self.root_checkbox.blockSignals(True)
                self.root_checkbox.setChecked(False)
                self.root_checkbox.blockSignals(False)
                self.use_root = False
                return
            self.use_root = True
        else:
            self.use_root = False
            self.adb_handler.root_mode = None

        self.refresh_files()

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
        selected_items = self.get_selected_items()
        if not selected_items:
            return

        self.clipboard = {
            'items': selected_items,
            'operation': 'copy'
        }
        self.status_label.setText(f"Copied {len(selected_items)} item(s) to clipboard")

    def cut_selected(self):
        selected_items = self.get_selected_items()
        if not selected_items:
            return

        self.clipboard = {
            'items': selected_items,
            'operation': 'cut'
        }
        self.status_label.setText(f"Cut {len(selected_items)} item(s)")

    def paste_items(self):
        if not self.clipboard or not self.clipboard['items']:
            self.status_label.setText("Clipboard is empty")
            return

        dest_dir = self.current_path

        
        conflicts = []
        for item in self.clipboard['items']:
            dest_path = f"{dest_dir}/{os.path.basename(item['path'])}"
            if self.adb_handler.path_exists(dest_path):
                conflicts.append(os.path.basename(item['path']))

        if conflicts:
            names = "\n".join(conflicts[:10])
            more = f"\n...and {len(conflicts) - 10} more" if len(conflicts) > 10 else ""
            reply = QMessageBox.question(
                self, "Item(s) Already Exist",
                f"The following already exist in the destination:\n\n{names}{more}\n\n"
                f"Overwrite them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.status_label.setText("Paste canceled")
                return

        operation = self.clipboard['operation']
        cut_mode = operation == 'cut'

        def run_paste():
            success_count = 0
            for item in self.clipboard['items']:
                src_path = item['path']
                dest_path = f"{dest_dir}/{os.path.basename(src_path)}"

                if operation == 'copy':
                    ok = self.adb_handler.copy_on_device(src_path, dest_path)
                else:
                    ok = self.adb_handler.move_on_device(src_path, dest_path)
                if ok:
                    success_count += 1
            return success_count

        def on_paste_done(count):
            if count > 0:
                if cut_mode:
                    self.clipboard = {'items': [], 'operation': None}
                self.show_success_message(f"Successfully {operation}ed {count} item(s)")
                self.refresh_files()
            else:
                self.show_error_message(f"Paste Error", f"Failed to {operation} items")

        self._run_modal(f"{operation.title()} {len(self.clipboard['items'])} items",
                        run_paste, on_done=on_paste_done)

    
    def show_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            self.tree_view.clearSelection()
            indexes = []
        else:
            indexes = self.tree_view.selectionModel().selectedRows()
        menu = QMenu()

        if self.clipboard and self.clipboard['items']:
            paste_action = menu.addAction("Paste")
            paste_action.triggered.connect(self.paste_items)
            menu.addSeparator()

        def _lam(name_fn):
            name_fn()

        if not indexes:
            new_file_action = menu.addAction("New File")
            new_file_action.triggered.connect(self.create_new_file)
            new_folder_action = menu.addAction("New Folder")
            new_folder_action.triggered.connect(self.create_new_folder)
            upload_file_action = menu.addAction("Upload to Device")
            upload_file_action.triggered.connect(self.upload_file_to_device)
        elif len(indexes) > 1:
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(self.copy_selected)
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(self.cut_selected)
            menu.addSeparator()
            delete_action = menu.addAction("Delete Selected")
            delete_action.triggered.connect(self.delete_selected_items)
            download_action = menu.addAction("Download to PC")
            download_action.triggered.connect(self.download_selected_items)
            copy_to_action = menu.addAction("Copy to Device Folder...")
            copy_to_action.triggered.connect(self.copy_selected_to)
            batch_rename_action = menu.addAction("Batch Rename...")
            batch_rename_action.triggered.connect(self.batch_rename_selected)
            total_size = sum(
                self.get_file_size_from_row(index.row())
                for index in indexes
                if not self.is_dir_from_row(index.row())
            )
            menu.addSeparator()
            size_label = menu.addAction(f"Total Size: {self.format_size(total_size)}")
            size_label.setEnabled(False)
        else:
            idx = indexes[0]
            name_index = self.tree_model.index(idx.row(), 0)
            type_index = self.tree_model.index(idx.row(), 1)
            item_name = self.tree_model.data(name_index)
            item_type = self.tree_model.data(type_index)

            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(self.copy_selected)
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(self.cut_selected)
            menu.addSeparator()

            if item_type == "File":
                open_action = menu.addAction("Open")
                open_action.triggered.connect(lambda checked, n=item_name: self.open_file_on_host(n))
                save_action = menu.addAction("Save to PC...")
                save_action.triggered.connect(lambda checked, n=item_name: self.copy_file_to(n))
                menu.addSeparator()
                rename_action = menu.addAction("Rename")
                rename_action.triggered.connect(lambda checked, n=item_name: self.rename_item(n))
                delete_action = menu.addAction("Delete")
                delete_action.triggered.connect(lambda checked, n=item_name: self.delete_item(n, is_dir=False))
            elif item_type == "Directory":
                save_action = menu.addAction("Save to PC...")
                save_action.triggered.connect(lambda checked, n=item_name: self.copy_folder_to(n))
                menu.addSeparator()
                rename_action = menu.addAction("Rename")
                rename_action.triggered.connect(lambda checked, n=item_name: self.rename_item(n))
                delete_action = menu.addAction("Delete")
                delete_action.triggered.connect(lambda checked, n=item_name: self.delete_item(n, is_dir=True))
        menu.exec(self.tree_view.viewport().mapToGlobal(position))

    

    def _run_background(self, name, fn, *args, on_done=None, on_error=None, refresh=False):
        task = self.task_manager.submit(name, fn, *args)

        def handle_result(val):
            is_ok = bool(val) if val is not None else False
            if is_ok:
                if on_done:
                    on_done(val)
                if refresh:
                    self.refresh_files()
            else:
                if on_error:
                    on_error()

        task.finished_signal.connect(handle_result)
        task.error_signal.connect(lambda msg: (on_error() if on_error else None))
        self._position_task_manager()
        return task

    def _run_modal(self, title, fn, *args, on_done=None, on_error=None, refresh=False):
        task = WorkerThread(title, fn, *args)

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setFixedSize(360, 130)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)

        label = QLabel(f"{title}...")
        layout.addWidget(label)

        bar = QProgressBar()
        bar.setRange(0, 0)
        layout.addWidget(bar)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        bg_btn = QPushButton("Background")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(bg_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        sent_to_background = [False]
        completed = [False]
        failed = [False]

        def reopen_dialog():
            if completed[0]:
                return
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()

        def send_to_background():
            if sent_to_background[0]:
                dlg.hide()
                return
            sent_to_background[0] = True
            dlg.hide()
            self.task_manager.add_task(task, name=title, on_reopen=reopen_dialog)
            self._position_task_manager()

        bg_btn.clicked.connect(send_to_background)

        def cancel_task():
            task.cancel()
            dlg.close()

        cancel_btn.clicked.connect(cancel_task)

        def handle_finished(val):
            completed[0] = True
            if dlg.isVisible():
                dlg.close()
            if failed[0]:
                return
            is_ok = not failed[0] and (bool(val) if val is not None else False)
            if is_ok:
                if on_done:
                    on_done(val)
                if refresh:
                    self.refresh_files()
            elif not sent_to_background[0]:
                if on_error:
                    on_error()
                else:
                    self.show_error_message("Error", f"{title} failed")

        def handle_error(msg):
            failed[0] = True
            if dlg.isVisible():
                dlg.close()
            if on_error:
                on_error()

        task.finished_signal.connect(handle_finished)
        task.error_signal.connect(handle_error)
        dlg.show()
        task.start()
        return task

    def _run_transfer(self, title, mode, src, dst, success_msg, error_msg):
        fn = self.adb_handler.pull_file if mode == 'pull' else self.adb_handler.push_file
        self._run_modal(
            title, fn, src, dst,
            on_done=lambda _: self.show_success_message(success_msg),
            on_error=lambda: self.show_error_message("Error", error_msg),
        )

    

    def copy_file_to(self, filename):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File As", filename)
        if not save_path:
            return
        self._run_transfer(
            "Copying file", 'pull', remote_path, save_path,
            f"File copied to: {save_path}",
            f"Failed to copy file: {filename}",
        )

    def copy_folder_to(self, foldername):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
        remote_path = f"{self.current_path.rstrip('/')}/{foldername}"
        save_dir = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not save_dir:
            return
        local_path = os.path.join(save_dir, foldername)
        self._run_transfer(
            "Copying folder", 'pull', remote_path, local_path,
            f"Folder copied to: {local_path}",
            f"Failed to copy folder: {foldername}",
        )

    def update_path_display(self):
        self.path_display.setText(self.current_path)
        self.back_btn.setEnabled(len(self.path_history) > 1)

    def go_back(self):
        if len(self.path_history) > 1:
            self.path_history.pop()
            self.current_path = self.path_history[-1]
            self.clear_search_on_navigation()
            self.update_path_display()
            self.refresh_files()

    def handle_double_click(self, index):
        name_index = self.tree_model.index(index.row(), 0)
        type_index = self.tree_model.index(index.row(), 1)

        item_name = self.tree_model.data(name_index)
        item_type = self.tree_model.data(type_index)

        print(f"Clicked on: '{item_name}' (Type: {item_type})")

        if not item_name:
            print("Empty item name, skipping...")
            return

        if item_type == "Directory":
            new_path = ""
            if item_name == "..":
                parent_path = "/".join(self.current_path.rstrip("/").split("/")[:-1])
                new_path = parent_path if parent_path else self.root_path
            else:
                new_path = f"{self.current_path.rstrip('/')}/{item_name}"

            print(f"Current path: {self.current_path}")
            print(f"New path: {new_path}")

            if new_path != self.current_path:
                self.current_path = new_path
                self.path_history.append(self.current_path)
                self.clear_search_on_navigation()
                self.update_path_display()
                print(f"Refreshing files for path: {self.current_path}")
                self.refresh_files()
        elif item_type == "File":
            self.open_file_on_host(item_name)

    def open_file_on_host(self, filename):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, filename)

        def run_pull():
            return self.adb_handler.pull_file(remote_path, local_path)

        def on_pulled(ok):
            if not ok:
                self.show_error_message("Open Error", f"Failed to pull file: {filename}")
                return
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

        self._run_modal("Downloading file", run_pull, on_done=on_pulled)

    

    def refresh_files(self):
        if not self.adb_handler.device_connected:
            self.status_label.setText("No ADB device connected")
            return

        
        if self._loading:
            self._refresh_pending = True
            return

        self._loading = True
        txt = f"Loading {self.current_path}..."
        self.status_label.setText(txt)
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])
        loading_item = QStandardItem("Loading...")
        loading_item.setEnabled(False)
        self.tree_model.appendRow([loading_item])

        def on_files(files):
            self._loading = False
            if files is not None:
                self.all_files = files
                self.apply_search_filter()
                self.show_status_message(f"Found {len(self.all_files)} items")
            else:
                self.show_error_message("Refresh Error", "Failed to list directory contents")

            if self._refresh_pending:
                self._refresh_pending = False
                self.refresh_files()

        task = WorkerThread(
            f"List {os.path.basename(self.current_path.rstrip('/')) or '/'}",
            self.adb_handler.list_directory, self.current_path, self.use_root,
        )
        self._refresh_task = task

        def clear_refresh_task(_=None):
            if getattr(self, '_refresh_task', None) is task:
                self._refresh_task = None

        task.finished_signal.connect(on_files)
        task.finished_signal.connect(clear_refresh_task)
        task.start()

    def clear_search_on_navigation(self):
        if self.search_bar.text():
            self.search_bar.blockSignals(True)
            self.search_bar.setText("")
            self.search_bar.blockSignals(False)
        self.apply_search_filter()

    def apply_search_filter(self):
        if not hasattr(self, 'all_files') or self.all_files is None:
            return
        search_text = self.search_bar.text().lower()
        filtered = [f for f in self.all_files if search_text in f.name.lower()]
        self.populate_view(filtered)

    def populate_view(self, files):
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])

        if files is None:
            return

        current_normalized = "/" if self.current_path == "/" else self.current_path.rstrip("/")
        if current_normalized != self.root_path:
            parent_item = QStandardItem("..")
            parent_item.setIcon(self._folder_icon)
            self.tree_model.appendRow([parent_item, QStandardItem("Directory"),
                                     QStandardItem(""), QStandardItem(""), QStandardItem("")])

        dirs = sorted([f for f in files if f.is_dir], key=lambda x: x.name.lower())
        regular_files = sorted([f for f in files if not f.is_dir], key=lambda x: x.name.lower())
        for file_item in dirs + regular_files:
            name_item = QStandardItem(file_item.name)
            if file_item.is_dir:
                name_item.setIcon(self._folder_icon)
            else:
                ext = os.path.splitext(file_item.name)[1].lower()
                if ext not in self._icon_cache:
                    icon = self._icon_provider.icon(QFileInfo(f"x{ext}"))
                    self._icon_cache[ext] = icon if not icon.isNull() else self._file_icon
                name_item.setIcon(self._icon_cache[ext])
            self.tree_model.appendRow([
                name_item,
                QStandardItem("Directory" if file_item.is_dir else "File"),
                QStandardItem(str(file_item.size) if not file_item.is_dir else ""),
                QStandardItem(file_item.permissions),
                QStandardItem(file_item.date_modified),
            ])
        for i in range(5):
            self.tree_view.resizeColumnToContents(i)

    def rename_item(self, old_name):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

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
            def run_delete():
                success_count = 0
                for name, is_dir in names_types:
                    path = f"{self.current_path.rstrip('/')}/{name}"
                    if self.adb_handler.delete_item(path, is_dir):
                        success_count += 1
                return success_count

            def on_done(count):
                if count == len(names_types):
                    self.show_success_message(f"Successfully deleted {count} items")
                else:
                    self.show_error_message("Delete Warning", f"Deleted {count}/{len(names_types)} items")
                self.refresh_files()

            self._run_modal(f"Deleting {len(names_types)} items", run_delete, on_done=on_done)

    def create_new_file(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

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
        filename = os.path.basename(file_path)
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"

        self._run_transfer(
            "Uploading file", 'push', file_path, remote_path,
            f"File uploaded to: {remote_path}",
            f"Failed to upload file: {filename}",
        )

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
        self.upload_files_and_folders_with_progress(files_to_upload)

    def upload_files_and_folders_with_progress(self, files, base_folder=None):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

        base_folder = base_folder or files[0][0] if files else None
        total = len(files)

        def run_upload():
            success_count = 0
            for file_path, rel_dir in files:
                filename = os.path.basename(file_path)
                if base_folder and rel_dir and rel_dir != ".":
                    remote_dir = f"{self.current_path.rstrip('/')}/{os.path.basename(base_folder)}/{rel_dir}".replace("\\", "/")
                elif base_folder:
                    remote_dir = f"{self.current_path.rstrip('/')}/{os.path.basename(base_folder)}".replace("\\", "/")
                else:
                    remote_dir = self.current_path.rstrip("/")
                if rel_dir:
                    self.adb_handler.create_folder(remote_dir)
                remote_path = f"{remote_dir}/{filename}".replace("\\", "/")
                ok = self.adb_handler.push_file(file_path, remote_path)
                if not ok:
                    raise Exception(f"Failed to upload {filename}")
                success_count += 1
            return success_count

        def on_done(count):
            if count == total:
                self.show_success_message(f"Successfully uploaded {count} files")
            else:
                self.show_error_message("Upload Warning", f"Uploaded {count}/{total} files")
            self.refresh_files()

        self._run_modal(f"Uploading {total} files", run_upload,
                        on_done=on_done,
                        on_error=lambda: self.show_error_message("Upload Error", "Upload failed"))

    def download_files_with_progress(self, files):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

        total = len(files)

        def run_download():
            success_count = 0
            for remote_path, local_path in files:
                ok = self.adb_handler.pull_file(remote_path, local_path)
                if not ok:
                    raise Exception(f"Failed to download {os.path.basename(remote_path)}")
                success_count += 1
            return success_count

        def on_done(count):
            if count == total:
                self.show_success_message(f"Successfully downloaded {count} files")
            else:
                self.show_error_message("Download Warning", f"Downloaded {count}/{total} files")

        self._run_modal(f"Downloading {total} files", run_download,
                        on_done=on_done,
                        on_error=lambda: self.show_error_message("Download Error", "Download failed"))

    def download_selected_items(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return

        save_dir = QFileDialog.getExistingDirectory(self, "Select Download Location")
        if not save_dir:
            return

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

        self.download_files_with_progress(files_to_download)

    def copy_selected_to(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return

        names = []
        for index in indexes:
            name_index = self.tree_model.index(index.row(), 0)
            type_index = self.tree_model.index(index.row(), 1)
            item_name = self.tree_model.data(name_index)
            is_dir = self.tree_model.data(type_index) == "Directory"
            if item_name and item_name != "..":
                names.append((item_name, is_dir))

        if not names:
            return

        from select_directory_dialog import SelectDirectoryDialog
        dialog = SelectDirectoryDialog(self, self.adb_handler, self.current_path, self.root_path, self.use_root)
        if dialog.exec() == dialog.DialogCode.Accepted:
            target_path = dialog.get_selected_path()
            if not target_path:
                return

            reply = QMessageBox.question(
                self, "Copy Items",
                f"Copy {len(names)} item(s) to '{target_path}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

            def run_copy():
                success_count = 0
                for name, is_dir in names:
                    source = f"{self.current_path.rstrip('/')}/{name}"
                    dest = f"{target_path.rstrip('/')}/{name}"
                    try:
                        if self.adb_handler.path_exists(dest):
                            self.adb_handler.delete_item(dest, is_dir)
                        if self.adb_handler.copy_on_device(source, dest):
                            success_count += 1
                    except Exception:
                        pass
                return success_count

            def on_done(count):
                if count == len(names):
                    self.show_success_message(f"Successfully copied {count} items")
                else:
                    self.show_error_message("Copy Warning", f"Copied {count}/{len(names)} items")
                self.refresh_files()

            self._run_modal(f"Copying {len(names)} items", run_copy, on_done=on_done)

    def batch_rename_selected(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return

        indexes = self.tree_view.selectionModel().selectedRows()
        if len(indexes) < 2:
            QMessageBox.information(self, "Info", "Select 2 or more items to batch rename.")
            return

        base_name, ok = QInputDialog.getText(self, "Batch Rename", "Enter base name:")
        if not ok or not base_name:
            return

        padding = len(str(len(indexes)))

        def run_rename():
            success_count = 0
            for i, index in enumerate(indexes):
                old_name_index = self.tree_model.index(index.row(), 0)
                old_name = self.tree_model.data(old_name_index)
                new_name = f"{base_name}{str(i+1).zfill(padding)}"
                old_path = f"{self.current_path.rstrip('/')}/{old_name}"
                new_path = f"{self.current_path.rstrip('/')}/{new_name}"
                if self.adb_handler.rename_item(old_path, new_path):
                    success_count += 1
            return success_count

        def on_done(count):
            if count == len(indexes):
                self.show_success_message(f"Successfully renamed {count} items")
            else:
                self.show_error_message("Rename Warning", f"Renamed {count}/{len(indexes)} items")
            self.refresh_files()

        self._run_modal(f"Renaming {len(indexes)} items", run_rename, on_done=on_done)
