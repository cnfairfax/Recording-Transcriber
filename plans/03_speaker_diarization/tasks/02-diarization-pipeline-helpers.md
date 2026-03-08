# Task 03-02: Diarization Pipeline Helpers in transcribe_task.py

- **Plan:** [plans/03_speaker_diarization/03_speaker_diarization.md](../03_speaker_diarization.md)
- **Agent type:** ML/Audio
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none (can run in parallel with 03-01)
- **Prerequisite plan:** Plan 01 must be complete before merging any Plan 03 task
- **Files to modify:** `src/transcribe_task.py`
- **Files to create:** `tests/test_diarization_helpers.py`

---

## What to Implement

Add the following pure helper functions to `src/transcribe_task.py`. These are self-contained and do not yet integrate with the transcription flow (that is task 03-03).

### `_pyannote_model_dir() -> Path`
Returns the path to the bundled pyannote models, handling both frozen (PyInstaller) and dev-mode execution:
```python
def _pyannote_model_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "models" / "pyannote"
    return Path(__file__).resolve().parent.parent / "models" / "pyannote"
```

### `_load_diarization_pipeline()`
Loads the local pyannote pipeline. Raises `FileNotFoundError` if models are missing:
```python
def _load_diarization_pipeline():
    from pyannote.audio import Pipeline
    pipeline_dir = _pyannote_model_dir() / "speaker-diarization-3.1"
    if not pipeline_dir.exists():
        raise FileNotFoundError(
            f"Bundled diarization model not found at {pipeline_dir}. "
            "Reinstall the application."
        )
    return Pipeline.from_pretrained(str(pipeline_dir))
```

### `_diarize(audio_path: str) -> list[tuple[float, float, str]]`
Runs diarization and returns speaker turn segments:
```python
def _diarize(audio_path: str) -> list[tuple[float, float, str]]:
    pipeline = _load_diarization_pipeline()
    diarization = pipeline(audio_path)
    return [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
```

### `_assign_speakers(segments, turns) -> list[tuple]`
Assigns the best-overlap speaker label to each transcription segment:
```python
def _assign_speakers(segments, turns):
    result = []
    for seg in segments:
        best_speaker, best_overlap = "Unknown", 0.0
        for t_start, t_end, speaker in turns:
            overlap = max(0, min(seg.end, t_end) - max(seg.start, t_start))
            if overlap > best_overlap:
                best_overlap, best_speaker = overlap, speaker
        result.append((seg, best_speaker))
    return result
```

---

## Tests to Write

File: `tests/test_diarization_helpers.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | `_pyannote_model_dir()` returns a `Path` ending in `models/pyannote` in dev mode | Wrong path |
| 2 | `_load_diarization_pipeline()` raises `FileNotFoundError` when the model directory doesn't exist | Raises wrong exception or no exception |
| 3 | `_assign_speakers(segments, turns)` assigns the correct speaker for a segment with clear overlap | Wrong speaker assigned |
| 4 | `_assign_speakers` assigns `"Unknown"` for a segment with no overlapping turns | Crashes or returns None |
| 5 | `_assign_speakers` picks the speaker with the greatest overlap when multiple turns overlap | Wrong speaker chosen |

Mock `pyannote.audio.Pipeline` — never load real model weights in tests.
Use simple `namedtuple` or `SimpleNamespace` objects for mock segments.

---

## Acceptance Criteria

1. All four helper functions exist with the signatures above.
2. `_pyannote_model_dir()` works correctly in both dev-mode and `sys.frozen` mode.
3. `_load_diarization_pipeline()` raises a clear `FileNotFoundError` if models are absent.
4. `_assign_speakers` correctly handles zero overlap, full overlap, and partial overlap cases.
5. All 5 new tests pass. All pre-existing tests pass.
6. `pyannote.audio` is imported lazily (inside the function), not at module top-level — the subprocess must still start without pyannote installed when diarization is disabled.

---

## Red-Flag Triggers

- `pyannote.audio.Pipeline.from_pretrained` doesn't accept a local path string in the installed version — check API docs before implementing.
- The config patching approach (for `config.yaml` segmentation model path) turns out to require in-place file mutation — escalate to Architect; this may need to move to a build step.
- Tests require `pyannote.audio` to be installed in CI — if it's too large, use `unittest.mock.patch` at the import level.
