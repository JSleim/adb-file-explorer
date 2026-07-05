from PyQt6.QtWidgets import QTreeView, QMessageBox
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag


ADB_MIME = "application/x-adb-paths"


class DropTreeView(QTreeView):

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.setDragEnabled(True)
        self.setAlternatingRowColors(True)

    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not event.source():
            event.acceptProposedAction()
            return
        if event.mimeData().hasFormat(ADB_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() and not event.source():
            event.acceptProposedAction()
            return
        if event.mimeData().hasFormat(ADB_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        
        if md.hasUrls() and not event.source():
            self.main_window.handle_drop_event(event)
            event.acceptProposedAction()
            return
        
        if md.hasFormat(ADB_MIME):
            self._handle_internal_drop(event)
            event.acceptProposedAction()
            return
        event.ignore()

    
    def startDrag(self, supportedActions):
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return

        paths = []
        for index in indexes:
            name = self.model().data(index.siblingAtColumn(0))
            if name and name != "..":
                paths.append(f"{self.main_window.current_path.rstrip('/')}/{name}")

        if not paths:
            return

        md = QMimeData()
        md.setData(ADB_MIME, "\n".join(paths).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(md)
        drag.exec(Qt.DropAction.CopyAction)

    def _handle_internal_drop(self, event):
        md = event.mimeData()
        raw = bytes(md.data(ADB_MIME)).decode("utf-8")
        src_paths = [p.strip() for p in raw.split("\n") if p.strip()]

        
        index = self.indexAt(event.position().toPoint())
        dest = self.main_window.current_path
        if index.isValid():
            name = self.model().data(index.siblingAtColumn(0))
            is_dir = self.model().data(index.siblingAtColumn(1)) == "Directory"
            if name == "..":
                dest = "/".join(self.main_window.current_path.rstrip("/").split("/")[:-1]) or "/"
            elif is_dir:
                dest = f"{self.main_window.current_path.rstrip('/')}/{name}"

        self.main_window._run_background(
            "Move items",
            self.main_window.adb_handler.move_on_device, src_paths[0],
            f"{dest.rstrip('/')}/{src_paths[0].rstrip('/').split('/')[-1]}",
            refresh=True,
            on_error=lambda: QMessageBox.warning(self.main_window, "Move Error", "Failed to move items."),
        )

        for src in src_paths[1:]:
            name = src.rstrip("/").split("/")[-1]
            dst = f"{dest.rstrip('/')}/{name}"
            self.main_window.adb_handler.move_on_device(src, dst)
