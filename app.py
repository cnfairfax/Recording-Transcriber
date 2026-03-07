import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from src.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Recording Transcriber")
    app.setOrganizationName("RecordingTranscriber")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
