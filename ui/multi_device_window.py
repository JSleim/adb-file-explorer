import configparser
import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from device_chooser import DeviceChooser
from handler import ADBHandler
from operation_control import is_cancelled
from search_dialog import DeviceSearchPanel
from ui.bookmarks import BookmarkStore, get_app_data_directory
from ui.device_dashboard import DeviceDashboardDialog
from ui.device_panel import DevicePanelGroup
from ui.permission_lint import PermissionLintDialog
from ui.task_manager import BackgroundTaskManager
from ui.theme import DARK, LIGHT


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(os.path.abspath(__file__)).parent


def _config_path():
    return get_app_data_directory() / "config.ini"


def _legacy_config_path():
    return get_base_dir() / "config.ini"


def _load_theme():
    B = configparser.ConfigParser()
    A = _config_path()
    D = not A.exists()
    C = _legacy_config_path() if D else A
    try:
        B.read(C, encoding="utf-8")
        E = B.getboolean("app", "dark_mode")
    except (configparser.Error, ValueError):
        return False
    if D and C.exists():
        try:
            A.parent.mkdir(parents=True, exist_ok=True)
            with A.open("w", encoding="utf-8") as F:
                B.write(F)
        except OSError:
            logging.getLogger(__name__).exception(
                "Could not migrate theme settings from %s to %s", C, A
            )
    return E


def _save_theme(dark):
    A = configparser.ConfigParser()
    B = _config_path()
    A.read(B, encoding="utf-8")
    if "app" not in A:
        A["app"] = {}
    A["app"]["dark_mode"] = "yes" if dark else "no"
    B.parent.mkdir(parents=True, exist_ok=True)
    with B.open("w", encoding="utf-8") as C:
        A.write(C)


