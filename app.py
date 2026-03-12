import importlib.util
import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.log_setup import configure_logging
from src.main_window import MainWindow

# Configure logging before anything else so that import-time errors are caught.
log = configure_logging()


def _check_dependencies() -> bool:
    """Return True if faster-whisper is installed, else show a helpful error.

    Uses importlib.util.find_spec instead of a bare ``import faster_whisper``
    to avoid loading ctranslate2 and torch in the GUI process.  On Windows,
    ctranslate2 >= 4.0 unconditionally imports torch at module-load time, and
    torch's _load_dll_libraries() causes a fatal access violation (SEH
    exception) that Python try/except cannot catch.  All ML libraries must
    only load inside src/transcribe_task.py (the child subprocess), which is
    designed to absorb native crashes without taking down the GUI.
    """
    if importlib.util.find_spec("faster_whisper") is not None:
        return True

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(
        None,
        "Missing dependency",
        "faster-whisper is not installed.\n\n"
        "Run the following and restart the app:\n\n"
        "    pip install faster-whisper openvino",
    )
    return False


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Recording Transcriber")
    app.setOrganizationName("RecordingTranscriber")

    if not _check_dependencies():
        sys.exit(1)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()