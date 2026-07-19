from PyQt6.QtWidgets import QTreeView, QMessageBox
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag


ADB_MIME = "application/x-adb-paths"



class DropTreeView(QTreeView):

    def __init__(self, parent_widget, main_window):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.setDragEnabled(True)
        self.setAlternatingRowColors(True)

    def _get_device_serial(self):
        if hasattr(self.main_window, 'device_serial'):
            return self.main_window.device_serial
        if hasattr(self.main_window, 'adb_handler') and self.main_window.adb_handler:
            return self.main_window.adb_handler.device_serial or ""
        return ""

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
            raw = bytes(md.data(ADB_MIME)).decode("utf-8")
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            if not lines:
                event.ignore()
                return

            src_serial = lines[0]
            paths = lines[1:]

            dest = self._get_drop_destination(event)

            
            my_serial = self._get_device_serial()
            if src_serial != my_serial and my_serial:
                self._handle_cross_device_drop(src_serial, paths, dest)
                event.acceptProposedAction()
                return

            
            self._handle_internal_drop(paths, dest)
            event.acceptProposedAction()
            return

        event.ignore()

    def _get_drop_destination(self, event):
        dest = self.main_window.current_path
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            name = self.model().data(index.siblingAtColumn(0))
            is_dir = self.model().data(index.siblingAtColumn(1)) == "Directory"
            if name == "..":
                dest = "/".join(self.main_window.current_path.rstrip("/").split("/")[:-1]) or "/"
            elif is_dir:
                dest = f"{self.main_window.current_path.rstrip('/')}/{name}"
        return dest

    def _handle_cross_device_drop(self, src_serial, paths, dest_path):
        
        if hasattr(self.main_window, 'cross_device_drop'):
            self.main_window.cross_device_drop.emit(src_serial, paths, dest_path)
        else:
            
            window = self.window()
            if hasattr(window, '_on_cross_device_drop'):
                
                pass
            QMessageBox.warning(self, "Cross-Device Drop",
                                "Cross-device streaming not available from this view.")

    def startDrag(self, supportedActions):
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return

        serial = self._get_device_serial()
        paths = []
        for index in indexes:
            name = self.model().data(index.siblingAtColumn(0))
            if name and name != "..":
                paths.append(f"{self.main_window.current_path.rstrip('/')}/{name}")

        if not paths:
            return

        md = QMimeData()
        data_lines = [serial] + paths
        md.setData(ADB_MIME, "\n".join(data_lines).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(md)
        drag.exec(Qt.DropAction.CopyAction)

    def _handle_internal_drop(self, paths, dest):
        if not paths:
            return
        first = paths[0]
        name = first.rstrip("/").split("/")[-1]
        dst_path = f"{dest.rstrip('/')}/{name}"

        self.main_window._run_background(
            "Move items",
            self.main_window.adb_handler.move_on_device, first, dst_path,
            refresh=True,
            on_error=lambda: QMessageBox.warning(self, "Move Error", "Failed to move items."),
        )

        for src in paths[1:]:
            name = src.rstrip("/").split("/")[-1]
            dst = f"{dest.rstrip('/')}/{name}"
            self.main_window.adb_handler.move_on_device(src, dst)
