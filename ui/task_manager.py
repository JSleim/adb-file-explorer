_E = "Failed"
_D = "Cancelled"
_C = True
_B = False
_A = None
import logging, threading
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from operation_control import (
    OperationControl,
    clear_current_operation,
    set_current_operation,
)

_logger = logging.getLogger(__name__)


class WorkerThread(QThread):
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(A, name, fn, *B, **C):
        super().__init__()
        A.name = name
        A._fn = fn
        A._args = B
        A._kwargs = C
        A._result = _A
        A._error_message = _A
        A._operation = OperationControl()
        A._cancel_callbacks = []
        A._cancel_callback_lock = threading.Lock()

    def run(A):
        set_current_operation(A._operation)
        try:
            A._result = A._fn(*A._args, **A._kwargs)
        except Exception as B:
            if not A.is_cancelled():
                A._result = _A
                A._error_message = str(B)
                A.error_signal.emit(A._error_message)
        finally:
            clear_current_operation()
            A.finished_signal.emit(A._result)

    def result(A):
        return A._result

    def error_message(A):
        return A._error_message

    def is_cancelled(A):
        return A._operation.cancelled

    def add_cancel_callback(A, callback):
        B = callback
        with A._cancel_callback_lock:
            if not A.is_cancelled():
                A._cancel_callbacks.append(B)
                return
        A._run_cancel_callback(B)

    def cancel(A):
        A.requestInterruption()
        A._operation.cancel()
        with A._cancel_callback_lock:
            B, A._cancel_callbacks = A._cancel_callbacks, []
        for C in B:
            A._run_cancel_callback(C)

    @staticmethod
    def _run_cancel_callback(callback):
        try:
            callback()
        except Exception:
            _logger.exception("Could not cancel a background operation")


class TaskRow(QFrame):
    removed = pyqtSignal(object)
    mousePressed = pyqtSignal(object)

    def __init__(A, task, name=_A, on_reopen=_A):
        B = task
        super().__init__()
        A.task = B
        A.name = name or getattr(B, "name", "Task")
        A._on_reopen = on_reopen
        A._result = _A
        A._finished = _B
        A._failed = _B
        A._setup_ui()
        A.setCursor(Qt.CursorShape.PointingHandCursor)
        B.finished_signal.connect(A._on_finished)
        B.error_signal.connect(A._on_error)
        if hasattr(B, "status_changed"):
            B.status_changed.connect(A.status_label.setText)

    def _setup_ui(A):
        A.setFixedHeight(44)
        B = QHBoxLayout(A)
        B.setContentsMargins(8, 2, 8, 2)
        B.setSpacing(8)
        D = QLabel("●")
        D.setObjectName("task_spinner")
        A._spinner = D
        B.addWidget(D)
        C = QVBoxLayout()
        C.setSpacing(0)
        E = QLabel(A.name)
        E.setObjectName("task_title")
        E.setTextFormat(Qt.TextFormat.PlainText)
        A.status_label = QLabel(A.tr("Running..."))
        A.status_label.setObjectName("task_status")
        C.addWidget(E)
        C.addWidget(A.status_label)
        B.addLayout(C, 1)
        A.progress = QProgressBar()
        A.progress.setRange(0, 0)
        A.progress.setFixedWidth(100)
        A.progress.setFixedHeight(14)
        A.progress.setTextVisible(_B)
        B.addWidget(A.progress)
        A.cancel_btn = QPushButton("✕")
        A.cancel_btn.setFixedSize(20, 20)
        A.cancel_btn.setStyleSheet("border: none; font-size: 10px; color: #999;")
        A.cancel_btn.clicked.connect(A._on_cancel)
        B.addWidget(A.cancel_btn)

    def _on_cancel(A):
        A.cancel_btn.setEnabled(_B)
        A.status_label.setText(A.tr("Cancelling..."))
        A.task.cancel()

    def _on_error(A, message):
        A._failed = _C
        A._spinner.setStyleSheet("color: #e53935; font-size: 14px;")
        A.status_label.setText(A.tr("Error: {0}").format(message[:40]))
        A.cancel_btn.setVisible(_B)
        QTimer.singleShot(4000, lambda: A.removed.emit(A))

    def mousePressEvent(A, event):
        super().mousePressEvent(event)
        if A.task.isRunning() and callable(A._on_reopen):
            A._on_reopen()
        elif A._finished:
            A._show_detail()

    def _show_detail(A):
        from PyQt6.QtWidgets import QMessageBox as E

        if A.task.is_cancelled():
            C = _D
        elif A._result is not _A and not A._failed and bool(A._result):
            C = "Succeeded"
        else:
            C = _E
        B = E(A)
        B.setWindowTitle(A.tr("Task: {0}").format(A.name))
        B.setText(A.tr("Status: {0}").format(C))
        D = f"Name: {A.name}\nResult: {A._result}"
        if A.task.error_message():
            D += f"\nError: {A.task.error_message()}"
        B.setDetailedText(D)
        B.exec()

    def _on_finished(A, result):
        B = result
        A._finished = _C
        if A._failed:
            return
        if A.task.is_cancelled():
            A._spinner.setStyleSheet("color: #999; font-size: 14px;")
            A._result = B
            A.status_label.setText(A.tr(_D))
            A.cancel_btn.setVisible(_B)
            QTimer.singleShot(3000, lambda: A.removed.emit(A))
            return
        A._spinner.setStyleSheet("color: #4caf50; font-size: 14px;")
        A._result = B
        C = bool(B) if B is not _A else _B
        A.status_label.setText(A.tr("Done ✓") if C else A.tr(_E))
        A.cancel_btn.setVisible(_B)
        QTimer.singleShot(5000, lambda: A.removed.emit(A))


