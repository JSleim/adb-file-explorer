import os
import sys
import tempfile
import subprocess
import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMessageBox, QLineEdit, QMenu, QFileDialog, QInputDialog,
    QLabel, QCheckBox, QFileIconProvider, QProgressBar, QDialog, QTreeView,
    QTabWidget, QTabBar, QApplication, QToolButton,
)
from PyQt6.QtGui import (
    QPainter, QPen, QStandardItemModel, QStandardItem, QAction,
    QKeySequence, QShortcut,
)
from PyQt6.QtCore import QStringListModel
from PyQt6.QtWidgets import QCompleter, QStyle, QStyleOptionButton
from PyQt6.QtCore import Qt, QTimer, QFileInfo, pyqtSignal, QPoint

from handler import ADBHandler
from operation_control import is_cancelled
from ui.widgets import DropTreeView
from ui.task_manager import WorkerThread
from ui.windows_drag import (
    build_manifest_for_paths,
    cancel_windows_drag,
    native_drag_available,
    start_windows_drag,
    wait_for_windows_drag,
)


class SortableStandardItem(QStandardItem):
    def __lt__(self, other):
        value = self.data(Qt.ItemDataRole.UserRole)
        other_value = other.data(Qt.ItemDataRole.UserRole)
        if value is not None and other_value is not None:
            return value < other_value
        return self.text().casefold() < other.text().casefold()


class ApplyToAllCheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return

        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, option, self
        )
        if not indicator.isValid():
            return

        start = (indicator.left() + 4, indicator.top() + 8)
        middle = (indicator.left() + 7, indicator.top() + 11)
        end = (indicator.left() + 12, indicator.top() + 5)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(
            Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
        ))
        painter.drawLine(*start, *middle)
        painter.drawLine(*middle, *end)
        painter.setPen(QPen(
            Qt.GlobalColor.white, 1.5, Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
        ))
        painter.drawLine(*start, *middle)
        painter.drawLine(*middle, *end)


