# Plan 10 — Diarization Progress Bar

## Status
Not started

## Prerequisites

This plan requires Plan 03 (Speaker Diarization) to be fully merged and working.
The `_diarize()` function in `src/transcribe_task.py` and the `diarize` flag on
`TranscribeWorker` must already exist.

## Goal

Show a real-time 0–100% progress bar while pyannote-audio is running speaker
diarization, so the UI does not appear to freeze after transcription finishes.

## Current Behaviour

After the per-file transcription loop completes (progress bar snaps to 100%), the
worker goes silent for tens of seconds while `_diarize()` runs `pipeline(audio_path)`.
The progress bar stays at 100% and the status label shows the last transcription
percentage. The user has no indication that work is still happening.

## Approach — pyannote `hook=` Callback

`SpeakerDiarization.apply()` (called internally when you invoke a `Pipeline`) accepts
an optional `hook` callable:

```python
pipeline(audio_path, hook=my_hook)
```

The hook signature is:

```python
def hook(step_name, step_artefact, file=None, completed=None, total=None, **_):
    ...
```

`completed` and `total` are only passed during the two time-consuming phases:

| `step_name`    | Meaning                                    |
|----------------|--------------------------------------------|
| `segmentation` | Neural segmentation (chunks of audio)      |
| `embeddings`   | Speaker embedding extraction (per chunk)   |

Both phases iterate `total` chunks and call the hook after each. We map them to
even halves of the progress range:

```
phase "segmentation"  →  0.0 – 50.0 %
phase "embeddings"    →  50.0 – 100.0 %
```

The hook emits a new JSON event `diarization_progress` to stdout, which the worker
relays as a new `diarization_progress` PyQt signal, which the UI uses to drive the
same progress bar (resetting it from the post-transcription 100% back to 0% at the
start of diarization).

## New JSON Event

```json
{"type": "diarization_progress", "path": "<audio_path>", "percent": 42.0}
```

Rules:
- `percent` is `float`, rounded to 1 decimal, in `[0.0, 100.0]`.
- `path` matches the `audio_path` argument passed to `_diarize()`.
- Only emitted when `total > 0`; other hook calls (no `completed`/`total`) are
  silently ignored.
- Emitted during `segmentation` and `embeddings` phases only.

## Changes Required

### 1. `src/transcribe_task.py`

Modify `_diarize(audio_path)` to build a hook closure and pass it to `pipeline()`:

```python
_DIARIZATION_PHASE_OFFSET: dict[str, float] = {"segmentation": 0.0, "embeddings": 50.0}

def _diarize(audio_path: str) -> list[tuple[float, float, str]]:
    pipeline = _load_diarization_pipeline()

    def _hook(step_name, step_artefact, file=None,
              completed=None, total=None, **_kw):
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

`_emit` is the existing module-level helper at line 58 of `transcribe_task.py`
(`print(json.dumps(obj), flush=True)`). No new helper needed.

The constant `_DIARIZATION_PHASE_OFFSET` is added at module level immediately
above the `_diarize` function (around line 479). The existing `_diarize`
function body is replaced in full.

### 2. `src/worker.py` — `TranscribeWorker`

Add one signal and one dispatch case (mirrors `file_progress` exactly):

```python
# Signal declaration (alongside file_progress):
diarization_progress = pyqtSignal(str, float)  # file_path, percent 0–100
```

```python
# In the event-dispatch loop:
elif etype == "diarization_progress":
    raw_percent = event.get("percent", 0)
    try:
        percent = float(raw_percent)
    except (TypeError, ValueError):
        percent = 0.0
    self.diarization_progress.emit(event.get("path", ""), percent)
```

### 3. `src/main_window.py` — `MainWindow`

Connect the signal and add a slot that:
1. Resets the bar from the post-transcription 100% back to 0 on the first call (or
   always — `setValue` is idempotent so race conditions are harmless).
2. Drives the bar from 0–100 with the received `percent`.
3. Updates the status label to say "Diarizing file N / M — 42%".

```python
# In _start_transcription, after the file_progress connect line:
#   self._worker.file_progress.connect(self._on_file_progress)
# and before the model_loading connect line:
#   self._worker.model_loading.connect(self._on_model_loading)
self._worker.diarization_progress.connect(self._on_diarization_progress)
```

```python
@pyqtSlot(str, float)
@safe_slot
def _on_diarization_progress(self, path: str, percent: float) -> None:
    """Update the progress bar during speaker diarization."""
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

## Edge Cases

| Situation | Behaviour |
|-----------|-----------|
| Audio has no speakers / pipeline short-circuits | `hook` is never called with `completed`/`total`; no `diarization_progress` events emitted; bar stays at whatever transcription left it |
| Only `segmentation` phase runs (no `embeddings`) | Progress goes 0–50% and stops; `file_done` fires and snaps bar to 100% |
| `total == 0` in hook callback | Guard in hook returns early; no division by zero, no event emitted |
| Diarization error / exception | Existing `except Exception` in the call site catches it; `_log` reports failure; `file_done` fires normally; bar snaps to 100% |
| Non-diarize run | `_diarize` is never called; `diarization_progress` signal is never emitted; no UI change |

## Testing Strategy

### Task 01 tests (`test_transcribe_diarization_progress.py`)
- `_emit` writes JSON to **stdout**, so tests must use pytest's `capsys` fixture to
  capture output and parse events: `json.loads(line)` for each non-empty line in
  `capsys.readouterr().out`.
- Mock `_load_diarization_pipeline` to return a **real callable** (not a bare
  `MagicMock`) that accepts `(audio_path, hook=None)` and explicitly calls `hook`
  with known `(step_name, artefact, completed=N, total=M)` sequences before
  returning a mock annotation.  A `MagicMock` return value will not call the
  hook automatically.
- Assert that `diarization_progress` events are emitted with correct `percent` values.
- Assert phase boundary: last segmentation event ≤ 50.0, first embeddings event ≥ 50.0.
- Assert `percent` is clamped to `[0.0, 100.0]`.
- Assert no events when hook called without `completed`/`total`.

### Task 02 tests (`test_worker_diarization_progress_signal.py`)
- Feed `{"type": "diarization_progress", "path": "a.wav", "percent": 37.5}` to a
  mocked worker, assert `diarization_progress` signal fires with args `("a.wav", 37.5)`.
- Missing `percent` defaults to `0.0`.
- Non-numeric `percent` defaults to `0.0` without raising.

### Task 03 tests (`test_ui_diarization_progress.py`)
- Connect a mock worker to `_on_diarization_progress`, emit the signal, assert the
  progress bar value and status label text update correctly.
- Assert `progress_bar.maximum() == 100` (bar is in determinate, not pulsing, mode).
- Assert `progress_bar.minimum() == 0`.

## Persona Impact

**Jordan** (non-technical end user): currently sees the progress bar freeze at 100%
for up to 30 seconds while diarization runs with no feedback. After this plan, the bar
resets to 0% and fills again with a "Diarizing file N / M — X%" label. She knows work
is happening and roughly how far along it is.

**Alex** (developer): one new event type, one new signal, one new slot — the same
pattern already used for `file_progress` and `model_loading`. Easy to test, easy to
extend.
