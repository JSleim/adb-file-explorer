import logging
import socket
import threading

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
                _logger.debug(
                    "A cancelled operation resource was already closed: %s", E
                )

    def register(A, resource, stop):
        B = resource
        with A._lock:
            if not A.cancelled:
                A._resources[B] = stop
                return
        A._stop_resource(B, stop)

    def unregister(A, resource):
        with A._lock:
            A._resources.pop(resource, None)

    @staticmethod
    def _stop_resource(resource, stop):
        try:
            stop(resource)
        except OSError as A:
            _logger.debug("A cancelled operation resource was already closed: %s", A)


def set_current_operation(operation):
    _current.operation = operation


def clear_current_operation():
    _current.operation = None


def current_operation():
    return getattr(_current, "operation", None)


def is_cancelled():
    A = current_operation()
    return A is not None and A.cancelled


def register_process(process):
    A = current_operation()
    if A is not None:
        A.register(process, _stop_process)


def unregister_process(process):
    A = current_operation()
    if A is not None:
        A.unregister(process)


def register_socket(sock):
    A = current_operation()
    if A is not None:
        A.register(sock, _stop_socket)


def unregister_socket(sock):
    A = current_operation()
    if A is not None:
        A.unregister(sock)


def _stop_process(process):
    A = process
    if A.poll() is None:
        A.kill()


def _stop_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()
