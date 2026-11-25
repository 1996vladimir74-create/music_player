import sys
import uos
import ubinascii

from config import ERROR_LOG, DF_LOG, LOG_MAX_BYTES


def hexs(data):
    return ubinascii.hexlify(bytes(data)).decode()


def _trim(path):
    try:
        if uos.stat(path)[6] > LOG_MAX_BYTES:
            uos.remove(path)
    except OSError:
        pass


def log_error(e):
    _trim(ERROR_LOG)
    try:
        with open(ERROR_LOG, "a") as f:
            sys.print_exception(e, f)
    except Exception:
        pass


def log_text(text):
    _trim(ERROR_LOG)
    try:
        with open(ERROR_LOG, "a") as f:
            f.write(text + "\n")
    except Exception:
        pass


def log_frame(frame):
    _trim(DF_LOG)
    try:
        with open(DF_LOG, "a") as f:
            f.write(hexs(frame) + "\n")
    except Exception:
        pass
