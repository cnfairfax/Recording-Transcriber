import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.log_setup import configure_logging
from src.main_window import MainWindow

# Configure logging before anything else so that import-time errors are caught.
log = configure_logging()


def _check_dependencies() -> bool:
    """Return True if faster-whisper is importable, else show a helpful error."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Missing dependency",
            "faster-whisper is not installed.\n\n"
            "Run the following and restart the app:\n\n"
            "    pip install faster-whisper openvino",
        )
        return False
    except Exception as exc:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Dependency error",
            f"Failed to import faster-whisper:\n\n{exc}\n\n"
            "Try:  pip install --force-reinstall faster-whisper",
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