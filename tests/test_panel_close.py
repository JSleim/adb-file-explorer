import os
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QShortcut
from PyQt6.QtCore import Qt

from ui.device_panel import DevicePanel
from ui.task_manager import WorkerThread


class DisconnectedHandler:
    device_connected = False
    device_serial = "test-device"
    devices = {}


class PanelCloseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_shortcuts_are_scoped_to_the_active_panel(self):
        panel = DevicePanel(None, DisconnectedHandler())

        shortcuts = panel.findChildren(QShortcut)

        self.assertEqual(len(shortcuts), 14)
        self.assertTrue(all(
            shortcut.context() == (
                Qt.ShortcutContext.WidgetShortcut
                if shortcut.parent() is panel.tree_view
                else Qt.ShortcutContext.WidgetWithChildrenShortcut
            )
            for shortcut in shortcuts
        ))
    def test_close_waits_for_refresh_worker_to_finish_before_deleting_panel(self):
        panel = DevicePanel(None, DisconnectedHandler())
        worker = WorkerThread("slow refresh", lambda: (time.sleep(0.05) or []))
        panel._refresh_task = worker
        worker.start()

        panel.prepare_for_close()

        self.assertFalse(sip.isdeleted(panel))
        deadline = time.monotonic() + 1
        while not sip.isdeleted(panel) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)

        self.assertFalse(worker.isRunning())
        self.assertTrue(sip.isdeleted(panel))


if __name__ == "__main__":
    unittest.main()
