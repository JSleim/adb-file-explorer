import os, subprocess, sys


def suppress_console():
    if sys.platform != "win32":
        return
    E = 134217728
    F = subprocess.Popen.__init__

    def A(self, args, **A):
        D = "creationflags"
        C = "startupinfo"
        A[D] = A.get(D, 0) | E
        if C not in A or A[C] is None:
            B = subprocess.STARTUPINFO()
            B.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            B.wShowWindow = subprocess.SW_HIDE
            A[C] = B
        F(self, args, **A)

    subprocess.Popen.__init__ = A
