import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.main_window import MainWindow


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


def _preload_faster_whisper() -> None:
    """Import faster-whisper in the main thread.

    Windows loads shared libraries (DLLs) in the context of the calling thread
    on first import.  Pre-loading here ensures ctranslate2 and its bundled
    runtime are fully initialised before the worker QThread starts, which
    prevents sporadic DLL-initialisation failures that can occur when a
    native library is first imported inside a background thread.
    """
    try:
        import faster_whisper  # noqa: F401
        from faster_whisper import WhisperModel  # noqa: F401
    except Exception:
        pass  # will be reported properly when the worker runs


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Recording Transcriber")
    app.setOrganizationName("RecordingTranscriber")

    if not _check_dependencies():
        sys.exit(1)

    _preload_faster_whisper()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()