"""Background worker thread that drives Whisper transcription."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Set

from PyQt6.QtCore import QThread, pyqtSignal


def _fmt_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_vtt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _to_srt(segments: list) -> str:
    lines: List[str] = []
    for i, seg in enumerate(segments, 1):
        start = _fmt_srt(seg["start"])
        end = _fmt_srt(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n")
    return "\n".join(lines)


def _to_vtt(segments: list) -> str:
    lines = ["WEBVTT\n"]
    for seg in segments:
        start = _fmt_vtt(seg["start"])
        end = _fmt_vtt(seg["end"])
        lines.append(f"{start} --> {end}\n{seg['text'].strip()}\n")
    return "\n".join(lines)


class TranscribeWorker(QThread):
    """Runs Whisper in a background thread and emits progress signals."""

    # Emitted when a file starts processing
    file_started = pyqtSignal(str)          # file_path
    # Emitted when a file finishes successfully
    file_done = pyqtSignal(str)             # file_path
    # Emitted when a file fails
    file_error = pyqtSignal(str, str)       # file_path, error message
    # Emitted with incremental log text (e.g. loading model)
    log_message = pyqtSignal(str)           # message
    # Emitted when all files are processed
    all_done = pyqtSignal()

    def __init__(
        self,
        file_paths: List[str],
        model_name: str,
        output_dir: str,
        formats: Set[str],
        language: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.file_paths = list(file_paths)
        self.model_name = model_name
        self.output_dir = output_dir
        self.formats = formats
        self.language = language or None
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_outputs(self, file_path: str, result: dict) -> None:
        base_name = Path(file_path).stem
        out_dir = self.output_dir if self.output_dir else str(Path(file_path).parent)
        os.makedirs(out_dir, exist_ok=True)

        if "txt" in self.formats:
            out = os.path.join(out_dir, base_name + ".txt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(result["text"].strip())

        if "srt" in self.formats:
            out = os.path.join(out_dir, base_name + ".srt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(_to_srt(result["segments"]))

        if "vtt" in self.formats:
            out = os.path.join(out_dir, base_name + ".vtt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(_to_vtt(result["segments"]))

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        # ── Import torch / whisper with a descriptive error if DLLs fail ──
        try:
            import torch  # noqa: F401  (validates DLL load before whisper)
        except OSError as exc:
            err = str(exc)
            if "1114" in err or "dll" in err.lower() or "initialization" in err.lower():
                msg = (
                    "PyTorch failed to load (DLL initialization error).\n\n"
                    "This usually means the installed PyTorch build doesn't match your\n"
                    "GPU drivers (or the Visual C++ Redistributable is missing).\n\n"
                    "Fix: run  python setup_torch.py  to auto-detect and install the\n"
                    "correct build, then restart the app."
                )
            else:
                msg = f"PyTorch import error: {exc}"
            self.log_message.emit(msg)
            self.all_done.emit()
            return
        except Exception as exc:
            self.log_message.emit(f"PyTorch import error: {exc}")
            self.all_done.emit()
            return

        try:
            import whisper
        except Exception as exc:
            self.log_message.emit(
                f"Whisper import error: {exc}\n"
                "Ensure openai-whisper is installed:  pip install openai-whisper"
            )
            self.all_done.emit()
            return

        self.log_message.emit(f"Loading Whisper model '{self.model_name}' …")
        try:
            model = whisper.load_model(self.model_name)
        except Exception as exc:
            self.log_message.emit(f"ERROR – failed to load model: {exc}")
            self.all_done.emit()
            return

        self.log_message.emit(f"Model '{self.model_name}' loaded.")

        for path in self.file_paths:
            if self._stop_requested:
                self.log_message.emit("Transcription cancelled by user.")
                break

            self.file_started.emit(path)
            self.log_message.emit(f"Transcribing: {Path(path).name}")

            transcribe_kwargs: dict = {}
            if self.language:
                transcribe_kwargs["language"] = self.language

            try:
                result = model.transcribe(path, **transcribe_kwargs)
                self._save_outputs(path, result)
                self.file_done.emit(path)
                self.log_message.emit(f"Done: {Path(path).name}")
            except Exception as exc:
                self.file_error.emit(path, str(exc))
                self.log_message.emit(f"Error transcribing {Path(path).name}: {exc}")

        self.all_done.emit()
