"""Centralised logging configuration for Recording Transcriber.

Call ``configure_logging()`` once, as early as possible in ``app.py``,
before any other imports that might emit log records.

What this module wires up
-------------------------
1. Python ``logging`` – StreamHandler (console) + RotatingFileHandler
   (app_log.txt next to the executable / project root).
2. ``sys.excepthook`` – logs unhandled exceptions in the main thread with
   full traceback before they would silently kill the process.
3. Qt message handler (``qInstallMessageHandler``) – forwards Qt warnings
   and criticals to the Python logger instead of the default stderr dump.
4. ``threading.excepthook`` – catches uncaught exceptions in *plain* Python
   threads (not QThread; that is handled separately in worker.py).
"""

from __future__ import annotations

import faulthandler
import functools
import logging
import logging.handlers
import sys
import threading
import traceback
from pathlib import Path


# ---------------------------------------------------------------------------
# Public logger – use this name everywhere in the app:
#   import logging; log = logging.getLogger("transcriber")
# ---------------------------------------------------------------------------
LOGGER_NAME = "transcriber"


def _log_dir() -> Path:
    """Return a writable directory for the log file."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle – write next to the .exe
        return Path(sys.executable).parent
    # Running from source – write to the project root
    return Path(__file__).resolve().parent.parent


def configure_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Configure the root + app logger and install global exception hooks.

    Safe to call multiple times (subsequent calls are no-ops).
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        # Already configured – don't double-add handlers
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console handler – always present so errors appear in the terminal
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 2. Rotating file handler – survives across runs, useful when there is no
    #    visible console (e.g. double-clicking the .exe)
    try:
        log_path = _log_dir() / "app_log.txt"
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,  # 2 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        logger.debug("Log file: %s", log_path)
    except OSError as exc:
        logger.warning("Could not open log file: %s", exc)

    # 3. sys.excepthook – unhandled exceptions in the main thread
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

    sys.excepthook = _excepthook

    # 4. threading.excepthook – unhandled exceptions in plain Python threads
    def _thread_excepthook(args: threading.ExceptHookArgs):
        if args.exc_type is SystemExit:
            return
        logger.critical(
            "Unhandled exception in thread %s:\n%s",
            args.thread,
            "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_tb
                )
            ),
        )

    threading.excepthook = _thread_excepthook

    # 5. Qt message handler – QtWarning / QtCritical / QtFatal → logger
    _install_qt_message_handler(logger)

    # 6. faulthandler – writes a native traceback to the log file on SIGSEGV /
    #    abort / assertion failure inside a C extension (e.g. ctranslate2).
    try:
        log_path = _log_dir() / "app_log.txt"
        _fault_file = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
        faulthandler.enable(file=_fault_file, all_threads=True)
        logger.debug("faulthandler enabled → %s", log_path)
    except Exception as exc:
        logger.warning("Could not enable faulthandler: %s", exc)

    logger.debug("Logging configured (level=%s).", logging.getLevelName(level))
    return logger


# ---------------------------------------------------------------------------
# Slot guard decorator
# ---------------------------------------------------------------------------

def safe_slot(func):
    """Decorator for PyQt slot methods.

    PyQt6 silently discards exceptions raised inside @pyqtSlot handlers
    (it prints a one-liner to stderr but does not call sys.excepthook and does
    not propagate the exception).  Wrapping a slot with this decorator ensures
    any unexpected exception is logged with a full traceback.

    Usage::

        @pyqtSlot(str)
        @safe_slot
        def _on_some_signal(self, value: str) -> None:
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logging.getLogger("transcriber").critical(
                "Unhandled exception in slot %s:\n%s",
                func.__qualname__,
                traceback.format_exc(),
            )
    return wrapper


def _install_qt_message_handler(logger: logging.Logger) -> None:
    """Redirect Qt's own diagnostics to the Python logger."""
    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

        _QT_LEVEL_MAP = {
            QtMsgType.QtDebugMsg:    logging.DEBUG,
            QtMsgType.QtInfoMsg:     logging.INFO,
            QtMsgType.QtWarningMsg:  logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg:    logging.CRITICAL,
        }

        def _qt_handler(msg_type, _context, message: str) -> None:
            log_level = _QT_LEVEL_MAP.get(msg_type, logging.WARNING)
            logger.log(log_level, "[Qt] %s", message)

        qInstallMessageHandler(_qt_handler)
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not install Qt message handler: %s", exc)
