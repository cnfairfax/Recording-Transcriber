# Task 02-02: Add model_loading / model_loaded Signals to worker.py

- **Plan:** [plans/02_model_loading_indicator/02_model_loading_indicator.md](../02_model_loading_indicator.md)
- **Agent type:** Backend
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 02-01 (event names `model_loading` / `model_loaded` defined there)
- **Files to modify:** `src/worker.py`
- **Files to create:** `tests/test_worker_model_signals.py`

---

## What to Implement

In `src/worker.py`, on `TranscribeWorker`:

### 1. Declare two new signals
```python
model_loading = pyqtSignal(str)   # model_name
model_loaded  = pyqtSignal(str)   # model_name
```

### 2. Dispatch the new events in the event loop
In the existing `elif etype == ...` chain that handles JSON event types, add:
```python
elif etype == "model_loading":
    self.model_loading.emit(event.get("model", ""))
elif etype == "model_loaded":
    self.model_loaded.emit(event.get("model", ""))
```

No other changes to `worker.py` are needed for this task.

---

## Tests to Write

File: `tests/test_worker_model_signals.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | Feeding `{"event": "model_loading", "model": "base"}` to the worker's event handler causes `model_loading` signal to emit with `"base"` | Signal not emitted or wrong value |
| 2 | Feeding `{"event": "model_loaded", "model": "base"}` causes `model_loaded` signal to emit with `"base"` | Signal not emitted or wrong value |
| 3 | A missing `"model"` key in the event emits an empty string `""` rather than raising | KeyError crashes the worker |

Use `qtbot.waitSignal` / `qtbot.assertNotEmitted`. Mock the subprocess — do not spawn `transcribe_task.py`.

---

## Acceptance Criteria

1. `TranscribeWorker` declares `model_loading = pyqtSignal(str)` and `model_loaded = pyqtSignal(str)`.
2. Both signals are dispatched correctly for their respective event types.
3. The worker does not crash on a malformed event (missing `"model"` key).
4. All 3 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- The event dispatch loop structure in `worker.py` doesn't support simple `elif` extension — escalate before refactoring.
- Adding the signals requires modifying `main_window.py` signal connections — that's task 02-03's job; stop and coordinate.
- A test requires spawning the real `transcribe_task.py` subprocess — use a mock instead.
