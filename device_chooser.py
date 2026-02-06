from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, 
                            QDialogButtonBox, QLabel, QListWidgetItem)
from PyQt6.QtCore import Qt


class DeviceChooser(QDialog):
    def __init__(self, devices, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Device")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        label = QLabel("Select a device to connect:")
        layout.addWidget(label)

        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        for serial, model in devices.items():
            item = QListWidgetItem(f"{model} ({serial})")
            item.setData(Qt.ItemDataRole.UserRole, serial)
            self.device_list.addItem(item)

        if self.device_list.count() > 0:
            self.device_list.setCurrentRow(0)

        layout.addWidget(self.device_list)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def selected_device(self):
        if self.device_list.currentItem():
            return self.device_list.currentItem().data(Qt.ItemDataRole.UserRole)
        return None
