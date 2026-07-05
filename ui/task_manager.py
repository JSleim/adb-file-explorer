from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QScrollArea, QWidget, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread


class WorkerThread(QThread):
    """Single thread class used by both modal and background task flows."""
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, name, fn, *args, **kwargs):
        super().__init__()
        self.name = name
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._result = None
        self._error_message = None

    def run(self):
        try:
            self._result = self._fn(*self._args, **self._kwargs)
        except Exception as e:
            self._result = None
            self._error_message = str(e)
            self.error_signal.emit(self._error_message)
        finally:
            self.finished_signal.emit(self._result)

    def result(self):
        return self._result

    def error_message(self):
        return self._error_message

    def cancel(self):
        self.requestInterruption()
        fn_self = getattr(self._fn, '__self__', None)
        if fn_self and hasattr(fn_self, '_active_process'):
            proc = fn_self._active_process
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass


class TaskRow(QFrame):
    removed = pyqtSignal(object)

    mousePressed = pyqtSignal(object)

    def __init__(self, task, name=None, on_reopen=None):
        super().__init__()
        self.task = task
        self.name = name or getattr(task, 'name', 'Task')
        self._on_reopen = on_reopen
        self._result = None
        self._finished = False
        self._failed = False
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        task.finished_signal.connect(self._on_finished)
        task.error_signal.connect(self._on_error)
        if hasattr(task, 'status_changed'):
            task.status_changed.connect(self.status_label.setText)

    def _setup_ui(self):
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)

        spinner = QLabel("●")
        spinner.setStyleSheet("color: #4a8fe0; font-size: 14px;")
        self._spinner = spinner
        layout.addWidget(spinner)

        info = QVBoxLayout()
        info.setSpacing(0)
        title = QLabel(self.name)
        title.setStyleSheet("font-weight: 600; font-size: 11px; color: #333;")
        title.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label = QLabel("Running...")
        self.status_label.setStyleSheet("font-size: 10px; color: #888;")
        info.addWidget(title)
        info.addWidget(self.status_label)
        layout.addLayout(info, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(100)
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedSize(20, 20)
        self.cancel_btn.setStyleSheet("border: none; font-size: 10px; color: #999;")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

    def _on_cancel(self):
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling...")
        self.task.cancel()

    def _on_error(self, message):
        self._failed = True
        self._spinner.setStyleSheet("color: #e53935; font-size: 14px;")
        self.status_label.setText(f"Error: {message[:40]}")
        self.cancel_btn.setVisible(False)
        QTimer.singleShot(4000, lambda: self.removed.emit(self))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.task.isRunning() and callable(self._on_reopen):
            self._on_reopen()
        elif self._finished:
            self._show_detail()

    def _show_detail(self):
        from PyQt6.QtWidgets import QMessageBox
        ok = not self._failed and bool(self._result) if self._result is not None else False
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Task: {self.name}")
        msg.setText(f"Status: {'Succeeded' if ok else 'Failed'}")
        detail = f"Name: {self.name}\nResult: {self._result}"
        if self.task.error_message():
            detail += f"\nError: {self.task.error_message()}"
        msg.setDetailedText(detail)
        msg.exec()

    def _on_finished(self, result):
        self._finished = True
        if self._failed:
            return
        self._spinner.setStyleSheet("color: #4caf50; font-size: 14px;")
        self._result = result
        ok = bool(result) if result is not None else False
        self.status_label.setText("Done ✓" if ok else "Failed")
        self.cancel_btn.setVisible(False)
        QTimer.singleShot(5000, lambda: self.removed.emit(self))


class BackgroundTaskManager(QFrame):
    """Collapsible floating panel showing active background tasks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = []
        self._expanded = True
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self):
        self.setObjectName("task_manager")
        self.setStyleSheet("""
            #task_manager {
                background: #ffffff;
                border: 1px solid #d8d8d8;
                border-radius: 8px;
            }
            #task_manager QLabel {
                color: #333333;
            }
            #task_manager QPushButton {
                background: transparent;
                color: #555555;
            }
        """)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: #f8f9fa; border-bottom: 1px solid #e8e8e8; border-radius: 8px 8px 0 0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        title = QLabel("Background Tasks")
        title.setStyleSheet("font-weight: 600; font-size: 11px; color: #555;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet("font-size: 10px; color: #888;")
        header_layout.addWidget(self.count_label)
        self.toggle_btn = QPushButton("−")
        self.toggle_btn.setFixedSize(18, 18)
        self.toggle_btn.setStyleSheet("border: 1px solid #ccc; border-radius: 3px; font-size: 10px;")
        self.toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self.toggle_btn)
        layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            " QScrollBar:vertical { width: 6px; background: transparent; }"
        )
        self._task_container = QWidget()
        self._task_container.setStyleSheet("background: #ffffff;")
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(4, 4, 4, 4)
        self._task_layout.setSpacing(6)
        self._no_tasks_label = QLabel("No background tasks")
        self._no_tasks_label.setStyleSheet("color: #888; margin: 8px;")
        self._task_layout.addWidget(self._no_tasks_label)
        self._task_layout.addStretch()
        self.scroll.setWidget(self._task_container)
        self.scroll.setMinimumHeight(50)
        self.scroll.setMaximumHeight(70)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        layout.addWidget(self.scroll)

    def submit(self, name, fn, *args, on_reopen=None):
        """Create thread, add task row, start, return task. Non-blocking."""
        task = WorkerThread(name, fn, *args)
        self.add_task(task, name=name, on_reopen=on_reopen)
        task.start()
        return task

    def add_task(self, task, name=None, on_reopen=None):
        """Add an already-created task to the panel."""
        self._expanded = True
        row = TaskRow(task, name=name, on_reopen=on_reopen)
        row.removed.connect(self._remove_row)
        task.finished_signal.connect(lambda _=None: self._update_count())
        task.error_signal.connect(lambda _=None: self._update_count())
        self._tasks.append(row)
        self._task_layout.insertWidget(self._task_layout.count() - 1, row)
        self._no_tasks_label.setVisible(False)
        self._update_count()
        self.setVisible(True)
        self._adjust_scroll_height()
        self.toggle_btn.setText("−")
        return task

    def _remove_row(self, row):
        if row in self._tasks:
            self._tasks.remove(row)
            self._task_layout.removeWidget(row)
            row.deleteLater()
            self._update_count()
            self._adjust_scroll_height()
        if not self._tasks:
            self._no_tasks_label.setVisible(True)
            self.setVisible(False)

    def _adjust_scroll_height(self):
        n = len(self._tasks)
        if n == 0:
            self.scroll.setMaximumHeight(70)
            self.scroll.setMinimumHeight(50)
            return
        self._no_tasks_label.setVisible(False)
        target_height = min(250, n * 48 + 12)
        self.scroll.setMaximumHeight(target_height)
        self.scroll.setMinimumHeight(50)
        self.adjustSize()

    def _update_count(self):
        active = sum(1 for r in self._tasks if r.task.isRunning())
        self.count_label.setText(str(active))

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._adjust_scroll_height()
            self.scroll.setMinimumHeight(0)
        else:
            self.scroll.setMaximumHeight(0)
            self.scroll.setMinimumHeight(0)
        self.toggle_btn.setText("−" if self._expanded else "+")
        self.adjustSize()
        self.updateGeometry()
        owner = self.window()
        if hasattr(owner, '_position_task_manager'):
            owner._position_task_manager()
