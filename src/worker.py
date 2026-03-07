"""Background worker thread that drives faster-whisper transcription.

Backend: faster-whisper (CTranslate2)
GPU support:
  - NVIDIA CUDA  via CTranslate2 CUDA device
  - Intel Arc    via OpenVINO (openvino package)
  - CPU fallback  always available
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Set

from PyQt6.QtCore import QThread, pyqtSignal

from src.model_manager import MODELS, model_download_root


# ---------------------------------------------------------------------------
# Subtitle formatting helpers
# ---------------------------------------------------------------------------

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
        start = _fmt_srt(seg.start)
        end = _fmt_srt(seg.end)
        lines.append(f"{i}\n{start} --> {end}\n{seg.text.strip()}\n")
    return "\n".join(lines)


def _to_vtt(segments: list) -> str:
    lines = ["WEBVTT\n"]
    for seg in segments:
        start = _fmt_vtt(seg.start)
        end = _fmt_vtt(seg.end)
        lines.append(f"{start} --> {end}\n{seg.text.strip()}\n")
    return "\n".join(lines)


def _model_size_hint(model_name: str) -> str:
    for name, size, _ in MODELS:
        if name == model_name:
            return size
    return "unknown size"


# ---------------------------------------------------------------------------
# Device detection (no torch required)
# ---------------------------------------------------------------------------

def _run(cmd: list) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.stdout if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def detect_best_device() -> tuple:
    """Return (device, compute_type) for faster-whisper / CTranslate2.

    Priority: NVIDIA CUDA > Intel Arc (OpenVINO) > CPU

    Each candidate is validated with ctranslate2.get_supported_compute_types()
    before being returned.  This avoids hard C-level crashes that occur when
    CTranslate2 attempts to initialise a backend whose native plugin cannot
    load (e.g. OpenVINO on a machine with an Arc GPU but an unsupported driver).
    """
    try:
        import ctranslate2 as ct2
    except ImportError:
        ct2 = None

    def _ct2_supports(device: str) -> bool:
        """Return True if ctranslate2 reports at least one usable compute type
        for *device*.  Falls back to True when ctranslate2 is not importable
        so that the caller can still attempt the device and catch any error."""
        if ct2 is None:
            return True
        try:
            return len(ct2.get_supported_compute_types(device)) > 0
        except Exception:
            return False

    # 1. NVIDIA CUDA
    out = _run(["nvidia-smi"])
    if out and re.search(r"CUDA\s+Version\s*:\s*(\d+)", out):
        if _ct2_supports("cuda"):
            return ("cuda", "float16")

    # 2. Intel Arc / Intel GPU via OpenVINO
    try:
        import openvino as ov
        core = ov.Core()
        gpu_devices = [d for d in core.available_devices if d.startswith("GPU")]
        if gpu_devices and _ct2_supports("openvino"):
            return ("openvino", "int8")
    except Exception:
        pass

    return ("cpu", "int8")


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class TranscribeWorker(QThread):
    """Runs faster-whisper in a background QThread and emits progress signals."""

    file_started = pyqtSignal(str)       # file_path
    file_done    = pyqtSignal(str)       # file_path
    file_error   = pyqtSignal(str, str)  # file_path, error message
    log_message  = pyqtSignal(str)       # informational text for the log box
    fatal_error  = pyqtSignal(str)       # unrecoverable error  shown as a dialog
    all_done     = pyqtSignal()

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
        self.file_paths  = list(file_paths)
        self.model_name  = model_name
        self.output_dir  = output_dir
        self.formats     = formats
        self.language    = language or None
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _save_outputs(self, file_path: str, segments: list) -> None:
        base_name = Path(file_path).stem
        out_dir = self.output_dir if self.output_dir else str(Path(file_path).parent)
        os.makedirs(out_dir, exist_ok=True)

        if "txt" in self.formats:
            out = os.path.join(out_dir, base_name + ".txt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(" ".join(seg.text.strip() for seg in segments))

        if "srt" in self.formats:
            out = os.path.join(out_dir, base_name + ".srt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(_to_srt(segments))

        if "vtt" in self.formats:
            out = os.path.join(out_dir, base_name + ".vtt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(_to_vtt(segments))

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        #  Import faster-whisper 
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            self.fatal_error.emit(
                f"faster-whisper is not installed.\n\nRun:\n"
                f"  pip install faster-whisper\n\nDetail: {exc}"
            )
            self.all_done.emit()
            return
        except Exception as exc:
            self.fatal_error.emit(
                f"Failed to import faster-whisper:\n\n{exc}\n\n"
                "Try:  pip install --force-reinstall faster-whisper"
            )
            self.all_done.emit()
            return

        #  Detect device 
        device, compute_type = detect_best_device()
        device_label = {
            "cuda": "NVIDIA GPU (CUDA)",
            "openvino": "Intel GPU (OpenVINO / Arc)",
            "cpu": "CPU",
        }.get(device, device)
        self.log_message.emit(f"Compute device : {device_label}")
        self.log_message.emit(f"Compute type   : {compute_type}")

        #  Load model 
        self.log_message.emit(
            f"Loading Whisper model '{self.model_name}'"
            f" (first run downloads {_model_size_hint(self.model_name)}) ..."
        )
        try:
            model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=compute_type,
                download_root=model_download_root(),
            )
        except Exception as exc:
            msg = str(exc)
            # Unconditional fallback: if the GPU-backed model load fails for
            # any reason (driver mismatch, plugin not found, unsupported op, …)
            # retry on CPU.  We do not keyword-filter the error because native
            # crashes from CTranslate2 backends can surface as generic Python
            # RuntimeErrors that don't mention "cuda" or "openvino".
            if device in ("cuda", "openvino"):
                self.log_message.emit(
                    f"  {device_label} failed: {msg}\n"
                    "  Falling back to CPU ..."
                )
                try:
                    model = WhisperModel(
                        self.model_name, device="cpu", compute_type="int8",
                        download_root=model_download_root(),
                    )
                    device, compute_type = "cpu", "int8"
                    self.log_message.emit("  CPU fallback succeeded.")
                except Exception as exc2:
                    self.fatal_error.emit(
                        f"GPU device ({device_label}) failed:\n  {msg}\n\n"
                        f"CPU fallback also failed:\n  {exc2}"
                    )
                    self.all_done.emit()
                    return
            else:
                self.fatal_error.emit(
                    f"Failed to load Whisper model '{self.model_name}':\n\n{exc}"
                )
                self.all_done.emit()
                return

        self.log_message.emit(f"Model '{self.model_name}' loaded.")

        #  Transcribe each file 
        for path in self.file_paths:
            if self._stop_requested:
                self.log_message.emit("Transcription cancelled by user.")
                break

            self.file_started.emit(path)
            self.log_message.emit(f"Transcribing: {Path(path).name}")

            kwargs: dict = {}
            if self.language:
                kwargs["language"] = self.language

            try:
                segments_gen, _info = model.transcribe(path, **kwargs)
                segments = list(segments_gen)  # materialise generator
                self._save_outputs(path, segments)
                self.file_done.emit(path)
                self.log_message.emit(f"Done: {Path(path).name}")
            except Exception as exc:
                self.file_error.emit(path, str(exc))
                self.log_message.emit(
                    f"Error transcribing {Path(path).name}: {exc}"
                )

        self.all_done.emit()