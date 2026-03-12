# Plan 07 — Fix Windows Startup Crash (torch/ctranslate2 in GUI Process)

## Status
Complete

---

## Goal

Prevent the application from crashing with a **Windows fatal exception: access
violation** at startup on Windows machines where `torch` ≥ 2.0 and
`ctranslate2` ≥ 4.0 are installed as part of the Plan 03 diarization
feature.

---

## Root Cause Analysis

### Crash chain

```
app.py:_check_dependencies()
  → import faster_whisper          ← line 16
  → faster_whisper/__init__.py     ← triggers ctranslate2 import
  → ctranslate2/__init__.py:58     ← from .converters import …
  → ctranslate2/specs/model_spec.py:18  ← import torch  ← NEW in ct2 v4.x
  → torch/__init__.py:280          ← module-level side effects
  → torch/__init__.py:256          ← _load_dll_libraries()
  → ACCESS VIOLATION
```

### Why ctranslate2 v4 is different from v3

ctranslate2 **v3.x** did not import `torch` unconditionally; it was an
optional extra used only when converting Hugging Face model weights. In
ctranslate2 **v4.x** the `specs/model_spec.py` module was refactored and now
does `import torch` at the top of the file. This executes every time any part
of `ctranslate2` is imported — including the simple existence check in
`_check_dependencies`.

ctranslate2 v4.x entered the dependency graph via Plan 03 (`pyannote.audio`
implies `torch ≥ 2.0`; `pip` resolved `ctranslate2 4.7.1` to satisfy that).

### Why torch crashes on Windows but not Linux

`torch/__init__.py` contains a Windows-only helper `_load_dll_libraries()`
(line 256 in the installed version) that manually locates and loads MSVC and
CUDA runtime DLLs. It does this by scanning `PATH` entries and calling
`os.add_dll_directory()`. Under some Windows runtime environments (e.g. when
launched from a fresh terminal, an IDE, or the PyInstaller-bundled exe), a DLL
path entry is `None` or points to a directory that does not exist yet, causing
an access violation inside the Win32 `AddDllDirectory` API. On Linux and macOS
the equivalent `_load_dll_libraries` path is never executed (shared objects are
resolved by `ld.so` at link time, not by Python code), so the Linux CI and dev
machines never hit this branch.

### Why `try/except` cannot catch it

A Windows fatal exception is a **structured exception (SEH)** raised asynchronously
at the native/OS level when the process tries to read or write an unmapped memory
page. Python's `try/except Exception` only catches Python-level exceptions; it has
no visibility into native SEH faults. The fault terminates the process immediately,
bypassing all Python exception handlers.

### Why the existing architecture does not protect us here

The subprocess isolation design in `src/transcribe_task.py` was built precisely
to contain this class of native crash: if ctranslate2 or torch crashes inside
the child process, only the child dies and the GUI keeps running. However,
`app.py:_check_dependencies()` **imports faster-whisper in the main GUI process
before any window is shown**, defeating that isolation entirely.

---

## Technical Approach

### Change 1 — `app.py`: replace `import` with `importlib.util.find_spec`

`importlib.util.find_spec(name)` locates a package on `sys.path` and returns
its `ModuleSpec` (or `None`) **without executing the package's `__init__.py`**.
Because the problematic code is inside `torch/__init__.py`, never running the
module avoids the crash entirely.

**Before (`app.py` lines 12–35):**
```python
def _check_dependencies() -> bool:
    """Return True if faster-whisper is importable, else show a helpful error."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Missing dependency",
            "faster-whisper is not installed.\n\n"
            "Run the following and restart the app:\n\n"
            "    pip install faster-whisper openvino",
        )
        return False
    except Exception as exc:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Dependency error",
            f"Failed to import faster-whisper:\n\n{exc}\n\n"
            "Try:  pip install --force-reinstall faster-whisper",
        )
        return False
```

**After:**
```python
import importlib.util

def _check_dependencies() -> bool:
    """Return True if faster-whisper is installed, else show a helpful error.

    Uses importlib.util.find_spec instead of a bare import so that the GUI
    process never loads torch or ctranslate2.  Those libraries contain Windows-
    only native code (torch._load_dll_libraries) that causes a fatal access
    violation under some Windows runtime environments.  All heavy ML imports
    happen exclusively inside the transcription subprocess (src/transcribe_task.py),
    which is designed to absorb native crashes without taking down the GUI.
    """
    if importlib.util.find_spec("faster_whisper") is not None:
        return True

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(
        None,
        "Missing dependency",
        "faster-whisper is not installed.\n\n"
        "Run the following and restart the app:\n\n"
        "    pip install faster-whisper openvino",
    )
    return False
```

**Rationale for removing the generic `except Exception` branch:**
The only failure mode `find_spec` can raise is an internal Python error (not
an `ImportError` from native code), so the broad exception handler is no longer
needed. If `find_spec` itself raises for some exotic reason, the unhandled
exception will surface in the log via `faulthandler`, which is the right
behaviour (it means the Python environment is broken in an unusual way).

