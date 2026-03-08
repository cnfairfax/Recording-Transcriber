"""Main application window for Recording Transcriber."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Set

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.log_setup import safe_slot
from src.worker import TranscribeWorker

log = logging.getLogger("transcriber")

# ---------------------------------------------------------------------------
# Supported media extensions
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".ogg",
        ".mkv", ".avi", ".mov", ".wmv", ".aac", ".opus",
        ".webm", ".ts", ".m4b", ".wma", ".3gp",
    }
)

# ---------------------------------------------------------------------------
# File status metadata
# ---------------------------------------------------------------------------
STATUS_ICON: Dict[str, str] = {
    "queued":       "⏳  Queued",
    "transcribing": "🔄  Transcribing…",
    "done":         "✅  Done",
    "error":        "❌  Error",
}

STATUS_COLOR: Dict[str, str] = {
    "queued":       "#aaaaaa",
    "transcribing": "#5bc8ff",
    "done":         "#4cd07d",
    "error":        "#ff5c5c",
}

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px;
    font-weight: bold;
    color: #89b4fa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 14px;
    color: #cdd6f4;
}

QPushButton:hover {
    background-color: #45475a;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton#transcribeBtn {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    padding: 8px 20px;
}

QPushButton#transcribeBtn:hover {
    background-color: #b4befe;
}

QPushButton#transcribeBtn:disabled {
    background-color: #313244;
    color: #6c7086;
}

QPushButton#cancelBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
    padding: 8px 20px;
}

QPushButton#cancelBtn:hover {
    background-color: #fab387;
}

QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 8px;
    color: #cdd6f4;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    selection-background-color: #45475a;
    color: #cdd6f4;
}

QLineEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 8px;
    color: #cdd6f4;
}

QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    outline: none;
}

QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #313244;
}

QListWidget::item:selected {
    background-color: #313244;
}

QPlainTextEdit {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 6px;
    color: #a6adc8;
    font-family: "Consolas", monospace;
    font-size: 11px;
}

QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}

QCheckBox {
    spacing: 6px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3.5 8.5 L6.5 11.5 L12.5 4.5' stroke='white' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
}

QSplitter::handle {
    background-color: #313244;
}

QStatusBar {
    background-color: #181825;
    color: #6c7086;
    border-top: 1px solid #313244;
}
"""


