from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class DeviceChooser(QDialog):
    def __init__(A, devices, parent=None):
        super().__init__(parent)
        A.setWindowTitle(A.tr("Open device panels"))
        A.setObjectName("device_chooser")
        A.setMinimumWidth(400)
        B = QVBoxLayout(A)
        C = QLabel(A.tr("Select device panels to open:"))
        C.setObjectName("chooser_prompt")
        B.addWidget(C)
        A.device_list = QListWidget()
        A.device_list.setObjectName("device_picker")
        A.device_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for D, F in devices.items():
            E = QListWidgetItem(f"{F} ({D})")
            E.setData(Qt.ItemDataRole.UserRole, D)
            A.device_list.addItem(E)
        if A.device_list.count() > 0:
            A.device_list.setCurrentRow(0)
        B.addWidget(A.device_list)
        A.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        A.button_box.accepted.connect(A.accept)
        A.button_box.rejected.connect(A.reject)
        B.addWidget(A.button_box)

    def selected_devices(A):
        return [A.data(Qt.ItemDataRole.UserRole) for A in A.device_list.selectedItems()]

    def selected_device(A):
        if A.device_list.currentItem():
            return A.device_list.currentItem().data(Qt.ItemDataRole.UserRole)
