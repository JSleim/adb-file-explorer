import sys
import sys
import os
import subprocess


def suppress_console():
    """Suppress console output for the application."""
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')

        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)

    devnull = open(os.devnull, 'w')
    sys.stdout = devnull
    sys.stderr = devnull

    subprocess.STARTUPINFO = subprocess.STARTUPINFO()
    subprocess.STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.STARTUPINFO.wShowWindow = subprocess.STARTF_USESHOWWINDOW

    os.environ['PYTHONUNBUFFERED'] = '1'
    if 'PYTHONIOENCODING' not in os.environ:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUNBUFFERED'] = '1'
