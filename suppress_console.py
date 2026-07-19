import sys
import os
import subprocess

def suppress_console():
    if sys.platform != 'win32':
        return

    CREATE_NO_WINDOW = 0x08000000
    _original_popen_init = subprocess.Popen.__init__

    def _patched_popen_init(self, args, **kwargs):
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | CREATE_NO_WINDOW
        if 'startupinfo' not in kwargs or kwargs['startupinfo'] is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = si
        _original_popen_init(self, args, **kwargs)

    subprocess.Popen.__init__ = _patched_popen_init