_B = "A cancelled operation resource was already closed: %s"
_A = None
import logging, socket, subprocess, threading

_current = threading.local()
_logger = logging.getLogger(__name__)


class OperationControl:
    def __init__(A):
        A._cancelled = threading.Event()
        A._lock = threading.Lock()
        A._resources = {}

    @property
    def cancelled(self):
        return self._cancelled.is_set()

    def cancel(A):
        with A._lock:
            if A._cancelled.is_set():
                return
            A._cancelled.set()
            B = list(A._resources.items())
        for C, D in B:
            try:
                D(C)
            except OSError as E:
                _logger.debug(_B, E)

    def register(A, resource, stop):
        B = resource
        with A._lock:
            if not A.cancelled:
                A._resources[B] = stop
                return
        A._stop_resource(B, stop)

    def unregister(A, resource):
        with A._lock:
            A._resources.pop(resource, _A)

    @staticmethod
    def _stop_resource(resource, stop):
        try:
            stop(resource)
        except OSError as A:
            _logger.debug(_B, A)


def set_current_operation(operation):
    _current.operation = operation


def clear_current_operation():
    _current.operation = _A


def current_operation():
    return getattr(_current, "operation", _A)


def is_cancelled():
    A = current_operation()
    return A is not _A and A.cancelled


def register_process(process):
    A = current_operation()
    if A is not _A:
        A.register(process, _stop_process)


def unregister_process(process):
    A = current_operation()
    if A is not _A:
        A.unregister(process)


def register_socket(sock):
    A = current_operation()
    if A is not _A:
        A.register(sock, _stop_socket)


def unregister_socket(sock):
    A = current_operation()
    if A is not _A:
        A.unregister(sock)


def _stop_process(process):
    A = process
    if A.poll() is _A:
        A.kill()


def _stop_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        0
    sock.close()
