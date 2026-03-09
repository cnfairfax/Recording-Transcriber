# Plan 03 — Speaker Diarization (pyannote-audio, Bundled Models)

## Status
In Progress

## Prerequisites — Plan 01 Compatibility

> **This plan is designed to be executed AFTER Plan 01 (Per-File Progress Bar)
> is complete.** The following Plan 01 changes will already exist in the
> codebase when Plan 03 work begins:
>
> | File | Plan 01 change that must be preserved |
> |------|---------------------------------------|
> | `src/transcribe_task.py` | Segment iteration loop with `file_progress` events (replaces `list(segments_gen)`) |
> | `src/worker.py` | `file_progress = pyqtSignal(str, float)` and its event dispatch case |
> | `src/main_window.py` | `_on_file_progress` slot, `_progress_bar_total`, two-tier progress model |
>
> **Rules to avoid regressions:**
> 1. **Never replace the per-segment `for` loop with `list(segments_gen)`** — the progress bar depends on it.
> 2. **Add diarization after the segment loop**, operating on the already-materialized `segments` list.
> 3. **Change `_save_outputs` / `_to_srt` / `_to_vtt` signatures** from `segments: list` to `tagged_segments: list[tuple]` — but keep a `(seg, None)` wrapper for the non-diarized path so the interface is uniform.
> 4. **The `file_progress` event uses `seg.end`** from the generator — this runs before output formatting and is unaffected by diarization.

## Goal
Label each segment in SRT/VTT output with a speaker tag (e.g. `[Speaker 1]`, `[Speaker 2]`) so voices are differentiated.

## Current Behaviour
- `model.transcribe()` yields segments with `.text`, `.start`, `.end` — no speaker info.
- Output files contain raw text with no speaker attribution.

