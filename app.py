import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.main_window import MainWindow


# ---------------------------------------------------------------------------
# Torch health-check helpers
# ---------------------------------------------------------------------------

def _torch_is_working() -> bool:
    """Return True if torch imports cleanly in a *fresh sub-process*.

    Testing in a sub-process is important: a broken DLL that fails inside a
    QThread may still succeed when imported directly in __main__ (different
    loader context), so this gives a more honest result.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import torch; import whisper"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Background thread that runs setup_torch.py and streams its output
# ---------------------------------------------------------------------------

class SetupThread(QThread):
    output_line = pyqtSignal(str)
    finished_ok  = pyqtSignal()
    finished_err = pyqtSignal(str)

    def run(self) -> None:
        try:
            proc = subprocess.Popen(
                [sys.executable, "setup_torch.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.output_line.emit(line.rstrip())
            proc.wait()
            if proc.returncode == 0:
                self.finished_ok.emit()
            else:
                self.finished_err.emit(
                    f"setup_torch.py exited with code {proc.returncode}"
                )
        except Exception as exc:
            self.finished_err.emit(str(exc))


# ---------------------------------------------------------------------------
# Setup dialog shown when torch is broken
# ---------------------------------------------------------------------------

SETUP_STYLESHEET = """
QDialog, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QLabel { color: #cdd6f4; }
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 18px;
    color: #cdd6f4;
}
QPushButton:hover  { background-color: #45475a; }
QPushButton#fixBtn {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#fixBtn:hover { background-color: #b4befe; }
QPushButton#fixBtn:disabled { background-color: #313244; color: #6c7086; }
QPlainTextEdit {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 6px;
    color: #a6adc8;
    font-family: Consolas, monospace;
    font-size: 11px;
}
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
}
QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }
"""


class TorchSetupDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PyTorch Setup Required")
        self.setMinimumWidth(520)
        self.setStyleSheet(SETUP_STYLESHEET)
        self._thread: SetupThread | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "<b>PyTorch (required for Whisper) could not be loaded.</b><br><br>"
            "This is usually caused by a CUDA/DLL version mismatch.<br>"
            "Click <b>Auto-Fix</b> to detect your GPU and install the correct build."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        self._log.setMaximumBlockCount(300)
        layout.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setFixedHeight(12)
        self._progress.hide()
        layout.addWidget(self._progress)

        btn_row_widget = QLabel()  # spacer
        layout.addWidget(btn_row_widget)

        from PyQt6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout()

        self._fix_btn = QPushButton("Auto-Fix Now")
        self._fix_btn.setObjectName("fixBtn")
        self._fix_btn.clicked.connect(self._start_fix)
        btn_row.addWidget(self._fix_btn)

        self._skip_btn = QPushButton("Skip (launch anyway)")
        self._skip_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._skip_btn)

        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._quit_btn)

        layout.addLayout(btn_row)

    def _start_fix(self) -> None:
        self._fix_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.show()
        self._log.setPlainText("")

        self._thread = SetupThread(self)
        self._thread.output_line.connect(self._on_line)
        self._thread.finished_ok.connect(self._on_ok)
        self._thread.finished_err.connect(self._on_err)
        self._thread.start()

    def _on_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _on_ok(self) -> None:
        self._progress.hide()
        self._log.appendPlainText("\n✓ Setup complete. Launching app…")
        QMessageBox.information(
            self,
            "Setup Complete",
            "PyTorch was installed successfully.\nThe app will now start.",
        )
        self.accept()

    def _on_err(self, msg: str) -> None:
        self._progress.hide()
        self._fix_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
        self._log.appendPlainText(f"\n✗ Error: {msg}")
        self._log.appendPlainText(
            "\nIf the problem persists, try installing the Visual C++ Redistributable:\n"
            "  https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
            "Then re-run:  python setup_torch.py"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Recording Transcriber")
    app.setOrganizationName("RecordingTranscriber")

    # --- Torch health check ---------------------------------------------------
    print("Checking PyTorch / Whisper availability…", flush=True)
    if not _torch_is_working():
        print("PyTorch check failed – showing setup dialog.", flush=True)
        dialog = TorchSetupDialog()
        result = dialog.exec()
        if result == QDialog.DialogCode.Rejected:
            sys.exit(1)
        # Whether user fixed or skipped, continue launching the window

    # --- Main window ----------------------------------------------------------
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
