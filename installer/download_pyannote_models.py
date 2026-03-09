"""
Download pyannote models for bundling into the installer.

Run ONCE before building the installer:
    python installer/download_pyannote_models.py --token YOUR_HF_TOKEN

The resulting models/ directory is then bundled by PyInstaller.
You only need a HuggingFace token for this download step.
End users of the installed application do NOT need a token.
"""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="HuggingFace access token")
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit("Install huggingface_hub first: pip install huggingface_hub")

    out = Path(__file__).resolve().parent.parent / "models" / "pyannote"
    out.mkdir(parents=True, exist_ok=True)

    for repo_id in [
        "pyannote/speaker-diarization-3.1",
        "pyannote/segmentation-3.0",
    ]:
        name = repo_id.split("/")[1]
        print(f"Downloading {repo_id}…")
        snapshot_download(
            repo_id,
            local_dir=str(out / name),
            token=args.token,
        )
        print(f"  → {out / name}")

    print("\nDone. Run pyinstaller next.")


if __name__ == "__main__":
    main()
