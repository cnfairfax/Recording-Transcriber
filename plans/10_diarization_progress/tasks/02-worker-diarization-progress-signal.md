# Task 10-02: Add diarization_progress Signal to TranscribeWorker

- **Plan:** [plans/10_diarization_progress/10_diarization_progress.md](../10_diarization_progress.md)
- **Agent type:** Backend
- **Depends on:** Task 10-01
- **Files to modify:** `src/worker.py`
- **Files to create:** `tests/test_worker_diarization_progress_signal.py`

---

## What to Implement

### Signal declaration

Add alongside the existing `file_progress` signal:

```python
diarization_progress = pyqtSignal(str, float)  # file_path, percent 0–100
```

### Event dispatch

Add a new branch in the `run()` event-dispatch loop, immediately after the
`file_progress` handler and before `model_loading`:

```python
elif etype == "diarization_progress":
    raw_percent = event.get("percent", 0)
    try:
        percent = float(raw_percent)
    except (TypeError, ValueError):
        log.warning(
            "Malformed 'diarization_progress' percent value %r in event: %s",
            raw_percent,
            event,
        )
        percent = 0.0
    self.diarization_progress.emit(
        event.get("path", ""),
        percent,
    )
```

The defensive `float()` conversion and fallback-to-0.0 pattern matches the existing
`file_progress` handler exactly.

---

## Tests to Write

File: `tests/test_worker_diarization_progress_signal.py`

Use the same `_run_worker_with_events` helper pattern as
`tests/test_worker_file_progress_signal.py`.

| # | Test | Red trigger |
|---|------|-------------|
| 1 | Well-formed `diarization_progress` event emits signal with correct `(path, percent)` args | Signal not emitted |
| 2 | Missing `"percent"` key defaults to `0.0` | `KeyError` or wrong value |
| 3 | Missing `"path"` key defaults to `""` | `KeyError` |
| 4 | Non-numeric `"percent"` (e.g. `"bad"`) defaults to `0.0` without raising | `ValueError` propagates |
| 5 | `diarization_progress` event does NOT accidentally trigger `file_progress` signal | Wrong signal fires |

---

## Acceptance Criteria

1. `TranscribeWorker.diarization_progress` signal exists with signature `(str, float)`.
2. A `{"type": "diarization_progress", "path": "x.wav", "percent": 37.5}` event
   causes `diarization_progress.emit("x.wav", 37.5)`.
3. Malformed percent values fall back to `0.0` with a warning log, no exception.
4. All existing worker tests still pass.
