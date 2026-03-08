# Plan 02 — Model Loading Progress Indicator

## Goal
Show a visible, animated indicator while the Whisper model is being loaded so the user knows the app hasn't frozen.

## Current Behaviour
- `transcribe_task.py` emits `_log("Loading Whisper model '...' ...")` then blocks during `WhisperModel(...)` construction.
- The GUI shows the log message but the progress bar sits at 0% with no animation.

## Approach — Indeterminate (Pulsing) Progress Bar
`WhisperModel.__init__()` does not expose any callback. It is a single blocking call that may take 2–30 seconds depending on model size, disk speed, and whether it needs to download. Rather than hack around this, use Qt's built-in indeterminate mode.

## Changes Required

### 1. `src/transcribe_task.py`
- Emit a new event **before** the `WhisperModel()` call:
  ```json
  {"type": "model_loading", "model": "large-v3"}
  ```
- Emit another event **after** it succeeds:
  ```json
  {"type": "model_loaded", "model": "large-v3"}
  ```
- These bracket the blocking call so the GUI knows when to start/stop the animation.

### 2. `src/worker.py` — `TranscribeWorker`
- Add two new signals:
  ```python
  model_loading = pyqtSignal(str)   # model_name
  model_loaded  = pyqtSignal(str)   # model_name
  ```
- In the event-dispatch loop:
  ```python
  elif etype == "model_loading":
      self.model_loading.emit(event.get("model", ""))
  elif etype == "model_loaded":
      self.model_loaded.emit(event.get("model", ""))
  ```

### 3. `src/main_window.py` — `MainWindow`
- **Connect** the new signals:
  ```python
  self._worker.model_loading.connect(self._on_model_loading)
  self._worker.model_loaded.connect(self._on_model_loaded)
  ```
- **`_on_model_loading` slot:**
  ```python
  @pyqtSlot(str)
  @safe_slot
  def _on_model_loading(self, model_name: str) -> None:
      self._progress_bar.setRange(0, 0)  # indeterminate / pulsing
      self._status_label.setText(f"Loading model '{model_name}'…")
  ```
  Setting the range to `(0, 0)` activates Qt's built-in "busy" animation — the bar chunk slides back and forth.

- **`_on_model_loaded` slot:**
  ```python
  @pyqtSlot(str)
  @safe_slot
  def _on_model_loaded(self, model_name: str) -> None:
      self._progress_bar.setRange(0, 100)  # back to normal mode
      self._progress_bar.setValue(0)
      self._status_label.setText(f"Model '{model_name}' ready — transcribing…")
  ```

## Stylesheet Consideration
The existing `QProgressBar::chunk` style (solid `#89b4fa` fill) works with indeterminate mode on Windows, but some Qt styles may not animate it. If needed, an additional stylesheet rule can be added:
```css
QProgressBar:indeterminate {
    background-color: #313244;
}
QProgressBar::chunk:indeterminate {
    background-color: #89b4fa;
    width: 80px;
}
```

## Edge Cases
- **Model already cached:** load is fast (2–5 s). The pulse shows briefly and disappears — no problem.
- **First-time download:** load can take minutes. The pulse keeps going until `model_loaded` fires.
- **GPU fallback path:** if the first `WhisperModel()` fails and retries on CPU, the subprocess already emits log messages for this. A second `model_loading` event is not needed — the indeterminate bar remains active until `model_loaded` or `fatal`.

## Testing
1. First run with a model not yet downloaded → pulsing bar for the full download + load time.
2. Subsequent run with cached model → brief pulse (2–5 s), then transitions to file progress.
3. Fatal error during load → bar stops pulsing when the error dialog appears.
