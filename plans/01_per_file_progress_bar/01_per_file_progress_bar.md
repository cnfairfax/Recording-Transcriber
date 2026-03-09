# Plan 01 — Per-File Transcription Progress Bar

## Status
Complete

## Goal
Show real-time progress (0–100%) for the file currently being transcribed, in addition to the existing file-count progress (e.g. "2 / 5 files").

## Current Behaviour
- `_progress_bar` range is set to `len(queued_files)` and incremented by 1 each time `file_done` fires.
- Within a single file there is zero feedback — the bar sits still until the file finishes.

## Approach — Segment-Based Estimation (no audio splitting)
faster-whisper's `model.transcribe()` returns a **generator** that lazily yields `Segment` objects. Each segment has `.start` and `.end` timestamps (seconds). The `TranscriptionInfo` object returned alongside the generator contains `.duration` (total audio duration in seconds).

By consuming the generator one segment at a time, we can compute:

```
progress_pct = (segment.end / audio_duration) * 100
```

This gives a smooth, monotonically increasing progress percentage with no need to chunk the audio.

## Changes Required

### 1. `src/transcribe_task.py`
- After calling `model.transcribe(path, **kwargs)`, capture `info.duration`.
- Emit a new event **`file_progress`** after each segment:
  ```json
  {"type": "file_progress", "path": "<path>", "percent": 42.7}
  ```
- Iterate the generator one segment at a time instead of `list(segments_gen)`:
  ```python
  segments_gen, info = model.transcribe(path, **kwargs)
  duration = info.duration or 1.0  # guard against 0
  segments = []
  for seg in segments_gen:
      segments.append(seg)
      pct = min(100.0, (seg.end / duration) * 100)
      _emit({"type": "file_progress", "path": path, "percent": round(pct, 1)})
  ```

### 2. `src/worker.py` — `TranscribeWorker`
- Add a new signal:
  ```python
  file_progress = pyqtSignal(str, float)  # file_path, percent 0-100
  ```
- In the event-dispatch loop, handle the new event type:
  ```python
  elif etype == "file_progress":
      self.file_progress.emit(event["path"], event.get("percent", 0))
  ```

### 3. `src/main_window.py` — `MainWindow`
- **Connect** the new signal:
  ```python
  self._worker.file_progress.connect(self._on_file_progress)
  ```
- **Add a two-tier progress model:**
  - Keep the existing file-count progress in the status label text.
  - Switch `_progress_bar` to range 0–100 when a file starts, and update it with percent values as `file_progress` events arrive.
  - When `file_done` fires, snap the bar to 100%, then reset to 0% for the next file.
- **Slot implementation:**
  ```python
  @pyqtSlot(str, float)
  @safe_slot
  def _on_file_progress(self, path: str, percent: float) -> None:
      self._progress_bar.setRange(0, 100)
      self._progress_bar.setValue(int(percent))
      done = sum(1 for s in self._file_statuses.values() if s == "done")
      total = self._progress_bar_total  # stashed in _start_transcription
      self._status_label.setText(
          f"File {done + 1} / {total}  —  {percent:.0f}%"
      )
  ```
- In `_start_transcription`, stash the total count:
  ```python
  self._progress_bar_total = len(queued_files)
  ```

## Edge Cases
- **Very short files** (< 1 s): may jump from 0% → 100% in one segment. Acceptable.
- **`info.duration` is `None` or 0**: fall back to `1.0` so the division doesn't fail; bar stays at 0% until `file_done`.
- **Segments that extend beyond `duration`** (rare rounding): clamp at 100%.

## Testing
1. Queue 1 file, start transcription → bar should animate from 0% → 100% smoothly.
2. Queue 3 files → bar resets for each file; status label shows "File 1/3 — 42%".
3. Error mid-file → bar stays where it was; file marked as error; next file starts at 0%.
