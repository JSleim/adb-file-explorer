from PyQt6.QtWidgets import QTreeView
from PyQt6.QtCore import Qt


class DropTreeView(QTreeView):
    """Tree view with drag-and-drop support for file upload."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDropMode.DropOnly)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.main_window.handle_drop_event(event)
            event.acceptProposedAction()
        else:
            event.ignore()
