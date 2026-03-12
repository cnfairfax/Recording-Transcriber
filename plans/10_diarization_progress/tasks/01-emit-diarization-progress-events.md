# Task 10-01: Emit diarization_progress Events from transcribe_task.py

- **Plan:** [plans/10_diarization_progress/10_diarization_progress.md](../10_diarization_progress.md)
- **Agent type:** ML/Audio (Backend)
- **Depends on:** Plan 03 complete
- **Files to modify:** `src/transcribe_task.py`
- **Files to create:** `tests/test_transcribe_diarization_progress.py`

---

## What to Implement

Add a `hook` closure inside `_diarize()` that emits `diarization_progress` events to
stdout as pyannote processes the audio.

### Module-level constant (add at module level immediately above `_diarize`)

```python
# Maps pyannote hook step names to the start of their percent range (two equal halves)
_DIARIZATION_PHASE_OFFSET: dict[str, float] = {
    "segmentation": 0.0,
    "embeddings": 50.0,
}
```

### Modified `_diarize`

```python
def _diarize(audio_path: str) -> list[tuple[float, float, str]]:
    """Run speaker diarization and return speaker turn segments.

    Returns a list of (start, end, speaker) tuples.
    """
    pipeline = _load_diarization_pipeline()

    def _hook(step_name, step_artefact, file=None,       # noqa: ANN001
              completed=None, total=None, **_kw):
        """pyannote progress hook — maps phases to 0–100% and emits events."""
        if completed is None or total is None or total == 0:
            return
        offset = _DIARIZATION_PHASE_OFFSET.get(step_name)
        if offset is None:
            return
        pct = round(offset + (completed / total) * 50.0, 1)
        _emit({"type": "diarization_progress",
               "path": audio_path,
               "percent": min(100.0, pct)})

    diarization = pipeline(audio_path, hook=_hook)
    return [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
```

Use the existing `_emit` helper (line 58 of `transcribe_task.py`,
`print(json.dumps(obj), flush=True)`).  Do not add a new helper.

The existing `_diarize` function body is replaced in full (the signature is
unchanged). The `_DIARIZATION_PHASE_OFFSET` constant is added at module level
immediately above the function.

---

## Tests to Write

File: `tests/test_transcribe_diarization_progress.py`

### Capturing emitted events

`_diarize` calls `_emit`, which writes JSON lines to **`sys.stdout`**.  Use
pytest's built-in `capsys` fixture to capture this output and parse events:

```python
def test_example(capsys):
    with patch("src.transcribe_task._load_diarization_pipeline",
               return_value=_make_fake_pipeline()):
        from src.transcribe_task import _diarize
        _diarize("test.wav")
    out = capsys.readouterr().out
    events = [json.loads(line) for line in out.splitlines() if line.strip()]
    diar_events = [e for e in events if e.get("type") == "diarization_progress"]
```

### Building the fake pipeline

**Important:** The mock pipeline must be a real Python callable that *actually
invokes the `hook` argument* — a bare `MagicMock()` will not do this.

```python
import json
from unittest.mock import MagicMock, patch

def _make_fake_pipeline(seg_total=4, emb_total=4):
    """Return a callable that simulates pyannote pipeline progress hook calls."""
    def fake_pipeline(audio_path, hook=None):
        if hook is not None:
            for i in range(1, seg_total + 1):
                hook("segmentation", None, file=None, completed=i, total=seg_total)
            for i in range(1, emb_total + 1):
                hook("embeddings", None, file=None, completed=i, total=emb_total)
        result = MagicMock()
        result.itertracks.return_value = []  # no speaker turns
        return result
    return fake_pipeline
```

### Test table

Mock `_load_diarization_pipeline` to return `_make_fake_pipeline()` in all tests.

| # | Test | Red trigger |
|---|------|-------------|
| 1 | `_diarize()` emits exactly 8 `diarization_progress` events (4 segmentation + 4 embedding) | Events not emitted |
| 2 | Segmentation events have `percent` in `[0.0, 50.0]` | Wrong range |
| 3 | Embedding events have `percent` in `(50.0, 100.0]` | Wrong range |
| 4 | All events have `"path"` matching the `audio_path` argument | Wrong or missing path |
| 5 | Hook called without `completed`/`total` → no event emitted (guard fires) | Exception or spurious event |
| 6 | `total == 0` in hook → no event emitted, no `ZeroDivisionError` | Crash |
| 7 | `percent` is clamped to 100.0 even if arithmetic would exceed it | Value > 100 |

---

## Acceptance Criteria

1. `_diarize` passes a `hook=` argument to `pipeline(...)`.
2. The hook emits `{"type": "diarization_progress", "path": ..., "percent": ...}` events.
3. `percent` is rounded to 1 decimal, in `[0.0, 100.0]`.
4. No events emitted when hook is called without `completed`/`total` keyword args.
5. All existing diarization tests still pass.
