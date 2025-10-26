import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger('ADBExplorer')
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    log_file = os.path.join(log_dir, 'adb_explorer.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    null_handler = logging.NullHandler()
    logger.addHandler(null_handler)

    adb_logger = logging.getLogger('ADBHandler')
    adb_logger.setLevel(logging.WARNING)

    if adb_logger.hasHandlers():
        adb_logger.handlers.clear()

    adb_logger.addHandler(file_handler)
    adb_logger.addHandler(null_handler)

    logging.getLogger('PyQt6').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    return logger