class BackgroundTaskManager(QFrame):
    def __init__(A, parent=_A):
        super().__init__(parent)
        A._tasks = []
        A._expanded = _C
        A._setup_ui()
        A.setVisible(_B)

    def _setup_ui(A):
        A.setObjectName("task_manager")
        A.setFixedWidth(360)
        C = QVBoxLayout(A)
        C.setContentsMargins(0, 0, 0, 0)
        C.setSpacing(0)
        D = QWidget()
        D.setObjectName("task_header")
        B = QHBoxLayout(D)
        B.setContentsMargins(10, 6, 10, 6)
        E = QLabel(A.tr("Background Tasks"))
        E.setObjectName("task_header_title")
        B.addWidget(E)
        B.addStretch()
        A.count_label = QLabel("0")
        A.count_label.setObjectName("task_count")
        B.addWidget(A.count_label)
        A.toggle_btn = QPushButton("−")
        A.toggle_btn.setFixedSize(18, 18)
        A.toggle_btn.setObjectName("task_toggle")
        A.toggle_btn.clicked.connect(A._toggle)
        B.addWidget(A.toggle_btn)
        C.addWidget(D)
        A.scroll = QScrollArea()
        A.scroll.setWidgetResizable(_C)
        A.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        A.scroll.setObjectName("task_scroll")
        A._task_container = QWidget()
        A._task_container.setObjectName("task_container")
        A._task_layout = QVBoxLayout(A._task_container)
        A._task_layout.setContentsMargins(4, 4, 4, 4)
        A._task_layout.setSpacing(6)
        A._no_tasks_label = QLabel(A.tr("No background tasks"))
        A._no_tasks_label.setObjectName("task_none")
        A._task_layout.addWidget(A._no_tasks_label)
        A._task_layout.addStretch()
        A.scroll.setWidget(A._task_container)
        A.scroll.setMinimumHeight(50)
        A.scroll.setMaximumHeight(70)
        A.scroll.viewport().setStyleSheet("background: transparent;")
        C.addWidget(A.scroll)

    def submit(B, name, fn, *C, on_reopen=_A):
        A = WorkerThread(name, fn, *C)
        B.add_task(A, name=name, on_reopen=on_reopen)
        A.start()
        return A

    def add_task(A, task, name=_A, on_reopen=_A):
        B = task
        A._expanded = _C
        C = TaskRow(B, name=name, on_reopen=on_reopen)
        C.removed.connect(A._remove_row)
        B.finished_signal.connect(lambda _=_A: A._update_count())
        B.error_signal.connect(lambda _=_A: A._update_count())
        A._tasks.append(C)
        A._task_layout.insertWidget(A._task_layout.count() - 1, C)
        A._no_tasks_label.setVisible(_B)
        A._update_count()
        A.setVisible(_C)
        A._adjust_scroll_height()
        A.toggle_btn.setText("−")
        return B

    def _remove_row(A, row):
        B = row
        if B in A._tasks:
            A._tasks.remove(B)
            A._task_layout.removeWidget(B)
            B.deleteLater()
            A._update_count()
            A._adjust_scroll_height()
        if not A._tasks:
            A._no_tasks_label.setVisible(_C)
            A.setVisible(_B)

    def _adjust_scroll_height(A):
        B = len(A._tasks)
        if B == 0:
            A.scroll.setMaximumHeight(70)
            A.scroll.setMinimumHeight(50)
            return
        A._no_tasks_label.setVisible(_B)
        C = min(250, B * 48 + 12)
        A.scroll.setMaximumHeight(C)
        A.scroll.setMinimumHeight(50)
        A.adjustSize()

    def _update_count(A):
        B = sum(1 for A in A._tasks if A.task.isRunning())
        A.count_label.setText(str(B))

    def _toggle(A):
        A._expanded = not A._expanded
        if A._expanded:
            A._adjust_scroll_height()
            A.scroll.setMinimumHeight(0)
        else:
            A.scroll.setMaximumHeight(0)
            A.scroll.setMinimumHeight(0)
        A.toggle_btn.setText("−" if A._expanded else "+")
        A.adjustSize()
        A.updateGeometry()
        B = A.window()
        if hasattr(B, "_position_task_manager"):
            B._position_task_manager()