## Approach — pyannote-audio with Bundled Model Weights
[pyannote-audio](https://github.com/pyannote/pyannote-audio) provides a pre-trained speaker diarization pipeline. We bundle the model weights directly in the installer so users never need a HuggingFace account or token. At runtime the pipeline loads from the local bundled path.

## New Dependencies
Add to `requirements.txt`:
```
torch>=2.0.0
torchaudio>=2.0.0
pyannote.audio>=3.1
```
**Impact:** ~2 GB additional download for torch. The pyannote weights themselves are small (~17 MB for the segmentation model).

## Bundled Models (No HF Token Required at Runtime)

### What to bundle
| Model | HuggingFace ID | License | Approx Size |
|-------|---------------|---------|-------------|
| Speaker diarization pipeline | `pyannote/speaker-diarization-3.1` | MIT | ~1 MB (config only) |
| Speaker segmentation model | `pyannote/segmentation-3.0` | MIT | ~17 MB (`pytorch_model.bin`) |

### How to download (one-time, by the developer)
Create a script `installer/download_pyannote_models.py`:
```python
"""Download pyannote models for bundling. Run once by the developer."""
from huggingface_hub import snapshot_download
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "models", "pyannote")
os.makedirs(OUT, exist_ok=True)

# Pipeline config
snapshot_download(
    "pyannote/speaker-diarization-3.1",
    local_dir=os.path.join(OUT, "speaker-diarization-3.1"),
    token="YOUR_HF_TOKEN_HERE",  # developer's own token
)

# Segmentation weights
snapshot_download(
    "pyannote/segmentation-3.0",
    local_dir=os.path.join(OUT, "segmentation-3.0"),
    token="YOUR_HF_TOKEN_HERE",
)
```
The resulting `models/pyannote/` directory is checked into the repo (or included via Git LFS / build artifact) and bundled into the installer.

### Bundled directory structure
```
models/
  pyannote/
    speaker-diarization-3.1/
      config.yaml
    segmentation-3.0/
      config.yaml
      pytorch_model.bin
```

### Loading from the local path at runtime
```python
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    "models/pyannote/speaker-diarization-3.1"  # local path, not a HF repo ID
)
```
pyannote's `from_pretrained` accepts a local directory path. The pipeline's `config.yaml` references the segmentation model — we patch it to point to the local `segmentation-3.0` path instead of the HF repo ID (see Changes Required § 3 below).

## Licensing & Attribution

### Legal basis
Both `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0` are released under the **MIT License**. MIT permits redistribution (including bundling in a free/open-source application) provided the license notice and copyright are preserved.

The "gated" status on HuggingFace is a **platform access control**, not an additional license restriction. Once downloaded, the weights can be freely redistributed under MIT.

### Required attribution
Include a file `THIRD_PARTY_LICENSES.md` (or a section in the existing `README.md`) with the following:

```markdown
## pyannote-audio

Speaker diarization powered by [pyannote-audio](https://github.com/pyannote/pyannote-audio).

### Models bundled in this application

- `pyannote/speaker-diarization-3.1` — MIT License
- `pyannote/segmentation-3.0` — MIT License

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

### Academic citation (optional but courteous)
The pyannote authors request citation in academic contexts:
```bibtex
@inproceedings{Bredin2023,
  author={Hervé Bredin},
  title={{pyannote.audio 2.1 speaker diarization pipeline: principle, benchmark, and recipe}},
  year=2023,
  booktitle={Proc. INTERSPEECH 2023},
}
```
Not legally required, but a link to the project in the README is good practice.

## Changes Required

### 1. `src/main_window.py` — UI
- Add a **"Speaker Diarization" checkbox** in the settings row (default: unchecked).
- No HF token field needed — models are bundled.
- Pass `diarize: bool` through to the worker.

### 2. `src/worker.py` — `TranscribeWorker`
- Accept `diarize` parameter.
- Pass it through in the subprocess job JSON:
  ```python
  job = {
      ...
      "diarize": self.diarize,
  }
  ```

### 3. `src/transcribe_task.py` — Diarization Logic

#### Model path resolution
```python
def _pyannote_model_dir() -> Path:
    """Return the path to the bundled pyannote models."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle
        return Path(sys._MEIPASS) / "models" / "pyannote"
    # Running from source
    return Path(__file__).resolve().parent.parent / "models" / "pyannote"
```

#### Pipeline loading
```python
def _load_diarization_pipeline():
    from pyannote.audio import Pipeline

    model_dir = _pyannote_model_dir()
    pipeline_dir = model_dir / "speaker-diarization-3.1"

    if not pipeline_dir.exists():
        raise FileNotFoundError(
            f"Bundled diarization model not found at {pipeline_dir}"
        )

    pipeline = Pipeline.from_pretrained(str(pipeline_dir))
    return pipeline
```

#### Config patching
The pipeline's `config.yaml` references the segmentation model by HuggingFace repo ID (e.g. `pyannote/segmentation-3.0`). Patch it at load time to use the local path:
```python
import yaml

def _patch_pipeline_config(pipeline_dir: Path, model_dir: Path) -> None:
    config_path = pipeline_dir / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Replace HF repo references with local paths
    seg_path = str(model_dir / "segmentation-3.0")
    # The config nests the segmentation model path under
    # pipeline.params.segmentation — update it:
    if "pipeline" in config and "params" in config["pipeline"]:
        params = config["pipeline"]["params"]
        if "segmentation" in params:
            params["segmentation"] = seg_path

    with open(config_path, "w") as f:
        yaml.dump(config, f)
```
Run this once during the build/packaging step, or at runtime before `from_pretrained`.

#### Diarization function
```python
def _diarize(audio_path: str) -> list[tuple[float, float, str]]:
    pipeline = _load_diarization_pipeline()
    diarization = pipeline(audio_path)
    turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append((turn.start, turn.end, speaker))
    return turns  # [(0.0, 3.5, "SPEAKER_00"), (3.5, 8.2, "SPEAKER_01"), ...]
```

#### Speaker assignment
```python
def _assign_speakers(segments, turns):
    result = []
    for seg in segments:
        best_speaker = "Unknown"
        best_overlap = 0.0
        for t_start, t_end, speaker in turns:
            overlap = max(0, min(seg.end, t_end) - max(seg.start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        result.append((seg, best_speaker))
    return result
```

#### Integration into main flow

> **IMPORTANT — Plan 01 compatibility.** After Plan 01 is implemented, the
> transcription loop in `transcribe_task.py` will already look like this:
>
> ```python
> segments_gen, info = model.transcribe(path, **kwargs)
> duration = info.duration or 1.0
> segments = []
> for seg in segments_gen:
>     segments.append(seg)
>     pct = min(100.0, (seg.end / duration) * 100)
>     _emit({"type": "file_progress", "path": path, "percent": round(pct, 1)})
> ```
>
> **Do NOT replace this with `segments = list(segments_gen)`** — that would
> destroy the per-file progress bar. Instead, add diarization *after* the
> existing loop finishes, using the already-materialized `segments` list.

```python
# ── Existing Plan 01 segment iteration (DO NOT MODIFY) ──────────
segments_gen, info = model.transcribe(path, **kwargs)
duration = info.duration or 1.0
segments = []
for seg in segments_gen:
    segments.append(seg)
    pct = min(100.0, (seg.end / duration) * 100)
    _emit({"type": "file_progress", "path": path, "percent": round(pct, 1)})

# ── NEW: Speaker diarization (Plan 03 addition) ─────────────────
if diarize:
    _log("Running speaker diarization…")
    _emit({"type": "file_progress_status", "path": path, "status": "Diarizing…"})
    try:
        turns = _diarize(path)
        tagged = _assign_speakers(segments, turns)
    except Exception as exc:
        _log(f"Diarization failed, proceeding without speaker labels: {exc}")
        tagged = [(seg, None) for seg in segments]
else:
    tagged = [(seg, None) for seg in segments]

_save_outputs(path, tagged, output_dir, formats)
```

### 4. `src/transcribe_task.py` — Output Formatting

> **Plan 01 compatibility note.** After Plan 01, the output functions
> (`_to_srt`, `_to_vtt`, `_save_outputs`) accept a plain `list` of segment
> objects. Plan 03 changes their signatures to accept a list of
> `(segment, speaker_label_or_None)` tuples instead. All call sites must be
> updated in the same commit. There is exactly one call site: the
> `_save_outputs(...)` call at the end of the per-file loop shown above.
>
> The `file_progress` event loop (Plan 01) is **not affected** because it
> uses `seg.end` directly from the generator — it runs before output
> formatting.

Update `_to_srt`, `_to_vtt`, and the `.txt` writer to accept tagged segments and prepend `[Speaker N]`:
```python
def _build_speaker_map(tagged_segments):
    """Map raw pyannote labels (SPEAKER_00, SPEAKER_01) to friendly names."""
    speaker_map = {}
    counter = 1
    for _, speaker in tagged_segments:
        if speaker and speaker not in speaker_map:
            speaker_map[speaker] = f"Speaker {counter}"
            counter += 1
    return speaker_map

def _to_srt(tagged_segments):
    speaker_map = _build_speaker_map(tagged_segments)
    lines = []
    for i, (seg, speaker) in enumerate(tagged_segments, 1):
        label = f"[{speaker_map[speaker]}] " if speaker else ""
        start = _fmt_srt(seg.start)
        end = _fmt_srt(seg.end)
        lines.append(f"{i}\n{start} --> {end}\n{label}{seg.text.strip()}\n")
    return "\n".join(lines)
```
Same pattern for `_to_vtt` and `.txt`.

> **Signature migration checklist.** After Plan 01, these functions take
> `segments: list`. Plan 03 changes them to `tagged_segments: list[tuple[Segment, str | None]]`.
> Update all three in lockstep:
>
> | Function | Plan 01 signature | Plan 03 signature |
> |----------|-------------------|-------------------|
> | `_to_srt(segments)` | `segments: list` | `tagged_segments: list[tuple]` |
> | `_to_vtt(segments)` | `segments: list` | `tagged_segments: list[tuple]` |
> | `_save_outputs(file_path, segments, output_dir, formats)` | `segments: list` | `tagged_segments: list[tuple]` |
>
> Inside `_save_outputs`, update the `.txt` writer from:
> ```python
> f.write(" ".join(seg.text.strip() for seg in segments))
> ```
> to:
> ```python
> speaker_map = _build_speaker_map(tagged_segments)
> parts = []
> for seg, speaker in tagged_segments:
>     label = f"[{speaker_map[speaker]}] " if speaker else ""
>     parts.append(f"{label}{seg.text.strip()}")
> f.write(" ".join(parts))
> ```

### 5. `requirements.txt`
Add (with a comment noting they're for diarization):
```
# Speaker diarization (optional feature)
torch>=2.0.0
torchaudio>=2.0.0
pyannote.audio>=3.1
```

### 6. `installer/recording_transcriber.spec` (PyInstaller)
Add the bundled models to the data files:
```python
datas=[
    ('models/pyannote', 'models/pyannote'),
],
```

### 7. `THIRD_PARTY_LICENSES.md`
Create this file with the MIT license text for pyannote (see Licensing & Attribution section above).

### 8. Error Handling
- If `pyannote.audio` is not installed and diarization is checked → emit:
  `"Speaker diarization requires pyannote.audio. Install with: pip install pyannote.audio torch torchaudio"`
- If bundled model files are missing → emit:
  `"Bundled diarization models not found. Reinstall the application."`
- If diarization fails at runtime → fall back to non-diarized output, log a warning. Do not fail the whole file.

## Performance Notes
- pyannote diarization adds ~30–60 s per file (CPU). If CUDA is available, it will use it automatically.
- The diarization runs sequentially after transcription for each file.
- The segmentation model (~17 MB) loads quickly from local disk.

## Testing
1. Enable diarization checkbox → SRT/VTT should contain `[Speaker 1]`, `[Speaker 2]` labels.
2. Disable diarization → output unchanged from current behaviour.
3. Bundled models missing → clear error message.
4. pyannote not installed → clear error message when diarization is attempted.
5. Single-speaker audio → all segments tagged `[Speaker 1]`.
6. Verify `THIRD_PARTY_LICENSES.md` is present and accurate.
