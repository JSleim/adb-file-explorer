import logging
import sys
from pathlib import Path

from suppress_console import suppress_console

suppress_console()

from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from logging_config import setup_logging
from ui.multi_device_window import MultiDeviceWindow
from ui.theme import LIGHT


def get_base_dir() -> Path:
    """Возвращает базовую директорию (учитывает сборку через PyInstaller)."""
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).parent


def get_app_icon_path() -> Path:
    return get_base_dir() / "assets" / "adb-explorer.ico"


def setup_translations(app: QApplication, logger: logging.Logger) -> list[QTranslator]:
    """Автоматически загружает переводы под язык системы, если они доступны."""
    translators = []
    system_locale = QLocale.system()
    logger.info("System locale detected: %s", system_locale.name())

    # 1. Загрузка системного перевода Qt (стандартные кнопки и диалоги)
    qt_translator = QTranslator()
    qt_translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(system_locale, "qtbase", "_", qt_translations_path):
        app.installTranslator(qt_translator)
        translators.append(qt_translator)
        logger.info("Qt base translation loaded for locale: %s", system_locale.name())

    # 2. Загрузка перевода приложения из папки i18n (ищет файлы вида ru_RU.qm или ru.qm)
    app_translator = QTranslator()
    i18n_dir = str(get_base_dir() / "i18n")
    if app_translator.load(system_locale, "", "", i18n_dir):
        app.installTranslator(app_translator)
        translators.append(app_translator)
        logger.info("App translation loaded from: %s", i18n_dir)
    else:
        logger.info("No matching translation found in %s, using default language", i18n_dir)

    return translators


def main():
    logger = setup_logging()
    app_logger = logging.getLogger("ADBExplorer")

    try:
        app = QApplication(sys.argv)

        app.translators = setup_translations(app, app_logger)

        app.setStyle("Fusion")

        app.setApplicationName("ADB Explorer")
        app.setApplicationVersion("1.0.0")
        app.setQuitOnLastWindowClosed(True)
        app.setWindowIcon(QIcon(str(get_app_icon_path())))

        app.setStyleSheet(LIGHT)

        window = MultiDeviceWindow()
        window.show()

        return app.exec()

    except Exception as e:
        logger.exception("Fatal error in application")
        QMessageBox.critical(
            None,
            QCoreApplication.translate("main", "Fatal Error"),
            QCoreApplication.translate("main", "A fatal error occurred:\n{0}\n\nCheck the log file for more details.").format(str(e))
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
