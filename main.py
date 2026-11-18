import logging, sys
from pathlib import Path
from suppress_console import suppress_console

suppress_console()
from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from logging_config import setup_logging
from ui.multi_device_window import MultiDeviceWindow
from ui.theme import LIGHT


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent


def get_app_icon_path():
    return get_base_dir() / "assets" / "adb-explorer.ico"


def setup_translations(app, logger):
    A = logger
    C = []
    B = QLocale.system()
    A.info("System locale detected: %s", B.name())
    D = QTranslator()
    G = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if D.load(B, "qtbase", "_", G):
        app.installTranslator(D)
        C.append(D)
        A.info("Qt base translation loaded for locale: %s", B.name())
    E = QTranslator()
    F = str(get_base_dir() / "i18n")
    if E.load(B, "", "", F):
        app.installTranslator(E)
        C.append(E)
        A.info("App translation loaded from: %s", F)
    else:
        A.info("No matching translation found in %s, using default language", F)
    return C


def main():
    B = "main"
    C = setup_logging()
    D = logging.getLogger("ADBExplorer")
    try:
        A = QApplication(sys.argv)
        A.translators = setup_translations(A, D)
        A.setStyle("Fusion")
        A.setApplicationName("ADB Explorer")
        A.setApplicationVersion("1.0.0")
        A.setQuitOnLastWindowClosed(True)
        A.setWindowIcon(QIcon(str(get_app_icon_path())))
        A.setStyleSheet(LIGHT)
        E = MultiDeviceWindow()
        E.show()
        return A.exec()
    except Exception as F:
        C.exception("Fatal error in application")
        QMessageBox.critical(
            None,
            QCoreApplication.translate(B, "Fatal Error"),
            QCoreApplication.translate(
                B,
                "A fatal error occurred:\n{0}\n\nCheck the log file for more details.",
            ).format(str(F)),
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
