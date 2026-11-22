import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(D, exist_ok=True)
    A = logging.getLogger("ADBExplorer")
    A.setLevel(logging.DEBUG)
    if A.hasHandlers():
        A.handlers.clear()
    F = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    G = os.path.join(D, "adb_explorer.log")
    C = RotatingFileHandler(G, maxBytes=5242880, backupCount=3, encoding="utf-8")
    C.setLevel(logging.DEBUG)
    C.setFormatter(F)
    A.addHandler(C)
    E = logging.NullHandler()
    A.addHandler(E)
    B = logging.getLogger("ADBHandler")
    B.setLevel(logging.WARNING)
    if B.hasHandlers():
        B.handlers.clear()
    B.addHandler(C)
    B.addHandler(E)
    logging.getLogger("PyQt6").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    return A
