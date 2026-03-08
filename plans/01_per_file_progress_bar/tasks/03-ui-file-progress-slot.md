# Task 01-03: Two-Tier Progress Bar and _on_file_progress Slot in main_window.py

- **Plan:** [plans/01_per_file_progress_bar/01_per_file_progress_bar.md](../01_per_file_progress_bar.md)
- **Agent type:** UI
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 01-02 (requires `file_progress = pyqtSignal(str, float)` to exist on `TranscribeWorker`)
- **Files to modify:** `src/main_window.py`
- **Files to create:** `tests/test_ui_file_progress.py`

---

## What to Implement

### 1. Stash the total file count at job start
In `_start_transcription` (or equivalent method that queues the job), store the number of files:
```python
self._progress_bar_total = len(queued_files)
```

### 2. Connect the new signal
Wherever other worker signals are connected, add:
```python
self._worker.file_progress.connect(self._on_file_progress)
```

### 3. `_on_file_progress` slot
```python
@pyqtSlot(str, float)
@safe_slot
def _on_file_progress(self, path: str, percent: float) -> None:
    self._progress_bar.setRange(0, 100)
    self._progress_bar.setValue(int(percent))
    done = sum(1 for s in self._file_statuses.values() if s == "done")
    total = self._progress_bar_total
    self._status_bar.showMessage(
        f"File {done + 1} / {total}  —  {percent:.0f}%"
    )
```

> **Note on widget names:** The actual names of the progress bar and status bar widgets in `main_window.py` may differ from `_progress_bar` and `_status_bar`. Read the current source before writing tests — use whatever names already exist.

### 4. Update `_on_file_started` and `_on_file_done`
- **`_on_file_started`:** set `_progress_bar.setRange(0, 100)` and `setValue(0)` so the bar is ready for the incoming `file_progress` events.
- **`_on_file_done`:** snap the bar to `setValue(100)` then reset to `setValue(0)` for the next file.

These adjustments replace the old file-count-based `setRange` / `setValue` calls. Remove or update any code that set `_progress_bar.setRange(0, len(files))` and incremented by 1 per file.

---

## Tests to Write

File: `tests/test_ui_file_progress.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | After `_on_file_progress("a.wav", 42.7)`, `progress_bar.value() == 42` | Bar not updated |
| 2 | After `_on_file_progress`, `progress_bar` is in determinate mode (`maximum == 100`) | Still in indeterminate mode from Plan 02 |
| 3 | Status bar text contains `"42%"` after `_on_file_progress("a.wav", 42.0)` | Text not updated |
| 4 | After `_on_file_done`, `progress_bar.value() == 0` (reset for next file) | Bar stuck at 100 |
| 5 | After `_on_file_started`, `progress_bar.value() == 0` and `maximum == 100` | Wrong initial state |

Use `qtbot`. Mock `TranscribeWorker` — do not run transcription. Pre-set `window._progress_bar_total = 3` and a minimal `_file_statuses` dict for tests that read them.

---

## Acceptance Criteria

1. `_on_file_progress` slot exists, is decorated with `@safe_slot` and `@pyqtSlot(str, float)`.
2. `_progress_bar_total` is set before the job starts.
3. The progress bar shows per-file percentage (0–100%) during transcription.
4. The status bar shows `"File N / M — P%"` format during transcription.
5. The old file-count-based progress logic (`setRange(0, len(files))` + `+= 1 per file`) is removed or superseded — no double-counting.
6. On `file_done`, the bar snaps to 100% then resets to 0% for the next file.
7. All 5 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- `TranscribeWorker` doesn't yet have the `file_progress` signal (task 01-02 not merged) — wait before wiring the connection.
- The progress bar widget is used for Plan 02's indeterminate mode as well — ensure `_on_file_progress` always sets the range back to `(0, 100)` so it doesn't conflict with `_on_model_loading`'s `(0, 0)`. The sequencing is: `model_loading` → indeterminate → `model_loaded` → `file_started` → determinate per-file progress. If both plans are active, verify the state machine is correct.
- The current `_on_file_done`/`_on_file_started` implementations are complex — read them carefully before modifying to avoid breaking status label, list item colouring, or button state.
