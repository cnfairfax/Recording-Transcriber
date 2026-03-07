"""Download a faster-whisper model to the Recording Transcriber data directory.

This script is bundled as ``download_model.exe`` by PyInstaller and called by
the Inno Setup installer immediately after the app files are placed.

Usage
-----
  download_model.exe --model large-v3
  download_model.exe --model small
  download_model.exe --model large-v3 --check   # exit 0 if already present

The selected model is saved to:
  Windows : %APPDATA%\\Recording Transcriber\\models\\
and is picked up automatically by the app on next launch (no re-download).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly from the repo root (development) as well as from the
# bundled PyInstaller MEIPASS directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.model_manager import (  # noqa: E402
    MODELS,
    MODEL_NAMES,
    is_model_downloaded,
    model_download_root,
)


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------

def download(model_name: str) -> int:
    """Download *model_name* into the app data dir.  Returns an exit code."""
    download_root = model_download_root()
    print(f"Model  : {model_name}")
    print(f"Target : {download_root}")
    print()

    if is_model_downloaded(model_name):
        print(f"Model '{model_name}' is already present. Nothing to download.")
        return 0

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        print(f"ERROR: faster-whisper is not available: {exc}", file=sys.stderr)
        return 1

    # Locate the size hint for display
    size_hint = next((s for n, s, _ in MODELS if n == model_name), "")
    print(f"Downloading '{model_name}' {size_hint} …")
    print("This may take several minutes.  Do not close this window.\n")

    try:
        # Instantiating WhisperModel triggers a download when the weights are
        # absent from download_root.  We immediately destroy the object so the
        # GPU memory is freed — the app will reload the model when needed.
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=download_root,
        )
        del model
        print(f"\nDownload complete — '{model_name}' is ready.")
        return 0
    except Exception as exc:
        print(f"\nERROR: download failed:\n  {exc}", file=sys.stderr)
        return 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="download_model",
        description="Download a Whisper model for Recording Transcriber.",
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=MODEL_NAMES,
        metavar="MODEL",
        help=f"Model to download. Choices: {', '.join(MODEL_NAMES)}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the model is already downloaded (exit 0=yes, 1=no).",
    )
    args = parser.parse_args()

    if args.check:
        if is_model_downloaded(args.model):
            print(f"Model '{args.model}' is already downloaded.")
            sys.exit(0)
        else:
            print(f"Model '{args.model}' is not yet downloaded.")
            sys.exit(1)

    sys.exit(download(args.model))


if __name__ == "__main__":
    main()
