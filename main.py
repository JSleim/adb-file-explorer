import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from logging_config import setup_logging
from ui.theme import STYLESHEET
from ui.explorer import ADBFileExplorer


def main():
    logger = setup_logging()

    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        app.setApplicationName("ADB Explorer")
        app.setApplicationVersion("1.0.0")
        app.setQuitOnLastWindowClosed(True)

        app.setStyleSheet(STYLESHEET)

        window = ADBFileExplorer()
        window.show()

        return app.exec()

    except Exception as e:
        logger.exception("Fatal error in application")
        QMessageBox.critical(
            None,
            "Fatal Error",
            f"A fatal error occurred:\n{str(e)}\n\nCheck the log file for more details."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
