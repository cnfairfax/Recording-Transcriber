# Task 03-05: Build — Dependencies, PyInstaller Spec, Model Download Script, Licenses

- **Plan:** [plans/03_speaker_diarization/03_speaker_diarization.md](../03_speaker_diarization.md)
- **Agent type:** Build
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none (can run in parallel with all other Plan 03 tasks)
- **Prerequisite plan:** Plan 01 must be complete before merging any Plan 03 task
- **Files to modify:** `requirements.txt`, `installer/recording_transcriber.spec`
- **Files to create:** `installer/download_pyannote_models.py`, `THIRD_PARTY_LICENSES.md`

---

## What to Implement

### 1. `requirements.txt` — Add diarization dependencies
Below the existing entries, add a clearly commented block:

```
# Speaker diarization (Plan 03 — optional feature)
torch>=2.0.0
torchaudio>=2.0.0
pyannote.audio>=3.1
```

### 2. `installer/recording_transcriber.spec` — Bundle the pyannote models
Add the bundled models directory to `datas`:
```python
datas=[
    ...,
    ('models/pyannote', 'models/pyannote'),
],
```

The `models/pyannote/` directory is populated by running `installer/download_pyannote_models.py` (see below). It must exist before `pyinstaller` is invoked. Add a guard or comment in the spec noting this prerequisite.

### 3. `installer/download_pyannote_models.py` — Developer model download script
Create a one-time script that developers run to pull the model weights before building:

```python
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
```

### 4. `THIRD_PARTY_LICENSES.md` — pyannote attribution

> **Note:** The README already contains an open-source acknowledgements section covering all current runtime dependencies. `THIRD_PARTY_LICENSES.md` is for the full MIT license text of the **bundled model weights**, which must be reproduced verbatim per the MIT license terms.

```markdown
# Third-Party Licenses

## pyannote-audio — Bundled Model Weights

Speaker diarization powered by [pyannote-audio](https://github.com/pyannote/pyannote-audio).

The following model weights are bundled in this application:

- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`

Copyright (c) 2020-present CNRS, Hervé Bredin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Tests to Write

File: `tests/test_build_plan03.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | `requirements.txt` contains `torch`, `torchaudio`, and `pyannote.audio` | Dependencies missing |
| 2 | `installer/recording_transcriber.spec` contains `'models/pyannote'` in its `datas` | Models won't be bundled |
| 3 | `installer/download_pyannote_models.py` exists and is syntactically valid Python | Script absent or broken |
| 4 | `THIRD_PARTY_LICENSES.md` exists and contains the word `"CNRS"` (validates the copyright text is present) | License text missing |

These are all file/string assertion tests — no build execution required.

---

## Acceptance Criteria

1. `requirements.txt` lists `torch`, `torchaudio`, and `pyannote.audio` with the version constraints from the plan.
2. The PyInstaller spec bundles `models/pyannote` as a data directory.
3. `installer/download_pyannote_models.py` runs cleanly and has a `--token` argument.
4. `THIRD_PARTY_LICENSES.md` exists at the repo root with the full MIT license text for pyannote.
5. All 4 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- `torch>=2.0.0` + `torchaudio` combined add more than 2 GB to the installer — check with the Architect whether a CPU-only torch wheel is acceptable to reduce size.
- The `models/pyannote/` directory doesn't exist when PyInstaller runs — spec needs a clear error or the build script must verify it.
- `THIRD_PARTY_LICENSES.md` content conflicts with the README acknowledgements section already added — resolve by keeping the README high-level and the licenses file for verbatim license text.
