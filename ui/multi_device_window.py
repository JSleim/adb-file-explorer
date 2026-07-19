import os
import sys
from pathlib import Path
import subprocess
import configparser

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QMessageBox, QStatusBar, QLabel, QToolBar, QDialog,
    QFileDialog, QMenu, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from handler import ADBHandler
from device_chooser import DeviceChooser
from ui.device_panel import DevicePanel
from ui.widgets import ADB_MIME
from ui.task_manager import BackgroundTaskManager
from ui.theme import LIGHT, DARK

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(os.path.abspath(__file__)).parent

CONFIG_PATH = get_base_dir() / "config.ini"

def _load_theme():
    cp = configparser.ConfigParser()
    cp.read(CONFIG_PATH)
    try:
        return cp.getboolean("app", "dark_mode")
    except Exception:
        return False


def _save_theme(dark: bool):
    cp = configparser.ConfigParser()
    cp.read(CONFIG_PATH)
    if "app" not in cp:
        cp["app"] = {}
    cp["app"]["dark_mode"] = "yes" if dark else "no"
    try:
        with open(CONFIG_PATH, "w") as f:
            cp.write(f)
    except Exception:
        pass


class MultiDeviceWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADB Explorer")
        self.setGeometry(100, 100, 1100, 600)

        self.device_panels = []
        self._dark = _load_theme()
        QApplication.instance().setStyleSheet(DARK if self._dark else LIGHT)

        
        self._setup_ui()

        
        self._initialize_panels()

        
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self._check_connections)
        self.connection_timer.start(10000)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.add_panel_btn = QPushButton("+ Add Panel")
        self.add_panel_btn.clicked.connect(self._add_panel)
        toolbar.addWidget(self.add_panel_btn)

        self.close_panel_btn = QPushButton("× Close Panel")
        self.close_panel_btn.clicked.connect(self._close_last_panel)
        self.close_panel_btn.setEnabled(False)
        toolbar.addWidget(self.close_panel_btn)

        toolbar.addSeparator()

        self.device_status_label = QLabel("Detecting devices...")
        toolbar.addWidget(self.device_status_label)

        
        menubar = self.menuBar()
        menubar.setObjectName("main_menu")
        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction("Cut", self._broadcast_cut)
        edit_menu.addAction("Copy", self._broadcast_copy)
        edit_menu.addAction("Paste", self._broadcast_paste)
        edit_menu.addSeparator()
        edit_menu.addAction("Delete", self._broadcast_delete)
        edit_menu.addAction("Rename", self._broadcast_rename)
        view_menu = menubar.addMenu("View")
        self.dark_mode_action = view_menu.addAction("Dark Mode")
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(self._dark)
        self.dark_mode_action.toggled.connect(self._toggle_theme)
        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction("Install APK...", self._install_apk_dialog)
        tools_menu.addAction("Install XAPK...", self._install_xapk_dialog)
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("Check for Updates...", self._open_updates)

        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(True)
        layout.addWidget(self.splitter)

        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        
        self.task_manager = BackgroundTaskManager(central)

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
        self.device_panels.clear()
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

    

    def _initialize_panels(self):
        initial_devices = ADBHandler().get_connected_devices()

        if not initial_devices:
            self.device_status_label.setText("No devices connected")
            self.status_label.setText("No ADB devices found. Connect a device and use + Add Panel.")
            return

        devices_list = list(initial_devices.items())
        self.device_status_label.setText(f"{len(devices_list)} device(s) connected")

        
        serial, model = devices_list[0]
        self._add_panel_for_device(serial, model)

        
        if len(devices_list) >= 2:
            serial, model = devices_list[1]
            self._add_panel_for_device(serial, model)

    def _add_panel_for_device(self, serial, model):
        try:
            handler = ADBHandler(device_serial=serial)
            panel = DevicePanel(self.splitter, handler, device_info={"model": model})
            self.splitter.addWidget(panel)
            self.device_panels.append(panel)
            panel.cross_device_drop.connect(self._on_cross_device_drop)

            
            idx = len(self.device_panels)
            self.status_label.setText(f"Added panel {idx}: {model} ({serial})")
            self._update_panel_count_ui()
            self._reconnect_drop_signals()
            return panel
        except Exception as e:
            self.status_label.setText(f"Failed to add panel: {e}")
            return None

    def _add_panel(self):
        handler = ADBHandler()
        devices = handler.get_connected_devices()
        if not devices:
            QMessageBox.information(self, "No Devices", "No ADB devices connected.")
            return

        
        existing_serials = {p.device_serial for p in self.device_panels}
        available = {s: m for s, m in devices.items() if s not in existing_serials}

        if not available:
            QMessageBox.information(self, "All Connected",
                                    "All detected devices already have panels open.")
            return

        dialog = DeviceChooser(available, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            serial = dialog.selected_device()
            model = available.get(serial, "Unknown")
            self._add_panel_for_device(serial, model)

    def _close_last_panel(self):
        if not self.device_panels:
            return
        panel = self.device_panels.pop()
        self.splitter.removeWidget(panel)
        panel.deleteLater()
        self._update_panel_count_ui()
        self._reconnect_drop_signals()
        self.status_label.setText("Panel closed")

    def _update_panel_count_ui(self):
        count = len(self.device_panels)
        self.close_panel_btn.setEnabled(count > 0)

    def _reconnect_drop_signals(self):
        
        pass  

    

    def _on_cross_device_drop(self, src_serial, paths, dest_path):
        
        dest_panel = self.sender()
        if not isinstance(dest_panel, DevicePanel):
            return

        
        src_panel = None
        for p in self.device_panels:
            if p.device_serial == src_serial:
                src_panel = p
                break

        if not src_panel:
            self.status_label.setText("Source device panel not found")
            return

        self._stream_items(src_panel, dest_panel, paths)

    def _stream_items(self, src_panel, dest_panel, paths):
        def run():
            for path in paths:
                name = path.rstrip('/').split('/')[-1]
                dest = f"{dest_panel.current_path.rstrip('/')}/{name}"
                
                test_cmd = ['adb', '-s', src_panel.device_serial, 'exec-out', 'test', '-d', path]
                test_r = subprocess.run(test_cmd, capture_output=True, timeout=10)
                is_dir = test_r.returncode == 0

                if is_dir:
                    ok = src_panel.adb_handler.stream_directory(
                        src_panel.device_serial, path,
                        dest_panel.device_serial, dest,
                    )
                else:
                    ok = src_panel.adb_handler.stream_file(
                        src_panel.device_serial, path,
                        dest_panel.device_serial, dest,
                    )
                if not ok:
                    return False
            return True

        def on_done(ok):
            if ok:
                self.status_label.setText("Stream complete")
                dest_panel.refresh_files()
            else:
                self.status_label.setText("Stream failed")

        self._run_modal(f"Stream to {dest_panel.device_name}", run, on_done=on_done)

    

    def _target_panel(self):
        for p in self.device_panels:
            if p.adb_handler.device_connected:
                return p
        return None

    def _install_apk_dialog(self):
        panel = self._target_panel()
        if not panel:
            QMessageBox.warning(self, "No Device", "No connected device panel to install to.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK (*.apk)")
        if not path:
            return
        self._run_modal(
            "Install APK", panel.adb_handler.install_apk, path,
            on_done=lambda ok: (
                self.status_label.setText("APK installed successfully") if ok
                else self.status_label.setText("APK installation failed")
            ),
        )

    def _install_xapk_dialog(self):
        panel = self._target_panel()
        if not panel:
            QMessageBox.warning(self, "No Device", "No connected device panel to install to.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select XAPK", "", "XAPK (*.xapk)")
        if not path:
            return

        def on_done(val):
            if val:
                self.status_label.setText(f"XAPK installed ({val} APK files)")

        def on_error():
            err = panel.adb_handler.last_error or "XAPK install failed"
            self.status_label.setText(err)

        self._run_modal("Install XAPK", panel.adb_handler.install_xapk, path,
                        on_done=on_done, on_error=on_error)

    

    def _active_panel(self):
        for p in self.device_panels:
            if p.tree_view.hasFocus():
                return p
        return self._target_panel()

    def _broadcast_copy(self):
        p = self._active_panel()
        if p:
            p.copy_selected()

    def _broadcast_cut(self):
        p = self._active_panel()
        if p:
            p.cut_selected()

    def _broadcast_paste(self):
        p = self._active_panel()
        if p:
            p.paste_items()

    def _broadcast_delete(self):
        p = self._active_panel()
        if p:
            p.delete_selected_items()

    def _broadcast_rename(self):
        p = self._active_panel()
        if p:
            if len(p.tree_view.selectionModel().selectedRows()) == 1:
                name = p.tree_model.data(p.tree_model.index(p.tree_view.selectionModel().selectedRows()[0].row(), 0))
                if name and name != "..":
                    p.rename_item(name)

    def _open_updates(self):
        QDesktopServices.openUrl(QUrl("https://github.com/JSleim/adb-file-explorer/releases"))

    def _toggle_theme(self, dark):
        _save_theme(dark)
        QApplication.instance().setStyleSheet(DARK if dark else LIGHT)

    

    def _check_connections(self):
        for panel in self.device_panels:
            was = panel.adb_handler.device_connected
            panel.adb_handler.device_connected = panel.adb_handler.check_adb_connection()
            if was != panel.adb_handler.device_connected:
                panel.update_connection_status()
                if not panel.adb_handler.device_connected:
                    panel.status_label.setText("Disconnected")
                else:
                    panel.status_label.setText("Reconnected")
                    panel.refresh_files()

    

    def _run_modal(self, title, fn, *args, on_done=None, on_error=None, refresh=False):
        from ui.task_manager import WorkerThread
        from PyQt6.QtWidgets import QProgressBar, QPushButton

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
                    pass  
            elif not sent_to_background[0]:
                if on_error:
                    on_error()
                else:
                    self.status_label.setText(f"{title} failed")

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
