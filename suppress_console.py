import subprocess
import sys


def suppress_console():
    if sys.platform != "win32":
        return
    E = 134217728
    F = subprocess.Popen.__init__

    def A(self, args, **A):
        A["creationflags"] = A.get("creationflags", 0) | E
        if "startupinfo" not in A or A["startupinfo"] is None:
            B = subprocess.STARTUPINFO()
            B.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            B.wShowWindow = subprocess.SW_HIDE
            A["startupinfo"] = B
        F(self, args, **A)

    subprocess.Popen.__init__ = A
