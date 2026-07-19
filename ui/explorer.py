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
from ui.device_panel import DevicePanel


class ADBFileExplorer(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADB File Explorer")
        self.setGeometry(100, 100, 800, 600)

        self.adb_handler = ADBHandler()
        self._panel = None

        self.setup_ui()

        self.select_device()

        if self.adb_handler.device_connected:
            self._init_panel()
            self.refresh_files()

    @property
    def current_path(self):
        return self._panel.current_path if self._panel else "/"

    @current_path.setter
    def current_path(self, val):
        if self._panel:
            self._panel.current_path = val

    @property
    def root_path(self):
        return self._panel.root_path if self._panel else "/"

    @root_path.setter
    def root_path(self, val):
        if self._panel:
            self._panel.root_path = val

    @property
    def path_history(self):
        return self._panel.path_history if self._panel else []

    @path_history.setter
    def path_history(self, val):
        if self._panel:
            self._panel.path_history = val

    @property
    def all_files(self):
        return self._panel.all_files if self._panel else []

    @all_files.setter
    def all_files(self, val):
        if self._panel:
            self._panel.all_files = val

    @property
    def clipboard(self):
        return self._panel.clipboard if self._panel else {'items': [], 'operation': None}

    @clipboard.setter
    def clipboard(self, val):
        if self._panel:
            self._panel.clipboard = val

    @property
    def use_root(self):
        return self._panel.use_root if self._panel else False

    @use_root.setter
    def use_root(self, val):
        if self._panel:
            self._panel.use_root = val

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
        self.clipboard = {'items': [], 'operation': None}
        self.use_root = False
        self._loading = False
        self._refresh_pending = False
        self._refresh_task = None

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

        self.task_manager = BackgroundTaskManager(main_widget)

        self.toolbar = self.addToolBar("Edit")
        self.copy_action = self.toolbar.addAction("Copy")
        self.copy_action.triggered.connect(self.copy_selected)
        self.cut_action = self.toolbar.addAction("Cut")
        self.cut_action.triggered.connect(self.cut_selected)
        self.paste_action = self.toolbar.addAction("Paste")
        self.paste_action.triggered.connect(self.paste_items)

        self.install_apk_action = self.toolbar.addAction("Install APK")
        self.install_apk_action.triggered.connect(self.install_apk_dialog)
        self.install_xapk_action = self.toolbar.addAction("Install XAPK")
        self.install_xapk_action.triggered.connect(self.install_xapk_dialog)

        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self.copy_shortcut.activated.connect(self.copy_selected)
        self.cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, self)
        self.cut_shortcut.activated.connect(self.cut_selected)
        self.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self.paste_shortcut.activated.connect(self.paste_items)

        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connection_periodically)
        self.connection_timer.start(10000)

    def _init_panel(self):
        self._panel = DevicePanel(self.centralWidget(), self.adb_handler)
        layout = self.centralWidget().layout()
        layout.addWidget(self._panel)

    def resizeEvent(self, event):
        super().resizeEvent(event)
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

    def on_root_toggle(self):
        if self.root_checkbox.isChecked():
            has_root = self.adb_handler.enable_root()
            if not has_root:
                QMessageBox.warning(
                    self, "Root Access",
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
        if self._panel:
            self._panel.use_root = self.use_root
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
                pass
            else:
                self.status_label.setText("ADB device reconnected")
                self.refresh_files()

    

    def refresh_files(self):
        if self._panel:
            self._panel.refresh_files()

    def apply_search_filter(self):
        if self._panel:
            self._panel.apply_search_filter()

    def populate_view(self, files):
        if self._panel:
            self._panel.populate_view(files)

    def show_context_menu(self, position):
        if self._panel:
            self._panel.show_context_menu(position)

    def get_file_size_from_row(self, row):
        return self._panel.get_file_size_from_row(row) if self._panel else 0

    def is_dir_from_row(self, row):
        return self._panel.is_dir_from_row(row) if self._panel else False

    def format_size(self, bytes_size):
        return self._panel.format_size(bytes_size) if self._panel else f"{bytes_size} B"

    def get_selected_items(self):
        return self._panel.get_selected_items() if self._panel else []

    def copy_selected(self):
        if self._panel:
            self._panel.copy_selected()

    def cut_selected(self):
        if self._panel:
            self._panel.cut_selected()

    def paste_items(self):
        if self._panel:
            self._panel.paste_items()

    def rename_item(self, old_name):
        if self._panel:
            self._panel.rename_item(old_name)

    def delete_item(self, name, is_dir=False):
        if self._panel:
            self._panel.delete_item(name, is_dir)

    def delete_selected_items(self):
        if self._panel:
            self._panel.delete_selected_items()

    def create_new_file(self):
        if self._panel:
            self._panel.create_new_file()

    def create_new_folder(self):
        if self._panel:
            self._panel.create_new_folder()

    def upload_file_to_device(self):
        if self._panel:
            self._panel.upload_file_to_device()

    def handle_drop_event(self, event):
        if self._panel:
            self._panel.handle_drop_event(event)

    def open_file_on_host(self, filename):
        if self._panel:
            self._panel.open_file_on_host(filename)

    def copy_file_to(self, filename):
        if self._panel:
            self._panel.copy_file_to(filename)

    def copy_folder_to(self, foldername):
        if self._panel:
            self._panel.copy_folder_to(foldername)

    def download_selected_items(self):
        if self._panel:
            self._panel.download_selected_items()

    def copy_selected_to(self):
        if self._panel:
            self._panel.copy_selected_to()

    def batch_rename_selected(self):
        if self._panel:
            self._panel.batch_rename_selected()

    def clear_search_on_navigation(self):
        if self._panel:
            self._panel.clear_search_on_navigation()

    def update_path_display(self):
        if self._panel:
            self._panel.update_path_display()

    def go_back(self):
        if self._panel:
            self._panel.go_back()

    def handle_double_click(self, index):
        if self._panel:
            self._panel.handle_double_click(index)

    def show_status_message(self, text, timeout=3000):
        self.status_label.setText(text)
        if timeout:
            QTimer.singleShot(timeout, lambda: self.status_label.setText("Ready"))

    def show_error_message(self, title, msg):
        QMessageBox.critical(self, title, msg)
        self.status_label.setText(f"Error: {title}")

    def show_success_message(self, msg):
        self.status_label.setText(msg)
        QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    

    def install_apk_dialog(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select APK file", "", "APK (*.apk)")
        if not path:
            return
        self._run_modal(
            "Install APK", self.adb_handler.install_apk, path,
            on_done=lambda ok: self.show_success_message("APK installed successfully") if ok else
                self.show_error_message("Install Error", "APK installation failed"),
            on_error=lambda: self.show_error_message(
                "Install Error",
                self.adb_handler.last_error or "APK installation failed",
            ),
        )

    def install_xapk_dialog(self):
        if not self.adb_handler.device_connected:
            self.show_error_message("Connection Error", "No ADB device connected")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select XAPK file", "", "XAPK (*.xapk)")
        if not path:
            return
        self._run_modal(
            "Install XAPK", self.adb_handler.install_xapk, path,
            on_done=lambda cnt: self.show_success_message(f"Installed {cnt} APKs") if cnt and cnt > 0 else
                self.show_error_message("Install Error", "XAPK installation failed"),
            on_error=lambda: self.show_error_message(
                "Install Error",
                self.adb_handler.last_error or "XAPK installation failed",
            ),
        )

    

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
