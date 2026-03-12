# Task 07-01: Replace `import faster_whisper` with `importlib.util.find_spec`

- **Plan:** [plans/07_fix_windows_startup_crash/07_fix_windows_startup_crash.md](../07_fix_windows_startup_crash.md)
- **Agent type:** Backend
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none
- **Files to modify:** `app.py`
- **Files to create:** `tests/test_check_dependencies.py`

---

## Context

`app.py:_check_dependencies()` currently checks for `faster_whisper` by running
`import faster_whisper`. On Windows with ctranslate2 ≥ 4.0, that import triggers the
chain `ctranslate2 → specs/model_spec.py → import torch → _load_dll_libraries()`,
which causes a Windows fatal SEH exception (access violation) before any window is
shown. The exception is not catchable by Python `try/except`.

The subprocess isolation architecture (`src/transcribe_task.py`) was designed to
absorb exactly this class of native crash — but only works if the main GUI process
never loads these libraries. This task restores that guarantee by replacing the bare
`import` with `importlib.util.find_spec`, which locates a package without executing
any of its code.

---

## What to Implement

### `app.py` — replace `_check_dependencies`

1. Add `import importlib.util` to the top-level imports.
2. Rewrite `_check_dependencies` to use `importlib.util.find_spec("faster_whisper")`
   instead of `import faster_whisper`.
3. Remove the generic `except Exception` branch — it is no longer needed because
   `find_spec` does not execute native code and cannot raise a Windows fatal exception.
4. Preserve the `except ImportError` / missing-package dialog behaviour: when
   `find_spec` returns `None`, show exactly the same `QMessageBox.critical` with the
   same title and message text as before.
5. Add a docstring explaining *why* `find_spec` is used instead of a bare import
   (reference the Windows torch `_load_dll_libraries` crash and subprocess isolation).

**Exact before/after is specified in the plan's "Technical Approach" section.**

Key contract: `_check_dependencies()` must remain a module-level callable that
returns `bool`. Its external signature does not change.

---

## Tests to Write

File: `tests/test_check_dependencies.py`

All three tests must mock `importlib.util.find_spec` so the test suite runs in
environments where `faster_whisper`, `ctranslate2`, and `torch` may not be installed.

### Test file preamble

```python
from __future__ import annotations

import importlib.util

import pytest
from PyQt6.QtWidgets import QMessageBox

from app import _check_dependencies
```

Notes:
- `_check_dependencies` is imported at module level, consistent with all other test
  files in the project. `app.py` at module level only calls `configure_logging()`,
  which is safe to run during test collection.
- All mocking uses only `monkeypatch` — do not mix in `unittest.mock.patch`.
- The 3-argument form `monkeypatch.setattr(obj, "attr", value)` must be used,
  not the 2-argument string form, so the target is unambiguous.

### Test 1 — returns `True` when the package is found

`find_spec` returns a non-`None` object → `_check_dependencies()` returns `True`
and no dialog is shown.

```python
def test_returns_true_when_package_found(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert _check_dependencies() is True
```

### Test 2 — returns `False` and shows a dialog when the package is missing

`find_spec` returns `None` → `_check_dependencies()` returns `False` and calls
`QMessageBox.critical` exactly once with a message containing `"faster-whisper"`.

`qtbot` is required so that pytest-qt's QApplication is active before
`_check_dependencies` runs; otherwise `QApplication.instance()` returns `None` and
`QApplication(sys.argv)` inside the function tries to create a second instance,
which can fail in headless CI.

```python
def test_returns_false_and_shows_dialog_when_missing(monkeypatch, qtbot):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    calls = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: calls.append(args))

    result = _check_dependencies()

    assert result is False
    assert len(calls) == 1, f"Expected QMessageBox.critical called once, got {len(calls)}"
    assert "faster-whisper" in calls[0][2], (
        f"Expected 'faster-whisper' in dialog message, got: {calls[0][2]!r}"
    )
```

### Test 3 — `find_spec` is invoked with the correct package name

`find_spec` must be called with `"faster_whisper"` (underscore, not hyphen).

```python
def test_find_spec_called_with_correct_name(monkeypatch):
    captured = []
    def fake_find_spec(name):
        captured.append(name)
        return object()
    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    _check_dependencies()
    assert captured == ["faster_whisper"]
```

---

## Acceptance Criteria

1. `pytest tests/test_check_dependencies.py` passes with all 3 tests green.
2. `pytest tests/` passes with no regressions in any pre-existing test.
3. `app.py` no longer contains `import faster_whisper` anywhere (bare or inside
   `_check_dependencies`).
4. `importlib.util.find_spec` is used in `_check_dependencies`.
5. The missing-package `QMessageBox.critical` dialog is still shown (same title and
   message text) when `find_spec` returns `None`.
6. The generic `except Exception` branch is removed.
7. `_check_dependencies` has a docstring that mentions the Windows crash reason.
8. Running `python app.py` on a Windows machine with `faster_whisper` installed
   must open the main window without any access violation in the log.

---

## Red-Flag Triggers

- Any import of `faster_whisper`, `ctranslate2`, or `torch` inside `app.py` after
  this change → stop and escalate. Those libraries must only load inside the
  subprocess.
- Test 1 or Test 3 passing without mocking `find_spec` → test isolation is broken,
  stop and fix the mock before proceeding.
- Existing tests in `tests/test_transcribe_model_events.py`,
  `tests/test_worker_file_progress_signal.py`, or `tests/test_worker_model_signals.py`
  start failing → the worker/subprocess contract has been accidentally modified, stop
  and escalate.
- `_check_dependencies` signature changes (return type, parameter list) → this
  breaks `main()` in `app.py`; stop and restore the original signature.
