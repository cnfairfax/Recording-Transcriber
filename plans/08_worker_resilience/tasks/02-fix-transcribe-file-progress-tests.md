# Task 08-02: Fix test_transcribe_file_progress — sys.modules Injection

- **Plan:** [plans/08_worker_resilience/08_worker_resilience.md](../08_worker_resilience.md)
- **Agent type:** Backend
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none (independent of 08-01)
- **Files to modify:** `tests/test_transcribe_file_progress.py`
- **Files to create:** none

---

## Context

Five tests in `test_transcribe_file_progress.py` currently crash the pytest
process with `OSError: [WinError 1114] A DLL initialization routine failed`.
The crash happens in `_run_main()`:

```python
with patch("faster_whisper.WhisperModel", return_value=mock_model):
    transcribe_task.main()
```

`unittest.mock.patch("faster_whisper.WhisperModel", ...)` resolves the dotted
string by importing `faster_whisper`. This triggers:

```
faster_whisper → ctranslate2 → ctranslate2.specs.model_spec (import torch) →
torch._load_dll_libraries() → DLL init failure (WinError 1114)
```

This is the same root cause as Plan 07, but on the test side. The fix is to
pre-inject a fake `faster_whisper` module into `sys.modules` BEFORE calling
`transcribe_task.main()`. Python's import machinery checks `sys.modules` first;
the real faster_whisper package is never loaded.

---

## What to Implement

### `tests/test_transcribe_file_progress.py` — replace `_run_main`

The ONLY function that needs to change is `_run_main`. All five tests call it
and nothing else needs to change.  

**Current `_run_main` (the problem):**
```python
def _run_main(job_json: str, mock_model) -> list[dict]:
    from src import transcribe_task

    captured = io.StringIO()

    with (
        patch("sys.stdin", io.StringIO(job_json)),
        patch("sys.stdout", captured),
        patch.object(transcribe_task, "detect_best_device", return_value=("cpu", "int8")),
        patch("faster_whisper.WhisperModel", return_value=mock_model),  # ← CRASH
    ):
        transcribe_task.main()

    events = []
    for line in captured.getvalue().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events
```

**Replacement `_run_main` (the fix):**
```python
def _run_main(job_json: str, mock_model) -> list[dict]:
    from src import transcribe_task

    # Pre-inject a stub module so transcribe_task.main()'s
    #   from faster_whisper import WhisperModel
    # never loads the real faster_whisper package.  Loading faster_whisper
    # triggers ctranslate2 → torch._load_dll_libraries() → WinError 1114
    # (DLL init failure) on Windows.  sys.modules is checked by the import
    # machinery before any real import is attempted.
    fake_fw = types.ModuleType("faster_whisper")
    fake_fw.WhisperModel = MagicMock(return_value=mock_model)

    captured = io.StringIO()
    with (
        patch.dict(sys.modules, {"faster_whisper": fake_fw}),
        patch("sys.stdin", io.StringIO(job_json)),
        patch("sys.stdout", captured),
        patch.object(transcribe_task, "detect_best_device",
                     return_value=("cpu", "int8")),
    ):
        transcribe_task.main()

    events = []
    for line in captured.getvalue().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events
```

### Verify imports at the top of the file

The fix requires `types` and `MagicMock` — both are already imported. Confirm
the file begins with:

```python
import types
from unittest.mock import MagicMock, patch
```

No new imports are needed. If either is missing, add it.

---

## TDD Note

The RED state already exists: running `pytest tests/test_transcribe_file_progress.py`
currently produces 5 failures (WinError 1114 / DLL init failure). The 5 existing
tests ARE the test suite for this fix. After applying the `_run_main` change,
all 5 must be GREEN.

There is no new production code to write — this is a test infrastructure fix.

---

## Acceptance Criteria

1. `pytest tests/test_transcribe_file_progress.py` — all 5 tests green.
2. `pytest tests/` — no regressions in any other test.
3. `_run_main` does NOT contain `patch("faster_whisper.WhisperModel")` or
   `patch("src.transcribe_task.WhisperModel")`.
4. `_run_main` uses `patch.dict(sys.modules, {"faster_whisper": ...})`.
5. The injected stub comment explains WHY `sys.modules` injection is used.

---

## Red-Flag Triggers

- Tests pass before the `_run_main` fix is applied → the test environment is
  not experiencing the Windows DLL issue; verify you're running on the correct
  platform/environment.
- Any of the 5 tests begin importing `faster_whisper` directly (not through
  `transcribe_task.main()`) → the injection won't intercept that; stop and
  escalate.
- `transcribe_task.py` is modified as part of this task → out of scope; stop.
  Only `tests/test_transcribe_file_progress.py` should be touched.
