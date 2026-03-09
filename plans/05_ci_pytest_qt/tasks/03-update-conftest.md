# Task 05-03: Update `conftest.py` Docstring

- **Plan:** [plans/05_ci_pytest_qt/05_ci_pytest_qt.md](../05_ci_pytest_qt.md)
- **Agent type:** Build
- **MAKER race:** No
- **Depends on:** 05-02 (the updated comment references `ci.yml`, which must exist)
- **Files to modify:** `conftest.py`
- **Files to create:** none

---

## What to Implement

Replace the module docstring in `conftest.py` only. The `if` block logic is **untouched**.

Old docstring:
```python
"""Root pytest configuration.

Sets QT_QPA_PLATFORM=offscreen when no display is available so that
PyQt6 widget tests can run in headless CI environments without a
physical or virtual display server.
"""
```

New docstring:
```python
"""Root pytest configuration.

Sets QT_QPA_PLATFORM=offscreen when running on Linux with no display,
so that PyQt6 widget tests can run in headless environments.

In GitHub Actions this variable is set at the job level in
.github/workflows/ci.yml (before any Python import), so this block
primarily acts as a safety net for local developer machines that
lack a display.
"""
```

---

## Tests to Write

Comment-only change — no new tests required. Re-run the full suite to confirm nothing regressed.

| # | Test | Red trigger |
|---|------|-------------|
| 1 | `pytest tests/ -v` passes without modification after the docstring change | Any test breaks post-edit |

---

## Acceptance Criteria

1. `conftest.py` docstring accurately documents that `QT_QPA_PLATFORM` is set at the CI job level in `.github/workflows/ci.yml`.
2. The `if sys.platform...` logic block is character-for-character identical to the original.
3. All pre-existing tests pass after the change.

---

## Red-Flag Triggers

- The `if` block logic has drifted from what `ci.yml` actually sets — reconcile before touching the comment.
