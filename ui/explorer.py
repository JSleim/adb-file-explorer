from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from device_chooser import DeviceChooser
from handler import ADBHandler
from ui.device_panel import DevicePanel
from ui.task_manager import BackgroundTaskManager, WorkerThread


class ADBFileExplorer(QMainWindow):
    def __init__(A):
        super().__init__()
        A.setWindowTitle(A.tr("ADB File Explorer"))
        A.setGeometry(100, 100, 800, 600)
        A.adb_handler = ADBHandler()
        A._panel = None
        A.setup_ui()
        A.select_device()
        if A.adb_handler.device_connected:
            A._init_panel()
            A.refresh_files()

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
        return (
            self._panel.clipboard if self._panel else {"items": [], "operation": None}
        )

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

    def select_device(A):
        E = A.tr("ADB File Explorer - {0} ({1})")
        if not A.adb_handler.device_connected:
            QMessageBox.critical(
                A,
                A.tr("No Devices"),
                A.tr("No ADB devices found. Please connect a device and try again."),
            )
            return False
        if len(A.adb_handler.devices) > 1:
            C = DeviceChooser(A.adb_handler.devices, A)
            if C.exec() == QDialog.DialogCode.Accepted:
                B = C.selected_device()
                if B:
                    A.adb_handler = ADBHandler(device_serial=B)
                    A.setWindowTitle(A.tr(E).format(A.adb_handler.devices[B], B))
                    return True
            return False
        elif len(A.adb_handler.devices) == 1:
            D = next(iter(A.adb_handler.devices.keys()))
            A.setWindowTitle(A.tr(E).format(A.adb_handler.devices[D], D))
            return True
        return False

    def setup_ui(A):
        A.clipboard = {"items": [], "operation": None}
        A.use_root = False
        A._loading = False
        A._refresh_pending = False
        A._refresh_task = None
        B = QWidget()
        A.setCentralWidget(B)
        A.main_layout = QVBoxLayout(B)
        A.status_bar = QStatusBar()
        A.setStatusBar(A.status_bar)
        A.status_label = QLabel(A.tr("Ready"))
        A.status_bar.addWidget(A.status_label)
        A.connection_label = QLabel("")
        A.status_bar.addPermanentWidget(A.connection_label)
        A.update_connection_status()
        A.root_checkbox = QCheckBox(A.tr("Root access"))
        A.root_checkbox.setChecked(False)
        A.root_checkbox.stateChanged.connect(A.on_root_toggle)
        A.status_bar.addPermanentWidget(A.root_checkbox)
        A.task_manager = BackgroundTaskManager(B)
        A.toolbar = A.addToolBar(A.tr("Edit"))
        A.copy_action = A.toolbar.addAction(A.tr("Copy"))
        A.copy_action.triggered.connect(A.copy_selected)
        A.cut_action = A.toolbar.addAction(A.tr("Cut"))
        A.cut_action.triggered.connect(A.cut_selected)
        A.paste_action = A.toolbar.addAction(A.tr("Paste"))
        A.paste_action.triggered.connect(A.paste_items)
        A.install_apk_action = A.toolbar.addAction(A.tr("Install APK"))
        A.install_apk_action.triggered.connect(A.install_apk_dialog)
        A.install_xapk_action = A.toolbar.addAction(A.tr("Install XAPK"))
        A.install_xapk_action.triggered.connect(A.install_xapk_dialog)
        A.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, A)
        A.copy_shortcut.activated.connect(A.copy_selected)
        A.cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, A)
        A.cut_shortcut.activated.connect(A.cut_selected)
        A.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, A)
        A.paste_shortcut.activated.connect(A.paste_items)
        A.connection_timer = QTimer()
        A.connection_timer.timeout.connect(A.check_connection_periodically)
        A.connection_timer.start(10000)

    def _init_panel(A):
        A._panel = DevicePanel(A.centralWidget(), A.adb_handler)
        B = A.centralWidget().layout()
        B.addWidget(A._panel)

    def resizeEvent(A, event):
        super().resizeEvent(event)
        A._position_task_manager()

    def showEvent(A, event):
        super().showEvent(event)
        if hasattr(A, "task_manager"):
            A._position_task_manager()

    def closeEvent(A, event):
        if hasattr(A, "task_manager"):
            A.task_manager.setParent(None)
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

    def on_root_toggle(A):
        C = "Root Access"
        if A.root_checkbox.isChecked():

            def B():
                A.root_checkbox.blockSignals(True)
                A.root_checkbox.setChecked(False)
                A.root_checkbox.blockSignals(False)
                A.root_checkbox.setEnabled(True)
                A.use_root = False
                A.adb_handler.root_mode = None
                if A._panel:
                    A._panel.use_root = False

            def D(has_root):
                A.root_checkbox.setEnabled(True)
                if not has_root:
                    B()
                    QMessageBox.warning(
                        A,
                        A.tr(C),
                        A.tr(
                            "Root access is not available on this device.\n\nIf rooted, grant superuser permissions on the device.\nIf not rooted, adb root may not be supported on production builds."
                        ),
                    )
                    return
                A.use_root = True
                if A._panel:
                    A._panel.use_root = True
                    A.refresh_files()

            def E():
                B()
                QMessageBox.warning(
                    A,
                    A.tr(C),
                    A.adb_handler.last_error or A.tr("Could not enable root access."),
                )

            A.root_checkbox.setEnabled(False)
            A._run_modal(
                A.tr("Enable root access"),
                A.adb_handler.enable_root,
                on_done=D,
                on_error=E,
                on_cancel=B,
            )
        else:
            A.use_root = False
            A.adb_handler.root_mode = None
            if A._panel:
                A._panel.use_root = False
                A.refresh_files()

    def update_connection_status(A):
        if A.adb_handler.device_connected:
            A.connection_label.setText(A.tr("🟢 Connected"))
            A.connection_label.setStyleSheet("color: green;")
        else:
            A.connection_label.setText(A.tr("🔴 Disconnected"))
            A.connection_label.setStyleSheet("color: red;")

    def check_connection_periodically(A):
        B = A.adb_handler.device_connected
        A.adb_handler.device_connected = A.adb_handler.check_adb_connection()
        if B != A.adb_handler.device_connected:
            A.update_connection_status()
            if A.adb_handler.device_connected:
                A.status_label.setText(A.tr("ADB device reconnected"))
                A.refresh_files()

    def refresh_files(A):
        if A._panel:
            A._panel.refresh_files()

    def apply_search_filter(A):
        if A._panel:
            A._panel.apply_search_filter()

    def populate_view(A, files):
        if A._panel:
            A._panel.populate_view(files)

    def show_context_menu(A, position):
        if A._panel:
            A._panel.show_context_menu(position)

    def get_file_size_from_row(A, row):
        return A._panel.get_file_size_from_row(row) if A._panel else 0

    def is_dir_from_row(A, row):
        return A._panel.is_dir_from_row(row) if A._panel else False

    def format_size(A, bytes_size):
        B = bytes_size
        return A._panel.format_size(B) if A._panel else f"{B} B"

    def get_selected_items(A):
        return A._panel.get_selected_items() if A._panel else []

    def copy_selected(A):
        if A._panel:
            A._panel.copy_selected()

    def cut_selected(A):
        if A._panel:
            A._panel.cut_selected()

    def paste_items(A):
        if A._panel:
            A._panel.paste_items()

    def rename_item(A, old_name):
        if A._panel:
            A._panel.rename_item(old_name)

    def delete_item(A, name, is_dir=False):
        if A._panel:
            A._panel.delete_item(name, is_dir)

    def delete_selected_items(A):
        if A._panel:
            A._panel.delete_selected_items()

    def create_new_file(A):
        if A._panel:
            A._panel.create_new_file()

    def create_new_folder(A):
        if A._panel:
            A._panel.create_new_folder()

    def upload_file_to_device(A):
        if A._panel:
            A._panel.upload_file_to_device()

    def handle_drop_event(A, event):
        if A._panel:
            A._panel.handle_drop_event(event)

    def open_file_on_host(A, filename):
        if A._panel:
            A._panel.open_file_on_host(filename)

    def copy_file_to(A, filename):
        if A._panel:
            A._panel.copy_file_to(filename)

    def copy_folder_to(A, foldername):
        if A._panel:
            A._panel.copy_folder_to(foldername)

    def download_selected_items(A):
        if A._panel:
            A._panel.download_selected_items()

    def copy_selected_to(A):
        if A._panel:
            A._panel.copy_selected_to()

    def batch_rename_selected(A):
        if A._panel:
            A._panel.batch_rename_selected()

    def clear_search_on_navigation(A):
        if A._panel:
            A._panel.clear_search_on_navigation()

    def update_path_display(A):
        if A._panel:
            A._panel.update_path_display()

    def go_back(A):
        if A._panel:
            A._panel.go_back()

    def handle_double_click(A, index):
        if A._panel:
            A._panel.handle_double_click(index)

    def show_status_message(A, text, timeout=3000):
        B = timeout
        A.status_label.setText(text)
        if B:
            QTimer.singleShot(B, lambda: A.status_label.setText(A.tr("Ready")))

    def show_error_message(A, title, msg):
        B = title
        QMessageBox.critical(A, B, msg)
        A.status_label.setText(A.tr("Error: {0}").format(B))

    def show_success_message(A, msg):
        A.status_label.setText(msg)
        QTimer.singleShot(2000, lambda: A.status_label.setText(A.tr("Ready")))

    def install_apk_dialog(A):
        C = A.tr("APK installation failed")
        if not A.adb_handler.device_connected:
            A.show_error_message(A.tr("No ADB device connected"))
            return
        B, _ = QFileDialog.getOpenFileName(
            A, A.tr("Select APK file"), "", "APK (*.apk)"
        )
        if not B:
            return
        A._run_modal(
            A.tr("Install APK"),
            A.adb_handler.install_apk,
            B,
            on_done=lambda ok: (
                A.show_success_message(A.tr("APK installed successfully"))
                if ok
                else A.show_error_message(A.tr(C))
            ),
            on_error=lambda: A.show_error_message(
                A.tr("Install Error"), A.adb_handler.last_error or A.tr(C)
            ),
        )

    def install_xapk_dialog(A):
        C = A.tr("XAPK installation failed")
        if not A.adb_handler.device_connected:
            A.show_error_message(A.tr("No ADB device connected"))
            return
        B, _ = QFileDialog.getOpenFileName(
            A, A.tr("Select XAPK file"), "", "XAPK (*.xapk)"
        )
        if not B:
            return
        A._run_modal(
            A.tr("Install XAPK"),
            A.adb_handler.install_xapk,
            B,
            on_done=lambda cnt: (
                A.show_success_message(A.tr("Installed {0} APKs").format(cnt))
                if cnt and cnt > 0
                else A.show_error_message(A.tr(C))
            ),
            on_error=lambda: A.show_error_message(
                A.tr("Install Error"), A.adb_handler.last_error or A.tr(C)
            ),
        )

    def _run_modal(
        B, title, fn, *P, on_done=None, on_error=None, on_cancel=None, refresh=False
    ):
        K = on_cancel
        J = on_done
        E = on_error
        D = title
        C = WorkerThread(D, fn, *P)
        A = QDialog(B)
        A.setWindowTitle(D)
        A.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        A.setWindowModality(Qt.WindowModality.WindowModal)
        A.setFixedSize(360, 130)
        F = QVBoxLayout(A)
        F.setContentsMargins(16, 16, 16, 16)
        Q = QLabel(f"{D}...")
        F.addWidget(Q)
        L = QProgressBar()
        L.setRange(0, 0)
        F.addWidget(L)
        G = QHBoxLayout()
        G.addStretch()
        M = QPushButton(B.tr("Background"))
        N = QPushButton(B.tr("Cancel"))
        G.addWidget(M)
        G.addWidget(N)
        F.addLayout(G)
        H = [False]
        O = [False]
        I = [False]

        def R():
            if O[0]:
                return
            A.show()
            A.raise_()
            A.activateWindow()

        def S():
            if H[0]:
                A.hide()
                return
            H[0] = True
            A.hide()
            B.task_manager.add_task(C, name=D, on_reopen=R)
            B._position_task_manager()

        M.clicked.connect(S)

        def T():
            C.cancel()
            A.close()

        N.clicked.connect(T)

        def U(val):
            F = val
            O[0] = True
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
                    B.refresh_files()
            elif not H[0]:
                if E:
                    E()
                else:
                    B.show_error_message(B.tr("{0} failed").format(D))

        def V(msg):
            I[0] = True
            if A.isVisible():
                A.close()
            if E:
                E()

        C.finished_signal.connect(U)
        C.error_signal.connect(V)
        A.show()
        C.start()
        return C
