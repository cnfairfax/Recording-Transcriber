# Task 02-03: Indeterminate Progress Bar for Model Loading in main_window.py

- **Plan:** [plans/02_model_loading_indicator/02_model_loading_indicator.md](../02_model_loading_indicator.md)
- **Agent type:** UI
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 02-02 (signal signatures `model_loading: pyqtSignal(str)` and `model_loaded: pyqtSignal(str)` must exist on `TranscribeWorker`)
- **Files to modify:** `src/main_window.py`
- **Files to create:** `tests/test_ui_model_loading.py`

---

## What to Implement

In `src/main_window.py`, wire the two new worker signals to slots that control the progress bar's indeterminate mode.

### 1. Connect signals
In the method where `_worker` signals are connected (alongside `file_started`, `file_done`, etc.), add:
```python
self._worker.model_loading.connect(self._on_model_loading)
self._worker.model_loaded.connect(self._on_model_loaded)
```

### 2. `_on_model_loading` slot
```python
@pyqtSlot(str)
@safe_slot
def _on_model_loading(self, model_name: str) -> None:
    self._progress_bar.setRange(0, 0)   # activates Qt's pulsing/indeterminate mode
    self._status_bar.showMessage(f"Loading model '{model_name}'…")
```

Setting `QProgressBar.setRange(0, 0)` is the standard Qt mechanism for indeterminate (busy) mode — the chunk slides back and forth continuously.

### 3. `_on_model_loaded` slot
```python
@pyqtSlot(str)
@safe_slot
def _on_model_loaded(self, model_name: str) -> None:
    self._progress_bar.setRange(0, 100)  # return to determinate mode
    self._progress_bar.setValue(0)
    self._status_bar.showMessage(f"Model '{model_name}' ready — transcribing…")
```

### 4. Stylesheet (if needed)
If testing shows the pulsing animation doesn't render on Windows with the current dark stylesheet, add these rules to `STYLESHEET`:
```css
QProgressBar:indeterminate {
    background-color: #313244;
}
QProgressBar::chunk:indeterminate {
    background-color: #89b4fa;
    width: 80px;
}
```
Only add if visually broken — do not add speculatively.

---

## Tests to Write

File: `tests/test_ui_model_loading.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | After `_on_model_loading("base")` is called, `progress_bar.minimum() == 0` and `progress_bar.maximum() == 0` | Bar not in indeterminate mode |
| 2 | After `_on_model_loaded("base")` is called, `progress_bar.maximum() == 100` and `progress_bar.value() == 0` | Bar stuck in indeterminate or wrong value |
| 3 | Status bar shows `"Loading model 'base'…"` after `_on_model_loading("base")` | Wrong text or no update |
| 4 | Status bar shows `"ready"` text after `_on_model_loaded("base")` | Text not updated |

Use `qtbot`. Mock `TranscribeWorker` — do not run transcription.

---

## Acceptance Criteria

1. Calling `_on_model_loading` puts the progress bar into indeterminate mode (`range == (0, 0)`).
2. Calling `_on_model_loaded` restores the progress bar to determinate mode (`range == (0, 100)`, `value == 0`).
3. Status bar updates reflect the model name in both slots.
4. Both slots are decorated with `@safe_slot` and `@pyqtSlot(str)`.
5. All 4 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- `TranscribeWorker` doesn't yet have the `model_loading` / `model_loaded` signals (task 02-02 not merged) — wait for 02-02 before connecting.
- The progress bar widget name in the current codebase differs from what the plan assumes — check `main_window.py` before writing tests.
- Adding the stylesheet rule for indeterminate mode visually breaks other progress bar states — escalate to Architect.
