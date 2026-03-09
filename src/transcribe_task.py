"""Standalone transcription subprocess.

This script is invoked as a child process by TranscribeWorker.  Running
faster-whisper (ctranslate2) in a subprocess instead of a QThread ensures
that any native crash (access violation, SIGABRT, etc.) kills only this
child process and not the GUI process.

Protocol
--------
Input : single JSON object written to stdin, terminated by a newline.
Output: sequence of newline-delimited JSON objects written to stdout.

Input schema::

    {
        "model_name":  str,
        "output_dir":  str,          # "" = same dir as source file
        "formats":     [str, ...],   # e.g. ["txt", "srt", "vtt"]
        "language":    str | null,   # null = auto-detect
        "file_paths":  [str, ...]
    }

Output event types::

    {"type": "model_loading", "model": str}
    {"type": "model_loaded",  "model": str}
    {"type": "log",           "msg": str}
    {"type": "file_started",  "path": str}
    {"type": "file_progress", "path": str, "percent": float}
    {"type": "file_done",     "path": str}
    {"type": "file_error",    "path": str, "error": str}
    {"type": "fatal",         "msg": str}
    {"type": "all_done"}
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Stdout helpers – every message is a newline-delimited JSON object so the
# parent process can parse events one-by-one from stdout.
# ---------------------------------------------------------------------------

def _emit(obj: dict) -> None:
    print(json.dumps(obj), flush=True)


def _log(msg: str) -> None:
    _emit({"type": "log", "msg": msg})


def _fatal(msg: str) -> None:
    _emit({"type": "fatal", "msg": msg})


# ---------------------------------------------------------------------------
# Subtitle helpers (duplicated from worker.py to keep this script standalone)
# ---------------------------------------------------------------------------

def _fmt_srt(s: float) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    ms = int(round((s % 1) * 1000))
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{ms:03d}"


def _fmt_vtt(s: float) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    ms = int(round((s % 1) * 1000))
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d}.{ms:03d}"


def _to_srt(segments: list) -> str:
    lines: List[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(
            f"{i}\n{_fmt_srt(seg.start)} --> {_fmt_srt(seg.end)}\n"
            f"{seg.text.strip()}\n"
        )
    return "\n".join(lines)


def _to_vtt(segments: list) -> str:
    lines = ["WEBVTT\n"]
    for seg in segments:
        lines.append(
            f"{_fmt_vtt(seg.start)} --> {_fmt_vtt(seg.end)}\n"
            f"{seg.text.strip()}\n"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Device detection (same logic as worker.py)
# ---------------------------------------------------------------------------

def _run_cmd(cmd: list) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.stdout if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def detect_best_device() -> tuple:
    try:
        import ctranslate2 as ct2
    except ImportError:
        ct2 = None

    def _ct2_supports(device: str) -> bool:
        if ct2 is None:
            return True
        try:
            return len(ct2.get_supported_compute_types(device)) > 0
        except Exception:
            return False

    out = _run_cmd(["nvidia-smi"])
    if out and re.search(r"CUDA\s+Version\s*:\s*(\d+)", out):
        if _ct2_supports("cuda"):
            return ("cuda", "float16")

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
# Output saving
# ---------------------------------------------------------------------------

def _save_outputs(file_path: str, segments: list, output_dir: str,
                  formats: list) -> None:
    base_name = Path(file_path).stem
    out_dir = output_dir if output_dir else str(Path(file_path).parent)
    os.makedirs(out_dir, exist_ok=True)

    if "txt" in formats:
        out = os.path.join(out_dir, base_name + ".txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(" ".join(seg.text.strip() for seg in segments))

    if "srt" in formats:
        out = os.path.join(out_dir, base_name + ".srt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(_to_srt(segments))

    if "vtt" in formats:
        out = os.path.join(out_dir, base_name + ".vtt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(_to_vtt(segments))


# ---------------------------------------------------------------------------
# Diarization helpers
# ---------------------------------------------------------------------------

def _pyannote_model_dir() -> Path:
    """Return the path to the bundled pyannote models."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "models" / "pyannote"
    return Path(__file__).resolve().parent.parent / "models" / "pyannote"


def _load_diarization_pipeline():
    """Load the local pyannote diarization pipeline."""
    from pyannote.audio import Pipeline  # lazy import — optional dependency
    pipeline_dir = _pyannote_model_dir() / "speaker-diarization-3.1"
    if not pipeline_dir.exists():
        raise FileNotFoundError(
            f"Bundled diarization model not found at {pipeline_dir}. "
            "Reinstall the application."
        )
    return Pipeline.from_pretrained(str(pipeline_dir))


