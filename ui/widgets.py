import posixpath

from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QMessageBox, QTreeView

ADB_MIME = "application/x-adb-paths"


class DropTreeView(QTreeView):
    def __init__(A, parent_widget, main_window):
        B = parent_widget
        super().__init__(B)
        A.parent_widget = B
        A.main_window = main_window
        A.setAcceptDrops(True)
        A.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        A.setDragEnabled(True)
        A.setAlternatingRowColors(True)

    def _get_device_serial(A):
        if hasattr(A.main_window, "device_serial"):
            return A.main_window.device_serial
        if hasattr(A.main_window, "adb_handler") and A.main_window.adb_handler:
            return A.main_window.adb_handler.device_serial or ""
        return ""

    def mousePressEvent(B, event):
        A = event
        if A.button() == Qt.MouseButton.BackButton:
            B.main_window.go_back()
            A.accept()
            return
        if A.button() == Qt.MouseButton.ForwardButton:
            B.main_window.go_forward()
            A.accept()
            return
        super().mousePressEvent(A)

    def keyPressEvent(C, event):
        A = event
        if A.text() and not A.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            B = C.currentIndex()
            if B.isValid() and B.column() != 0:
                C.setCurrentIndex(B.siblingAtColumn(0))
        super().keyPressEvent(A)

    def dragEnterEvent(B, event):
        A = event
        if A.mimeData().hasUrls() and not A.source():
            A.acceptProposedAction()
            return
        if B._adb_paths_payload(A.mimeData()) is not None:
            A.acceptProposedAction()
            return
        A.ignore()

    def dragMoveEvent(B, event):
        A = event
        if A.mimeData().hasUrls() and not A.source():
            A.acceptProposedAction()
            return
        if B._adb_paths_payload(A.mimeData()) is not None:
            A.acceptProposedAction()
            return
        A.ignore()

    def dropEvent(B, event):
        A = event
        D = A.mimeData()
        if D.hasUrls() and not A.source():
            B.main_window.handle_drop_event(A)
            A.acceptProposedAction()
            return
        E = B._adb_paths_payload(D)
        if E is not None:
            J = E.decode("utf-8").rstrip("\x00")
            C = [A.strip() for A in J.split("\n") if A.strip()]
            if not C:
                A.ignore()
                return
            F = C[0]
            G = C[1:]
            H = B._get_drop_destination(A)
            I = B._get_device_serial()
            if F != I and I:
                B._handle_cross_device_drop(F, G, H)
                A.acceptProposedAction()
                return
            B._handle_internal_drop(G, H)
            A.acceptProposedAction()
            return
        A.ignore()

    @staticmethod
    def _adb_paths_payload(mime_data):
        A = mime_data
        if A.hasFormat(ADB_MIME):
            return bytes(A.data(ADB_MIME))
        for B in A.formats():
            if B.startswith("application/x-qt-windows-mime;value=") and ADB_MIME in B:
                return bytes(A.data(B))

    def _get_drop_destination(A, event):
        B = A.main_window.current_path
        C = A.indexAt(event.position().toPoint())
        if C.isValid():
            D = A.model().data(C.siblingAtColumn(0))
            E = A.model().data(C.siblingAtColumn(1)) == "Directory"
            if D == "..":
                B = (
                    "/".join(A.main_window.current_path.rstrip("/").split("/")[:-1])
                    or "/"
                )
            elif E:
                B = f"{A.main_window.current_path.rstrip('/')}/{D}"
        return B

    def _handle_cross_device_drop(A, src_serial, paths, dest_path):
        if hasattr(A.main_window, "cross_device_drop"):
            A.main_window.cross_device_drop.emit(src_serial, paths, dest_path)
        else:
            B = A.window()
            if hasattr(B, "_on_cross_device_drop"):
                pass
            QMessageBox.warning(
                A,
                A.tr("Cross-Device Drop"),
                A.tr("Cross-device streaming not available from this view."),
            )

    def startDrag(A, supportedActions):
        D = A.selectionModel().selectedRows()
        if not D:
            return
        G = A._get_device_serial()
        B = []
        for H in D:
            C = A.model().data(H.siblingAtColumn(0))
            if C and C != "..":
                B.append(f"{A.main_window.current_path.rstrip('/')}/{C}")
        if not B:
            return
        try:
            if A.main_window.start_native_drag(B):
                A.main_window.status_label.setText(
                    A.tr(
                        "Drop accepted; Windows may continue copying in the background."
                    )
                )
                return
            A.main_window.status_label.setText(
                A.tr("Native Windows drag source unavailable; using in-app drag.")
            )
        except (OSError, RuntimeError, ValueError) as I:
            QMessageBox.warning(A, A.tr("Drag Error"), str(I))
            A.main_window.status_label.setText(
                A.tr("Native drag failed; using in-app drag.")
            )
        E = QMimeData()
        J = [G] + B
        E.setData(ADB_MIME, "\n".join(J).encode("utf-8"))
        F = QDrag(A)
        F.setMimeData(E)
        F.exec(Qt.DropAction.CopyAction)

    def _handle_internal_drop(A, paths, dest):
        B = paths
        if not B:
            return
        C = posixpath.normpath(dest)
        B = [
            path
            for path in B
            if posixpath.dirname(posixpath.normpath(path)) != C
        ]
        if not B:
            return
        D = B[0]
        C = posixpath.basename(posixpath.normpath(D))
        F = posixpath.join(dest, C)
        A.main_window._run_background(
            "Move items",
            A.main_window.adb_handler.move_on_device,
            D,
            F,
            refresh=True,
            on_error=lambda: QMessageBox.warning(
                A, A.tr("Move Error"), A.tr("Failed to move items.")
            ),
        )
        for E in B[1:]:
            C = posixpath.basename(posixpath.normpath(E))
            G = posixpath.join(dest, C)
            A.main_window.adb_handler.move_on_device(E, G)