### Change 2 — no changes to `src/transcribe_task.py` or `src/worker.py`

The subprocess already imports `faster_whisper`, `ctranslate2`, and
`pyannote.audio` lazily when transcription starts. The isolation architecture
is already correct; this plan only removes the inadvertent eager import in the
main process.

---

## File Map

| File | Change |
|------|--------|
| `app.py` | Replace `import faster_whisper` with `importlib.util.find_spec("faster_whisper")` |
| `tests/test_check_dependencies.py` | New test file (3 test cases — see Testing Strategy) |

No other files are modified.

---

## Dependency and Compatibility Impact

| Dependency | Impact |
|------------|--------|
| `importlib.util` | Standard library, no new install required |
| `faster-whisper` | Check is now presence-only (find_spec), not import. Behaviour-equivalent: if the package is missing, user sees the same error dialog. |
| `ctranslate2` / `torch` | Never imported in the GUI process — this is the entire point of the fix. |
| PyInstaller build | No impact. `importlib.util` is always bundled. `find_spec` works correctly inside PyInstaller bundles as long as the package is included in the spec. |

---

## Edge Cases

| Scenario | Behaviour before fix | Behaviour after fix |
|----------|---------------------|---------------------|
| `faster-whisper` not installed | `ImportError` caught, error dialog shown | `find_spec` returns `None`, same error dialog shown |
| `faster-whisper` installed but ctranslate2 DLL missing | Native crash (access violation) at startup | GUI launches. Error surfaces during the first transcription attempt inside the subprocess, reported via `fatal_error` signal. User sees an error in the log box instead of a silent crash. |
| ctranslate2 v3 (no torch import) | Would not crash, but check still defeats subprocess isolation | Fixed — no meaningful regression |
| PyInstaller bundle on Windows | Same crash path as dev run | Fixed — GUI launches without importing torch |
| `faster-whisper` installed but corrupt | `find_spec` returns a spec (package is present), GUI launches. Corruption surfaces in the subprocess on first use. | Acceptable: the subprocess error path already handles `fatal` events. |

---

## Testing Strategy

New file: `tests/test_check_dependencies.py`

All three tests mock `importlib.util.find_spec` so no ML package needs to be
importable in the test environment.

### Test 1 — returns `True` when faster-whisper is found
```python
def test_returns_true_when_package_found(monkeypatch, qtbot):
    monkeypatch.setattr("importlib.util.find_spec", lambda name: object())
    assert _check_dependencies() is True
```

### Test 2 — returns `False` and shows dialog when faster-whisper is missing
```python
def test_returns_false_and_shows_dialog_when_missing(monkeypatch, qtbot):
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    with patch("app.QMessageBox.critical") as mock_dialog:
        result = _check_dependencies()
    assert result is False
    mock_dialog.assert_called_once()
    args = mock_dialog.call_args[0]
    assert "faster-whisper" in args[2]   # message text
```

### Test 3 — `find_spec` is called with the correct package name
```python
def test_find_spec_called_with_correct_name(monkeypatch, qtbot):
    captured = []
    def fake_find_spec(name):
        captured.append(name)
        return object()
    monkeypatch.setattr("importlib.util.find_spec", fake_find_spec)
    _check_dependencies()
    assert captured == ["faster_whisper"]
```

---

## Persona Impact Assessment

### Jordan (non-technical end user)
- **Before:** App crashes silently on every launch. No error dialog, no log message
  visible to the user. Jordan thinks the app is broken and cannot self-diagnose.
- **After:** App opens normally. If `faster-whisper` is missing (install-from-source
  scenario), Jordan sees the same friendly "Missing dependency" dialog as before.
  The UX is strictly better — the common path (installed via the installer) now
  works, and the error path is unchanged.

### Alex (technically proficient power user)
- **Before:** Alex notices the access violation in `app_log.txt` but cannot work
  around it without patching the source. On Windows, the app is completely unusable
  after Plan 03.
- **After:** App starts cleanly. Alex gets the full feature set including diarization.
  Errors from the subprocess (e.g. missing CUDA DLLs, corrupt model files) are now
  surfaced through the established `fatal_error` signal path rather than silently
  killing the process.

---

## Sequencing Note

This plan is a **blocking P0 fix** — the application cannot be launched at all on
Windows after Plan 03. It should be implemented and merged before any further
Windows testing or feature work. Plan 06 (new-folder crash fix) can be parallelised
but depends on the GUI actually launching, so this fix should land first or
concurrently.

---

## Out of Scope

- Investigating and fixing the underlying `torch._load_dll_libraries` Windows bug.
  That is an upstream PyTorch issue; the correct long-term fix is a PyTorch
  patch, not something we own.
- Pinning `ctranslate2 < 4` to avoid the eager torch import. Pinning a transitive
  dependency to an older major version introduces its own forward-compatibility
  risk and should be a last resort. The `find_spec` approach is more robust and
  does not restrict future dependency upgrades.
- Verifying torch CUDA DLL resolution on Windows. If a user's Windows CUDA
  installation is broken, the subprocess crash path already handles this gracefully.
