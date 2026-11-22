import configparser
import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
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
from ui.device_panel import DevicePanelGroup
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

        G = D.addMenu(A.tr("Tools"))
        G.addAction(A.tr("Install APK..."), A._install_apk_dialog)
        G.addAction(A.tr("Install XAPK..."), A._install_xapk_dialog)
        G.addSeparator()
        G.addAction(A.tr("Search on Device..."), A._open_global_search)

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
                A.splitter, E, device_info={"model": D}, bookmark_store=A.bookmark_store
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

    def _run_modal(
        B, title, fn, *Q, on_done=None, on_error=None, on_cancel=None, refresh=False
    ):
        K = on_cancel
        J = on_done
        E = on_error
        D = title
        from PyQt6.QtWidgets import QProgressBar as R
        from PyQt6.QtWidgets import QPushButton as L

        from ui.task_manager import WorkerThread as S

        C = S(D, fn, *Q)
        A = QDialog(B)
        A.setWindowTitle(D)
        A.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        A.setWindowModality(Qt.WindowModality.WindowModal)
        A.setFixedSize(360, 130)
        F = QVBoxLayout(A)
        F.setContentsMargins(16, 16, 16, 16)
        T = QLabel(f"{D}...")
        F.addWidget(T)
        M = R()
        M.setRange(0, 0)
        F.addWidget(M)
        G = QHBoxLayout()
        G.addStretch()
        N = L(B.tr("Background"))
        O = L(B.tr("Cancel"))
        G.addWidget(N)
        G.addWidget(O)
        F.addLayout(G)
        H = [False]
        P = [False]
        I = [False]

        def U():
            if P[0]:
                return
            A.show()
            A.raise_()
            A.activateWindow()

        def V():
            if H[0]:
                A.hide()
                return
            H[0] = True
            A.hide()
            B.task_manager.add_task(C, name=D, on_reopen=U)
            B._position_task_manager()

        N.clicked.connect(V)

        def W():
            C.cancel()
            A.close()

        O.clicked.connect(W)

        def X(val):
            F = val
            P[0] = True
            if A.isVisible():
                A.close()
            if C.is_cancelled():
                if K:
                    K()
                return
            if I[0]:
                return
            G = not I[0] and (bool(F) if F is not None else False)
            if G:
                if J:
                    J(F)
                if refresh:
                    pass
            elif not H[0]:
                if E:
                    E()
                else:
                    B.status_label.setText(B.tr("{0} failed").format(D))

        def Y(msg):
            I[0] = True
            if A.isVisible():
                A.close()
            if E:
                E()

        C.finished_signal.connect(X)
        C.error_signal.connect(Y)
        A.show()
        C.start()
        return C

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

    def _navigate_to_search_result(A, serial, remote_path, use_root=False):
        B = None
        for C in A.device_panels:
            if C.device_serial == serial:
                B = C
                break
        if B is None:
            E = ADBHandler().get_unique_devices()
            B = A._add_panel_for_device(serial, E.get(serial, A.tr("Unknown")))
        if B is None:
            return

        if use_root and B.adb_handler.root_mode != "su":
            try:
                B.adb_handler.enable_root()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Could not enable root mode for %s", serial
                )

        if use_root and B.adb_handler.root_mode == "su":
            quoted = B.adb_handler._shell_quote(remote_path)
            F = B.adb_handler._run_adb_command(
                ["exec-out", "su", "-c", f"test -d {quoted}"], timeout=10
            )
        else:
            F = B.adb_handler._run_adb_command(
                ["exec-out", "test", "-d", remote_path], timeout=10
            )
        if F.returncode == 0:
            D = remote_path
            G = None
        else:
            D = remote_path.rsplit("/", 1)[0] or "/"
            G = remote_path.rsplit("/", 1)[-1]

        H = B.add_tab(path=D)
        if H is None:
            return
        if use_root and not H.use_root:
            H.use_root = True
            H.refresh_files()
        if G:

            def _select_found_item():
                for row in range(H.tree_model.rowCount()):
                    idx = H.tree_model.index(row, 0)
                    if H.tree_model.data(idx) == G:
                        H.tree_view.setCurrentIndex(idx)
                        H.tree_view.scrollTo(idx)
                        break

            QTimer.singleShot(800, _select_found_item)