class PathInput(QLineEdit):

    def __init__(self, panel):
        super().__init__()
        self._panel = panel
        self._completer = QCompleter([], self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(self._completer)
        self.returnPressed.connect(self._navigate)

    def update_completions(self, items):
        names = [f.name for f in items] if items else []
        
        parent = "/".join(self._panel.current_path.rstrip("/").split("/")[:-1]) or "/"
        names.append("..")
        model = QStringListModel(names)
        self._completer.setModel(model)

    def _navigate(self):
        text = self.text().strip()
        if not text:
            return
        
        if text.startswith("/"):
            target = text
        else:
            target = f"{self._panel.current_path.rstrip('/')}/{text}"
        self._panel.navigate_to(target)


class DevicePanel(QWidget):

    cross_device_drop = pyqtSignal(str, list, str)
    close_requested = pyqtSignal()
    path_changed = pyqtSignal(str)

    def __init__(
        self, parent, adb_handler, device_info=None, start_path=None,
        compact_header=False,
    ):
        super().__init__(parent)
        self.adb_handler = adb_handler
        self.device_info = device_info or {}
        
        self.clipboard = {'items': [], 'operation': None}

        
        self.use_root = False
        self._loading = False
        self._refresh_pending = False
        self._refresh_task = None
        self._closing = False

        
        self._icon_provider = QFileIconProvider()
        self._folder_icon = self._icon_provider.icon(QFileIconProvider.IconType.Folder)
        self._file_icon = self._icon_provider.icon(QFileIconProvider.IconType.File)
        self._icon_cache = {}

        
        self.root_path = "/"
        self.current_path = start_path or "/storage/emulated/0"
        self.path_history = [self.current_path]
        self._history_index = 0
        self.all_files = []

        self._setup_ui()
        self._setup_context_menu()
        if compact_header:
            self.device_header.parentWidget().hide()
            self.conn_label.hide()
        self.update_path_display()

    @property
    def device_serial(self):
        return self.adb_handler.device_serial or ""

    @property
    def device_name(self):
        serial = self.device_serial
        model = self.device_info.get("model") or self.adb_handler.devices.get(serial, "")
        return model or serial

    

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        
        header_container = QWidget()
        header_container.setObjectName("panel_header")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(6, 2, 4, 2)
        self.device_header = QLabel(self.device_name)
        self.device_header.setObjectName("device_header")
        header_layout.addWidget(self.device_header)
        header_layout.addStretch()
        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("panel_close_btn")
        self.close_btn.setToolTip("Close this device panel")
        self.close_btn.setAccessibleName("Close device panel")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self.close_btn)
        layout.addWidget(header_container)

        
        self.conn_label = QLabel("🟢 Connected" if self.adb_handler.device_connected else "🔴 Disconnected")
        self.conn_label.setStyleSheet("color: green; font-size: 10px; padding: 0 8px 2px 8px;")
        layout.addWidget(self.conn_label)

        
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)

        self.back_btn = QPushButton("<")
        self.back_btn.setMaximumWidth(36)
        self.back_btn.setObjectName("back_btn")
        self.back_btn.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_btn)

        self.up_btn = QPushButton("^")
        self.up_btn.setMaximumWidth(36)
        self.up_btn.setObjectName("up_btn")
        self.up_btn.clicked.connect(self.go_up)
        nav_layout.addWidget(self.up_btn)

        self.path_display = PathInput(self)
        self.path_display.setObjectName("path_display")
        nav_layout.addWidget(self.path_display)

        refresh_btn = QPushButton("↻")
        refresh_btn.setMaximumWidth(32)
        refresh_btn.clicked.connect(self.refresh_files)
        nav_layout.addWidget(refresh_btn)

        nav_container = QWidget()
        nav_container.setObjectName("panel_nav")
        nav_container.setLayout(nav_layout)
        layout.addWidget(nav_container)

        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter files")
        self.search_bar.setObjectName("search_bar")
        self.search_bar.textChanged.connect(self.apply_search_filter)
        layout.addWidget(self.search_bar)

        
        self.tree_view = DropTreeView(self, self)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setSortingEnabled(True)
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, header.ResizeMode.ResizeToContents)
        self.tree_view.doubleClicked.connect(self.handle_double_click)
        self.tree_view.activated.connect(self.handle_double_click)
        self._setup_shortcuts()
        layout.addWidget(self.tree_view)

        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-size: 10px; color: #888; padding: 0 4px;")
        layout.addWidget(self.status_label)

        if self.adb_handler.device_connected:
            self.refresh_files()
        else:
            self.status_label.setText("No ADB device connected")

    def _setup_context_menu(self):
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)

    def _setup_shortcuts(self):
        self._shortcuts = []
        bindings = (
            (QKeySequence.StandardKey.Copy, self.copy_selected),
            (QKeySequence.StandardKey.Cut, self.cut_selected),
            (QKeySequence.StandardKey.Paste, self.paste_items),
            (QKeySequence(Qt.Key.Key_Delete), self._shortcut_delete),
            (QKeySequence(Qt.Key.Key_F2), self._shortcut_rename),
            (QKeySequence("Alt+Left"), self.go_back),
            (QKeySequence("Alt+Right"), self.go_forward),
            (QKeySequence("Alt+Up"), self.go_up),
            (QKeySequence(Qt.Key.Key_F5), self.refresh_files),
            (QKeySequence("Ctrl+F"), self.focus_filter),
            (QKeySequence("Ctrl+L"), self.focus_address_bar),
        )
        for key, handler in bindings:
            shortcut = QShortcut(key, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

        backspace = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self.tree_view)
        backspace.setContext(Qt.ShortcutContext.WidgetShortcut)
        backspace.activated.connect(self.go_back)
        self._shortcuts.append(backspace)

    def update_connection_status(self):
        if self.adb_handler.device_connected:
            self.conn_label.setText("🟢 Connected")
            self.conn_label.setStyleSheet("color: green; font-size: 10px; padding: 0 8px 2px 8px;")
        else:
            self.conn_label.setText("🔴 Disconnected")
            self.conn_label.setStyleSheet("color: red; font-size: 10px; padding: 0 8px 2px 8px;")

    

    def update_path_display(self):
        self.path_display.setText(self.current_path)
        self.back_btn.setEnabled(self._history_index > 0)
        self.path_changed.emit(self.current_path)

    def navigate_to(self, path):
        if path == self.current_path:
            return
        self.path_history = self.path_history[:self._history_index + 1]
        self.path_history.append(path)
        self._history_index = len(self.path_history) - 1
        self.current_path = path
        self.clear_search_on_navigation()
        self.update_path_display()
        self.refresh_files()

    def go_up(self):
        parent = "/".join(self.current_path.rstrip("/").split("/")[:-1]) or self.root_path
        if parent != self.current_path:
            self.navigate_to(parent)

    def go_back(self):
        if self._history_index > 0:
            self._history_index -= 1
            self._navigate_history()

    def go_forward(self):
        if self._history_index < len(self.path_history) - 1:
            self._history_index += 1
            self._navigate_history()

    def _navigate_history(self):
        self.current_path = self.path_history[self._history_index]
        self.clear_search_on_navigation()
        self.update_path_display()
        self.refresh_files()

    def focus_filter(self):
        self.search_bar.setFocus()
        self.search_bar.selectAll()

    def focus_address_bar(self):
        self.path_display.setFocus()
        self.path_display.selectAll()

    def clear_search_on_navigation(self):
        if self.search_bar.text():
            self.search_bar.blockSignals(True)
            self.search_bar.setText("")
            self.search_bar.blockSignals(False)
        self.apply_search_filter()

    def start_native_drag(self, paths):
        if not native_drag_available():
            return False
        manifest = build_manifest_for_paths(
            self.adb_handler,
            self.all_files,
            paths,
            use_root=self.use_root,
        )
        operation_id = start_windows_drag(
            self.device_serial,
            manifest,
            use_su=self.use_root and self.adb_handler.root_mode == "su",
        )
        if operation_id is None:
            return True
        if operation_id:
            task_manager = getattr(self.window(), "task_manager", None)
            if task_manager is not None:
                task = WorkerThread(
                    "Copying files to Windows",
                    wait_for_windows_drag,
                    operation_id,
                )
                task.add_cancel_callback(
                    lambda: cancel_windows_drag(operation_id)
                )
                task_manager.add_task(task, name=task.name)
                task.start()
                if hasattr(self.window(), "_position_task_manager"):
                    self.window()._position_task_manager()
        return True

    

    def refresh_files(self):
        if self._closing:
            return
        if not self.adb_handler.device_connected:
            self.status_label.setText("No ADB device")
            return
        if self._loading:
            self._refresh_pending = True
            return

        self._loading = True
        self.status_label.setText(f"Loading {self.current_path}...")
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Name', 'Type', 'Size', 'Permissions', 'Modified'])
        loading_item = QStandardItem("Loading...")
        loading_item.setEnabled(False)
        self.tree_model.appendRow([loading_item])

        def on_files(files):
            self._loading = False
            if self._closing:
                return
            if files is not None:
                self.all_files = files
                self.apply_search_filter()
                self.status_label.setText(f"Found {len(self.all_files)} items")
            else:
                self.status_label.setText("Failed to list directory")
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

    def prepare_for_close(self):
        """Keep the panel alive until its refresh worker has stopped."""
        if self._closing:
            return

        self._closing = True
        self._refresh_pending = False
        self.hide()

        task = self._refresh_task
        if task is not None and task.isRunning():
            task.finished.connect(self.deleteLater)
        else:
            self.deleteLater()


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
            name_item = SortableStandardItem(file_item.name)
            name_item.setData(
                (0 if file_item.is_dir else 1, file_item.name.casefold()),
                Qt.ItemDataRole.UserRole,
            )
            if file_item.is_dir:
                name_item.setIcon(self._folder_icon)
            else:
                ext = os.path.splitext(file_item.name)[1].lower()
                if ext not in self._icon_cache:
                    icon = self._icon_provider.icon(QFileInfo(f"x{ext}"))
                    self._icon_cache[ext] = icon if not icon.isNull() else self._file_icon
                name_item.setIcon(self._icon_cache[ext])
            size_item = SortableStandardItem(
                str(file_item.size) if not file_item.is_dir else ""
            )
            size_item.setData(
                file_item.size if not file_item.is_dir else None,
                Qt.ItemDataRole.UserRole,
            )
            modified_item = SortableStandardItem(file_item.date_modified)
            modified_item.setData(
                file_item.date_modified, Qt.ItemDataRole.UserRole
            )
            self.tree_model.appendRow([
                name_item,
                SortableStandardItem("Directory" if file_item.is_dir else "File"),
                size_item,
                SortableStandardItem(file_item.permissions),
                modified_item,
            ])
        for i in range(5):
            self.tree_view.resizeColumnToContents(i)
        self.path_display.update_completions(files)

    def handle_double_click(self, index):
        name_index = self.tree_model.index(index.row(), 0)
        type_index = self.tree_model.index(index.row(), 1)
        item_name = self.tree_model.data(name_index)
        item_type = self.tree_model.data(type_index)
        if not item_name:
            return
        if item_type == "Directory":
            new_path = ""
            if item_name == "..":
                parent_path = "/".join(self.current_path.rstrip("/").split("/")[:-1])
                new_path = parent_path if parent_path else self.root_path
            else:
                new_path = f"{self.current_path.rstrip('/')}/{item_name}"
            if new_path and new_path != self.current_path:
                self.navigate_to(new_path)
        elif item_type == "File":
            self.open_file_on_host(item_name)

    

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
        items = self.get_selected_items()
        if not items:
            return
        self.clipboard = {'items': items, 'operation': 'copy'}
        self.status_label.setText(f"Copied {len(items)} item(s)")

    def cut_selected(self):
        items = self.get_selected_items()
        if not items:
            return
        self.clipboard = {'items': items, 'operation': 'cut'}
        self.status_label.setText(f"Cut {len(items)} item(s)")

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
                f"The following already exist in the destination:\n\n{names}{more}\n\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.status_label.setText("Paste canceled")
                return

        operation = self.clipboard['operation']
        cut_mode = operation == 'cut'

        def run_paste():
            count = 0
            for item in self.clipboard['items']:
                if is_cancelled():
                    return count
                src = item['path']
                dst = f"{dest_dir}/{os.path.basename(src)}"
                if operation == 'copy':
                    ok = self.adb_handler.copy_on_device(src, dst)
                else:
                    ok = self.adb_handler.move_on_device(src, dst)
                if ok:
                    count += 1
            return count

        def on_paste_done(count):
            if count > 0:
                if cut_mode:
                    self.clipboard = {'items': [], 'operation': None}
                self.status_label.setText(f"Pasted {count} item(s)")
                self.refresh_files()
            else:
                self.status_label.setText("Paste failed")

        self._run_modal(f"Paste {len(self.clipboard['items'])} items", run_paste, on_done=on_paste_done)

    

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

        if not indexes:
            menu.addAction("New File", self.create_new_file)
            menu.addAction("New Folder", self.create_new_folder)
            menu.addAction("Upload to Device", self.upload_file_to_device)
            menu.addAction("Import Folder from PC...", self.import_folder_from_pc)
        elif len(indexes) > 1:
            menu.addAction("Copy", self.copy_selected)
            menu.addAction("Cut", self.cut_selected)
            menu.addSeparator()
            menu.addAction("Delete Selected", self.delete_selected_items)
            menu.addAction("Download to PC", self.download_selected_items)
            menu.addAction("Copy to Device Folder...", self.copy_selected_to)
            menu.addAction("Batch Rename...", self.batch_rename_selected)
            total_size = sum(
                self.get_file_size_from_row(idx.row())
                for idx in indexes
                if not self.is_dir_from_row(idx.row())
            )
            menu.addSeparator()
            sz_lbl = menu.addAction(f"Total Size: {self.format_size(total_size)}")
            sz_lbl.setEnabled(False)
        else:
            idx = indexes[0]
            item_name = self.tree_model.data(self.tree_model.index(idx.row(), 0))
            item_type = self.tree_model.data(self.tree_model.index(idx.row(), 1))

            menu.addAction("Copy", self.copy_selected)
            menu.addAction("Cut", self.cut_selected)
            menu.addSeparator()

            if item_type == "File":
                menu.addAction("Open", lambda n=item_name: self.open_file_on_host(n))
                menu.addAction("Save to PC...", lambda n=item_name: self.copy_file_to(n))
                menu.addSeparator()
                menu.addAction("Rename", lambda n=item_name: self.rename_item(n))
                menu.addAction("Delete", lambda n=item_name: self.delete_item(n, is_dir=False))
            elif item_type == "Directory":
                menu.addAction("Save to PC...", lambda n=item_name: self.copy_folder_to(n))
                menu.addSeparator()
                menu.addAction("Rename", lambda n=item_name: self.rename_item(n))
                menu.addAction("Delete", lambda n=item_name: self.delete_item(n, is_dir=True))

        
        menu.addSeparator()
        send_menu = menu.addMenu("Send to Device...")
        self._populate_send_to_menu(send_menu, indexes, position)

        menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def _populate_send_to_menu(self, menu, indexes, position):
        if not indexes:
            menu.addAction("No items selected").setEnabled(False)
            return
        items = self.get_selected_items()
        if not items:
            menu.addAction("No items selected").setEnabled(False)
            return

        parent = self.window()
        if not hasattr(parent, 'device_panels'):
            menu.addAction("No other devices").setEnabled(False)
            return

        target_devices = []
        for panel in parent.device_panels:
            contains_view = getattr(panel, "contains_view", None)
            is_current_panel = (
                panel is self
                or (contains_view is not None and contains_view(self))
            )
            if not is_current_panel and panel.adb_handler.device_connected:
                target_devices.append(panel)

        if not target_devices:
            menu.addAction("No other devices").setEnabled(False)
            return

        for panel in target_devices:
            action = menu.addAction(panel.device_name)
            action.triggered.connect(
                lambda checked=False, p=panel, its=items: self._send_items_to_device(its, p)
            )

    def _send_items_to_device(self, items, target_panel):
        def run_stream():
            for item in items:
                if is_cancelled():
                    return False
                dest = f"{target_panel.current_path.rstrip('/')}/{item['name']}"
                if item['is_dir']:
                    ok = self.adb_handler.stream_directory(
                        self.device_serial, item['path'],
                        target_panel.device_serial, dest,
                        line_callback=lambda msg: None,
                    )
                else:
                    ok = self.adb_handler.stream_file(
                        self.device_serial, item['path'],
                        target_panel.device_serial, dest,
                    )
                if not ok:
                    return False
            return True

        def on_done(ok):
            if ok:
                self.status_label.setText(f"Sent {len(items)} item(s) to {target_panel.device_name}")
                target_panel.refresh_files()
            else:
                self.status_label.setText("Stream failed")

        self._run_modal(f"Streaming to {target_panel.device_name}", run_stream, on_done=on_done)

    

    def get_file_size_from_row(self, row):
        size_index = self.tree_model.index(row, 2)
        size_text = self.tree_model.data(size_index)
        return int(size_text) if size_text and size_text.isdigit() else 0

    def is_dir_from_row(self, row):
        type_index = self.tree_model.index(row, 1)
        return self.tree_model.data(type_index) == "Directory"

    def format_size(self, bytes_size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

    def open_file_on_host(self, filename):
        if not self.adb_handler.device_connected:
            self.status_label.setText("No connection")
            return
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, filename)

        def run_pull():
            return self.adb_handler.pull_file(remote_path, local_path)

        def on_pulled(ok):
            if not ok:
                self.status_label.setText(f"Failed to open {filename}")
                return
            try:
                if sys.platform.startswith('win'):
                    os.startfile(local_path)
                elif sys.platform.startswith('darwin'):
                    subprocess.run(['open', local_path])
                else:
                    subprocess.run(['xdg-open', local_path])
                self.status_label.setText(f"Opened {filename}")
            except Exception:
                self.status_label.setText(f"Failed to open file")

        self._run_modal("Downloading file", run_pull, on_done=on_pulled)

    def copy_file_to(self, filename):
        if not self.adb_handler.device_connected:
            return
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File As", filename)
        if not save_path:
            return
        self._run_transfer("Copying file", remote_path, save_path,
                           f"File copied: {save_path}", f"Failed to copy {filename}")

    def copy_folder_to(self, foldername):
        if not self.adb_handler.device_connected:
            return
        remote_path = f"{self.current_path.rstrip('/')}/{foldername}"
        save_dir = QFileDialog.getExistingDirectory(self, "Select Destination")
        if not save_dir:
            return
        local_path = os.path.join(save_dir, foldername)
        self._run_transfer("Copying folder", remote_path, local_path,
                           f"Folder copied: {local_path}", f"Failed to copy {foldername}")

    def _run_transfer(self, title, src, dst, success_msg, error_msg):
        fn = self.adb_handler.pull_file
        self._run_modal(
            title, fn, src, dst,
            on_done=lambda _: self.status_label.setText(success_msg),
            on_error=lambda: self.status_label.setText(error_msg),
        )

    def rename_item(self, old_name):
        if not self.adb_handler.device_connected:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            f"New name for '{old_name}':",
            text=old_name,
        )
        if ok and new_name and new_name != old_name:
            old_path = f"{self.current_path.rstrip('/')}/{old_name}"
            new_path = f"{self.current_path.rstrip('/')}/{new_name}"

            def on_done(_):
                self.status_label.setText(f"Renamed to '{new_name}'")
                self.refresh_files()

            def on_error():
                self.status_label.setText(f"Rename failed")

            self._run_modal(
                f"Rename {old_name}",
                self.adb_handler.rename_item,
                old_path,
                new_path,
                on_done=on_done,
                on_error=on_error,
            )

    def delete_item(self, name, is_dir=False):
        if not self.adb_handler.device_connected:
            return
        confirmation = (
            f"Delete folder '{name}' and all of its contents, including "
            "subfolders?"
            if is_dir
            else f"Delete '{name}'?"
        )
        reply = QMessageBox.question(
            self, "Delete", confirmation,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            path = f"{self.current_path.rstrip('/')}/{name}"

            def on_done(_):
                self.status_label.setText(f"Deleted '{name}'")
                self.refresh_files()

            def on_error():
                self.status_label.setText(f"Delete failed")

            self._run_modal(
                f"Delete {name}",
                self.adb_handler.delete_item,
                path,
                is_dir,
                on_done=on_done,
                on_error=on_error,
            )

    def _shortcut_delete(self):
        indexes = self.tree_view.selectionModel().selectedRows()
        if indexes:
            self.delete_selected_items()

    def _shortcut_rename(self):
        indexes = self.tree_view.selectionModel().selectedRows()
        if len(indexes) != 1:
            return
        name = self.tree_model.data(self.tree_model.index(indexes[0].row(), 0))
        if not name or name == "..":
            return
        self.rename_item(name)

    def delete_selected_items(self):
        if not self.adb_handler.device_connected:
            return
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return
        names_types = []
        for index in indexes:
            name = self.tree_model.data(self.tree_model.index(index.row(), 0))
            typ = self.tree_model.data(self.tree_model.index(index.row(), 1))
            if name and name != "..":
                names_types.append((name, typ == "Directory"))
        if not names_types:
            return
        has_directories = any(is_dir for _, is_dir in names_types)
        if len(names_types) == 1:
            name, is_dir = names_types[0]
            confirmation = (
                f"Delete folder '{name}' and all of its contents, including "
                "subfolders?"
                if is_dir
                else f"Delete '{name}'?"
            )
        else:
            confirmation = f"Delete {len(names_types)} selected items?"
            if has_directories:
                confirmation += (
                    "\nAny selected folders and all their contents, including "
                    "subfolders, will also be deleted."
                )
        reply = QMessageBox.question(
            self, "Delete",
            confirmation,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            def run_delete():
                count = 0
                for name, is_dir in names_types:
                    if is_cancelled():
                        return count
                    path = f"{self.current_path.rstrip('/')}/{name}"
                    if self.adb_handler.delete_item(path, is_dir):
                        count += 1
                return count

            def on_done(count):
                self.status_label.setText(f"Deleted {count} items")
                self.refresh_files()

            self._run_modal(f"Delete {len(names_types)} items", run_delete, on_done=on_done)

    def create_new_file(self):
        if not self.adb_handler.device_connected:
            return
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            path = f"{self.current_path.rstrip('/')}/{name}"

            def on_done(_):
                self.status_label.setText(f"Created '{name}'")
                self.refresh_files()

            def on_error():
                self.status_label.setText(f"Create failed")

            self._run_modal(
                f"Create file {name}",
                self.adb_handler.create_file,
                path,
                on_done=on_done,
                on_error=on_error,
            )

    def create_new_folder(self):
        if not self.adb_handler.device_connected:
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            path = f"{self.current_path.rstrip('/')}/{name}"

            def on_done(_):
                self.status_label.setText(f"Created '{name}'")
                self.refresh_files()

            def on_error():
                self.status_label.setText(f"Create failed")

            self._run_modal(
                f"Create folder {name}",
                self.adb_handler.create_folder,
                path,
                on_done=on_done,
                on_error=on_error,
            )

    def upload_file_to_device(self):
        if not self.adb_handler.device_connected:
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not file_path:
            return
        self.upload_files_and_folders([file_path])

    def import_folder_from_pc(self):
        if not self.adb_handler.device_connected:
            return
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Import")
        if folder_path:
            self.upload_files_and_folders([folder_path])

    def upload_files_and_folders(self, files):
        if not self.adb_handler.device_connected:
            return

        target_path = self.current_path.rstrip("/") or "/"
        try:
            plan = self._build_upload_plan(files, target_path)
        except (OSError, RuntimeError) as error:
            self.status_label.setText(f"Import from PC failed: {error}")
            return
        if not plan["files"] and not plan["directories"]:
            self.status_label.setText("No files to upload")
            return

        self._run_modal(
            "Checking destination files",
            self._inspect_upload_conflicts,
            plan,
            on_done=lambda result: self._resolve_upload_conflicts(
                plan, result[0]
            ),
            on_error=lambda: self.status_label.setText(
                "Could not verify destination files; import was not started"
            ),
            on_cancel=lambda: self.status_label.setText("Import cancelled"),
        )

    @staticmethod
    def _build_upload_plan(files, target_path):
        directories = []
        uploads = []

        def raise_walk_error(error):
            raise error

        for path in files:
            if os.path.isdir(path):
                folder_name = os.path.basename(os.path.normpath(path))
                if not folder_name:
                    raise RuntimeError(
                        f"Cannot determine the folder name for '{path}'."
                    )
                remote_root = f"{target_path.rstrip('/')}/{folder_name}"
                for root, _, filenames in os.walk(path, onerror=raise_walk_error):
                    relative_dir = os.path.relpath(root, path)
                    remote_dir = remote_root
                    if relative_dir != ".":
                        relative_dir = relative_dir.replace(os.sep, "/")
                        remote_dir = f"{remote_root}/{relative_dir}"
                    directories.append(remote_dir)
                    for filename in filenames:
                        local_path = os.path.join(root, filename)
                        uploads.append((
                            local_path,
                            remote_dir,
                            f"{remote_dir.rstrip('/')}/{filename}",
                        ))
            elif os.path.isfile(path):
                filename = os.path.basename(path)
                uploads.append((
                    path,
                    target_path,
                    f"{target_path.rstrip('/')}/{filename}",
                ))
            else:
                raise RuntimeError(f"'{path}' is not a file or folder.")

        return {
            "directories": list(dict.fromkeys(directories)),
            "files": uploads,
        }

    def _inspect_upload_conflicts(self, plan):
        conflicts = {}
        files_by_directory = {}
        for upload in plan["files"]:
            files_by_directory.setdefault(upload[1], []).append(upload)
        remote_directories = list(dict.fromkeys(
            [*plan["directories"], *files_by_directory]
        ))
        for remote_dir in remote_directories:
            if is_cancelled():
                return (conflicts,)

            self.adb_handler.last_error = None
            exists = self.adb_handler._remote_path_exists(
                remote_dir, use_root=self.use_root
            )
            if exists is None:
                error = getattr(self.adb_handler, "last_error", None)
                raise RuntimeError(
                    f"Could not verify destination folder '{remote_dir}'"
                    + (f": {error}" if error else ".")
                )
            if not exists:
                continue

            self.adb_handler.last_error = None
            entries = self.adb_handler.list_directory(remote_dir, self.use_root)
            listing_error = getattr(self.adb_handler, "last_error", None)
            if entries is None or listing_error:
                raise RuntimeError(
                    f"Could not list destination folder '{remote_dir}'"
                    + (f": {listing_error}" if listing_error else ".")
                )

            existing_entries = {entry.name: entry for entry in entries}
            for local_path, _, remote_path in files_by_directory.get(remote_dir, ()):
                existing = existing_entries.get(os.path.basename(local_path))
                if existing is None:
                    continue
                if existing.is_dir:
                    raise RuntimeError(
                        f"Cannot upload file '{local_path}': a folder already "
                        f"exists at '{remote_path}'."
                    )
                conflicts[remote_path] = (local_path, existing)
        return (conflicts,)

    @staticmethod
    def _format_upload_size(size):
        value = float(size)
        for unit in ("Bytes", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{int(value)} {unit}" if unit == "Bytes" else f"{value:.1f} {unit}"
            value /= 1024

    def _confirm_upload_conflict(self, remote_path, local_path, existing):
        source_info = os.stat(local_path)
        source_modified = datetime.fromtimestamp(source_info.st_mtime).strftime(
            "%d/%m/%Y %H:%M:%S"
        )
        try:
            destination_modified = datetime.strptime(
                existing.date_modified, "%Y-%m-%d %H:%M"
            ).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            destination_modified = existing.date_modified

        box = QMessageBox(self)
        box.setWindowTitle("File already exists")
        box.setText("The following file already exists:")
        box.setInformativeText(
            f"{remote_path}\n\n"
            f"Source: {self._format_upload_size(source_info.st_size)}, "
            f"Modified {source_modified}\n"
            f"Destination: {self._format_upload_size(existing.size)}, "
            f"Modified {destination_modified}\n\n"
            "Overwriting will replace the existing content."
        )
        overwrite = box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton("Skip", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        apply_to_all = ApplyToAllCheckBox("Apply to all conflicts")
        apply_to_all.setObjectName("apply_to_all_conflicts")
        apply_to_all.setAccessibleName("Apply to all file conflicts")
        apply_to_all.setToolTip(
            "Use this choice for every remaining file conflict in this import."
        )
        box.setCheckBox(apply_to_all)
        box.exec()
        clicked = box.clickedButton()
        if clicked is overwrite:
            choice = "overwrite"
        elif clicked is skip:
            choice = "skip"
        else:
            choice = "cancel"
        return choice, apply_to_all.isChecked()

    def _resolve_upload_conflicts(self, plan, conflicts):
        choices = {}
        apply_choice = None
        for remote_path, (local_path, existing) in conflicts.items():
            if apply_choice is None:
                try:
                    choice, apply_to_all = self._confirm_upload_conflict(
                        remote_path, local_path, existing
                    )
                except (OSError, OverflowError, ValueError) as error:
                    self.status_label.setText(
                        f"Could not read source file '{local_path}': {error}; "
                        "import was not started"
                    )
                    return
                if apply_to_all and choice != "cancel":
                    apply_choice = choice
            else:
                choice = apply_choice
            if choice == "cancel":
                self.status_label.setText("Import cancelled; no files were uploaded")
                return
            choices[remote_path] = choice

        def run_upload():
            uploaded = 0
            skipped = 0
            for remote_dir in plan["directories"]:
                if is_cancelled():
                    return uploaded, skipped
                if not self.adb_handler.create_folder(remote_dir):
                    raise RuntimeError(
                        f"Failed to create device folder '{remote_dir}'."
                    )
            for local_path, _, remote_path in plan["files"]:
                if is_cancelled():
                    return uploaded, skipped
                if choices.get(remote_path) == "skip":
                    skipped += 1
                    continue
                if not self.adb_handler.push_file(local_path, remote_path):
                    raise RuntimeError(
                        f"Failed to upload '{local_path}' to '{remote_path}'."
                    )
                uploaded += 1
            return uploaded, skipped

        def on_done(result):
            uploaded, skipped = result
            self.status_label.setText(
                f"Uploaded {uploaded} files; skipped {skipped}"
            )
            self.refresh_files()

        self._run_modal(
            "Importing files from PC",
            run_upload,
            on_done=on_done,
            on_error=lambda: self.status_label.setText("Import from PC failed"),
            on_cancel=lambda: self.status_label.setText("Import cancelled"),
        )

    def download_selected_items(self):
        if not self.adb_handler.device_connected:
            return
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return
        save_dir = QFileDialog.getExistingDirectory(self, "Download Location")
        if not save_dir:
            return
        pairs = []
        for index in indexes:
            name = self.tree_model.data(self.tree_model.index(index.row(), 0))
            typ = self.tree_model.data(self.tree_model.index(index.row(), 1))
            if not name or name == "..":
                continue
            remote = f"{self.current_path.rstrip('/')}/{name}"
            local = os.path.join(save_dir, name)
            pairs.append((remote, local))

        def run_dl():
            count = 0
            for remote, local in pairs:
                if is_cancelled():
                    return count
                if self.adb_handler.pull_file(remote, local):
                    count += 1
            return count

        def on_done(count):
            self.status_label.setText(f"Downloaded {count} files")

        self._run_modal(f"Download {len(pairs)} files", run_dl, on_done=on_done)

    def copy_selected_to(self):
        if not self.adb_handler.device_connected:
            return
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            return
        names = []
        for index in indexes:
            name = self.tree_model.data(self.tree_model.index(index.row(), 0))
            is_dir = self.tree_model.data(self.tree_model.index(index.row(), 1)) == "Directory"
            if name and name != "..":
                names.append((name, is_dir))
        if not names:
            return

        from select_directory_dialog import SelectDirectoryDialog
        dialog = SelectDirectoryDialog(
            self, self.adb_handler, self.current_path, self.root_path, self.use_root
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            target = dialog.get_selected_path()
            if not target:
                return
            if QMessageBox.question(self, "Copy", f"Copy {len(names)} items to '{target}'?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                return

            def run_copy():
                count = 0
                for name, is_dir in names:
                    if is_cancelled():
                        return count
                    src = f"{self.current_path.rstrip('/')}/{name}"
                    dst = f"{target.rstrip('/')}/{name}"
                    backup = None
                    copied = False
                    try:
                        if self.adb_handler.path_exists(dst):
                            backup_path = (
                                f"{dst.rsplit('/', 1)[0]}/"
                                f".adb-explorer-backup-{uuid.uuid4().hex}"
                            )
                            if not self.adb_handler._move_remote_path_for_recovery(
                                dst, backup_path
                            ):
                                continue
                            backup = backup_path
                        copied = self.adb_handler.copy_on_device(src, dst)
                        if copied:
                            count += 1
                    except Exception:
                        copied = False
                    finally:
                        if backup:
                            if copied:
                                self.adb_handler._remove_remote_partial(backup)
                            else:
                                self.adb_handler._remove_remote_partial(dst)
                                self.adb_handler._move_remote_path_for_recovery(
                                    backup, dst
                                )
                return count

            def on_done(count):
                self.status_label.setText(f"Copied {count} items")
                self.refresh_files()

            self._run_modal(f"Copy {len(names)} items", run_copy, on_done=on_done)

    def batch_rename_selected(self):
        if not self.adb_handler.device_connected:
            return
        indexes = self.tree_view.selectionModel().selectedRows()
        if len(indexes) < 2:
            QMessageBox.information(self, "Info", "Select 2+ items to batch rename.")
            return
        base, ok = QInputDialog.getText(self, "Batch Rename", "Base name:")
        if not ok or not base:
            return
        padding = len(str(len(indexes)))

        def run():
            count = 0
            for i, index in enumerate(indexes):
                if is_cancelled():
                    return count
                old = self.tree_model.data(self.tree_model.index(index.row(), 0))
                new = f"{base}{str(i+1).zfill(padding)}"
                old_path = f"{self.current_path.rstrip('/')}/{old}"
                new_path = f"{self.current_path.rstrip('/')}/{new}"
                if self.adb_handler.rename_item(old_path, new_path):
                    count += 1
            return count

        def on_done(count):
            self.status_label.setText(f"Renamed {count} items")
            self.refresh_files()

        self._run_modal(f"Rename {len(indexes)} items", run, on_done=on_done)

    

    def handle_drop_event(self, event):
        if not self.adb_handler.device_connected:
            return
        urls = event.mimeData().urls()
        if not urls:
            return
        paths = [u.toLocalFile() for u in urls]
        self.upload_files_and_folders(paths)

    

    def _run_modal(
        self, title, fn, *args, on_done=None, on_error=None, on_cancel=None,
        refresh=False,
    ):
        task = WorkerThread(title, fn, *args)

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
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
            parent_window = self.window()
            task_manager = getattr(parent_window, "task_manager", None)
            if task_manager is None:
                return
            sent_to_background[0] = True
            dlg.hide()
            task_manager.add_task(task, name=title, on_reopen=reopen_dialog)
            if hasattr(parent_window, "_position_task_manager"):
                parent_window._position_task_manager()

        bg_btn.setEnabled(hasattr(self.window(), "task_manager"))
        bg_btn.clicked.connect(send_to_background)

        def cancel_task():
            task.cancel()
            dlg.close()

        cancel_btn.clicked.connect(cancel_task)

        def handle_finished(val):
            completed[0] = True
            if dlg.isVisible():
                dlg.close()
            if task.is_cancelled():
                if on_cancel:
                    on_cancel()
                return
            if failed[0]:
                return
            is_ok = bool(val) if val is not None else False
            if is_ok:
                if on_done:
                    on_done(val)
                if refresh:
                    self.refresh_files()
            else:
                if on_error:
                    on_error()

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

    def _run_background(self, name, fn, *args, on_done=None, on_error=None, refresh=False):
        parent_window = self.window()
        if hasattr(parent_window, 'task_manager'):
            task = parent_window.task_manager.submit(name, fn, *args)
        else:
            task = WorkerThread(name, fn, *args)
            task.start()

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
        return task


class NonOverlappingTabBar(QTabBar):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.separate_scroll_buttons()

    def separate_scroll_buttons(self, buttons=None):
        if buttons is None:
            buttons = {
                "left" if button.objectName() == "ScrollLeftButton" else "right": button
                for button in self.findChildren(QToolButton)
                if button.objectName() in {"ScrollLeftButton", "ScrollRightButton"}
            }
        left = buttons.get("left")
        right = buttons.get("right")
        if left is None or right is None:
            return
        button_width = 14
        button_height = 24
        gap = 3
        y = (self.height() - button_height) // 2
        left.setFixedSize(button_width, button_height)
        right.setFixedSize(button_width, button_height)
        left.move(self.width() - (button_width * 2 + gap), y)
        right.move(self.width() - button_width, y)


class DevicePanelGroup(QWidget):
    cross_device_drop = pyqtSignal(str, list, str)
    close_requested = pyqtSignal()

    def __init__(self, parent, adb_handler, device_info=None):
        super().__init__(parent)
        self.adb_handler = adb_handler
        self.device_info = device_info or {}
        self._views = []
        self._closing = False
        self._last_path = "/storage/emulated/0"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header_container = QWidget()
        header_container.setObjectName("panel_header")
        header = QHBoxLayout(header_container)
        header.setContentsMargins(6, 2, 4, 2)
        header.setSpacing(6)
        self.device_header = QLabel(self.device_name)
        self.device_header.setObjectName("device_header")
        header.addWidget(self.device_header)
        header.addStretch()
        self.conn_label = QLabel()
        header.addWidget(self.conn_label)
        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("panel_close_btn")
        self.close_btn.setToolTip("Close this device panel")
        self.close_btn.setAccessibleName("Close device panel")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(self.close_btn)
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setObjectName("add_path_tab_btn")
        self.add_tab_btn.setToolTip("Add a path tab")
        self.add_tab_btn.setAccessibleName("Add path tab")
        self.add_tab_btn.setFixedSize(30, 30)
        self.add_tab_btn.clicked.connect(lambda: self.add_tab())
        header.insertWidget(header.count() - 1, self.add_tab_btn)
        layout.addWidget(header_container)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("path_tabs")
        self.tabs.setTabBar(NonOverlappingTabBar())
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.currentChanged.connect(self._update_connection_status)
        self.tabs.tabBar().setObjectName("path_tab_bar")
        layout.addWidget(self.tabs)

        self.add_tab()
        self.update_connection_status()

    @property
    def active_view(self):
        return self.tabs.currentWidget()

    @property
    def device_serial(self):
        return self.adb_handler.device_serial or ""

    @property
    def device_name(self):
        serial = self.device_serial
        model = self.device_info.get("model") or self.adb_handler.devices.get(serial, "")
        return model or serial

    @property
    def current_path(self):
        return (
            self.active_view.current_path
            if self.active_view else self._last_path
        )

    @current_path.setter
    def current_path(self, path):
        if self.active_view:
            self.active_view.current_path = path

    def __getattr__(self, name):
        views = self.__dict__.get("_views")
        if views:
            active_view = self.active_view
            if active_view is not None:
                return getattr(active_view, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def add_tab(self, path=None):
        if self._closing:
            return None
        start_path = path or self.current_path
        view = DevicePanel(
            self.tabs,
            self.adb_handler,
            self.device_info,
            start_path=start_path,
            compact_header=True,
        )
        self._views.append(view)
        view.path_changed.connect(
            lambda changed_path, panel=view: self._on_view_path_changed(
                panel, changed_path
            )
        )
        view.cross_device_drop.connect(self.cross_device_drop)
        index = self.tabs.addTab(view, self._tab_title(start_path))
        close_button = QToolButton(self.tabs.tabBar())
        close_button.setObjectName("close_path_tab_btn")
        close_button.setText("x")
        close_button.setToolTip("Close tab")
        close_button.setAccessibleName("Close tab")
        close_button.setAutoRaise(True)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(
            lambda _checked=False, tab=view: self._close_view(tab)
        )
        self.tabs.tabBar().setTabButton(
            index, self.tabs.tabBar().ButtonPosition.RightSide, close_button
        )
        self.tabs.setCurrentIndex(index)
        self._enable_click_activation()
        QTimer.singleShot(0, self._style_tab_scroll_buttons)
        self._update_connection_status()
        return view

    def _enable_click_activation(self):
        widgets = [self, *self.findChildren(QWidget)]
        for widget in widgets:
            if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
                widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def _style_tab_scroll_buttons(self):
        buttons = self.tabs.tabBar().findChildren(QToolButton)
        scroll_buttons = {}
        for button in buttons:
            if button.objectName() == "ScrollLeftButton":
                button.setText("<")
                button.setToolTip("Scroll tabs left")
                button.setAccessibleName("Scroll tabs left")
                scroll_buttons["left"] = button
            elif button.objectName() == "ScrollRightButton":
                button.setText(">")
                button.setToolTip("Scroll tabs right")
                button.setAccessibleName("Scroll tabs right")
                scroll_buttons["right"] = button
            else:
                continue
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tabs.tabBar().separate_scroll_buttons(scroll_buttons)

    @staticmethod
    def _tab_title(path):
        return path.rstrip("/").rsplit("/", 1)[-1] or "/"

    def _update_tab_title(self, view, path):
        index = self.tabs.indexOf(view)
        if index >= 0:
            self.tabs.setTabText(index, self._tab_title(path))

    def _on_view_path_changed(self, view, path):
        self._last_path = path
        self._update_tab_title(view, path)

    def _close_view(self, view):
        index = self.tabs.indexOf(view)
        if index < 0:
            return
        self._last_path = view.current_path
        self._views.remove(view)
        self.tabs.removeTab(index)
        view.prepare_for_close()
        if self._views:
            self._update_connection_status()

    def _close_tab(self, index):
        if not 0 <= index < len(self._views):
            return
        self._close_view(self._views[index])

    def close_active_tab(self):
        if self.active_view is not None:
            self._close_view(self.active_view)

    def _update_connection_status(self, _index=None):
        if not self._views:
            return
        self.device_header.setText(self.device_name)
        if self.adb_handler.device_connected:
            self.conn_label.setText("🟢 Connected")
            self.conn_label.setStyleSheet("color: green; font-size: 10px; padding: 0 8px 2px 8px;")
        else:
            self.conn_label.setText("🔴 Disconnected")
            self.conn_label.setStyleSheet("color: red; font-size: 10px; padding: 0 8px 2px 8px;")

    def update_connection_status(self):
        for view in self._views:
            view.update_connection_status()
        self._update_connection_status()

    def contains_focus(self):
        focus_widget = QApplication.focusWidget()
        return focus_widget is not None and (
            focus_widget is self or self.isAncestorOf(focus_widget)
        )

    def contains_view(self, view):
        return view in self._views

    def prepare_for_close(self):
        if self._closing:
            return
        self._closing = True
        self.hide()
        for view in self._views:
            view.prepare_for_close()
        self._views.clear()
        self.deleteLater()
