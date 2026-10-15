import logging
import socket
import subprocess
import threading


_current = threading.local()
_logger = logging.getLogger(__name__)


class OperationControl:
    def __init__(self):
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._resources = {}

    @property
    def cancelled(self):
        return self._cancelled.is_set()

    def cancel(self):
        with self._lock:
            if self._cancelled.is_set():
                return
            self._cancelled.set()
            resources = list(self._resources.items())
        for resource, stop in resources:
            try:
                stop(resource)
            except OSError as error:
                _logger.debug("A cancelled operation resource was already closed: %s", error)

    def register(self, resource, stop):
        with self._lock:
            if not self.cancelled:
                self._resources[resource] = stop
                return
        self._stop_resource(resource, stop)

    def unregister(self, resource):
        with self._lock:
            self._resources.pop(resource, None)

    @staticmethod
    def _stop_resource(resource, stop):
        try:
            stop(resource)
        except OSError as error:
            _logger.debug("A cancelled operation resource was already closed: %s", error)


def set_current_operation(operation):
    _current.operation = operation


def clear_current_operation():
    _current.operation = None


def current_operation():
    return getattr(_current, "operation", None)


def is_cancelled():
    operation = current_operation()
    return operation is not None and operation.cancelled


def register_process(process):
    operation = current_operation()
    if operation is not None:
        operation.register(process, _stop_process)


def unregister_process(process):
    operation = current_operation()
    if operation is not None:
        operation.unregister(process)


def register_socket(sock):
    operation = current_operation()
    if operation is not None:
        operation.register(sock, _stop_socket)


def unregister_socket(sock):
    operation = current_operation()
    if operation is not None:
        operation.unregister(sock)


def _stop_process(process):
    if process.poll() is None:
        process.kill()


def _stop_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()
