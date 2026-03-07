"""Central model storage and discovery for Recording Transcriber.

Models are kept in a versioned-friendly location outside the install dir so
they survive app updates and are shared between the app and the download helper.

Storage root
------------
  Windows : %APPDATA%\\Recording Transcriber\\models\\
  Linux   : $XDG_DATA_HOME/Recording Transcriber/models/  (or ~/.local/share/…)
  macOS   : ~/Library/Application Support/Recording Transcriber/models/

faster-whisper model layout (set via download_root)
----------------------------------------------------
  {models_dir}/models--Systran--faster-whisper-{model_name}/
    blobs/
    refs/
    snapshots/{commit_hash}/
      model.bin
      config.json
      vocabulary.json
      tokenizer.json
      ...
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Recording Transcriber"

# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------

# Each entry: (model_name, approx_size, short_description)
MODELS: list[tuple[str, str, str]] = [
    ("tiny",     "~75 MB",   "Fastest — lowest accuracy"),
    ("base",     "~145 MB",  "Very fast — basic accuracy"),
    ("small",    "~466 MB",  "Good balance of speed and accuracy"),
    ("medium",   "~1.5 GB",  "High accuracy, moderate speed"),
    ("large-v2", "~3.1 GB",  "Very high accuracy"),
    ("large-v3", "~3.1 GB",  "Best overall accuracy (recommended)"),
]

MODEL_NAMES: list[str] = [m[0] for m in MODELS]
DEFAULT_MODEL = "large-v3"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_models_dir() -> Path:
    """Return the directory where Whisper model weights are stored."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME / "models"


def model_download_root() -> str:
    """Return the download_root string to pass to faster_whisper.WhisperModel()."""
    return str(get_models_dir())


# ---------------------------------------------------------------------------
# Download status
# ---------------------------------------------------------------------------

def is_model_downloaded(model_name: str) -> bool:
    """Return True if model weights are already present in the local cache.

    faster-whisper stores files via huggingface_hub.  The snapshot directory
    for a downloaded model will contain ``model.bin``.
    """
    models_dir = get_models_dir()
    pattern = f"models--Systran--faster-whisper-{model_name}"
    candidate = models_dir / pattern / "snapshots"
    if not candidate.exists():
        return False
    for snap in candidate.iterdir():
        if (snap / "model.bin").exists():
            return True
    return False
