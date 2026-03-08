# Task 01-02: Add file_progress Signal to worker.py

- **Plan:** [plans/01_per_file_progress_bar/01_per_file_progress_bar.md](../01_per_file_progress_bar.md)
- **Agent type:** Backend
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 01-01 (event name `file_progress` with fields `path` and `percent` defined there)
- **Files to modify:** `src/worker.py`
- **Files to create:** `tests/test_worker_file_progress_signal.py`

---

## What to Implement

In `src/worker.py`, on `TranscribeWorker`:

### 1. Declare the new signal
```python
file_progress = pyqtSignal(str, float)  # file_path, percent 0–100
```

### 2. Dispatch the new event type
In the existing `elif etype == ...` event-dispatch chain, add:
```python
elif etype == "file_progress":
    self.file_progress.emit(
        event.get("path", ""),
        float(event.get("percent", 0)),
    )
```

No other changes to `worker.py` are needed for this task.

---

## Tests to Write

File: `tests/test_worker_file_progress_signal.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | Feeding `{"event": "file_progress", "path": "a.wav", "percent": 42.7}` to the worker emits `file_progress` with args `("a.wav", 42.7)` | Signal not emitted or wrong args |
| 2 | A missing `"percent"` key defaults to `0.0` rather than raising | `KeyError` crashes the worker |
| 3 | A missing `"path"` key defaults to `""` rather than raising | `KeyError` crashes the worker |
| 4 | `percent` is cast to `float` (test with an integer `42` in the event dict) | `TypeError` in signal emission |

Use `qtbot.waitSignal`. Mock the subprocess — do not spawn `transcribe_task.py`.

---

## Acceptance Criteria

1. `TranscribeWorker` declares `file_progress = pyqtSignal(str, float)`.
2. The signal is emitted for every incoming `file_progress` event.
3. Missing `path` or `percent` fields do not crash the worker.
4. All 4 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- The event dispatch structure doesn't use a simple `elif etype ==` chain — understand the actual dispatch pattern before adding the case.
- Adding the signal requires changes to `main_window.py` signal connections — that is task 01-03's job; stop there.
- The signal type `(str, float)` conflicts with existing signal definitions — check for naming collisions.