def _diarize(audio_path: str) -> list:
    """Run speaker diarization and return speaker turn segments.

    Returns a list of (start, end, speaker) tuples.
    """
    pipeline = _load_diarization_pipeline()
    diarization = pipeline(audio_path)
    return [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]


def _assign_speakers(segments, turns) -> list:
    """Assign the best-overlap speaker label to each transcription segment.

    Parameters
    ----------
    segments:
        Iterable of segment objects with ``start`` and ``end`` float attributes.
    turns:
        List of ``(t_start, t_end, speaker)`` tuples from ``_diarize()``.

    Returns
    -------
    list of ``(segment, speaker_label)`` tuples.
    """
    result = []
    for seg in segments:
        best_speaker, best_overlap = "Unknown", 0.0
        for t_start, t_end, speaker in turns:
            overlap = max(0.0, min(seg.end, t_end) - max(seg.start, t_start))
            if overlap > best_overlap:
                best_overlap, best_speaker = overlap, speaker
        result.append((seg, best_speaker))
    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Read job parameters from stdin
    raw = sys.stdin.read()
    try:
        job = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fatal(f"Invalid job JSON: {exc}")
        return

    model_name  = job["model_name"]
    output_dir  = job.get("output_dir", "")
    formats     = job.get("formats", ["txt"])
    language    = job.get("language") or None
    file_paths  = job["file_paths"]

    # Import faster-whisper
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        _fatal(
            f"faster-whisper is not installed.\n\nRun:\n"
            f"  pip install faster-whisper\n\nDetail: {exc}"
        )
        return
    except Exception as exc:
        _fatal(
            f"Failed to import faster-whisper:\n\n{exc}\n\n"
            "Try:  pip install --force-reinstall faster-whisper"
        )
        return

    # Detect device
    try:
        from src.model_manager import model_download_root
        download_root = model_download_root()
    except Exception:
        download_root = None

    device, compute_type = detect_best_device()
    device_label = {
        "cuda": "NVIDIA GPU (CUDA)",
        "openvino": "Intel GPU (OpenVINO / Arc)",
        "cpu": "CPU",
    }.get(device, device)
    _log(f"Compute device : {device_label}")
    _log(f"Compute type   : {compute_type}")

    # Load model
    _log(f"Loading Whisper model '{model_name}' ...")
    _emit({"type": "model_loading", "model": model_name})
    try:
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
    except Exception as exc:
        msg = str(exc)
        if device in ("cuda", "openvino"):
            _log(f"  {device_label} failed: {msg}\n  Falling back to CPU ...")
            try:
                model = WhisperModel(
                    model_name, device="cpu", compute_type="int8",
                    download_root=download_root,
                )
                device, compute_type = "cpu", "int8"
                _log("  CPU fallback succeeded.")
            except Exception as exc2:
                _fatal(
                    f"GPU device ({device_label}) failed:\n  {msg}\n\n"
                    f"CPU fallback also failed:\n  {exc2}"
                )
                return
        else:
            _fatal(f"Failed to load Whisper model '{model_name}':\n\n{exc}")
            return

    _emit({"type": "model_loaded", "model": model_name})
    _log(f"Model '{model_name}' loaded.")

    # Transcribe each file
    for path in file_paths:
        _emit({"type": "file_started", "path": path})
        _log(f"Transcribing: {Path(path).name}")

        kwargs: dict = {}
        if language:
            kwargs["language"] = language

        try:
            segments_gen, info = model.transcribe(path, **kwargs)
            duration = info.duration or 1.0   # guard against None / 0
            segments = []
            for seg in segments_gen:
                segments.append(seg)
                pct = min(100.0, (seg.end / duration) * 100)
                _emit({"type": "file_progress", "path": path, "percent": round(pct, 1)})
            _save_outputs(path, segments, output_dir, formats)
            _emit({"type": "file_done", "path": path})
            _log(f"Done: {Path(path).name}")
        except Exception as exc:
            import traceback
            err = traceback.format_exc()
            _emit({"type": "file_error", "path": path, "error": str(exc)})
            _log(f"Error transcribing {Path(path).name}: {err}")

    _emit({"type": "all_done"})


if __name__ == "__main__":
    main()
