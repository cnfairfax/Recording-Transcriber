# Task 10-03: Wire diarization_progress to the Progress Bar in MainWindow

- **Plan:** [plans/10_diarization_progress/10_diarization_progress.md](../10_diarization_progress.md)
- **Agent type:** UI
- **Depends on:** Task 10-02
- **Files to modify:** `src/main_window.py`
- **Files to create:** `tests/test_ui_diarization_progress.py`

---

## What to Implement

### 1. Connect the signal in `_start_transcription`

Add immediately after the `file_progress` connect line:

```python
self._worker.diarization_progress.connect(self._on_diarization_progress)
```

### 2. Add the slot

Add after `_on_file_progress` and before `_on_file_error`:

```python
@pyqtSlot(str, float)
@safe_slot
def _on_diarization_progress(self, path: str, percent: float) -> None:
    """Update the progress bar during speaker diarization.

    Called by TranscribeWorker.diarization_progress for each pyannote hook event.
    ``percent`` is in the 0–100 range (inclusive).
    Resets the bar from its post-transcription state (100%) back to 0–100 as
    diarization progresses.
    """
    bar_value = int(round(percent))
    self._progress_bar.setRange(0, 100)
    self._progress_bar.setValue(bar_value)
    try:
        file_num = self._run_files.index(path) + 1
    except ValueError:
        file_num = 1
    total = len(self._run_files)
    self._status_label.setText(
        f"Diarizing file {file_num} / {total}  —  {bar_value}%"
    )
```

No new widget is needed. This reuses `_progress_bar` and `_status_label`, exactly
as `_on_file_progress` does.

---

## Tests to Write

File: `tests/test_ui_diarization_progress.py`

Use `qtbot` to instantiate `MainWindow` and call the slot directly (no real worker
needed). Mirror the `_make_window()` helper pattern from
`tests/test_ui_file_progress.py`, which sets `_run_files`, `_file_statuses`, and
the bar to the 0-100 range.

| # | Test | Red trigger |
|---|------|-------------|
| 1 | `_on_diarization_progress("x.wav", 37.5)` sets `_progress_bar.value()` to `38` | Bar not updated |
| 2 | Status label text contains `"Diarizing"` | Label not updated |
| 3 | Status label text contains the file count and percent, e.g. `"/ 1"` and `"38%"` | Wrong text format |
| 4 | `_progress_bar.minimum() == 0` and `_progress_bar.maximum() == 100` after call (bar is determinate, not pulsing) | Bar stuck in indeterminate mode |
| 5 | Pre-set bar to 100, call `_on_diarization_progress("x.wav", 0.0)`, assert `value() == 0` (bar resets from completion state) | Bar not reset |

You will need to set up `_run_files` on the window instance before calling the slot:

```python
window._run_files = ["x.wav"]
```

---

## Acceptance Criteria

1. Calling `_on_diarization_progress(path, percent)` updates `_progress_bar` to
   `int(round(percent))` with range `(0, 100)`.
2. Status label reads `"Diarizing file N / M  —  X%"`.
3. `diarization_progress` is connected in `_start_transcription` before `_worker.start()`.
4. All existing UI tests still pass.
