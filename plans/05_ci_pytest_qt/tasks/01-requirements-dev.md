# Task 05-01: Create `requirements-dev.txt`

- **Plan:** [plans/05_ci_pytest_qt/05_ci_pytest_qt.md](../05_ci_pytest_qt.md)
- **Agent type:** Build
- **MAKER race:** No
- **Depends on:** none
- **Files to modify:** none
- **Files to create:** `requirements-dev.txt`

---

## What to Implement

Create `requirements-dev.txt` at the project root with `pytest` and `pytest-qt` as the sole contents. This file must **not** be referenced by `requirements.txt` or the PyInstaller spec — it is for developer/CI use only.

```
# Development and test dependencies only.
# Install with: pip install -r requirements-dev.txt
# (Also install production deps first: pip install -r requirements.txt)

pytest>=7.4.0
pytest-qt>=4.4.0
```

Do not touch `requirements.txt`.

---

## Tests to Write

This task produces a dependency manifest, not application code — no unit tests. The acceptance test is a full `pytest tests/ -v` run that passes after a clean install using both files.

---

## Acceptance Criteria

1. `requirements-dev.txt` exists at the project root.
2. It contains `pytest>=7.4.0` and `pytest-qt>=4.4.0`.
3. `requirements.txt` is **unchanged** (diff shows zero modifications).
4. Running `pip install -r requirements.txt && pip install -r requirements-dev.txt && pytest tests/ -v` on a clean virtualenv completes without errors.

---

## Red-Flag Triggers

- Any test in `tests/` requires a package not covered by `requirements.txt` or `requirements-dev.txt` — list it and escalate before adding it silently.
- `openvino` or `faster-whisper` fails to install in the target environment — do **not** stub or skip those installs; escalate.
