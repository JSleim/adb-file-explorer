from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeView,
    QVBoxLayout,
)


class SelectDirectoryDialog(QDialog):
    def __init__(
        A,
        parent,
        adb_handler,
        start_path="/storage/emulated/0",
        root_path="/",
        use_root=False,
    ):
        E = root_path
        D = start_path
        super().__init__(parent)
        A.setWindowTitle(A.tr("Select Destination Folder"))
        A.resize(600, 400)
        A.adb_handler = adb_handler
        A.selected_path = None
        A.root_path = "/" if E == "/" else E.rstrip("/")
        A.current_path = "/" if D == "/" else D.rstrip("/")
        A.use_root = use_root
        C = QVBoxLayout(A)
        A.status_label = QLabel(A.tr("Ready"))
        C.addWidget(A.status_label)
        A.tree_view = QTreeView()
        A.tree_model = QStandardItemModel()
        A.tree_model.setHorizontalHeaderLabels(["Name", "Path"])
        A.tree_view.setModel(A.tree_model)
        A.tree_view.setHeaderHidden(False)
        A.tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        C.addWidget(A.tree_view)
        B = QHBoxLayout()
        F = QPushButton(A.tr("Up"))
        F.clicked.connect(A.go_up)
        B.addWidget(F)
        G = QPushButton(A.tr("Select"))
        G.clicked.connect(A.accept)
        B.addWidget(G)
        H = QPushButton(A.tr("Cancel"))
        H.clicked.connect(A.reject)
        B.addWidget(H)
        C.addLayout(B)
        A.tree_view.doubleClicked.connect(A.on_double_click)
        if A.adb_handler.device_connected:
            A.refresh()
        else:
            A.status_label.setText(A.tr("No ADB device connected"))
            QMessageBox.warning(
                A, A.tr("Connection Error"), A.tr("No ADB device connected")
            )

    def refresh(A):
        if not A.adb_handler.device_connected:
            A.status_label.setText(A.tr("No ADB device connected"))
            return
        A.status_label.setText(A.tr("Loading directories..."))
        A.tree_model.clear()
        A.tree_model.setHorizontalHeaderLabels([A.tr("Name"), A.tr("Path")])
        if A.current_path != A.root_path:
            B = "/".join(A.current_path.split("/")[:-1])
            if not B:
                B = A.root_path
            G = QStandardItem("..")
            C = QStandardItem(B)
            A.tree_model.appendRow([G, C])
        try:
            D = A.adb_handler.list_directory(A.current_path, use_root=A.use_root)
            if D is None:
                A.status_label.setText(A.tr("Failed to load directories"))
                return
            E = sorted([A for A in D if A.is_dir], key=lambda x: x.name.lower())
            for F in E:
                H = QStandardItem(F.name)
                C = QStandardItem(F.path)
                A.tree_model.appendRow([H, C])
            A.status_label.setText(A.tr("Found {0} directories").format(len(E)))
        except Exception as I:
            A.status_label.setText(A.tr("Error loading directories: {0}").format(I))
        A.tree_view.setColumnHidden(1, True)
        A.tree_view.resizeColumnToContents(0)

    def go_up(A):
        if A.current_path == A.root_path:
            return
        B = "/".join(A.current_path.split("/")[:-1])
        if not B:
            B = A.root_path
        A.current_path = B
        A.refresh()

    def on_double_click(A, index):
        B = index
        if not A.adb_handler.device_connected:
            return
        D = A.tree_model.itemFromIndex(B)
        C = A.tree_model.item(B.row(), 1)
        if C and D.text() != "..":
            A.current_path = C.text()
            A.refresh()

    def accept(A):
        if not A.adb_handler.device_connected:
            QMessageBox.warning(
                A, A.tr("Connection Error"), A.tr("No ADB device connected")
            )
            return
        B = A.tree_view.selectionModel().selectedRows()
        if not B:
            QMessageBox.warning(
                A, A.tr("No Selection"), A.tr("Please select a folder.")
            )
            return
        C = B[0]
        D = A.tree_model.index(C.row(), 1)
        A.selected_path = A.tree_model.data(D)
        super().accept()

    def get_selected_path(A):
        return A.selected_path
