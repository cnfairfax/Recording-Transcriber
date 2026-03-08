# Task 01-01: Emit file_progress Events from transcribe_task.py

- **Plan:** [plans/01_per_file_progress_bar/01_per_file_progress_bar.md](../01_per_file_progress_bar.md)
- **Agent type:** ML/Audio
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none
- **Files to modify:** `src/transcribe_task.py`
- **Files to create:** `tests/test_transcribe_file_progress.py`

---

## What to Implement

In `src/transcribe_task.py`, replace the existing `list(segments_gen)` call (or equivalent bulk consumption of the segment generator) with a per-segment loop that emits a `file_progress` event after each segment.

### Before (current pattern)
```python
segments_gen, info = model.transcribe(path, **kwargs)
segments = list(segments_gen)
```

### After
```python
segments_gen, info = model.transcribe(path, **kwargs)
duration = info.duration or 1.0   # guard against None / 0
segments = []
for seg in segments_gen:
    segments.append(seg)
    pct = min(100.0, (seg.end / duration) * 100)
    _emit({"event": "file_progress", "path": path, "percent": round(pct, 1)})
```

**`_emit` notation:** use whichever emit helper already exists in the file (likely `_emit(event_dict)` or `print(json.dumps(...), flush=True)`). Do not introduce a new helper.

**Critical:** The `segments` list must still be fully built (all segment objects appended) before it is passed to `_save_outputs`. The loop change must not break the downstream output formatting.

---

## Tests to Write

File: `tests/test_transcribe_file_progress.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | Processing a mock job emits at least one `file_progress` event per file | Event never emitted |
| 2 | Each `file_progress` event has `"path"` and `"percent"` keys | Missing keys crash the worker |
| 3 | `percent` values are monotonically non-decreasing and clamped to 100.0 | Out-of-order or >100 |
| 4 | When `info.duration` is `None`, no division error occurs and percent is 0.0 | `ZeroDivisionError` or `TypeError` |
| 5 | The accumulated `segments` list after the loop contains all segments (same as `list(segments_gen)` would have) | Segments lost — breaks output formatting |

Mock `WhisperModel` with a fake generator that yields 3 known segments and `TranscriptionInfo(duration=10.0)`. Do not load real model weights.

---

## Acceptance Criteria

1. `src/transcribe_task.py` no longer uses `list(segments_gen)` in the per-file transcription path.
2. A `file_progress` event is emitted for every yielded segment.
3. `percent` is rounded to 1 decimal place and clamped to `[0.0, 100.0]`.
4. The `path` field in each event matches the file being transcribed.
5. Downstream output (SRT, VTT, TXT) is unaffected — all segments are still collected.
6. All 5 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- The existing code uses `list(segments_gen)` in multiple places — audit all call sites before changing.
- The `_emit` / stdout JSON mechanism doesn't support emitting during iteration (buffered or closed) — escalate.
- `info.duration` is unavailable in the version of faster-whisper installed — check `TranscriptionInfo` fields before relying on it.
- Any test touches real model files or requires network access.