class MultiDeviceWindow(QMainWindow):
    def __init__(A):
        super().__init__()
        A.setWindowTitle(A.tr("ADB Explorer"))
        A.setGeometry(100, 100, 1100, 600)
        A.device_panels = []
        A.clipboard = {
            "items": [],
            "operation": None,
            "source_device_serial": None,
        }
        A._last_active_panel = None
        A.bookmark_store = BookmarkStore()
        A._dark = _load_theme()
        QApplication.instance().setStyleSheet(DARK if A._dark else LIGHT)
        A._setup_ui()
        A._initialize_panels()
        A.connection_timer = QTimer()
        A.connection_timer.timeout.connect(A._check_connections)
        A.connection_timer.start(10000)

    def _setup_ui(A):
        H = QApplication.instance()
        H.focusChanged.connect(A._remember_active_panel)
        E = QWidget()
        A.setCentralWidget(E)
        F = QVBoxLayout(E)
        F.setContentsMargins(0, 0, 0, 0)
        F.setSpacing(0)
        B = QToolBar("Main")
        B.setMovable(False)
        A.addToolBar(B)
        A.add_panel_btn = QPushButton(A.tr("+ Add Panel"))
        A.add_panel_btn.setObjectName("add_panel_btn")
        A.add_panel_btn.clicked.connect(A._add_panel)
        B.addWidget(A.add_panel_btn)
        A.add_tab_btn = QPushButton(A.tr("+ Add Tab"))
        A.add_tab_btn.setObjectName("add_tab_btn")
        A.add_tab_btn.clicked.connect(A._add_tab)
        B.addWidget(A.add_tab_btn)
        A.add_tab_shortcut = QShortcut(QKeySequence("Ctrl+T"), A)
        A.add_tab_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        A.add_tab_shortcut.activated.connect(A._add_tab)
        A.close_tab_shortcut = QShortcut(QKeySequence("Ctrl+W"), A)
        A.close_tab_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        A.close_tab_shortcut.activated.connect(A._close_active_tab)
        A.global_search_btn = QPushButton(A.tr("Search Device"))
        A.global_search_btn.setObjectName("add_panel_btn")
        A.global_search_btn.clicked.connect(A._open_global_search)
        B.addWidget(A.global_search_btn)

        A.global_search_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F"), A)
        A.global_search_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        A.global_search_shortcut.activated.connect(A._open_global_search)

        B.addSeparator()
        A.device_status_label = QLabel(A.tr("Detecting devices..."))
        B.addWidget(A.device_status_label)
        D = A.menuBar()
        D.setObjectName("main_menu")
        C = D.addMenu(A.tr("Edit"))
        C.addAction(A.tr("Cut"), A._broadcast_cut)
        C.addAction(A.tr("Copy"), A._broadcast_copy)
        C.addAction(A.tr("Paste"), A._broadcast_paste)
        C.addSeparator()
        C.addAction(A.tr("Delete"), A._broadcast_delete)
        C.addAction(A.tr("Rename"), A._broadcast_rename)
        I = D.addMenu(A.tr("View"))
        A.dark_mode_action = I.addAction(A.tr("Dark Mode"))
        A.dark_mode_action.setCheckable(True)
        A.dark_mode_action.setChecked(A._dark)
        A.dark_mode_action.toggled.connect(A._toggle_theme)
        A.search_dock_action = I.addAction(A.tr("Device Search Panel"))
        A.search_dock_action.setCheckable(True)
        A.search_dock_action.setChecked(False)
        A.search_dock_action.toggled.connect(A._toggle_search_panel)
        A.dashboard_dock_action = I.addAction(A.tr("Device Dashboard Panel"))
        A.dashboard_dock_action.setCheckable(True)
        A.dashboard_dock_action.setChecked(False)
        A.dashboard_dock_action.toggled.connect(A._toggle_dashboard_panel)

        G = D.addMenu(A.tr("Tools"))
        G.addAction(A.tr("Install APK..."), A._install_apk_dialog)
        G.addAction(A.tr("Install XAPK..."), A._install_xapk_dialog)
        G.addSeparator()
        G.addAction(A.tr("Search on Device..."), A._open_global_search)
        A.dashboard_action = G.addAction(A.tr("Device Dashboard..."))
        A.dashboard_action.triggered.connect(A._open_device_dashboard)
        A.lint_action = G.addAction(A.tr("Permission Lint..."))
        A.lint_action.triggered.connect(A._open_permission_lint)

        J = D.addMenu(A.tr("Help"))
        J.addAction(A.tr("Check for Updates..."), A._open_updates)
        A.splitter = QSplitter(Qt.Orientation.Horizontal)
        A.splitter.setChildrenCollapsible(True)
        F.addWidget(A.splitter)
        A.status_bar = QStatusBar()
        A.setStatusBar(A.status_bar)
        A.status_label = QLabel(A.tr("Ready"))
        A.status_bar.addWidget(A.status_label)
        A.task_manager = BackgroundTaskManager(E)
        A.search_panel = DeviceSearchPanel(A)
        A.search_panel.file_selected.connect(A._navigate_to_search_result)
        A.search_dock = QDockWidget(A.tr("Device Search"), A)
        A.search_dock.setObjectName("device_search_dock")
        A.search_dock.setWidget(A.search_panel)
        A.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, A.search_dock)
        A.search_dock.hide()
        A.search_dock.visibilityChanged.connect(A.search_dock_action.setChecked)
        A.dashboard_panel = DeviceDashboardDialog(parent=A)
        dashboard_scroll = QScrollArea(A)
        dashboard_scroll.setWidgetResizable(True)
        dashboard_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        dashboard_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        dashboard_scroll.setWidget(A.dashboard_panel)
        A.dashboard_dock = QDockWidget(A.tr("Device Dashboard"), A)
        A.dashboard_dock.setObjectName("device_dashboard_dock")
        A.dashboard_dock.setWidget(dashboard_scroll)
        A.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, A.dashboard_dock)
        A.dashboard_dock.hide()
        A.dashboard_dock.visibilityChanged.connect(A.dashboard_dock_action.setChecked)

    def resizeEvent(A, event):
        super().resizeEvent(event)
        if hasattr(A, "task_manager") and A.task_manager.isVisible():
            A._position_task_manager()

    def showEvent(A, event):
        super().showEvent(event)
        if hasattr(A, "task_manager"):
            A._position_task_manager()

    def closeEvent(A, event):
        if hasattr(A, "task_manager"):
            A.task_manager.setParent(None)
        if hasattr(A, "search_panel"):
            A.search_panel.shutdown()
        if hasattr(A, "dashboard_panel"):
            A.dashboard_panel._shutdown_worker()
        A.device_panels.clear()
        event.accept()

    def _position_task_manager(C):
        if not hasattr(C, "task_manager"):
            return
        A = C.task_manager
        D = A.parentWidget() or C
        B = 15
        E = max(B, D.width() - A.width() - B)
        F = max(B, D.height() - A.height() - B)
        A.move(E, F)
        A.raise_()

    def _initialize_panels(A):
        E = ADBHandler().get_unique_devices()
        if not E:
            A.device_status_label.setText(A.tr("No devices connected"))
            A.status_label.setText(
                A.tr("No ADB devices found. Connect a device and use + Add Panel.")
            )
            return
        B = list(E.items())
        A.device_status_label.setText(A.tr("{0} device(s) connected").format(len(B)))
        C, D = B[0]
        A._add_panel_for_device(C, D)
        if len(B) >= 2:
            C, D = B[1]
            A._add_panel_for_device(C, D)

    def _add_panel_for_device(A, serial, model):
        D = model
        C = serial
        try:
            E = ADBHandler(device_serial=C)
            B = DevicePanelGroup(
                A.splitter,
                E,
                device_info={"model": D},
                bookmark_store=A.bookmark_store,
                clipboard=A.clipboard,
            )
            A.splitter.addWidget(B)
            A.device_panels.append(B)
            A._last_active_panel = B
            B.cross_device_drop.connect(A._on_cross_device_drop)
            B.close_requested.connect(lambda p=B: A._close_panel(p))
            B.tabs.tabBar().tabBarClicked.connect(
                lambda _index, p=B: A._remember_panel(p)
            )
            F = len(A.device_panels)
            A.status_label.setText(A.tr("Added panel {0}: {1} ({2})").format(F, D, C))
            A._update_panel_count_ui()
            A._reconnect_drop_signals()
            return B
        except Exception as G:
            A.status_label.setText(A.tr("Failed to add panel: {0}").format(G))
            return

    def _add_panel(A):
        E = ADBHandler()
        B = E.get_unique_devices()
        if not B:
            QMessageBox.information(
                A, A.tr("No Devices"), A.tr("No ADB devices connected.")
            )
            return
        C = DeviceChooser(B, A)
        if C.exec() == QDialog.DialogCode.Accepted:
            for D in C.selected_devices():
                A._add_panel_for_device(D, B.get(D, A.tr("Unknown")))

    def _add_tab(A):
        B = A._active_panel()
        if B is None:
            QMessageBox.information(
                A, A.tr("No Panel"), A.tr("Add a device panel before opening a tab.")
            )
            return
        B.add_tab()

    def _close_active_tab(B):
        A = B._active_panel()
        if A is not None:
            A.close_active_tab()

    def _close_panel(A, panel):
        B = panel
        if B not in A.device_panels:
            return
        A.device_panels.remove(B)
        if A._last_active_panel is B:
            A._last_active_panel = A.device_panels[-1] if A.device_panels else None
        B.setParent(None)
        B.prepare_for_close()
        A._update_panel_count_ui()
        A._reconnect_drop_signals()
        if hasattr(A, "dashboard_dock") and A.dashboard_dock.isVisible():
            active = A._active_panel()
            A.dashboard_panel.set_device(active.adb_handler if active else None)
        A.status_label.setText(A.tr("Panel closed"))

    def _update_panel_count_ui(A):
        C = len(A.device_panels) > 1
        for B in A.device_panels:
            if hasattr(B, "set_multi_panel_mode"):
                B.set_multi_panel_mode(C)

    def _reconnect_drop_signals(A):
        pass

    def _on_cross_device_drop(A, src_serial, paths, dest_path):
        C = A.sender()
        if not isinstance(C, DevicePanelGroup):
            return
        B = None
        for D in A.device_panels:
            if D.device_serial == src_serial:
                B = D
                break
        if not B:
            A.status_label.setText(A.tr("Source device panel not found"))
            return
        A._stream_items(B, C, paths)

    def _stream_items(A, src_panel, dest_panel, paths):
        C = dest_panel
        B = src_panel

        def D():
            D = "/"
            for path in paths:
                if is_cancelled():
                    return False
                G = A.rstrip(D).split(D)[-1]
                E = f"{C.current_path.rstrip(D)}/{G}"
                H = B.adb_handler._run_adb_command(
                    ["exec-out", "test", "-d", A], timeout=10
                )
                I = H.returncode == 0
                if I:
                    F = B.adb_handler.stream_directory(
                        B.device_serial, A, C.device_serial, E
                    )
                else:
                    F = B.adb_handler.stream_file(
                        B.device_serial, A, C.device_serial, E
                    )
                if not F:
                    return False
            return True

        def E(ok):
            if ok:
                A.status_label.setText(A.tr("Stream complete"))
                C.refresh_files()
            else:
                A.status_label.setText(A.tr("Stream failed"))

        A._run_modal(A.tr("Stream to {0}").format(C.device_name), D, on_done=E)

    def _target_panel(B):
        for A in B.device_panels:
            if A.adb_handler.device_connected:
                return A

    def _install_apk_dialog(A):
        B = A._target_panel()
        if not B:
            QMessageBox.warning(
                A, A.tr("No Device"), A.tr("No connected device panel to install to.")
            )
            return
        C, _ = QFileDialog.getOpenFileName(A, A.tr("Select APK"), "", "APK (*.apk)")
        if not C:
            return
        A._run_modal(
            A.tr("Install APK"),
            B.adb_handler.install_apk,
            C,
            on_done=lambda ok: (
                A.status_label.setText(A.tr("APK installed successfully"))
                if ok
                else A.status_label.setText(A.tr("APK installation failed"))
            ),
        )

    def _install_xapk_dialog(A):
        B = A._target_panel()
        if not B:
            QMessageBox.warning(
                A, A.tr("No Device"), A.tr("No connected device panel to install to.")
            )
            return
        C, _ = QFileDialog.getOpenFileName(A, A.tr("Select XAPK"), "", "XAPK (*.xapk)")
        if not C:
            return

        def D(val):
            if val:
                A.status_label.setText(
                    A.tr("XAPK installed ({0} APK files)").format(val)
                )

        def E():
            C = B.adb_handler.last_error or A.tr("XAPK install failed")
            A.status_label.setText(C)

        A._run_modal(
            A.tr("Install XAPK"), B.adb_handler.install_xapk, C, on_done=D, on_error=E
        )

    def _active_panel(A):
        if A._last_active_panel in A.device_panels:
            return A._last_active_panel
        for B in A.device_panels:
            if B.contains_focus():
                A._last_active_panel = B
                return B
        return A._target_panel()

    def _remember_panel(A, panel):
        B = panel
        if B in A.device_panels:
            A._last_active_panel = B
            if hasattr(A, "dashboard_dock") and A.dashboard_dock.isVisible():
                A.dashboard_panel.set_device(B.adb_handler)

    def _remember_active_panel(C, _old_widget, new_widget):
        A = new_widget
        if A is None:
            return
        for B in C.device_panels:
            if A is B or B.isAncestorOf(A):
                C._remember_panel(B)
                return

    def _broadcast_copy(B):
        A = B._active_panel()
        if A and A.active_view:
            A.active_view.copy_selected()

    def _broadcast_cut(B):
        A = B._active_panel()
        if A and A.active_view:
            A.active_view.cut_selected()

    def _broadcast_paste(B):
        A = B._active_panel()
        if A and A.active_view:
            A.active_view.paste_items()

    def _broadcast_delete(B):
        A = B._active_panel()
        if A and A.active_view:
            A.active_view.delete_selected_items()

    def _broadcast_rename(D):
        B = D._active_panel()
        if B and B.active_view:
            A = B.active_view
            if len(A.tree_view.selectionModel().selectedRows()) == 1:
                C = A.tree_model.data(
                    A.tree_model.index(
                        A.tree_view.selectionModel().selectedRows()[0].row(), 0
                    )
                )
                if C and C != "..":
                    A.rename_item(C)

    def _open_updates(A):
        QDesktopServices.openUrl(
            QUrl("https://github.com/JSleim/adb-file-explorer/releases")
        )

    def _toggle_theme(A, dark):
        B = dark
        try:
            _save_theme(B)
        except (OSError, configparser.Error) as C:
            logging.getLogger(__name__).exception(
                "Could not save theme settings to %s", _config_path()
            )
            A.status_label.setText(A.tr("Could not save theme settings: {0}").format(C))
        A._dark = B
        QApplication.instance().setStyleSheet(DARK if B else LIGHT)

    def _check_connections(B):
        for A in B.device_panels:
            C = A.adb_handler.device_connected
            A.adb_handler.device_connected = A.adb_handler.check_adb_connection()
            if C != A.adb_handler.device_connected:
                A.update_connection_status()
                if not A.adb_handler.device_connected:
                    A.status_label.setText(B.tr("Disconnected"))
                else:
                    A.status_label.setText(B.tr("Reconnected"))
                    A.refresh_files()
                    if (
                        hasattr(B, "dashboard_dock")
                        and B.dashboard_dock.isVisible()
                        and B._active_panel() is A
                    ):
                        B.dashboard_panel.refresh()

    def _create_modal_dialog(self, title: str):
        from PyQt6.QtWidgets import QProgressBar, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setFixedSize(360, 130)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel(f"{title}..."))

        progress = QProgressBar()
        progress.setRange(0, 0)
        layout.addWidget(progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        bg_btn = QPushButton(self.tr("Background"))
        cancel_btn = QPushButton(self.tr("Cancel"))
        btn_row.addWidget(bg_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        return dialog, bg_btn, cancel_btn

    def _handle_modal_finished(
        self, val, title, worker, state, on_done, on_error, on_cancel
    ):
        state["finished"] = True
        if worker.is_cancelled():
            if on_cancel:
                on_cancel()
            return
        if state["errored"]:
            return

        if val:
            if on_done:
                on_done(val)
        elif not state["backgrounded"]:
            if on_error:
                on_error()
            else:
                self.status_label.setText(self.tr("{0} failed").format(title))

    def _run_modal(
        self, title, fn, *args, on_done=None, on_error=None, on_cancel=None, refresh=False
    ):
        from ui.task_manager import WorkerThread

        worker = WorkerThread(title, fn, *args)
        dialog, bg_btn, cancel_btn = self._create_modal_dialog(title)
        state = {"backgrounded": False, "finished": False, "errored": False}

        def reopen():
            if not state["finished"]:
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()

        def move_to_background():
            dialog.hide()
            if not state["backgrounded"]:
                state["backgrounded"] = True
                self.task_manager.add_task(worker, name=title, on_reopen=reopen)
                self._position_task_manager()

        def cancel_task():
            worker.cancel()
            dialog.close()

        def on_finished(val):
            if dialog.isVisible():
                dialog.close()
            self._handle_modal_finished(
                val, title, worker, state, on_done, on_error, on_cancel
            )

        def on_worker_error(msg):
            state["errored"] = True
            if dialog.isVisible():
                dialog.close()
            if on_error:
                on_error()

        bg_btn.clicked.connect(move_to_background)
        cancel_btn.clicked.connect(cancel_task)
        worker.finished_signal.connect(on_finished)
        worker.error_signal.connect(on_worker_error)

        dialog.show()
        worker.start()
        return worker

    def _open_global_search(A):
        B = A._active_panel()
        A.search_panel.refresh_devices(B.device_serial if B else None)
        A.search_panel.set_use_root(
            bool(B and B.active_view and getattr(B.active_view, "use_root", False))
        )
        A.search_dock.show()
        A.resizeDocks([A.search_dock], [380], Qt.Orientation.Horizontal)
        A.search_dock.raise_()
        A.search_panel.focus_search()

    def _toggle_search_panel(A, visible):
        if visible:
            A._open_global_search()
        else:
            A.search_dock.hide()

    def _open_device_dashboard(A):
        B = A._active_panel()
        A.dashboard_panel.set_device(B.adb_handler if B else None)
        A.dashboard_dock.show()
        A.resizeDocks([A.dashboard_dock], [380], Qt.Orientation.Horizontal)
        A.dashboard_dock.raise_()

    def _toggle_dashboard_panel(A, visible):
        if visible:
            A._open_device_dashboard()
        else:
            A.dashboard_dock.hide()

    def _open_permission_lint(A):
        B = A._active_panel()
        if not B:
            QMessageBox.information(
                A, A.tr("No Devices"), A.tr("No device panel is open.")
            )
            return
        C = B.active_view
        D = PermissionLintDialog(
            B.adb_handler,
            start_path=C.current_path if C else "/",
            use_root=bool(C and getattr(C, "use_root", False)),
            parent=A,
        )
        D.item_selected.connect(A._navigate_to_search_result)
        D.exec()

    def _get_or_create_device_panel(self, serial: str):
        for panel in self.device_panels:
            if panel.device_serial == serial:
                return panel
        devices = ADBHandler().get_unique_devices()
        return self._add_panel_for_device(serial, devices.get(serial, self.tr("Unknown")))

    def _is_remote_directory(self, panel, remote_path: str, use_root: bool) -> bool:
        if use_root and panel.adb_handler.root_mode == "su":
            quoted = panel.adb_handler._shell_quote(remote_path)
            res = panel.adb_handler._run_adb_command(
                ["exec-out", "su", "-c", f"test -d {quoted}"], timeout=10
            )
        else:
            res = panel.adb_handler._run_adb_command(
                ["exec-out", "test", "-d", remote_path], timeout=10
            )
        return res.returncode == 0

    def _focus_item_in_tab(self, tab, filename: str, retries: int = 10):
        for row in range(tab.tree_model.rowCount()):
            idx = tab.tree_model.index(row, 0)
            if tab.tree_model.data(idx) == filename:
                tab.tree_view.setCurrentIndex(idx)
                tab.tree_view.scrollTo(idx)
                tab.tree_view.setFocus()
                return

        # Если список файлов ещё загружается в фоне — повторяем проверку каждые 150 мс
        if retries > 0:
            QTimer.singleShot(
                150, lambda: self._focus_item_in_tab(tab, filename, retries - 1)
            )

    def _navigate_to_search_result(
        self, serial, remote_path, use_root=False, is_directory=None
    ):
        panel = self._get_or_create_device_panel(serial)
        if panel is None:
            return

        if use_root and panel.adb_handler.root_mode != "su":
            try:
                panel.adb_handler.enable_root()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Could not enable root mode for %s", serial
                )

        if is_directory is None:
            is_directory = self._is_remote_directory(panel, remote_path, use_root)

        if is_directory:
            target_dir, target_file = remote_path, None
        else:
            parent, _, name = remote_path.rpartition("/")
            target_dir = parent or "/"
            target_file = name

        tab = panel.add_tab(path=target_dir)
        if tab is None:
            return

        if use_root and not tab.use_root:
            tab.use_root = True
            tab.refresh_files()

        if target_file:
            QTimer.singleShot(150, lambda: self._focus_item_in_tab(tab, target_file))