# ---------------------------------------------------------------------------
# Drop Zone widget
# ---------------------------------------------------------------------------
class DropZone(QFrame):
    """A frame that accepts drag-and-dropped audio/video files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "DropZone {"
            "  border: 2px dashed #45475a;"
            "  border-radius: 12px;"
            "  background-color: #181825;"
            "}"
            "DropZone[active='true'] {"
            "  border-color: #89b4fa;"
            "  background-color: #1e2433;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("🎵 🎞️")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(28)
        icon_label.setFont(icon_font)

        hint_label = QLabel("Drag & drop audio or video files here")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_font = QFont()
        hint_font.setPointSize(12)
        hint_label.setFont(hint_font)
        hint_label.setStyleSheet("color: #6c7086;")

        sub_label = QLabel(
            "Supported: mp3, mp4, wav, flac, m4a, ogg, mkv, avi, mov, wmv, aac, opus, webm …"
        )
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setStyleSheet("color: #585b70; font-size: 11px;")

        layout.addWidget(icon_label)
        layout.addWidget(hint_label)
        layout.addWidget(sub_label)

        self._active = False

    # ------------------------------------------------------------------
    # Drag-and-drop event handlers
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(
                Path(u.toLocalFile()).suffix.lower() in SUPPORTED_EXTENSIONS
                for u in urls
            ):
                event.acceptProposedAction()
                self._set_active(True)
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_active(False)

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        self._set_active(False)
        paths = [
            u.toLocalFile()
            for u in event.mimeData().urls()
            if Path(u.toLocalFile()).suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if paths:
            # Walk up to find the main window and call its add_files method
            parent = self.parent()
            while parent and not isinstance(parent, MainWindow):
                parent = parent.parent()
            if isinstance(parent, MainWindow):
                parent.add_files(paths)
        event.acceptProposedAction()

    def _set_active(self, active: bool) -> None:
        self._active = active
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Recording Transcriber")
        self.setMinimumSize(780, 640)
        self.resize(900, 700)

        # State
        self._file_statuses: Dict[str, str] = {}   # path -> status
        self._worker: TranscribeWorker | None = None

        self._build_ui()
        self.setStyleSheet(STYLESHEET)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)

        # ── Drop zone ──────────────────────────────────────────────────
        self._drop_zone = DropZone()
        root.addWidget(self._drop_zone)

        # ── Toolbar (Browse + Clear) ───────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        browse_btn = QPushButton("➕  Add Files…")
        browse_btn.clicked.connect(self._browse_files)
        toolbar.addWidget(browse_btn)

        clear_btn = QPushButton("🗑  Clear Finished")
        clear_btn.clicked.connect(self._clear_finished)
        toolbar.addWidget(clear_btn)

        remove_btn = QPushButton("✖  Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        toolbar.addWidget(remove_btn)

        toolbar.addStretch()

        self._file_count_label = QLabel("No files queued")
        self._file_count_label.setStyleSheet("color: #6c7086;")
        toolbar.addWidget(self._file_count_label)

        root.addLayout(toolbar)

        # ── File queue list ────────────────────────────────────────────
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        root.addWidget(self._file_list, stretch=2)

        # ── Settings row ───────────────────────────────────────────────
        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)

        # Model
        model_box = QGroupBox("Whisper Model")
        model_layout = QVBoxLayout(model_box)
        self._model_combo = QComboBox()
        self._model_combo.addItems(
            ["tiny", "base", "small", "medium",
             "large", "large-v2", "large-v3"]
        )
        self._model_combo.setCurrentText("large-v3")
        model_layout.addWidget(self._model_combo)
        settings_row.addWidget(model_box)

        # Language
        lang_box = QGroupBox("Language")
        lang_layout = QVBoxLayout(lang_box)
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Auto-detect", None)
        self._lang_combo.addItem("English", "en")
        self._lang_combo.addItem("Spanish", "es")
        self._lang_combo.addItem("French", "fr")
        self._lang_combo.addItem("German", "de")
        self._lang_combo.addItem("Italian", "it")
        self._lang_combo.addItem("Portuguese", "pt")
        self._lang_combo.addItem("Dutch", "nl")
        self._lang_combo.addItem("Polish", "pl")
        self._lang_combo.addItem("Russian", "ru")
        self._lang_combo.addItem("Japanese", "ja")
        self._lang_combo.addItem("Chinese", "zh")
        self._lang_combo.addItem("Korean", "ko")
        lang_layout.addWidget(self._lang_combo)
        settings_row.addWidget(lang_box)

        # Output formats
        fmt_box = QGroupBox("Output Formats")
        fmt_layout = QHBoxLayout(fmt_box)
        self._fmt_txt = QCheckBox(".txt")
        self._fmt_txt.setChecked(True)
        self._fmt_srt = QCheckBox(".srt")
        self._fmt_srt.setChecked(True)
        self._fmt_vtt = QCheckBox(".vtt")
        self._fmt_vtt.setChecked(True)
        fmt_layout.addWidget(self._fmt_txt)
        fmt_layout.addWidget(self._fmt_srt)
        fmt_layout.addWidget(self._fmt_vtt)
        settings_row.addWidget(fmt_box)

        root.addLayout(settings_row)

        # ── Output directory ───────────────────────────────────────────
        outdir_box = QGroupBox("Save Transcripts To")
        outdir_layout = QHBoxLayout(outdir_box)

        self._outdir_edit = QLineEdit()
        self._outdir_edit.setPlaceholderText(
            "Leave blank to save next to each source file"
        )
        self._outdir_edit.setReadOnly(True)

        outdir_browse_btn = QPushButton("Browse…")
        outdir_browse_btn.setFixedWidth(90)
        outdir_browse_btn.clicked.connect(self._browse_outdir)

        outdir_clear_btn = QPushButton("✖")
        outdir_clear_btn.setFixedWidth(30)
        outdir_clear_btn.setToolTip("Clear – save next to source files")
        outdir_clear_btn.clicked.connect(lambda: self._outdir_edit.clear())

        outdir_layout.addWidget(self._outdir_edit)
        outdir_layout.addWidget(outdir_browse_btn)
        outdir_layout.addWidget(outdir_clear_btn)

        root.addWidget(outdir_box)

        # ── Action buttons ─────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addStretch()

        self._transcribe_btn = QPushButton("▶  Transcribe All")
        self._transcribe_btn.setObjectName("transcribeBtn")
        self._transcribe_btn.clicked.connect(self._start_transcription)
        action_row.addWidget(self._transcribe_btn)

        self._cancel_btn = QPushButton("⏹  Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_transcription)
        action_row.addWidget(self._cancel_btn)

        root.addLayout(action_row)

        # ── Log / progress splitter ────────────────────────────────────
        self._log_box = QPlainTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setMaximumBlockCount(500)
        self._log_box.setPlaceholderText("Transcription log will appear here…")
        self._log_box.setFixedHeight(100)
        root.addWidget(self._log_box)

        # ── Status bar ─────────────────────────────────────────────────
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setFixedHeight(10)
        self._progress_bar.setTextVisible(False)

        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label)
        status_bar.addPermanentWidget(self._progress_bar)

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def add_files(self, paths: list[str]) -> None:
        """Add file paths to the queue (skips duplicates and already-done files)."""
        added = 0
        for path in paths:
            if path in self._file_statuses:
                continue  # already in queue
            ext = Path(path).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            self._file_statuses[path] = "queued"
            self._add_list_item(path, "queued")
            added += 1
        self._refresh_count()
        if added:
            self._log(f"Added {added} file(s) to the queue.")

    def _add_list_item(self, path: str, status: str) -> None:
        name = Path(path).name
        label = f"{STATUS_ICON.get(status, status)}   {name}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setForeground(QColor(STATUS_COLOR.get(status, "#cdd6f4")))
        item.setToolTip(path)
        self._file_list.addItem(item)

    def _update_item_status(self, path: str, status: str) -> None:
        self._file_statuses[path] = status
        name = Path(path).name
        label = f"{STATUS_ICON.get(status, status)}   {name}"
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == path:
                item.setText(label)
                item.setForeground(QColor(STATUS_COLOR.get(status, "#cdd6f4")))
                break
        self._refresh_count()

    def _refresh_count(self) -> None:
        total = len(self._file_statuses)
        done = sum(1 for s in self._file_statuses.values() if s == "done")
        queued = sum(1 for s in self._file_statuses.values() if s == "queued")
        if total == 0:
            self._file_count_label.setText("No files queued")
        else:
            self._file_count_label.setText(
                f"{total} file(s)  ·  {done} done  ·  {queued} queued"
            )

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio / Video Files",
            "",
            "Media Files (*.mp3 *.mp4 *.wav *.flac *.m4a *.ogg *.mkv *.avi "
            "*.mov *.wmv *.aac *.opus *.webm *.ts *.m4b *.wma *.3gp);;"
            "All Files (*)",
        )
        if paths:
            self.add_files(paths)

    def _browse_outdir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._outdir_edit.text() or ""
        )
        if directory:
            self._outdir_edit.setText(directory)

    def _clear_finished(self) -> None:
        to_remove = [p for p, s in self._file_statuses.items() if s == "done"]
        for path in to_remove:
            del self._file_statuses[path]
            for i in range(self._file_list.count()):
                item = self._file_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == path:
                    self._file_list.takeItem(i)
                    break
        self._refresh_count()

    def _remove_selected(self) -> None:
        selected = self._file_list.selectedItems()
        for item in selected:
            path = item.data(Qt.ItemDataRole.UserRole)
            if self._file_statuses.get(path) == "transcribing":
                continue  # don't remove actively transcribing file
            self._file_statuses.pop(path, None)
            row = self._file_list.row(item)
            self._file_list.takeItem(row)
        self._refresh_count()

    # ------------------------------------------------------------------
    # Transcription control
    # ------------------------------------------------------------------

    def _get_formats(self) -> Set[str]:
        fmts: Set[str] = set()
        if self._fmt_txt.isChecked():
            fmts.add("txt")
        if self._fmt_srt.isChecked():
            fmts.add("srt")
        if self._fmt_vtt.isChecked():
            fmts.add("vtt")
        return fmts

    def _start_transcription(self) -> None:
        queued_files = [
            p for p, s in self._file_statuses.items() if s == "queued"
        ]
        if not queued_files:
            QMessageBox.information(
                self, "Nothing to do", "No queued files to transcribe."
            )
            return

        formats = self._get_formats()
        if not formats:
            QMessageBox.warning(
                self, "No formats selected", "Please select at least one output format."
            )
            return

        model_name = self._model_combo.currentText()
        output_dir = self._outdir_edit.text().strip()
        language = self._lang_combo.currentData()

        self._worker = TranscribeWorker(
            file_paths=queued_files,
            model_name=model_name,
            output_dir=output_dir,
            formats=formats,
            language=language,
        )
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.file_error.connect(self._on_file_error)
        self._worker.log_message.connect(self._log)
        self._worker.fatal_error.connect(self._on_fatal_error)
        self._worker.all_done.connect(self._on_all_done)

        self._transcribe_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setRange(0, len(queued_files))
        self._progress_bar.setValue(0)
        self._status_label.setText(f"Transcribing 0 / {len(queued_files)} …")
        self._worker.start()

    def _cancel_transcription(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("Cancelling…")

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    @safe_slot
    def _on_fatal_error(self, message: str) -> None:
        """Show unrecoverable transcription errors prominently as a dialog."""
        self._transcribe_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText("Error – see details")
        self._log(f"FATAL: {message}")
        QMessageBox.critical(self, "Transcription Error", message)

    @pyqtSlot(str)
    @safe_slot
    def _on_file_started(self, path: str) -> None:
        self._update_item_status(path, "transcribing")

    @pyqtSlot(str)
    @safe_slot
    def _on_file_done(self, path: str) -> None:
        self._update_item_status(path, "done")
        done = sum(1 for s in self._file_statuses.values() if s == "done")
        total_in_run = self._progress_bar.maximum()
        self._progress_bar.setValue(done)
        self._status_label.setText(f"Transcribing {done} / {total_in_run} …")

    @pyqtSlot(str, str)
    @safe_slot
    def _on_file_error(self, path: str, error: str) -> None:
        self._update_item_status(path, "error")

    @pyqtSlot(str)
    @safe_slot
    def _log(self, message: str) -> None:
        self._log_box.appendPlainText(message)
        self._log_box.verticalScrollBar().setValue(
            self._log_box.verticalScrollBar().maximum()
        )

    @pyqtSlot()
    @safe_slot
    def _on_all_done(self) -> None:
        self._transcribe_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        done = sum(1 for s in self._file_statuses.values() if s == "done")
        errors = sum(1 for s in self._file_statuses.values() if s == "error")
        self._status_label.setText(
            f"Finished – {done} succeeded, {errors} failed."
        )
        self._progress_bar.setValue(self._progress_bar.maximum())
        self._worker = None
