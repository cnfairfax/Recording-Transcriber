# Plan 08 — Worker Resilience: Crash Surface and Test Fix

## Status
Ready for Implementation

---

## Goal

Fix two related defects exposed by the Windows environment:

1. **Worker hangs indefinitely when the subprocess crashes under Windows Error
   Reporting (WER).** If the subprocess terminates with an access violation,
   WER holds the process handle alive while it collects a crash report. The
   subprocess's stdout pipe remains open until WER finishes (potentially
   minutes). The reader thread blocks on stdout; the event loop blocks on the
   queue; the GUI appears frozen with the progress bar at 0.

2. **Five tests in `test_transcribe_file_progress.py` crash pytest with
   `OSError: [WinError 1114]`.** The tests patch `faster_whisper.WhisperModel`
   using `unittest.mock.patch("faster_whisper.WhisperModel", ...)`. Resolving
   that target string requires Python to `import faster_whisper`, which triggers
   `ctranslate2 → specs/model_spec.py → import torch → _load_dll_libraries()`.
   This crashes the pytest process with a Windows fatal exception — the same
   root cause as Plan 07, but on the test side.

---

## Root Cause

### Defect 1 — WER hang

`worker.py:TranscribeWorker.run()` event loop:

```python
while True:
    if self._stop_requested:
        ...break
    try:
        raw_line = _line_queue.get(timeout=0.25)
    except queue.Empty:
        continue          # ← loops forever if process is WER-held
    if raw_line is None:  # never arrives while WER holds the pipe
        break
```

The `except queue.Empty: continue` branch never checks whether the subprocess
has already exited. When WER holds the process alive, `proc.poll()` returns
`None` while the process handle is live, but once WER completes (or is
dismissed), `proc.poll()` returns the exit code.

However the user may wait minutes. The correct fix is to call `proc.poll()`
inside the `Empty` handler and break out as soon as the process has exited so
that the at-exit crash detection and `fatal_error` emission run promptly.

### Defect 2 — test faster_whisper import crash

```python
with patch("faster_whisper.WhisperModel", return_value=mock_model):
    # ↑ unittest.mock resolves "faster_whisper.WhisperModel" by importing
    # faster_whisper, which chain-imports ctranslate2 → torch → DLL crash
    transcribe_task.main()
```

Fix: pre-inject a stub module into `sys.modules["faster_whisper"]` BEFORE
`transcribe_task.main()` is called. `main()` does `from faster_whisper import
WhisperModel` inside a `try` block. Python's import machinery checks
`sys.modules` first; if a stub is present, the real package is never loaded.

---

## Technical Approach

### Change 1 — `src/worker.py`: proc.poll() guard in event loop

In the `except queue.Empty` handler, add a `proc.poll() is not None` check:

```python
except queue.Empty:
    # Guard against Windows Error Reporting (WER) holding the subprocess
    # handle alive after a crash.  WER keeps the stdout pipe open while
    # it collects a crash dump, so the reader thread never delivers the
    # EOF sentinel.  Checking proc.poll() lets us detect process death
    # without waiting for WER to finish.
    if proc.poll() is not None:
        log.warning(
            "Subprocess exited (code %s) while stdout was still open; "
            "breaking event loop.",
            proc.poll(),
        )
        break
    continue
```

No other changes to `worker.py`. The existing exit-code check and
`fatal_error` emission at the bottom of `run()` already handle the crash
detection correctly once the loop exits.

### Change 2 — `tests/test_transcribe_file_progress.py`: sys.modules injection

Replace the `patch("faster_whisper.WhisperModel", ...)` stanza in `_run_main`
with a `sys.modules` stub:

```python
import types

def _run_main(job_json: str, mock_model) -> list[dict]:
    from src import transcribe_task

    # Inject a stub module so transcribe_task.main()'s
    #   from faster_whisper import WhisperModel
    # never loads the real package (which triggers ctranslate2→torch→DLL crash).
    fake_fw = types.ModuleType("faster_whisper")
    fake_fw.WhisperModel = mock_model.__class__  # class, not instance

    captured = io.StringIO()
    with (
        patch.dict(sys.modules, {"faster_whisper": fake_fw}),
        patch("sys.stdin", io.StringIO(job_json)),
        patch("sys.stdout", captured),
        patch.object(transcribe_task, "detect_best_device",
                     return_value=("cpu", "int8")),
        patch.object(fake_fw, "WhisperModel", return_value=mock_model),
    ):
        transcribe_task.main()
    ...
```

Note: `patch.object(fake_fw, "WhisperModel", return_value=mock_model)` is
used rather than assigning directly so that the stub is torn down after
each test.

---

## File Map

| File | Change |
|------|--------|
| `src/worker.py` | Add `proc.poll()` guard in `except queue.Empty` |
| `tests/test_worker_crash_detection.py` | New — 2 tests covering the WER hang fix |
| `tests/test_transcribe_file_progress.py` | Replace `patch("faster_whisper.WhisperModel")` with sys.modules injection |

---

## Testing Strategy

### New file: `tests/test_worker_crash_detection.py`

#### Test 1 — Worker emits fatal_error when subprocess dies with non-zero exit code

Construct a fake subprocess that writes nothing to stdout and exits with code
`-1073741819` (0xC0000005, the Windows access violation SEH code). Verify
`fatal_error` signal is emitted (not `all_done` silently).

#### Test 2 — Worker does not hang when subprocess exits without closing stdout (WER scenario)

Construct a fake subprocess that exits immediately but whose stdout pipe
remains technically open (simulated with a pipe that is readable but contains
no data and whose write end is held open by a sentinel thread to simulate WER).
Verify that after the subprocess exits (`proc.poll() != None`), the worker
breaks out of the event loop within a short timeout (e.g., 2 seconds), not
after waiting indefinitely.

Implementation note: use `unittest.mock.MagicMock` to stub the `Popen` object.
Control `proc.poll()` return value and `stdout` line iteration independently.

### Modified file: `tests/test_transcribe_file_progress.py`

All 5 existing tests must pass after the sys.modules injection change. No new
tests needed — the existing 5 tests already cover the correct behaviour; the
only change is the patching mechanism.

---

## Acceptance Criteria

1. `pytest tests/test_worker_crash_detection.py` — 2 new tests green.
2. `pytest tests/test_transcribe_file_progress.py` — all 5 existing tests green
   (was: 5 failures / pytest process crash).
3. `pytest tests/` — no regressions in any other test.
4. `src/worker.py` contains a `proc.poll() is not None` check inside the
   `except queue.Empty` handler.
5. `tests/test_transcribe_file_progress.py` does NOT contain
   `patch("faster_whisper.WhisperModel")` or
   `patch("src.transcribe_task.WhisperModel")`.
6. A manual smoke test: run the app, start a transcription (without diarization),
   then kill the Python subprocess from Task Manager. Verify that within ~2
   seconds the app shows a "Transcription process crashed" dialog rather than
   hanging indefinitely.

---

## Persona Impact

**Jordan:** Sees a clear error dialog ("Transcription process crashed") instead
of a frozen app that requires force-quitting. Knows to restart and try again.

**Alex:** Tests now pass on Windows without needing to skip or special-case the
faster_whisper test file. `pytest tests/` is green on both platforms.

---

## Sequencing

Can be implemented immediately — no dependencies on any other open plan.
Plan 09 (pyannote Windows compat) is independent and awaiting human approval.
