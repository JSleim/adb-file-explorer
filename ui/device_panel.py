_A4 = "This folder is already in favorites"
_A3 = "Could not load favorites: {0}"
_A2 = "Hide navigation pane"
_A1 = "Documents"
_A0 = "ScrollRightButton"
_z = "Import cancelled"
_y = "Create failed"
_x = "Created '{0}'"
_w = "Delete '{0}'?"
_v = "Delete folder '{0}' and all of its contents, including subfolders?"
_u = "Failed to copy {0}"
_t = "Add to favorites"
_s = "New Folder"
_r = "New File"
_q = "is_dir"
_p = "_position_task_manager"
_o = "color: red; font-size: 10px; padding: 0 8px 2px 8px;"
_n = "Close device panel"
_m = "Close this device panel"
_l = "panel_close_btn"
_k = "device_header"
_j = "panel_header"
_i = "right"
_h = "left"
_g = "ScrollLeftButton"
_f = "cancel"
_e = "Copy"
_d = "File"
_c = "Modified"
_b = "Permissions"
_a = "Size"
_Z = "Type"
_Y = "color: green; font-size: 10px; padding: 0 8px 2px 8px;"
_X = "🔴 Disconnected"
_W = "🟢 Connected"
_V = "folder"
_U = "existing_names_by_directory"
_T = "directories"
_S = "files"
_R = "Delete"
_Q = "Rename"
_P = "task_manager"
_O = "Name"
_N = "/storage/emulated/0"
_M = "favorite"
_L = "note"
_K = "operation"
_J = "kind"
_I = "Directory"
_H = "name"
_G = ".."
_F = "items"
_E = "path"
_D = True
_C = False
_B = "/"
_A = None
import os, re, subprocess, sys, tempfile, uuid, logging
from datetime import datetime
from PyQt6.QtCore import (
    QCoreApplication,
    QEvent,
    QFileInfo,
    QItemSelectionModel,
    QPoint,
    QSize,
    QStringListModel,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyleOptionButton,
    QTabBar,
    QTabWidget,
    QToolButton,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import (
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from handler import ADBHandler
from ui.bookmarks import BookmarkStore
from operation_control import is_cancelled
from ui.task_manager import WorkerThread
from ui.widgets import DropTreeView
from ui.windows_drag import (
    build_manifest_for_paths,
    cancel_windows_drag,
    native_drag_available,
    start_windows_drag,
    wait_for_windows_drag,
)

_logger = logging.getLogger(__name__)


def _natural_sort_key(value):
    return tuple(
        (1, int(A)) if A.isdigit() else (0, A)
        for A in re.split("([0-9]+)", value.casefold())
    )


class SortableStandardItem(QStandardItem):
    def __lt__(A, other):
        B = other
        C = A.data(Qt.ItemDataRole.UserRole)
        D = B.data(Qt.ItemDataRole.UserRole)
        if C is not _A and D is not _A:
            return C < D
        return _natural_sort_key(A.text()) < _natural_sort_key(B.text())


class ApplyToAllCheckBox(QCheckBox):
    def paintEvent(C, event):
        super().paintEvent(event)
        if not C.isChecked():
            return
        E = QStyleOptionButton()
        C.initStyleOption(E)
        A = C.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, E, C)
        if not A.isValid():
            return
        F = A.left() + 4, A.top() + 8
        D = A.left() + 7, A.top() + 11
        G = A.left() + 12, A.top() + 5
        B = QPainter(C)
        B.setRenderHint(QPainter.RenderHint.Antialiasing)
        B.setPen(
            QPen(
                Qt.GlobalColor.black,
                3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        B.drawLine(*F, *D)
        B.drawLine(*D, *G)
        B.setPen(
            QPen(
                Qt.GlobalColor.white,
                1.5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        B.drawLine(*F, *D)
        B.drawLine(*D, *G)


class PathBreadcrumbs(QWidget):
    def __init__(A, panel):
        C = "Edit path"
        B = panel
        super().__init__(B)
        A._panel = B
        A._layout = QHBoxLayout(A)
        A._layout.setContentsMargins(2, 0, 2, 0)
        A._layout.setSpacing(4)
        A._scroll_area = QScrollArea(A)
        A._scroll_area.setObjectName("path_breadcrumb_scroll")
        A._scroll_area.setWidgetResizable(_C)
        A._scroll_area.viewport().setObjectName("path_breadcrumb_viewport")
        A._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        A._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        A._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        A._scroll_area.setMinimumWidth(0)
        A._scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        A._scroll_area.setFixedHeight(24)
        A._content = QWidget()
        A._content.setObjectName("path_breadcrumb_content")
        A._content_layout = QHBoxLayout(A._content)
        A._content_layout.setContentsMargins(0, 0, 0, 0)
        A._content_layout.setSpacing(0)
        A._scroll_area.setWidget(A._content)
        A._scroll_area.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum: A._scroll_to_end()
        )
        A._layout.addWidget(A._scroll_area, 1)
        A._edit_button = QToolButton(A)
        A._edit_button.setObjectName("path_breadcrumb_edit")
        A._edit_button.setText("✎")
        A._edit_button.setToolTip(A.tr(C))
        A._edit_button.setAccessibleName(A.tr(C))
        A._edit_button.setAutoRaise(_D)
        A._edit_button.clicked.connect(B.focus_address_bar)
        A._layout.addWidget(A._edit_button)
        A.setMinimumWidth(0)
        A.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        A.set_path(B.current_path)

    def sizeHint(A):
        return QSize(180, 24)

    def minimumSizeHint(A):
        return QSize(0, 24)

    def set_path(A, path):
        A._content.setMinimumSize(0, 0)
        while A._content_layout.count():
            J = A._content_layout.takeAt(0)
            E = J.widget()
            if E is not _A:
                E.deleteLater()
        K = [A for A in path.split(_B) if A]
        C = [(_B, _B)]
        F = ""
        for G in K:
            F += f"/{G}"
            C.append((G, F))
        for H, (L, D) in enumerate(C):
            if H:
                I = QLabel("›", A)
                I.setObjectName("path_breadcrumb_separator")
                A._content_layout.addWidget(I)
            B = QToolButton(A)
            B.setObjectName(
                "path_breadcrumb_current"
                if H == len(C) - 1
                else "path_breadcrumb_segment"
            )
            B.setText(L)
            B.setToolTip(D)
            B.setAccessibleName(A.tr("Navigate to {0}").format(D))
            B.setAutoRaise(_D)
            B.setCursor(Qt.CursorShape.PointingHandCursor)
            B.clicked.connect(
                lambda _checked=_C, destination=D: A._panel.navigate_to(destination)
            )
            A._content_layout.addWidget(B)
        QTimer.singleShot(0, A._update_content_size)

    def _update_content_size(A):
        A._content_layout.activate()
        B = A._content_layout.sizeHint()
        A._content.setMinimumSize(B)
        A._content.resize(B)
        A._content.updateGeometry()
        A._scroll_to_end()

    def _scroll_to_end(B):
        A = B._scroll_area.horizontalScrollBar()
        A.setValue(A.maximum())


class PathInput(QLineEdit):
    def __init__(A, panel):
        super().__init__()
        A._panel = panel
        A._completion_model = QStringListModel(A)
        A._completer = QCompleter(A._completion_model, A)
        A._completion_paths = set()
        A._loaded_completion_paths = set()
        A._requested_completion_paths = set()
        A._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        A._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        A._completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        A._completer.activated.connect(A._accept_completion)
        A._completer.popup().setObjectName("path_completion_popup")
        A.setCompleter(A._completer)
        A.installEventFilter(A)
        A.textEdited.connect(A._show_completions)
        A.returnPressed.connect(A._navigate)

    def update_completions(A, items):
        B = A._panel.current_path.rstrip(_B) or _B
        A._loaded_completion_paths.add(B)
        C = [A for A in B.split(_B) if A]
        A._completion_paths.update(
            {_B + _B.join(C[:A]) + _B for A in range(1, len(C) + 1)}
        )
        A.add_directory_completions(B, items)

    def add_directory_completions(A, path, items):
        B = path.rstrip(_B)
        A._loaded_completion_paths.add(B or _B)
        A._completion_paths.update(
            f"{B}/{A.name}/" for A in items or [] if A.is_dir and A.name != _G
        )
        A._completion_model.setStringList(sorted(A._completion_paths))

    def _request_directory_completions(A, path):
        B = path
        B = B.rstrip(_B) or _B
        if (
            B in A._loaded_completion_paths
            or B in A._requested_completion_paths
            or not A._panel.adb_handler.device_connected
        ):
            return
        A._requested_completion_paths.add(B)
        C = WorkerThread(
            A.tr("Complete path {0}").format(B),
            A._panel.adb_handler.list_directory,
            B,
            A._panel.use_root,
        )
        A._panel._path_completion_tasks.add(C)

        def D(items):
            C = items
            A._requested_completion_paths.discard(B)
            if A._panel._closing:
                return
            if C is _A:
                A._panel.status_label.setText(
                    A.tr("Failed to load path suggestions for {0}").format(B)
                )
                return
            A.add_directory_completions(B, C)
            D = A.text()
            if D.startswith(f"{B.rstrip(_B)}/"):
                A._completer.setCompletionPrefix(D)
                A._completer.complete()

        C.finished_signal.connect(D)
        C.error_signal.connect(
            lambda error: A._panel.status_label.setText(
                A.tr("Path suggestions failed: {0}").format(error)
            )
        )

        def E():
            A._panel._path_completion_tasks.discard(C)
            A._panel._delete_after_background_tasks()

        C.finished.connect(E)
        C.start()

    def _show_completions(A, text):
        B = text
        if not B:
            A._completer.popup().hide()
            return
        if B.endswith(_B):
            A._request_directory_completions(B)
        A._completer.setCompletionPrefix(B)
        A._completer.complete()

    def _accept_completion(A, completion):
        B = completion
        A.setText(B)
        A.setCursorPosition(len(B))
        A._completer.popup().hide()
        A._request_directory_completions(B)

    def _try_accept_completion(A):
        A._completer.setCompletionPrefix(A.text())
        A._completer.setCurrentRow(0)
        B = A._completer.currentCompletion()
        if not B:
            return _C
        A._accept_completion(B)
        return _D

    def eventFilter(B, watched, event):
        C = watched
        A = event
        if (
            C is B
            and A.type() == QEvent.Type.KeyPress
            and A.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Right)
            and (A.key() == Qt.Key.Key_Tab or B.cursorPosition() == len(B.text()))
            and B._try_accept_completion()
        ):
            A.accept()
            return _D
        return super().eventFilter(C, A)

    def keyPressEvent(A, event):
        B = event
        C = B.key()
        if C == Qt.Key.Key_Escape:
            A.setText(A._panel.current_path)
            A._panel.show_breadcrumbs()
            B.accept()
            return
        if (
            C == Qt.Key.Key_Tab
            or C == Qt.Key.Key_Right
            and A.cursorPosition() == len(A.text())
        ) and A._try_accept_completion():
            B.accept()
            return
        super().keyPressEvent(B)

    def _navigate(A):
        B = A.text().strip()
        if not B:
            return
        if B.startswith(_B):
            C = B
        else:
            C = f"{A._panel.current_path.rstrip(_B)}/{B}"
        A._panel.navigate_to(C)
        A._panel.show_breadcrumbs()


class DevicePanel(QWidget):
    cross_device_drop = pyqtSignal(str, list, str)
    favorite_requested = pyqtSignal(str, str)
    close_requested = pyqtSignal()
    path_changed = pyqtSignal(str)

    def __init__(
        A,
        parent,
        adb_handler,
        device_info=_A,
        start_path=_A,
        compact_header=_C,
        clipboard=_A,
    ):
        B = clipboard
        super().__init__(parent)
        A.adb_handler = adb_handler
        A.device_info = device_info or {}
        A.clipboard = B if B is not _A else {_F: [], _K: _A}
        A.use_root = _C
        A._loading = _C
        A._refresh_pending = _C
        A._refresh_task = _A
        A._path_completion_tasks = set()
        A._close_wait_tasks = set()
        A._closing = _C
        A._icon_provider = QFileIconProvider()
        A._folder_icon = A._icon_provider.icon(QFileIconProvider.IconType.Folder)
        A._file_icon = A._icon_provider.icon(QFileIconProvider.IconType.File)
        A._icon_cache = {}
        A.root_path = _B
        A.current_path = start_path or _N
        A.path_history = [A.current_path]
        A._history_index = 0
        A.all_files = []
        A._setup_ui()
        A._setup_context_menu()
        if compact_header:
            A.device_header.parentWidget().hide()
            A.conn_label.hide()
        A.update_path_display()

    @property
    def device_serial(self):
        return self.adb_handler.device_serial or ""

    @property
    def device_name(self):
        A = self
        B = A.device_serial
        C = A.device_info.get("model") or A.adb_handler.devices.get(B, "")
        return C or B

    def _setup_ui(A):
        J = "font-size: 10px; color: #888; padding: 0 4px;"
        B = QVBoxLayout(A)
        B.setContentsMargins(0, 0, 0, 0)
        B.setSpacing(2)
        H = QWidget()
        H.setObjectName(_j)
        E = QHBoxLayout(H)
        E.setContentsMargins(6, 2, 4, 2)
        A.device_header = QLabel(A.device_name)
        A.device_header.setObjectName(_k)
        E.addWidget(A.device_header)
        E.addStretch()
        A.close_btn = QPushButton("X")
        A.close_btn.setObjectName(_l)
        A.close_btn.setToolTip(A.tr(_m))
        A.close_btn.setAccessibleName(A.tr(_n))
        A.close_btn.setFixedSize(24, 24)
        A.close_btn.clicked.connect(A.close_requested.emit)
        E.addWidget(A.close_btn)
        B.addWidget(H)
        A.conn_label = QLabel(A.tr(_W) if A.adb_handler.device_connected else A.tr(_X))
        A.conn_label.setStyleSheet(_Y)
        B.addWidget(A.conn_label)
        C = QHBoxLayout()
        C.setSpacing(4)
        A.back_btn = QPushButton("<")
        A.back_btn.setMaximumWidth(36)
        A.back_btn.setObjectName("back_btn")
        A.back_btn.clicked.connect(A.go_back)
        C.addWidget(A.back_btn)
        A.up_btn = QPushButton("^")
        A.up_btn.setMaximumWidth(36)
        A.up_btn.setObjectName("up_btn")
        A.up_btn.clicked.connect(A.go_up)
        C.addWidget(A.up_btn)
        A.path_display = PathInput(A)
        A.path_display.setObjectName("path_display")
        A.path_breadcrumbs = PathBreadcrumbs(A)
        A.path_stack = QStackedWidget()
        A.path_stack.setObjectName("path_stack")
        A.path_stack.addWidget(A.path_breadcrumbs)
        A.path_stack.addWidget(A.path_display)
        A.path_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        A.path_stack.setCurrentWidget(A.path_breadcrumbs)
        C.addWidget(A.path_stack)
        I = QPushButton("↻")
        I.setMaximumWidth(32)
        I.clicked.connect(A.refresh_files)
        C.addWidget(I)
        F = QWidget()
        F.setObjectName("panel_nav")
        F.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        F.setLayout(C)
        B.addWidget(F)
        A.search_bar = QLineEdit()
        A.search_bar.setPlaceholderText(A.tr("Filter files"))
        A.search_bar.setObjectName("search_bar")
        A.search_bar.textChanged.connect(A.apply_search_filter)
        B.addWidget(A.search_bar)
        A.tree_view = DropTreeView(A, A)
        A.tree_model = QStandardItemModel()
        A.tree_model.setHorizontalHeaderLabels(
            [A.tr(_O), A.tr(_Z), A.tr(_a), A.tr(_b), A.tr(_c)]
        )
        A.tree_view.setModel(A.tree_model)
        A.tree_view.selectionModel().selectionChanged.connect(A.update_selection_count)
        A.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        A.tree_view.setSortingEnabled(_D)
        D = A.tree_view.header()
        D.setStretchLastSection(_C)
        D.setSectionResizeMode(0, D.ResizeMode.Stretch)
        for K in (1, 2, 3, 4):
            D.setSectionResizeMode(K, D.ResizeMode.ResizeToContents)
        A.tree_view.doubleClicked.connect(A.handle_double_click)
        A.tree_view.activated.connect(A.handle_double_click)
        A._setup_shortcuts()
        B.addWidget(A.tree_view)
        A.status_label = QLabel(A.tr("Ready"))
        A.status_label.setStyleSheet(J)
        A.selection_count_label = QLabel(A.tr("0 items selected"))
        A.selection_count_label.setObjectName("selection_count_label")
        A.selection_count_label.setStyleSheet(J)
        G = QHBoxLayout()
        G.addWidget(A.status_label)
        G.addStretch()
        G.addWidget(A.selection_count_label)
        B.addLayout(G)
        if A.adb_handler.device_connected:
            A.refresh_files()
        else:
            A.status_label.setText(A.tr("No ADB device connected"))

    def _setup_context_menu(A):
        A.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        A.tree_view.customContextMenuRequested.connect(A.show_context_menu)

    def _setup_shortcuts(A):
        A._shortcuts = []
        D = (
            (QKeySequence.StandardKey.Copy, A.copy_selected),
            (QKeySequence.StandardKey.Cut, A.cut_selected),
            (QKeySequence.StandardKey.Paste, A.paste_items),
            (QKeySequence(Qt.Key.Key_Delete), A._shortcut_delete),
            (QKeySequence(Qt.Key.Key_F2), A._shortcut_rename),
            (QKeySequence("Alt+Left"), A.go_back),
            (QKeySequence("Alt+Right"), A.go_forward),
            (QKeySequence("Alt+Up"), A.go_up),
            (QKeySequence(Qt.Key.Key_F5), A.refresh_files),
            (QKeySequence("Ctrl+F"), A.focus_filter),
            (QKeySequence("Ctrl+L"), A.focus_address_bar),
        )
        for E, F in D:
            B = QShortcut(E, A)
            B.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            B.activated.connect(F)
            A._shortcuts.append(B)
        C = QShortcut(QKeySequence(Qt.Key.Key_Backspace), A.tree_view)
        C.setContext(Qt.ShortcutContext.WidgetShortcut)
        C.activated.connect(A.go_back)
        A._shortcuts.append(C)

    def update_connection_status(A):
        if A.adb_handler.device_connected:
            A.conn_label.setText(A.tr(_W))
            A.conn_label.setStyleSheet(_Y)
        else:
            A.conn_label.setText(A.tr(_X))
            A.conn_label.setStyleSheet(_o)

    def update_path_display(A):
        A.path_display.setText(A.current_path)
        A.path_breadcrumbs.set_path(A.current_path)
        A.path_stack.setCurrentWidget(A.path_breadcrumbs)
        A.back_btn.setEnabled(A._history_index > 0)
        A.path_changed.emit(A.current_path)

    def navigate_to(A, path):
        B = path
        if B == A.current_path:
            return
        A.path_history = A.path_history[: A._history_index + 1]
        A.path_history.append(B)
        A._history_index = len(A.path_history) - 1
        A.current_path = B
        A.clear_search_on_navigation()
        A.update_path_display()
        A.refresh_files()

    def go_up(A):
        B = _B.join(A.current_path.rstrip(_B).split(_B)[:-1]) or A.root_path
        if B != A.current_path:
            A.navigate_to(B)

    def go_back(A):
        if A._history_index > 0:
            A._history_index -= 1
            A._navigate_history()

    def go_forward(A):
        if A._history_index < len(A.path_history) - 1:
            A._history_index += 1
            A._navigate_history()

    def _navigate_history(A):
        A.current_path = A.path_history[A._history_index]
        A.clear_search_on_navigation()
        A.update_path_display()
        A.refresh_files()

    def focus_filter(A):
        A.search_bar.setFocus()
        A.search_bar.selectAll()

    def focus_address_bar(A):
        A.path_stack.setCurrentWidget(A.path_display)
        A.path_display.setFocus()
        A.path_display.selectAll()

    def show_breadcrumbs(A):
        A.path_display.setText(A.current_path)
        A.path_display.completer().popup().hide()
        A.path_breadcrumbs.set_path(A.current_path)
        A.path_stack.setCurrentWidget(A.path_breadcrumbs)

    def clear_search_on_navigation(A):
        if A.search_bar.text():
            A.search_bar.blockSignals(_D)
            A.search_bar.setText("")
            A.search_bar.blockSignals(_C)
        A.apply_search_filter()

    def start_native_drag(A, paths):
        if not native_drag_available():
            return _C
        E = build_manifest_for_paths(
            A.adb_handler, A.all_files, paths, use_root=A.use_root
        )
        B = start_windows_drag(
            A.device_serial, E, use_su=A.use_root and A.adb_handler.root_mode == "su"
        )
        if B is _A:
            return _D
        if B:
            D = getattr(A.window(), _P, _A)
            if D is not _A:
                C = WorkerThread(
                    A.tr("Copying files to Windows"), wait_for_windows_drag, B
                )
                C.add_cancel_callback(lambda: cancel_windows_drag(B))
                D.add_task(C, name=C.name)
                C.start()
                if hasattr(A.window(), _p):
                    A.window()._position_task_manager()
        return _D

    def refresh_files(A):
        if A._closing:
            return
        if not A.adb_handler.device_connected:
            A.status_label.setText(A.tr("No ADB device"))
            return
        if A._loading:
            A._refresh_pending = _D
            return
        A._loading = _D
        A.status_label.setText(A.tr("Loading {0}...").format(A.current_path))
        A.tree_model.clear()
        A.tree_model.setHorizontalHeaderLabels(
            [A.tr(_O), A.tr(_Z), A.tr(_a), A.tr(_b), A.tr(_c)]
        )
        C = QStandardItem(A.tr("Loading..."))
        C.setEnabled(_C)
        A.tree_model.appendRow([C])

        def D(files):
            B = files
            A._loading = _C
            if A._closing:
                return
            if B is not _A:
                A.all_files = B
                A.apply_search_filter()
                A.status_label.setText(A.tr("Found {0} items").format(len(A.all_files)))
            else:
                A.status_label.setText(A.tr("Failed to list directory"))
            if A._refresh_pending:
                A._refresh_pending = _C
                A.refresh_files()

        B = WorkerThread(
            f"List {os.path.basename(A.current_path.rstrip(_B))or _B}",
            A.adb_handler.list_directory,
            A.current_path,
            A.use_root,
        )
        A._refresh_task = B

        def E(_=_A):
            if getattr(A, "_refresh_task", _A) is B:
                A._refresh_task = _A

        B.finished_signal.connect(D)
        B.finished_signal.connect(E)
        B.start()

    def prepare_for_close(A):
        "Keep the panel alive until its refresh worker has stopped."
        if A._closing:
            return
        A._closing = _D
        A._refresh_pending = _C
        A.hide()
        A._delete_after_background_tasks()

    def _delete_after_background_tasks(A):
        D = [A._refresh_task, *A._path_completion_tasks]
        C = [A for A in D if A is not _A and A.isRunning()]
        if C:
            for B in C:
                if B not in A._close_wait_tasks:
                    A._close_wait_tasks.add(B)
                    B.finished.connect(A._delete_after_background_tasks)
            return
        if A._closing:
            A.deleteLater()

    def apply_search_filter(A):
        if not hasattr(A, "all_files") or A.all_files is _A:
            return
        B = A.search_bar.text().lower()
        C = [A for A in A.all_files if B in A.name.lower()]
        A.populate_view(C)

    def populate_view(A, files):
        C = files
        A.tree_model.clear()
        A.tree_model.setHorizontalHeaderLabels(
            [A.tr(_O), A.tr(_Z), A.tr(_a), A.tr(_b), A.tr(_c)]
        )
        A.update_selection_count()
        if C is _A:
            return
        J = _B if A.current_path == _B else A.current_path.rstrip(_B)
        if J != A.root_path:
            F = QStandardItem(_G)
            F.setIcon(A._folder_icon)
            A.tree_model.appendRow(
                [
                    F,
                    QStandardItem(A.tr(_I)),
                    QStandardItem(""),
                    QStandardItem(""),
                    QStandardItem(""),
                ]
            )
        K = sorted([A for A in C if A.is_dir], key=lambda x: _natural_sort_key(x.name))
        L = sorted(
            [A for A in C if not A.is_dir], key=lambda x: _natural_sort_key(x.name)
        )
        for B in K + L:
            D = SortableStandardItem(B.name)
            D.setData(
                (0 if B.is_dir else 1, _natural_sort_key(B.name)),
                Qt.ItemDataRole.UserRole,
            )
            if B.is_dir:
                D.setIcon(A._folder_icon)
            else:
                E = os.path.splitext(B.name)[1].lower()
                if E not in A._icon_cache:
                    G = A._icon_provider.icon(QFileInfo(f"x{E}"))
                    A._icon_cache[E] = G if not G.isNull() else A._file_icon
                D.setIcon(A._icon_cache[E])
            H = SortableStandardItem(str(B.size) if not B.is_dir else "")
            H.setData(B.size if not B.is_dir else _A, Qt.ItemDataRole.UserRole)
            I = SortableStandardItem(B.date_modified)
            I.setData(B.date_modified, Qt.ItemDataRole.UserRole)
            A.tree_model.appendRow(
                [
                    D,
                    SortableStandardItem(A.tr(_I) if B.is_dir else A.tr(_d)),
                    H,
                    SortableStandardItem(B.permissions),
                    I,
                ]
            )
        for M in range(5):
            A.tree_view.resizeColumnToContents(M)
        A.path_display.update_completions(C)

    def handle_double_click(A, index):
        D = index
        G = A.tree_model.index(D.row(), 0)
        H = A.tree_model.index(D.row(), 1)
        C = A.tree_model.data(G)
        E = A.tree_model.data(H)
        if not C:
            return
        if E == A.tr(_I):
            B = ""
            if C == _G:
                F = _B.join(A.current_path.rstrip(_B).split(_B)[:-1])
                B = F if F else A.root_path
            else:
                B = f"{A.current_path.rstrip(_B)}/{C}"
            if B and B != A.current_path:
                A.navigate_to(B)
        elif E == A.tr(_d):
            A.open_file_on_host(C)

    def get_selected_items(A):
        B = []
        for C in A.tree_view.selectionModel().selectedRows():
            D = A.tree_model.itemFromIndex(C.siblingAtColumn(0)).text()
            E = A.tree_model.itemFromIndex(C.siblingAtColumn(1)).text()
            B.append(
                {
                    _H: D,
                    _E: f"{A.current_path.rstrip(_B)}/{D}",
                    _q: E.lower() == "directory",
                }
            )
        return B

    def update_selection_count(A, *D):
        B = {
            B.row()
            for B in A.tree_view.selectionModel().selectedIndexes()
            if A.tree_model.item(B.row(), 0).text() != _G
        }
        C = len(B)
        A.selection_count_label.setText(A.tr("Selected items: {0}").format(C))

    def copy_selected(A):
        B = A.get_selected_items()
        if not B:
            return
        A.clipboard.update({_F: B, _K: "copy"})
        A.status_label.setText(A.tr("Copied {0} item(s)").format(len(B)))

    def cut_selected(A):
        B = A.get_selected_items()
        if not B:
            return
        A.clipboard.update({_F: B, _K: "cut"})
        A.status_label.setText(A.tr("Cut {0} item(s)").format(len(B)))

    def paste_items(A):
        if not A.clipboard or not A.clipboard[_F]:
            A.status_label.setText(A.tr("Clipboard is empty"))
            return
        D = A.current_path
        B = []
        for C in A.clipboard[_F]:
            F = f"{D}/{os.path.basename(C[_E])}"
            if A.adb_handler.path_exists(F):
                B.append(os.path.basename(C[_E]))
        if B:
            G = "\n".join(B[:10])
            H = f"\n...and {len(B)-10} more" if len(B) > 10 else ""
            I = QMessageBox.question(
                A,
                A.tr("Item(s) Already Exist"),
                A.tr(
                    "The following already exist in the destination:\n\n{0}{1}\n\nOverwrite?"
                ).format(G, H),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if I == QMessageBox.StandardButton.No:
                A.status_label.setText(A.tr("Paste canceled"))
                return
        E = A.clipboard[_K]
        J = E == "cut"

        def K():
            B = 0
            for H in A.clipboard[_F]:
                if is_cancelled():
                    return B
                C = H[_E]
                F = f"{D}/{os.path.basename(C)}"
                if E == "copy":
                    G = A.adb_handler.copy_on_device(C, F)
                else:
                    G = A.adb_handler.move_on_device(C, F)
                if G:
                    B += 1
            return B

        def L(count):
            B = count
            if B > 0:
                if J:
                    A.clipboard.update({_F: [], _K: _A})
                A.status_label.setText(A.tr("Pasted {0} item(s)").format(B))
                A.refresh_files()
            else:
                A.status_label.setText(A.tr("Paste failed"))

        A._run_modal(A.tr("Paste {0} items").format(len(A.clipboard[_F])), K, on_done=L)

    def show_context_menu(A, position):
        K = "Save to PC..."
        J = "Cut"
        G = position
        F = A.tree_view.indexAt(G)
        if not F.isValid():
            A.tree_view.clearSelection()
            D = []
        else:
            E = A.tree_view.selectionModel()
            L = E.selectedRows()
            if not any(A.row() == F.row() for A in L):
                E.clearSelection()
                E.select(
                    F,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                E.setCurrentIndex(F, QItemSelectionModel.SelectionFlag.NoUpdate)
            D = E.selectedRows()
        B = QMenu()
        if A.clipboard and A.clipboard[_F]:
            M = B.addAction(A.tr("Paste"))
            M.triggered.connect(A.paste_items)
            B.addSeparator()
        if not D:
            B.addAction(A.tr(_r), A.create_new_file)
            B.addAction(A.tr(_s), A.create_new_folder)
            B.addAction(A.tr("Upload to Device"), A.upload_file_to_device)
            B.addAction(A.tr("Import Folder from PC..."), A.import_folder_from_pc)
        elif len(D) > 1:
            B.addAction(A.tr(_e), A.copy_selected)
            B.addAction(A.tr(J), A.cut_selected)
            B.addSeparator()
            B.addAction(A.tr("Delete Selected"), A.delete_selected_items)
            B.addAction(A.tr("Download to PC"), A.download_selected_items)
            B.addAction(A.tr("Copy to Device Folder..."), A.copy_selected_to)
            B.addAction(A.tr("Batch Rename..."), A.batch_rename_selected)
            N = sum(
                A.get_file_size_from_row(B.row())
                for B in D
                if not A.is_dir_from_row(B.row())
            )
            B.addSeparator()
            O = B.addAction(A.tr("Total Size: {0}").format(A.format_size(N)))
            O.setEnabled(_C)
        else:
            H = D[0]
            C = A.tree_model.data(A.tree_model.index(H.row(), 0))
            I = A.tree_model.data(A.tree_model.index(H.row(), 1))
            B.addAction(A.tr(_e), A.copy_selected)
            B.addAction(A.tr(J), A.cut_selected)
            B.addSeparator()
            if I == A.tr(_d):
                B.addAction(A.tr("Open"), lambda n=C: A.open_file_on_host(n))
                B.addAction(A.tr(K), lambda n=C: A.copy_file_to(n))
                B.addSeparator()
                B.addAction(A.tr(_Q), lambda n=C: A.rename_item(n))
                B.addAction(A.tr(_R), lambda n=C: A.delete_item(n, is_dir=_C))
            elif I == A.tr(_I):
                if C != _G:
                    P = f"{A.current_path.rstrip(_B)}/{C}"
                    B.addAction(
                        A.tr(_t), lambda n=C, p=P: A.favorite_requested.emit(n, p)
                    )
                    B.addSeparator()
                B.addAction(A.tr(K), lambda n=C: A.copy_folder_to(n))
                B.addSeparator()
                B.addAction(A.tr(_Q), lambda n=C: A.rename_item(n))
                B.addAction(A.tr(_R), lambda n=C: A.delete_item(n, is_dir=_D))
        B.addSeparator()
        Q = B.addMenu(A.tr("Send to Device..."))
        A._populate_send_to_menu(Q, D, G)
        B.exec(A.tree_view.viewport().mapToGlobal(G))

    def _populate_send_to_menu(A, menu, indexes, position):
        I = "No other devices"
        H = "No items selected"
        C = menu
        if not indexes:
            C.addAction(A.tr(H)).setEnabled(_C)
            return
        E = A.get_selected_items()
        if not E:
            C.addAction(A.tr(H)).setEnabled(_C)
            return
        F = A.window()
        if not hasattr(F, "device_panels"):
            C.addAction(A.tr(I)).setEnabled(_C)
            return
        D = []
        for B in F.device_panels:
            G = getattr(B, "contains_view", _A)
            J = B is A or G is not _A and G(A)
            if not J and B.adb_handler.device_connected:
                D.append(B)
        if not D:
            C.addAction(A.tr(I)).setEnabled(_C)
            return
        for B in D:
            K = C.addAction(B.device_name)
            K.triggered.connect(
                lambda checked=_C, p=B, its=E: A._send_items_to_device(its, p)
            )

    def _send_items_to_device(A, items, target_panel):
        D = items
        B = target_panel

        def C():
            for C in D:
                if is_cancelled():
                    return _C
                E = f"{B.current_path.rstrip(_B)}/{C[_H]}"
                if C[_q]:
                    F = A.adb_handler.stream_directory(
                        A.device_serial,
                        C[_E],
                        B.device_serial,
                        E,
                        line_callback=lambda msg: _A,
                    )
                else:
                    F = A.adb_handler.stream_file(
                        A.device_serial, C[_E], B.device_serial, E
                    )
                if not F:
                    return _C
            return _D

        def E(ok):
            if ok:
                A.status_label.setText(
                    A.tr("Sent {0} item(s) to {1}").format(len(D), B.device_name)
                )
                B.refresh_files()
            else:
                A.status_label.setText(A.tr("Stream failed"))

        A._run_modal(A.tr("Streaming to {0}").format(B.device_name), C, on_done=E)

    def get_file_size_from_row(B, row):
        C = B.tree_model.index(row, 2)
        A = B.tree_model.data(C)
        return int(A) if A and A.isdigit() else 0

    def is_dir_from_row(A, row):
        B = A.tree_model.index(row, 1)
        return A.tree_model.data(B) == A.tr(_I)

    def format_size(C, bytes_size):
        A = bytes_size
        for B in ["B", "KB", "MB", "GB"]:
            if A < 1024.0:
                return f"{A:.1f} {B}"
            A /= 1024.0
        return f"{A:.1f} TB"

    def open_file_on_host(A, filename):
        B = filename
        if not A.adb_handler.device_connected:
            A.status_label.setText(A.tr("No connection"))
            return
        D = f"{A.current_path.rstrip(_B)}/{B}"
        E = tempfile.gettempdir()
        C = os.path.join(E, B)

        def F():
            return A.adb_handler.pull_file(D, C)

        def G(ok):
            if not ok:
                A.status_label.setText(A.tr("Failed to open {0}").format(B))
                return
            try:
                if sys.platform.startswith("win"):
                    os.startfile(C)
                elif sys.platform.startswith("darwin"):
                    subprocess.run(["open", C])
                else:
                    subprocess.run(["xdg-open", C])
                A.status_label.setText(A.tr("Opened {0}").format(B))
            except Exception:
                A.status_label.setText(A.tr("Failed to open file"))

        A._run_modal(A.tr("Downloading file"), F, on_done=G)

    def copy_file_to(A, filename):
        B = filename
        if not A.adb_handler.device_connected:
            return
        D = f"{A.current_path.rstrip(_B)}/{B}"
        C, E = QFileDialog.getSaveFileName(A, A.tr("Save File As"), B)
        if not C:
            return
        A._run_transfer(
            A.tr("Copying file"),
            D,
            C,
            A.tr("File copied: {0}").format(C),
            A.tr(_u).format(B),
        )

    def copy_folder_to(A, foldername):
        B = foldername
        if not A.adb_handler.device_connected:
            return
        E = f"{A.current_path.rstrip(_B)}/{B}"
        C = QFileDialog.getExistingDirectory(A, A.tr("Select Destination"))
        if not C:
            return
        D = os.path.join(C, B)
        A._run_transfer(
            A.tr("Copying folder"),
            E,
            D,
            A.tr("Folder copied: {0}").format(D),
            A.tr(_u).format(B),
        )

    def _run_transfer(A, title, src, dst, success_msg, error_msg):
        B = A.adb_handler.pull_file
        A._run_modal(
            title,
            B,
            src,
            dst,
            on_done=lambda _: A.status_label.setText(success_msg),
            on_error=lambda: A.status_label.setText(error_msg),
        )

    def rename_item(A, old_name):
        B = old_name
        if not A.adb_handler.device_connected:
            return
        C, D = QInputDialog.getText(
            A, A.tr(_Q), A.tr("New name for '{0}':").format(B), text=B
        )
        if D and C and C != B:
            E = f"{A.current_path.rstrip(_B)}/{B}"
            F = f"{A.current_path.rstrip(_B)}/{C}"

            def G(_):
                A.status_label.setText(A.tr("Renamed to '{0}'").format(C))
                A.refresh_files()

            def H():
                A.status_label.setText(A.tr("Rename failed"))

            A._run_modal(
                A.tr("Rename {0}").format(B),
                A.adb_handler.rename_item,
                E,
                F,
                on_done=G,
                on_error=H,
            )

    def delete_item(A, name, is_dir=_C):
        C = is_dir
        B = name
        if not A.adb_handler.device_connected:
            return
        D = A.tr(_v).format(B) if C else A.tr(_w).format(B)
        E = QMessageBox.question(
            A,
            A.tr(_R),
            D,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if E == QMessageBox.StandardButton.Yes:
            F = f"{A.current_path.rstrip(_B)}/{B}"

            def G(_):
                A.status_label.setText(A.tr("Deleted '{0}'").format(B))
                A.refresh_files()

            def H():
                A.status_label.setText(A.tr("Delete failed"))

            A._run_modal(
                A.tr("Delete {0}").format(B),
                A.adb_handler.delete_item,
                F,
                C,
                on_done=G,
                on_error=H,
            )

    def _shortcut_delete(A):
        B = A.tree_view.selectionModel().selectedRows()
        if B:
            A.delete_selected_items()

    def _shortcut_rename(A):
        C = A.tree_view.selectionModel().selectedRows()
        if len(C) != 1:
            return
        B = A.tree_model.data(A.tree_model.index(C[0].row(), 0))
        if not B or B == _G:
            return
        A.rename_item(B)

    def delete_selected_items(A):
        if not A.adb_handler.device_connected:
            return
        E = A.tree_view.selectionModel().selectedRows()
        if not E:
            return
        B = []
        for F in E:
            C = A.tree_model.data(A.tree_model.index(F.row(), 0))
            G = A.tree_model.data(A.tree_model.index(F.row(), 1))
            if C and C != _G:
                B.append((C, G == A.tr(_I)))
        if not B:
            return
        H = any(A for (B, A) in B)
        if len(B) == 1:
            C, I = B[0]
            D = A.tr(_v).format(C) if I else A.tr(_w).format(C)
        else:
            D = A.tr("Delete {0} selected items?").format(len(B))
            if H:
                D += A.tr(
                    "\nAny selected folders and all their contents, including subfolders, will also be deleted."
                )
        J = QMessageBox.question(
            A,
            A.tr(_R),
            D,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if J == QMessageBox.StandardButton.Yes:

            def K():
                C = 0
                for D, E in B:
                    if is_cancelled():
                        return C
                    F = f"{A.current_path.rstrip(_B)}/{D}"
                    if A.adb_handler.delete_item(F, E):
                        C += 1
                return C

            def L(count):
                A.status_label.setText(A.tr("Deleted {0} items").format(count))
                A.refresh_files()

            A._run_modal(A.tr("Delete {0} items").format(len(B)), K, on_done=L)

    def create_new_file(A):
        if not A.adb_handler.device_connected:
            return
        B, C = QInputDialog.getText(A, A.tr(_r), A.tr("File name:"))
        if C and B:
            D = f"{A.current_path.rstrip(_B)}/{B}"

            def E(_):
                A.status_label.setText(A.tr(_x).format(B))
                A.refresh_files()

            def F():
                A.status_label.setText(A.tr(_y))

            A._run_modal(
                A.tr("Create file {0}").format(B),
                A.adb_handler.create_file,
                D,
                on_done=E,
                on_error=F,
            )

    def create_new_folder(A):
        if not A.adb_handler.device_connected:
            return
        B, C = QInputDialog.getText(A, A.tr(_s), A.tr("Folder name:"))
        if C and B:
            D = f"{A.current_path.rstrip(_B)}/{B}"

            def E(_):
                A.status_label.setText(A.tr(_x).format(B))
                A.refresh_files()

            def F():
                A.status_label.setText(A.tr(_y))

            A._run_modal(
                A.tr("Create folder {0}").format(B),
                A.adb_handler.create_folder,
                D,
                on_done=E,
                on_error=F,
            )

    def upload_file_to_device(A):
        if not A.adb_handler.device_connected:
            return
        B, C = QFileDialog.getOpenFileName(A, A.tr("Select File to Upload"))
        if not B:
            return
        A.upload_files_and_folders([B])

    def import_folder_from_pc(A):
        if not A.adb_handler.device_connected:
            return
        B = QFileDialog.getExistingDirectory(A, A.tr("Select Folder to Import"))
        if B:
            A.upload_files_and_folders([B])

    def upload_files_and_folders(A, files):
        if not A.adb_handler.device_connected:
            return
        C = A.current_path.rstrip(_B) or _B
        try:
            B = A._build_upload_plan(files, C)
        except (OSError, RuntimeError) as D:
            A.status_label.setText(A.tr("Import from PC failed: {0}").format(D))
            return
        if not B[_S] and not B[_T]:
            A.status_label.setText(A.tr("No files to upload"))
            return
        A._run_modal(
            A.tr("Checking destination files"),
            A._inspect_upload_conflicts,
            B,
            on_done=lambda result: A._resolve_upload_conflicts(B, result[0]),
            on_error=lambda: A.status_label.setText(
                A.tr("Could not verify destination files; import was not started")
            ),
            on_cancel=lambda: A.status_label.setText(A.tr(_z)),
        )

    @staticmethod
    def _next_renamed_destination(remote_path, occupied_names):
        C = occupied_names
        G, D = remote_path.rsplit(_B, 1)
        A, E = os.path.splitext(D)
        if not A:
            A, E = D, ""
        F = 1
        while _D:
            B = f"{A} ({F}){E}"
            if B not in C:
                C.add(B)
                return f"{G}/{B}"
            F += 1

    @staticmethod
    def _build_upload_plan(files, target_path):
        K = "DevicePanel"
        E = target_path
        G = []
        F = []

        def L(error):
            raise error

        for A in files:
            if os.path.isdir(A):
                H = os.path.basename(os.path.normpath(A))
                if not H:
                    raise RuntimeError(
                        QCoreApplication.translate(
                            K, "Cannot determine the folder name for '{0}'."
                        ).format(A)
                    )
                I = f"{E.rstrip(_B)}/{H}"
                for J, O, M in os.walk(A, onerror=L):
                    B = os.path.relpath(J, A)
                    C = I
                    if B != ".":
                        B = B.replace(os.sep, _B)
                        C = f"{I}/{B}"
                    G.append(C)
                    for D in M:
                        N = os.path.join(J, D)
                        F.append((N, C, f"{C.rstrip(_B)}/{D}"))
            elif os.path.isfile(A):
                D = os.path.basename(A)
                F.append((A, E, f"{E.rstrip(_B)}/{D}"))
            else:
                raise RuntimeError(
                    QCoreApplication.translate(
                        K, "'{0}' is not a file or folder."
                    ).format(A)
                )
        return {_T: list(dict.fromkeys(G)), _S: F}

    def _inspect_upload_conflicts(A, plan):
        O = "last_error"
        C = plan
        D = {}
        C[_U] = {}
        E = {}
        for I in C[_S]:
            E.setdefault(I[1], []).append(I)
        P = list(dict.fromkeys([*C[_T], *E]))
        for B in P:
            if is_cancelled():
                return (D,)
            A.adb_handler.last_error = _A
            J = A.adb_handler._remote_path_exists(B, use_root=A.use_root)
            if J is _A:
                K = getattr(A.adb_handler, O, _A)
                raise RuntimeError(
                    A.tr("Could not verify destination folder '{0}'").format(B)
                    + (f": {K}" if K else ".")
                )
            if not J:
                C[_U][B] = set()
                continue
            A.adb_handler.last_error = _A
            L = A.adb_handler.list_directory(B, A.use_root)
            F = getattr(A.adb_handler, O, _A)
            if L is _A or F:
                raise RuntimeError(
                    A.tr("Could not list destination folder '{0}'").format(B)
                    + (f": {F}" if F else ".")
                )
            M = {A.name: A for A in L}
            C[_U][B] = set(M)
            for G, Q, N in E.get(B, ()):
                H = M.get(os.path.basename(G))
                if H is _A:
                    continue
                if H.is_dir:
                    raise RuntimeError(
                        A.tr(
                            "Cannot upload file '{0}': a folder already exists at '{1}'."
                        ).format(G, N)
                    )
                D[N] = G, H
        return (D,)

    @staticmethod
    def _format_upload_size(size):
        C = "Bytes"
        A = float(size)
        for B in (C, "KB", "MB", "GB", "TB"):
            if A < 1024 or B == "TB":
                return f"{int(A)} {B}" if B == C else f"{A:.1f} {B}"
            A /= 1024

    def _confirm_upload_conflict(A, remote_path, local_path, existing):
        E = existing
        G = os.stat(local_path)
        K = datetime.fromtimestamp(G.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        try:
            H = datetime.strptime(E.date_modified, "%Y-%m-%d %H:%M").strftime(
                "%d/%m/%Y %H:%M"
            )
        except ValueError:
            H = E.date_modified
        B = QMessageBox(A)
        B.setWindowTitle(A.tr("File already exists"))
        B.setText(A.tr("The following file already exists:"))
        B.setInformativeText(
            A.tr(
                "{0}\n\nSource: {1}, Modified {2}\nDestination: {3}, Modified {4}\n\nOverwrite replaces the existing content. Rename Destination keeps the existing file under a numbered name before uploading."
            ).format(
                remote_path,
                A._format_upload_size(G.st_size),
                K,
                A._format_upload_size(E.size),
                H,
            )
        )
        L = B.addButton(A.tr("Overwrite"), QMessageBox.ButtonRole.AcceptRole)
        I = B.addButton(A.tr(_Q), QMessageBox.ButtonRole.ActionRole)
        I.setMinimumWidth(130)
        J = B.addButton(A.tr("Skip"), QMessageBox.ButtonRole.ActionRole)
        J.setMinimumWidth(100)
        B.addButton(A.tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        C = ApplyToAllCheckBox(A.tr("Apply to all conflicts"))
        C.setObjectName("apply_to_all_conflicts")
        C.setAccessibleName(A.tr("Apply to all file conflicts"))
        C.setToolTip(
            A.tr("Use this choice for every remaining file conflict in this import.")
        )
        B.setCheckBox(C)
        B.exec()
        F = B.clickedButton()
        if F is L:
            D = "overwrite"
        elif F is I:
            D = "rename"
        elif F is J:
            D = "skip"
        else:
            D = _f
        return D, C.isChecked()

    def _resolve_upload_conflicts(A, plan, conflicts):
        F = plan
        H = {}
        I = {}
        G = F.get(_U, {})
        D = _A
        for C, (E, J) in conflicts.items():
            if D is _A:
                try:
                    B, K = A._confirm_upload_conflict(C, E, J)
                except (OSError, OverflowError, ValueError) as L:
                    A.status_label.setText(
                        A.tr(
                            "Could not read source file '{0}': {1}; import was not started"
                        ).format(E, L)
                    )
                    return
                if K and B != _f:
                    D = B
            else:
                B = D
            if B == _f:
                A.status_label.setText(A.tr("Import cancelled; no files were uploaded"))
                return
            H[C] = B
            if B == "rename":
                M = C.rsplit(_B, 1)[0] or _B
                N = G.setdefault(M, set())
                I[C] = DevicePanel._next_renamed_destination(C, N)

        def O():
            C = 0
            D = 0
            E = 0
            for J in F[_T]:
                if is_cancelled():
                    return C, D, E
                if not A.adb_handler.create_folder(J):
                    raise RuntimeError(
                        A.tr("Failed to create device folder '{0}'.").format(J)
                    )
            for K, L, B in F[_S]:
                if is_cancelled():
                    return C, D, E
                if H.get(B) == "skip":
                    D += 1
                    continue
                G = I.get(B)
                if G is not _A:
                    if not A.adb_handler.rename_item(B, G, use_root=A.use_root):
                        raise RuntimeError(
                            A.tr(
                                f"Failed to preserve existing file '{{0}}' as '{1}'."
                            ).format(B, G)
                        )
                    E += 1
                if not A.adb_handler.push_file(K, B):
                    raise RuntimeError(
                        A.tr("Failed to upload '{0}' to '{1}'.").format(K, B)
                    )
                C += 1
            return C, D, E

        def P(result):
            B, C, D = result
            A.status_label.setText(
                A.tr(
                    "Uploaded {0} files; skipped {1}; preserved {2} existing files"
                ).format(B, C, D)
            )
            A.refresh_files()

        A._run_modal(
            A.tr("Importing files from PC"),
            O,
            on_done=P,
            on_error=lambda: A.status_label.setText(A.tr("Import from PC failed")),
            on_cancel=lambda: A.status_label.setText(A.tr(_z)),
        )

    def download_selected_items(A):
        if not A.adb_handler.device_connected:
            return
        D = A.tree_view.selectionModel().selectedRows()
        if not D:
            return
        E = QFileDialog.getExistingDirectory(A, A.tr("Download Location"))
        if not E:
            return
        C = []
        for F in D:
            B = A.tree_model.data(A.tree_model.index(F.row(), 0))
            K = A.tree_model.data(A.tree_model.index(F.row(), 1))
            if not B or B == _G:
                continue
            G = f"{A.current_path.rstrip(_B)}/{B}"
            H = os.path.join(E, B)
            C.append((G, H))

        def I():
            B = 0
            for D, E in C:
                if is_cancelled():
                    return B
                if A.adb_handler.pull_file(D, E):
                    B += 1
            return B

        def J(count):
            A.status_label.setText(A.tr("Downloaded {0} files").format(count))

        A._run_modal(A.tr("Download {0} files").format(len(C)), I, on_done=J)

    def copy_selected_to(A):
        if not A.adb_handler.device_connected:
            return
        D = A.tree_view.selectionModel().selectedRows()
        if not D:
            return
        C = []
        for E in D:
            B = A.tree_model.data(A.tree_model.index(E.row(), 0))
            H = A.tree_model.data(A.tree_model.index(E.row(), 1)) == A.tr(_I)
            if B and B != _G:
                C.append((B, H))
        if not C:
            return
        from select_directory_dialog import SelectDirectoryDialog as I

        G = I(A, A.adb_handler, A.current_path, A.root_path, A.use_root)
        if G.exec() == QDialog.DialogCode.Accepted:
            F = G.get_selected_path()
            if not F:
                return
            if (
                QMessageBox.question(
                    A,
                    A.tr(_e),
                    A.tr("Copy {0} items to '{1}'?").format(len(C), F),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.No
            ):
                return

            def J():
                G = 0
                for H, K in C:
                    if is_cancelled():
                        return G
                    J = f"{A.current_path.rstrip(_B)}/{H}"
                    B = f"{F.rstrip(_B)}/{H}"
                    D = _A
                    E = _C
                    try:
                        if A.adb_handler.path_exists(B):
                            I = f"{B.rsplit(_B,1)[0]}/.adb-explorer-backup-{uuid.uuid4().hex}"
                            if not A.adb_handler._move_remote_path_for_recovery(B, I):
                                continue
                            D = I
                        E = A.adb_handler.copy_on_device(J, B)
                        if E:
                            G += 1
                    except Exception:
                        E = _C
                    finally:
                        if D:
                            if E:
                                A.adb_handler._remove_remote_partial(D)
                            else:
                                A.adb_handler._remove_remote_partial(B)
                                A.adb_handler._move_remote_path_for_recovery(D, B)
                return G

            def K(count):
                A.status_label.setText(A.tr("Copied {0} items").format(count))
                A.refresh_files()

            A._run_modal(A.tr("Copy {0} items").format(len(C)), J, on_done=K)

    def batch_rename_selected(A):
        if not A.adb_handler.device_connected:
            return
        B = A.tree_view.selectionModel().selectedRows()
        if len(B) < 2:
            QMessageBox.information(
                A, A.tr("Info"), A.tr("Select 2+ items to batch rename.")
            )
            return
        D, C = QInputDialog.getText(A, A.tr("Batch Rename"), A.tr("Base name:"))
        if not C or not D:
            return
        E = len(str(len(B)))

        def F():
            C = 0
            for F, G in enumerate(B):
                if is_cancelled():
                    return C
                H = A.tree_model.data(A.tree_model.index(G.row(), 0))
                I = f"{D}{str(F+1).zfill(E)}"
                J = f"{A.current_path.rstrip(_B)}/{H}"
                K = f"{A.current_path.rstrip(_B)}/{I}"
                if A.adb_handler.rename_item(J, K):
                    C += 1
            return C

        def G(count):
            A.status_label.setText(A.tr("Renamed {0} items").format(count))
            A.refresh_files()

        A._run_modal(A.tr("Rename {0} items").format(len(B)), F, on_done=G)

    def handle_drop_event(A, event):
        if not A.adb_handler.device_connected:
            return
        B = event.mimeData().urls()
        if not B:
            return
        C = [A.toLocalFile() for A in B]
        A.upload_files_and_folders(C)

    def _run_modal(C, title, fn, *P, on_done=_A, on_error=_A, on_cancel=_A, refresh=_C):
        J = on_cancel
        I = on_done
        E = on_error
        D = title
        B = WorkerThread(D, fn, *P)
        A = QDialog(C)
        A.setWindowTitle(D)
        A.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, _C)
        A.setWindowModality(Qt.WindowModality.WindowModal)
        A.setFixedSize(360, 130)
        F = QVBoxLayout(A)
        F.setContentsMargins(16, 16, 16, 16)
        Q = QLabel(f"{D}...")
        F.addWidget(Q)
        K = QProgressBar()
        K.setRange(0, 0)
        F.addWidget(K)
        G = QHBoxLayout()
        G.addStretch()
        H = QPushButton(C.tr("Background"))
        L = QPushButton(C.tr("Cancel"))
        G.addWidget(H)
        G.addWidget(L)
        F.addLayout(G)
        M = [_C]
        N = [_C]
        O = [_C]

        def R():
            if N[0]:
                return
            A.show()
            A.raise_()
            A.activateWindow()

        def S():
            if M[0]:
                A.hide()
                return
            E = C.window()
            F = getattr(E, _P, _A)
            if F is _A:
                return
            M[0] = _D
            A.hide()
            F.add_task(B, name=D, on_reopen=R)
            if hasattr(E, _p):
                E._position_task_manager()

        H.setEnabled(hasattr(C.window(), _P))
        H.clicked.connect(S)

        def T():
            B.cancel()
            A.close()

        L.clicked.connect(T)

        def U(val):
            D = val
            N[0] = _D
            if A.isVisible():
                A.close()
            if B.is_cancelled():
                if J:
                    J()
                return
            if O[0]:
                return
            F = bool(D) if D is not _A else _C
            if F:
                if I:
                    I(D)
                if refresh:
                    C.refresh_files()
            elif E:
                E()

        def V(msg):
            O[0] = _D
            if A.isVisible():
                A.close()
            if E:
                E()

        B.finished_signal.connect(U)
        B.error_signal.connect(V)
        A.show()
        B.start()
        return B

    def _run_background(C, name, fn, *D, on_done=_A, on_error=_A, refresh=_C):
        E = on_done
        B = on_error
        F = C.window()
        if hasattr(F, _P):
            A = F.task_manager.submit(name, fn, *D)
        else:
            A = WorkerThread(name, fn, *D)
            A.start()

        def G(val):
            A = val
            D = bool(A) if A is not _A else _C
            if D:
                if E:
                    E(A)
                if refresh:
                    C.refresh_files()
            elif B:
                B()

        A.finished_signal.connect(G)
        A.error_signal.connect(lambda msg: B() if B else _A)
        return A


class NonOverlappingTabBar(QTabBar):
    def resizeEvent(A, event):
        super().resizeEvent(event)
        A.separate_scroll_buttons()

    def separate_scroll_buttons(A, buttons=_A):
        B = buttons
        if B is _A:
            B = {
                _h if A.objectName() == _g else _i: A
                for A in A.findChildren(QToolButton)
                if A.objectName() in {_g, _A0}
            }
        D = B.get(_h)
        E = B.get(_i)
        if D is _A or E is _A:
            return
        C = 14
        F = 24
        H = 3
        G = (A.height() - F) // 2
        D.setFixedSize(C, F)
        E.setFixedSize(C, F)
        D.move(A.width() - (C * 2 + H), G)
        E.move(A.width() - C, G)


class BookmarkDialog(QDialog):
    def __init__(A, parent, bookmark, title):
        C = bookmark
        super().__init__(parent)
        A.setWindowTitle(title)
        E = QVBoxLayout(A)
        B = QFormLayout()
        A.name_input = QLineEdit(C.get(_H, ""))
        A.path_input = QLineEdit(C.get(_E, ""))
        A.path_input.setReadOnly(_D)
        A.note_input = QLineEdit(C.get(_L, ""))
        B.addRow(A.tr(_O), A.name_input)
        B.addRow(A.tr("Path"), A.path_input)
        B.addRow(A.tr("Note"), A.note_input)
        E.addLayout(B)
        D = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        D.accepted.connect(A.accept)
        D.rejected.connect(A.reject)
        E.addWidget(D)

    def bookmark(A):
        return {
            _H: A.name_input.text().strip(),
            _E: A.path_input.text(),
            _L: A.note_input.text().strip(),
        }


_DEVICE_FOLDER_SHORTCUTS = (
    ("Downloads", "Download"),
    (_A1, _A1),
    ("Pictures", "Pictures"),
    ("Music", "Music"),
    ("Videos", "Movies"),
    ("Camera", "DCIM"),
)


class DevicePanelGroup(QWidget):
    cross_device_drop = pyqtSignal(str, list, str)
    close_requested = pyqtSignal()

    def __init__(
        A, parent, adb_handler, device_info=_A, bookmarks_path=_A, bookmark_store=_A
    ):
        super().__init__(parent)
        A.adb_handler = adb_handler
        A.device_info = device_info or {}
        A.clipboard = {_F: [], _K: _A}
        A._views = []
        A._navigation_items = []
        A._closing = _C
        A._last_path = _N
        A._multi_panel_mode = _C
        A._navigation_pane_open = _D
        A._restore_navigation_pane_open = _D
        A._bookmark_store = bookmark_store or BookmarkStore(bookmarks_path)
        A._bookmark_store.bookmarks_changed.connect(A._on_bookmarks_changed)
        try:
            A._bookmarks = A._bookmark_store.load(A.device_serial)
            A._bookmark_load_error = _A
        except (OSError, ValueError) as E:
            A._bookmarks = []
            A._bookmark_load_error = str(E)
        C = QVBoxLayout(A)
        C.setContentsMargins(0, 0, 0, 0)
        C.setSpacing(2)
        D = QWidget()
        D.setObjectName(_j)
        B = QHBoxLayout(D)
        B.setContentsMargins(6, 2, 4, 2)
        B.setSpacing(6)
        A.navigation_toggle_btn = QToolButton()
        A.navigation_toggle_btn.setObjectName("navigation_toggle_btn")
        A.navigation_toggle_btn.setText("◧")
        A.navigation_toggle_btn.setCheckable(_D)
        A.navigation_toggle_btn.setChecked(_D)
        A.navigation_toggle_btn.setToolTip(A.tr(_A2))
        A.navigation_toggle_btn.setAccessibleName(A.tr("Toggle navigation pane"))
        A.navigation_toggle_btn.clicked.connect(A.toggle_navigation_pane)
        B.addWidget(A.navigation_toggle_btn)
        A.device_header = QLabel(A.device_name)
        A.device_header.setObjectName(_k)
        B.addWidget(A.device_header)
        B.addStretch()
        A.conn_label = QLabel()
        B.addWidget(A.conn_label)
        A.close_btn = QPushButton("X")
        A.close_btn.setObjectName(_l)
        A.close_btn.setToolTip(A.tr(_m))
        A.close_btn.setAccessibleName(A.tr(_n))
        A.close_btn.setFixedSize(30, 30)
        A.close_btn.clicked.connect(A.close_requested.emit)
        B.addWidget(A.close_btn)
        A.add_tab_btn = QPushButton("+")
        A.add_tab_btn.setObjectName("add_path_tab_btn")
        A.add_tab_btn.setToolTip(A.tr("Add a path tab"))
        A.add_tab_btn.setAccessibleName(A.tr("Add path tab"))
        A.add_tab_btn.setFixedSize(30, 30)
        A.add_tab_btn.clicked.connect(lambda: A.add_tab())
        B.insertWidget(B.count() - 1, A.add_tab_btn)
        C.addWidget(D)
        A.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        A.content_splitter.setObjectName("panel_content_splitter")
        A.content_splitter.setChildrenCollapsible(_C)
        A.favorites_pane = A._create_favorites_pane()
        A.content_splitter.addWidget(A.favorites_pane)
        A.tabs = QTabWidget(A.content_splitter)
        A.tabs.setObjectName("path_tabs")
        A.tabs.setTabBar(NonOverlappingTabBar())
        A.tabs.setDocumentMode(_D)
        A.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideMiddle)
        A.tabs.currentChanged.connect(A._on_active_tab_changed)
        A.tabs.tabBar().setObjectName("path_tab_bar")
        A.content_splitter.addWidget(A.tabs)
        A.content_splitter.setStretchFactor(0, 0)
        A.content_splitter.setStretchFactor(1, 1)
        A.content_splitter.setSizes([180, 640])
        C.addWidget(A.content_splitter, 1)
        A.add_tab()
        A.update_connection_status()
        if A._bookmark_load_error:
            A._show_bookmark_error(A.tr(_A3).format(A._bookmark_load_error))

    def _create_favorites_pane(A):
        B = QWidget(A.content_splitter)
        B.setObjectName("favorites_pane")
        B.setMinimumWidth(140)
        B.setMaximumWidth(240)
        C = QVBoxLayout(B)
        C.setContentsMargins(6, 8, 6, 6)
        C.setSpacing(6)
        D = QHBoxLayout()
        E = QLabel(A.tr("Folders"), B)
        E.setObjectName("navigation_title")
        D.addWidget(E)
        D.addStretch()
        C.addLayout(D)
        A.navigation_tree = QTreeWidget(B)
        A.navigation_tree.setObjectName("navigation_tree")
        A.navigation_tree.setHeaderHidden(_D)
        A.navigation_tree.setRootIsDecorated(_D)
        A.navigation_tree.setUniformRowHeights(_D)
        A.navigation_tree.setIndentation(16)
        A.navigation_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        A.navigation_tree.customContextMenuRequested.connect(
            A._show_bookmark_context_menu
        )
        A.navigation_tree.itemClicked.connect(A._activate_navigation_item)
        A.navigation_tree.itemActivated.connect(A._activate_navigation_item)
        C.addWidget(A.navigation_tree)
        A._refresh_navigation_tree()
        return B

    def _refresh_navigation_tree(A):
        N = "storage"
        M = "favorites"
        I = "section"
        G = {}
        for O in range(A.navigation_tree.topLevelItemCount()):
            B = A.navigation_tree.topLevelItem(O)
            P = B.data(0, Qt.ItemDataRole.UserRole) or {}
            J = P.get(I)
            if J:
                G[J] = B.isExpanded()
        A.navigation_tree.clear()
        A._navigation_items = []
        F = QFileIconProvider().icon(QFileIconProvider.IconType.Folder)
        C = QTreeWidgetItem([A.tr("Favorites")])
        C.setFont(0, A._navigation_group_font())
        C.setIcon(0, F)
        C.setData(0, Qt.ItemDataRole.UserRole, {_J: "group", I: M})
        A.navigation_tree.addTopLevelItem(C)
        for D in A._bookmarks:
            B = QTreeWidgetItem([D[_H]])
            B.setIcon(0, F)
            B.setData(0, Qt.ItemDataRole.UserRole, {_J: _M, _E: D[_E], "bookmark": D})
            H = D[_E]
            if D.get(_L):
                H = f"{D[_L]}\n{H}"
            B.setToolTip(0, H)
            C.addChild(B)
            A._navigation_items.append((B, D[_E]))
        if not A._bookmarks:
            K = QTreeWidgetItem([A.tr("No favorites yet")])
            K.setFlags(Qt.ItemFlag.NoItemFlags)
            C.addChild(K)
        C.setExpanded(G.get(M, _D))
        E = QTreeWidgetItem([A.tr("Internal storage")])
        E.setFont(0, A._navigation_group_font())
        E.setIcon(0, F)
        E.setData(0, Qt.ItemDataRole.UserRole, {_J: _V, _E: _N, I: N})
        A.navigation_tree.addTopLevelItem(E)
        A._navigation_items.append((E, _N))
        for Q, R in _DEVICE_FOLDER_SHORTCUTS:
            L = f"/storage/emulated/0/{R}"
            B = QTreeWidgetItem([A.tr(Q)])
            B.setIcon(0, F)
            B.setData(0, Qt.ItemDataRole.UserRole, {_J: _V, _E: L})
            E.addChild(B)
            A._navigation_items.append((B, L))
        E.setExpanded(G.get(N, _D))
        if hasattr(A, "tabs"):
            A._update_navigation_selection(A.current_path)

    def _navigation_group_font(B):
        A = B.navigation_tree.font()
        A.setBold(_D)
        return A

    def _activate_navigation_item(A, item, _column=0):
        B = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if B.get(_J) in {_V, _M}:
            if A.active_view is not _A:
                A.active_view.navigate_to(B[_E])

    def _on_bookmarks_changed(A, device_id):
        if device_id != A.device_serial:
            return
        try:
            A._bookmarks = A._bookmark_store.load(A.device_serial)
        except (OSError, ValueError) as B:
            A._show_bookmark_error(A.tr(_A3).format(B))
            return
        A._refresh_navigation_tree()

    def _show_bookmark_error(C, message, view=_A):
        A = message
        _logger.warning(A)
        B = view if view is not _A else C.active_view
        if B is not _A:
            B.status_label.setText(A)

    def _save_bookmarks(A, bookmarks):
        B = bookmarks
        try:
            A._bookmark_store.save(A.device_serial, B)
        except (OSError, ValueError) as C:
            A._show_bookmark_error(A.tr("Could not save favorites: {0}").format(C))
            return _C
        A._bookmarks = B
        A._refresh_navigation_tree()
        return _D

    def add_bookmark(B, name, path, note=""):
        A = {_H: name.strip(), _E: path, _L: note.strip()}
        if not A[_H] or not A[_E].startswith(_B):
            raise ValueError("A favorite needs a name and absolute device path")
        if any(B[_E] == A[_E] for B in B._bookmarks):
            return _C
        return B._save_bookmarks([*B._bookmarks, A])

    def _edit_bookmark_dialog(A, bookmark, title):
        C = bookmark
        E = BookmarkDialog(A, C, title)
        if E.exec() != QDialog.DialogCode.Accepted:
            return
        B = E.bookmark()
        if not B[_H]:
            A._show_bookmark_error(A.tr("Favorite name cannot be empty"))
            return
        if C in A._bookmarks:
            F = A._bookmarks.index(C)
            D = list(A._bookmarks)
            D[F] = B
        else:
            if any(A[_E] == B[_E] for A in A._bookmarks):
                A._show_bookmark_error(A.tr(_A4))
                return
            D = [*A._bookmarks, B]
        A._save_bookmarks(D)

    def _selected_bookmark(C):
        B = C.navigation_tree.currentItem()
        A = B.data(0, Qt.ItemDataRole.UserRole) if B else _A
        if A and A.get(_J) == _M:
            return A.get("bookmark")

    def _remove_bookmark(A):
        B = A._selected_bookmark()
        if B is _A:
            return
        A._save_bookmarks([A for A in A._bookmarks if A != B])

    def _edit_selected_bookmark(A):
        B = A._selected_bookmark()
        if B is not _A:
            A._edit_bookmark_dialog(B, A.tr("Edit favorite"))

    def _show_bookmark_context_menu(A, position):
        D = position
        B = A.navigation_tree.itemAt(D)
        if B is _A:
            return
        F = B.data(0, Qt.ItemDataRole.UserRole) or {}
        E = F.get(_J)
        if E not in {_V, _M}:
            return
        A.navigation_tree.setCurrentItem(B)
        C = QMenu(A)
        C.addAction(A.tr("Open"), lambda: A._activate_navigation_item(B))
        if E == _M:
            C.addAction(A.tr("Edit"), A._edit_selected_bookmark)
            C.addAction(A.tr("Remove from favorites"), A._remove_bookmark)
        else:
            C.addAction(A.tr(_t), lambda: A._pin_navigation_item(B))
        C.exec(A.navigation_tree.viewport().mapToGlobal(D))

    def _pin_navigation_item(A, item):
        B = item.data(0, Qt.ItemDataRole.UserRole) or {}
        A._add_folder_to_favorites(item.text(0), B[_E], A.active_view)

    def _add_folder_to_favorites(A, name, path, source_view=_A):
        B = source_view
        if any(A[_E] == path for A in A._bookmarks):
            A._show_bookmark_error(A.tr(_A4), B)
            return
        if A.add_bookmark(name, path) and B is not _A:
            B.status_label.setText(A.tr("Added '{0}' to favorites").format(name))

    def _update_navigation_selection(B, path):
        D = path.rstrip(_B) or _B
        A = _A
        E = -1
        for F, G in B._navigation_items:
            C = G.rstrip(_B) or _B
            if (D == C or D.startswith(C + _B)) and len(C) > E:
                A = F
                E = len(C)
        if A is _A:
            B.navigation_tree.clearSelection()
            B.navigation_tree.setCurrentItem(_A)
            return
        if A.parent() is not _A:
            A.parent().setExpanded(_D)
        B.navigation_tree.setCurrentItem(A)
        B.navigation_tree.scrollToItem(A)

    def toggle_navigation_pane(A, _checked=_C):
        A._set_navigation_pane_open(not A._navigation_pane_open)
        A._restore_navigation_pane_open = A._navigation_pane_open

    def _set_navigation_pane_open(A, is_open):
        B = is_open
        A._navigation_pane_open = B
        A.favorites_pane.setVisible(B)
        A.navigation_toggle_btn.setChecked(B)
        A.navigation_toggle_btn.setToolTip(
            A.tr(_A2) if B else A.tr("Show navigation pane")
        )

    def set_multi_panel_mode(A, enabled):
        B = enabled
        if B == A._multi_panel_mode:
            return
        if B:
            A._restore_navigation_pane_open = A._navigation_pane_open
            A._multi_panel_mode = _D
            A._set_navigation_pane_open(_C)
            return
        A._multi_panel_mode = _C
        A._set_navigation_pane_open(A._restore_navigation_pane_open)

    @property
    def active_view(self):
        return self.tabs.currentWidget()

    @property
    def device_serial(self):
        return self.adb_handler.device_serial or ""

    @property
    def device_name(self):
        A = self
        B = A.device_serial
        C = A.device_info.get("model") or A.adb_handler.devices.get(B, "")
        return C or B

    @property
    def current_path(self):
        A = self
        return A.active_view.current_path if A.active_view else A._last_path

    @current_path.setter
    def current_path(self, path):
        if self.active_view:
            self.active_view.current_path = path

    def __getattr__(A, name):
        C = A.__dict__.get("_views")
        if C:
            B = A.active_view
            if B is not _A:
                return getattr(B, name)
        raise AttributeError(f"{type(A).__name__!s} has no attribute {name!r}")

    def add_tab(A, path=_A):
        F = "Close tab"
        if A._closing:
            return
        D = path or A.current_path
        B = DevicePanel(
            A.tabs,
            A.adb_handler,
            A.device_info,
            start_path=D,
            compact_header=_D,
            clipboard=A.clipboard,
        )
        A._views.append(B)
        B.path_changed.connect(
            lambda changed_path, panel=B: A._on_view_path_changed(panel, changed_path)
        )
        B.favorite_requested.connect(
            lambda name, path, source=B: A._add_folder_to_favorites(name, path, source)
        )
        B.cross_device_drop.connect(A.cross_device_drop)
        E = A.tabs.addTab(B, A._tab_title(D))
        C = QToolButton(A.tabs.tabBar())
        C.setObjectName("close_path_tab_btn")
        C.setText("x")
        C.setToolTip(A.tr(F))
        C.setAccessibleName(A.tr(F))
        C.setAutoRaise(_D)
        C.setCursor(Qt.CursorShape.PointingHandCursor)
        C.clicked.connect(lambda _checked=_C, tab=B: A._close_view(tab))
        A.tabs.tabBar().setTabButton(E, A.tabs.tabBar().ButtonPosition.RightSide, C)
        A.tabs.setCurrentIndex(E)
        A._enable_click_activation()
        QTimer.singleShot(0, A._style_tab_scroll_buttons)
        A._update_connection_status()
        return B

    def _enable_click_activation(A):
        C = [A, *A.findChildren(QWidget)]
        for B in C:
            if B.focusPolicy() == Qt.FocusPolicy.NoFocus:
                B.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def _style_tab_scroll_buttons(B):
        E = "Scroll tabs right"
        D = "Scroll tabs left"
        F = B.tabs.tabBar().findChildren(QToolButton)
        C = {}
        for A in F:
            if A.objectName() == _g:
                A.setText("<")
                A.setToolTip(B.tr(D))
                A.setAccessibleName(B.tr(D))
                C[_h] = A
            elif A.objectName() == _A0:
                A.setText(">")
                A.setToolTip(B.tr(E))
                A.setAccessibleName(B.tr(E))
                C[_i] = A
            else:
                continue
            A.setCursor(Qt.CursorShape.PointingHandCursor)
        B.tabs.tabBar().separate_scroll_buttons(C)

    @staticmethod
    def _tab_title(path):
        return path.rstrip(_B).rsplit(_B, 1)[-1] or _B

    def _update_tab_title(A, view, path):
        B = A.tabs.indexOf(view)
        if B >= 0:
            A.tabs.setTabText(B, A._tab_title(path))

    def _on_view_path_changed(A, view, path):
        B = path
        A._last_path = B
        A._update_tab_title(view, B)
        if view is A.active_view:
            A._update_navigation_selection(B)

    def _close_view(A, view):
        B = view
        C = A.tabs.indexOf(B)
        if C < 0:
            return
        A._last_path = B.current_path
        A._views.remove(B)
        A.tabs.removeTab(C)
        B.prepare_for_close()
        if A._views:
            A._update_connection_status()

    def _close_tab(A, index):
        B = index
        if not 0 <= B < len(A._views):
            return
        A._close_view(A._views[B])

    def close_active_tab(A):
        if A.active_view is not _A:
            A._close_view(A.active_view)

    def _update_connection_status(A, _index=_A):
        if not A._views:
            return
        A.device_header.setText(A.device_name)
        if A.adb_handler.device_connected:
            A.conn_label.setText(A.tr(_W))
            A.conn_label.setStyleSheet(_Y)
        else:
            A.conn_label.setText(A.tr(_X))
            A.conn_label.setStyleSheet(_o)

    def _on_active_tab_changed(A, _index=_A):
        A._update_connection_status()
        if A.active_view is not _A:
            A._update_navigation_selection(A.active_view.current_path)

    def update_connection_status(A):
        for B in A._views:
            B.update_connection_status()
        A._update_connection_status()

    def contains_focus(B):
        A = QApplication.focusWidget()
        return A is not _A and (A is B or B.isAncestorOf(A))

    def contains_view(A, view):
        return view in A._views

    def prepare_for_close(A):
        if A._closing:
            return
        A._closing = _D
        A.hide()
        for B in A._views:
            B.prepare_for_close()
        A._views.clear()
        A.deleteLater()
