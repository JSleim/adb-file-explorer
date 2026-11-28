import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel

from ui.device_dashboard import DeviceDashboardDialog


class DeviceDashboardTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_system_labels_are_translated_only_once(self):
        class TranslatedDashboard(DeviceDashboardDialog):
            def tr(self, text, *args):
                translations = {
                    "Model": "Модель",
                    "Модель": "WRONG",
                }
                return translations.get(text, text)

        dialog = TranslatedDashboard()
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        dialog.close()

        self.assertIn("Модель:", labels)
        self.assertNotIn("WRONG:", labels)


if __name__ == "__main__":
    unittest.main()
