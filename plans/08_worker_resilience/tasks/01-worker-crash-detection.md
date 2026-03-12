# Task 08-01: Fix Worker WER Hang — proc.poll() Guard in Event Loop

- **Plan:** [plans/08_worker_resilience/08_worker_resilience.md](../08_worker_resilience.md)
- **Agent type:** Backend
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none
- **Files to modify:** `src/worker.py`
- **Files to create:** `tests/test_worker_crash_detection.py`

---

## Context

`TranscribeWorker.run()` in `src/worker.py` event-loops on a queue fed by a
reader thread. When the subprocess crashes on Windows, the Windows Error
Reporting (WER) service may hold the process handle alive for an extended
period while collecting a dump. During this time:
- `proc.stdout` remains technically open (the process handle has not been
  released)
- The reader thread blocks on `for raw in stdout`
- The sentinel `None` is never placed on the queue
- The main loop spins on `queue.Empty` for as long as WER holds the process

The fix is one line: inside `except queue.Empty`, call `proc.poll()` and
break out of the loop if the process has already exited. The existing exit-code
check and `fatal_error` emission below the loop already handle crash reporting
correctly; this task just makes the loop exit promptly.

---

## What to Implement

### `src/worker.py` — add `proc.poll()` guard

Locate the `except queue.Empty: continue` block (currently the only statement
after the `except` is `continue`). Replace it with:

```python
            except queue.Empty:
                # Guard against Windows Error Reporting (WER) holding the
                # subprocess handle alive after a crash.  WER keeps stdout
                # open while it collects a dump, preventing the reader thread
                # from delivering the EOF sentinel.  Polling the process here
                # lets us detect exit without waiting for WER to finish.
                if proc.poll() is not None:
                    log.warning(
                        "Subprocess exited (code %s) without sending EOF; "
                        "breaking event loop.",
                        proc.returncode,
                    )
                    break
                continue
```

No other changes to `worker.py`. The existing code that follows the loop
(`proc.wait()`, exit-code check, `fatal_error` emission, `all_done`) is already
correct and handles the crash reporting.

---

## Tests to Write

File: `tests/test_worker_crash_detection.py`

```python
"""Tests for Plan 08 Task 08-01 — Worker WER hang fix.

Verifies that TranscribeWorker does not hang indefinitely when the subprocess
crashes and Windows Error Reporting (WER) holds the process handle open.
"""
from __future__ import annotations
```

### Preamble imports

```python
from __future__ import annotations

import io
import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QCoreApplication

from src.worker import TranscribeWorker
```

### Helper — build a fake Popen object

The fake process:
- Has a stdout that never yields any lines (simulates WER holding the pipe open)
- Has `poll()` that returns `None` for the first few calls, then returns
  the crash exit code (`-1073741819` = `0xC0000005` = Windows access violation)
- Has `returncode` attribute set to `-1073741819`
- Has `stderr.read()` returning `""`

```python
def _make_crashing_proc(exit_code: int = -1073741819, poll_delay: int = 2):
    """
    A fake Popen object whose process exits after poll_delay calls to poll().
    stdout never yields lines (WER holds pipe open).
    """
    proc = MagicMock()
    proc.returncode = exit_code

    # stdout that blocks indefinitely (like a pipe held open by WER)
    _block_queue: queue.Queue = queue.Queue()
    def _stdout_iter():
        # Block until released (never, in the WER scenario)
        _block_queue.get()
        return iter([])

    proc.stdout = MagicMock()
    proc.stdout.__iter__ = lambda self: _stdout_iter()

    # poll() returns None for first `poll_delay` calls, then exit_code
    _call_count = [0]
    def _poll():
        _call_count[0] += 1
        if _call_count[0] <= poll_delay:
            return None
        return exit_code

    proc.poll = _poll
    proc.wait = MagicMock(return_value=exit_code)
    proc.terminate = MagicMock()
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.close = MagicMock()
    proc.stderr = MagicMock()
    proc.stderr.read = MagicMock(return_value="")
    return proc
```

### Test 1 — Worker breaks out of event loop when subprocess exits (WER scenario)

Verify that `TranscribeWorker.run()` finishes within 2 seconds when the
subprocess has exited but stdout is held open.

```python
def test_worker_exits_when_subprocess_dies_with_open_stdout(qtbot):
    worker = TranscribeWorker(
        file_paths=["dummy.wav"],
        model_name="tiny",
        output_dir="",
        formats={"txt"},
    )
    fatal_messages = []
    worker.fatal_error.connect(lambda msg: fatal_messages.append(msg))

    fake_proc = _make_crashing_proc(exit_code=-1073741819, poll_delay=2)

    completed = threading.Event()
    original_run = worker.run

    def patched_run():
        original_run()
        completed.set()

    worker.run = patched_run

    with patch("src.worker.subprocess.Popen", return_value=fake_proc):
        thread = threading.Thread(target=worker.run)
        thread.daemon = True
        thread.start()
        finished = thread.join(timeout=5.0)

    assert not thread.is_alive(), (
        "Worker thread did not finish within 5 s — "
        "likely stuck in event loop due to WER holding stdout open."
    )
```

### Test 2 — Worker emits fatal_error on non-zero exit code

Verify that when the subprocess exits with a non-zero code, `fatal_error` is
emitted with a message containing the exit code.

```python
def test_worker_emits_fatal_error_on_crash_exit_code(qtbot):
    worker = TranscribeWorker(
        file_paths=["dummy.wav"],
        model_name="tiny",
        output_dir="",
        formats={"txt"},
    )
    fatal_messages = []
    worker.fatal_error.connect(lambda msg: fatal_messages.append(msg))

    fake_proc = _make_crashing_proc(exit_code=-1073741819, poll_delay=1)

    with patch("src.worker.subprocess.Popen", return_value=fake_proc):
        thread = threading.Thread(target=worker.run)
        thread.daemon = True
        thread.start()
        thread.join(timeout=5.0)

    assert fatal_messages, (
        "Expected fatal_error to be emitted when subprocess exits non-zero, "
        "but no fatal_error signals were received."
    )
    assert any("-1073741819" in msg or "crashed" in msg.lower()
               for msg in fatal_messages), (
        f"Expected crash message to mention exit code, got: {fatal_messages}"
    )
```

---

## Acceptance Criteria

1. `pytest tests/test_worker_crash_detection.py` — 2 tests green.
2. `pytest tests/` — no regressions in any pre-existing test.
3. `src/worker.py` contains `if proc.poll() is not None: break` inside the
   `except queue.Empty` handler.
4. The `except queue.Empty` block has a comment explaining the WER scenario.

---

## Red-Flag Triggers

- Tests pass without the `proc.poll()` fix being in place → mock is wrong,
  test is not actually verifying the fix. Stop and correct the mock.
- TranscribeWorker's `run()` signature or signal names modified → escalate.
- Any change to the subprocess spawn logic (Popen call, arguments, env) →
  escalate; this is an architecture decision.
