"""
Download pyannote models for bundling into the installer.

Run ONCE before building the installer:
    python installer/download_pyannote_models.py --token YOUR_HF_TOKEN

The resulting models/ directory is then bundled by PyInstaller.
You only need a HuggingFace token for this download step.
End users of the installed application do NOT need a token.

Models downloaded:
  pyannote/speaker-diarization-3.1       — pipeline config
  pyannote/segmentation-3.0             — segmentation model weights
  pyannote/wespeaker-voxceleb-resnet34-LM — speaker embedding weights

After downloading, the script rewrites speaker-diarization-3.1/config.yaml to
reference the other two models via local paths so the application never
contacts HuggingFace Hub at runtime.
"""
import argparse
from pathlib import Path


def _rewrite_config(pipeline_dir: Path, seg_dir: Path, embed_dir: Path) -> None:
    """Rewrite config.yaml to use local paths for segmentation and embedding."""
    try:
        import yaml
    except ImportError:
        raise SystemExit("Install pyyaml first: pip install pyyaml")

    config_path = pipeline_dir / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Model.from_pretrained only recognises file paths, not directories.
    # Both segmentation and embedding (pyannote/wespeaker-voxceleb-resnet34-LM)
    # are PyTorch models loaded via pyannote Model.from_pretrained — point at
    # pytorch_model.bin in each directory.
    cfg["pipeline"]["params"]["segmentation"] = str((seg_dir / "pytorch_model.bin").resolve())
    cfg["pipeline"]["params"]["embedding"] = str((embed_dir / "pytorch_model.bin").resolve())

    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

    print(f"  → patched {config_path.name}")


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

    models = [
        "pyannote/speaker-diarization-3.1",
        "pyannote/segmentation-3.0",
        "pyannote/wespeaker-voxceleb-resnet34-LM",
    ]

    for repo_id in models:
        name = repo_id.split("/")[1]
        print(f"Downloading {repo_id}…")
        try:
            snapshot_download(
                repo_id,
                local_dir=str(out / name),
                token=args.token,
            )
        except Exception as exc:
            raise SystemExit(
                f"Failed to download {repo_id}.\n"
                f"  Error: {exc}\n"
                "  Check that your --token is valid and you have accepted the model license at\n"
                f"  https://huggingface.co/{repo_id}"
            ) from exc
        print(f"  → {out / name}")

    # Rewrite config.yaml so sub-models resolve to local paths at runtime.
    print("\nPatching speaker-diarization-3.1/config.yaml to use local paths…")
    _rewrite_config(
        pipeline_dir=out / "speaker-diarization-3.1",
        seg_dir=out / "segmentation-3.0",
        embed_dir=out / "wespeaker-voxceleb-resnet34-LM",
    )

    print("\nDone. Run pyinstaller next.")


if __name__ == "__main__":
    main()
