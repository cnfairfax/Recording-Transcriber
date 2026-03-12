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
# Constants
# ---------------------------------------------------------------------------

_UNKNOWN_SPEAKER = "Unknown"

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


def _build_speaker_map(tagged_segments: list) -> dict:
    """Map raw pyannote labels to friendly numbered names."""
    speaker_map: dict = {}
    counter = 1
    for _, speaker in tagged_segments:
        if speaker and speaker not in speaker_map:
            speaker_map[speaker] = f"Speaker {counter}"
            counter += 1
    return speaker_map


def _to_srt(tagged_segments: list) -> str:
    speaker_map = _build_speaker_map(tagged_segments)
    lines: List[str] = []
    for i, (seg, speaker) in enumerate(tagged_segments, 1):
        label = f"[{speaker_map[speaker]}] " if speaker else ""
        start = _fmt_srt(seg.start)
        end = _fmt_srt(seg.end)
        lines.append(f"{i}\n{start} --> {end}\n{label}{seg.text.strip()}\n")
    return "\n".join(lines)


def _to_vtt(tagged_segments: list) -> str:
    speaker_map = _build_speaker_map(tagged_segments)
    lines = ["WEBVTT\n"]
    for seg, speaker in tagged_segments:
        label = f"[{speaker_map[speaker]}] " if speaker else ""
        lines.append(
            f"{_fmt_vtt(seg.start)} --> {_fmt_vtt(seg.end)}\n"
            f"{label}{seg.text.strip()}\n"
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

def _save_outputs(file_path: str, tagged_segments: list, output_dir: str,
                  formats: list) -> None:
    base_name = Path(file_path).stem
    out_dir = output_dir if output_dir else str(Path(file_path).parent)
    os.makedirs(out_dir, exist_ok=True)

    if "txt" in formats:
        out = os.path.join(out_dir, base_name + ".txt")
        speaker_map = _build_speaker_map(tagged_segments)
        parts = []
        for seg, speaker in tagged_segments:
            label = f"[{speaker_map[speaker]}] " if speaker else ""
            parts.append(f"{label}{seg.text.strip()}")
        with open(out, "w", encoding="utf-8") as f:
            f.write(" ".join(parts))

    if "srt" in formats:
        out = os.path.join(out_dir, base_name + ".srt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(_to_srt(tagged_segments))

    if "vtt" in formats:
        out = os.path.join(out_dir, base_name + ".vtt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(_to_vtt(tagged_segments))


# ---------------------------------------------------------------------------
# Diarization helpers
# ---------------------------------------------------------------------------

def _pyannote_model_dir() -> Path:
    """Return the path to the bundled pyannote models.

    When running as a PyInstaller bundle ``sys.frozen`` is ``True`` and
    ``sys._MEIPASS`` holds the temporary extraction directory.  The
    ``_MEIPASS`` attribute is set by PyInstaller alongside ``frozen``, so it
    is always present when ``frozen`` is truthy; ``getattr`` is used here
    purely as a defensive measure.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        return Path(meipass) / "models" / "pyannote"
    return Path(__file__).resolve().parent.parent / "models" / "pyannote"


def _patch_torchaudio_compat() -> None:
    """Inject compatibility shims for torchaudio APIs removed in 2.5.0.

    torchaudio 2.5.0 removed the legacy backend system and three public APIs
    that pyannote.audio 3.x depends on:

      - ``torchaudio.AudioMetaData``   — used as a return-type annotation in
                                         ``pyannote/audio/core/io.py``; evaluated
                                         at module-import time in Python 3.12+.
      - ``torchaudio.list_audio_backends()`` — called at ``Audio.__init__`` to
                                         pick a default I/O backend.
      - ``torchaudio.info(path, ...)`` — called to read audio file metadata.

    Wheels for torchaudio < 2.5 are not available for Python 3.13, so we
    restore the missing attributes using ``soundfile`` (already a hard
    dependency of pyannote.audio) before pyannote loads rather than
    downgrading torch.
    """
    try:
        import torchaudio  # noqa: PLC0415
    except ImportError:
        return  # torchaudio not installed; pyannote will fail with its own error

    # 1. AudioMetaData -------------------------------------------------------
    if not hasattr(torchaudio, "AudioMetaData"):
        from typing import NamedTuple

        class AudioMetaData(NamedTuple):  # type: ignore[no-redef]
            sample_rate: int
            num_frames: int
            num_channels: int
            bits_per_sample: int
            encoding: str

        torchaudio.AudioMetaData = AudioMetaData  # type: ignore[attr-defined]

    # 2. list_audio_backends() -----------------------------------------------
    if not hasattr(torchaudio, "list_audio_backends"):
        def list_audio_backends() -> list:  # type: ignore[no-redef]
            """Return available audio backends (shim: always reports soundfile)."""
            return ["soundfile"]

        torchaudio.list_audio_backends = list_audio_backends  # type: ignore[attr-defined]

    # 3. info() --------------------------------------------------------------
    if not hasattr(torchaudio, "info"):
        import soundfile as _sf  # noqa: PLC0415 — already a pyannote dependency

        _AudioMetaData = torchaudio.AudioMetaData  # captured after step 1

        def info(path, frame_offset: int = 0, num_frames: int = -1,  # type: ignore[no-redef]
                 backend: str | None = None) -> "torchaudio.AudioMetaData":  # type: ignore[name-defined]
            """Return audio metadata using soundfile (shim for torchaudio >= 2.5)."""
            from io import IOBase  # noqa: PLC0415
            src = path.read() if isinstance(path, IOBase) else path
            meta = _sf.info(src)
            if isinstance(path, IOBase):
                path.seek(0)
            return _AudioMetaData(
                sample_rate=meta.samplerate,
                num_frames=meta.frames,
                num_channels=meta.channels,
                bits_per_sample=16,   # soundfile exposes subtype but not bit-depth; 16 is a safe default
                encoding=meta.subtype or "PCM_16",
            )

        torchaudio.info = info  # type: ignore[attr-defined]

    # 4. load() --------------------------------------------------------------
    # torchaudio 2.10 tries torchcodec as a backend, which requires FFmpeg
    # DLLs not present in a headless/bundled environment.  Shim load() to
    # read via soundfile + return the same (waveform, sample_rate) tuple that
    # callers expect.
    _ORIGINAL_LOAD = getattr(torchaudio, "_original_load_before_shim", None)
    if _ORIGINAL_LOAD is None and hasattr(torchaudio, "load"):
        # Check whether the existing load raises on this machine.
        # We replace it unconditionally on Windows to avoid the torchcodec
        # DLL search every time audio is loaded.
        import platform as _pl  # noqa: PLC0415
        if _pl.system() == "Windows":
            import torch as _torch  # noqa: PLC0415
            import soundfile as _sf2  # noqa: PLC0415

            _original_load = torchaudio.load
            torchaudio._original_load_before_shim = _original_load  # type: ignore[attr-defined]

            def load(  # type: ignore[no-redef]
                filepath,
                frame_offset: int = 0,
                num_frames: int = -1,
                normalize: bool = True,
                channels_first: bool = True,
                format: str | None = None,  # noqa: A002
                backend: str | None = None,
                buffer_size: int = 4096,
            ):
                """Load audio via soundfile (shim — avoids missing torchcodec DLLs on Windows)."""
                data, sr = _sf2.read(
                    filepath,
                    start=frame_offset,
                    stop=None if num_frames < 0 else frame_offset + num_frames,
                    dtype="float32",
                    always_2d=True,
                )
                # soundfile returns [frames, channels]; convert to [channels, frames]
                waveform = _torch.from_numpy(data.T)
                if not channels_first:
                    waveform = waveform.T
                if not normalize:
                    # soundfile always returns float32 normalised -1…1; undo for int16 source
                    waveform = (waveform * 32768).to(_torch.int16)
                return waveform, sr

            torchaudio.load = load  # type: ignore[attr-defined]


def _patch_huggingface_hub_compat() -> None:
    """Re-add ``use_auth_token`` support to huggingface_hub >= 1.0.

    ``huggingface_hub`` 1.0 removed the deprecated ``use_auth_token`` kwarg
    from ``hf_hub_download`` and related functions.  pyannote.audio 3.x still
    passes it.  This shim wraps the affected functions so that
    ``use_auth_token=X`` is transparently forwarded as ``token=X``.
    """
    try:
        import huggingface_hub as _hf  # noqa: PLC0415
        import inspect  # noqa: PLC0415
    except ImportError:
        return

    _FUNCTIONS_TO_PATCH = [
        "hf_hub_download",
        "snapshot_download",
    ]

    def _make_compat_wrapper(original_fn):  # type: ignore[no-untyped-def]
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            if "use_auth_token" in kwargs:
                token = kwargs.pop("use_auth_token")
                # Only forward if the caller didn't also provide token=
                kwargs.setdefault("token", token)
            return original_fn(*args, **kwargs)
        wrapper.__wrapped__ = original_fn  # type: ignore[attr-defined]
        return wrapper

    for fn_name in _FUNCTIONS_TO_PATCH:
        fn = getattr(_hf, fn_name, None)
        if fn is None:
            continue
        # Skip if already patched or if the function still accepts use_auth_token
        if getattr(fn, "__wrapped__", None) is not None:
            continue
        try:
            if "use_auth_token" in inspect.signature(fn).parameters:
                continue  # native support still present — no patch needed
        except (ValueError, TypeError):
            pass
        setattr(_hf, fn_name, _make_compat_wrapper(fn))


def _patch_lightning_fabric_load_compat() -> None:
    """Patch lightning_fabric to use weights_only=False for local checkpoints.

    PyTorch 2.6+ changed the default value of ``weights_only`` in ``torch.load``
    from ``False`` to ``True``.  pyannote.audio checkpoints store custom Python
    objects (``Specifications``, ``TorchVersion``, etc.) that are not on the
    default safe-globals allowlist.

    pyannote calls ``lightning_fabric.utilities.cloud_io._load`` without
    specifying ``weights_only``, leaving it as ``None``.  We patch ``_load`` so
    that ``None`` resolves to ``False``, enabling deserialization of these
    trusted bundled checkpoints.
    """
    try:
        import lightning_fabric.utilities.cloud_io as _ci  # noqa: PLC0415
    except ImportError:
        return

    if getattr(_ci._load, "__weights_only_patched__", False):
        return  # already patched

    _original = _ci._load

    def _patched_load(path_or_url, map_location=None, weights_only=None):  # type: ignore[no-untyped-def]
        if weights_only is None:
            weights_only = False
        return _original(path_or_url, map_location=map_location, weights_only=weights_only)

    _patched_load.__weights_only_patched__ = True  # type: ignore[attr-defined]
    _ci._load = _patched_load


def _load_diarization_pipeline():
    """Load the local pyannote diarization pipeline (fully offline).

    All three models must be present under ``models/pyannote/`` (populated
    by ``installer/download_pyannote_models.py`` before building the
    installer, or in the dev tree after running that script):

      models/pyannote/speaker-diarization-3.1/  — pipeline config.yaml
      models/pyannote/segmentation-3.0/          — segmentation weights
      models/pyannote/wespeaker-voxceleb-resnet34-LM/ — embedding weights

    The config.yaml ships with ``pyannote/segmentation-3.0`` and
    ``pyannote/wespeaker-voxceleb-resnet34-LM`` as HuggingFace repo IDs.
    Those IDs are replaced at runtime with the resolved local absolute paths
    so pyannote never contacts the Hub.  A patched copy is written to a
    temporary file; the temp file is cleaned up after the pipeline loads.
    """
    import tempfile  # noqa: PLC0415
    import yaml      # noqa: PLC0415 — pyyaml is a pyannote dependency

    _patch_torchaudio_compat()
    _patch_huggingface_hub_compat()
    _patch_lightning_fabric_load_compat()

    from pyannote.audio import Pipeline  # lazy import — optional dependency

    models_dir = _pyannote_model_dir()
    pipeline_dir = models_dir / "speaker-diarization-3.1"
    seg_dir = models_dir / "segmentation-3.0"
    embed_dir = models_dir / "wespeaker-voxceleb-resnet34-LM"

    for path, label in [
        (pipeline_dir, "speaker-diarization-3.1"),
        (seg_dir,      "segmentation-3.0"),
        (embed_dir,    "wespeaker-voxceleb-resnet34-LM"),
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Bundled model not found: {path}\n"
                "Run: python installer/download_pyannote_models.py --token YOUR_HF_TOKEN"
            )

    config_path = pipeline_dir / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Replace HuggingFace repo IDs with resolved local absolute paths.
    # Model.from_pretrained only checks os.path.isfile(), never is_dir(), so we
    # must point at pytorch_model.bin (not the containing directory) for both
    # the segmentation and embedding models.
    params = cfg.get("pipeline", {}).get("params", {})
    if "segmentation" in params:
        params["segmentation"] = str(seg_dir / "pytorch_model.bin")
    if "embedding" in params:
        params["embedding"] = str(embed_dir / "pytorch_model.bin")

    # Write a patched config to a temp file; pyannote.from_pretrained
    # skips repo-ID validation when given an existing file path.
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    try:
        yaml.dump(cfg, tmp, default_flow_style=False, allow_unicode=True)
        tmp.close()
        return Pipeline.from_pretrained(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _diarize(audio_path: str) -> list[tuple[float, float, str]]:
    """Run speaker diarization and return speaker turn segments.

    Returns a list of (start, end, speaker) tuples.
    """
    pipeline = _load_diarization_pipeline()
    diarization = pipeline(audio_path)
    return [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]


def _assign_speakers(
    segments: list,
    turns: list[tuple[float, float, str]],
) -> list[tuple]:
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
        best_speaker, best_overlap = _UNKNOWN_SPEAKER, 0.0
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
    diarize     = job.get("diarize", False)

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

            # Speaker diarization (after transcription loop)
            if diarize:
                _log("Running speaker diarization…")
                try:
                    turns = _diarize(path)
                    tagged = _assign_speakers(segments, turns)
                except ImportError:
                    _log(
                        "Speaker diarization requires pyannote.audio. "
                        "Reinstall the application with diarization support."
                    )
                    tagged = [(seg, None) for seg in segments]
                except FileNotFoundError:
                    _log("Bundled diarization models not found. Reinstall the application.")
                    tagged = [(seg, None) for seg in segments]
                except Exception as exc:
                    _log(f"Diarization failed, proceeding without speaker labels: {exc}")
                    tagged = [(seg, None) for seg in segments]
            else:
                tagged = [(seg, None) for seg in segments]

            _save_outputs(path, tagged, output_dir, formats)
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
