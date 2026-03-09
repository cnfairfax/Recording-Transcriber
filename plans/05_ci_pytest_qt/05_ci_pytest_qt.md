# Plan 05 — GitHub Actions CI for pytest-qt

## Goal

Provide a reliable, repeatable test environment in GitHub Actions so that cloud agents
can execute the full pytest suite — including pytest-qt widget tests — without
platform-initialization failures.

## Problem Statement

Cloud agents consistently fail to run pytest-qt tests due to three compounding issues:

| # | Problem | Root cause |
|---|---------|-----------|
| 1 | `pytest-qt` not installed | Neither `pytest` nor `pytest-qt` appear in `requirements.txt`. Agents installing from that file cannot use the `qtbot` fixture. |
| 2 | No canonical CI workflow | `.github/workflows/` does not exist. Agents have no reference for how to configure the test environment. |
| 3 | Qt6 xcb plugin crash on headless Linux | `ubuntu-latest` runners lack `libxcb-cursor0`, `libegl1`, and related libraries that Qt6 probes at import time — before `conftest.py` can set `QT_QPA_PLATFORM`. |

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dev-dep location | New `requirements-dev.txt` | Keeps production install (Jordan's installer) slim; signals to Alex that these are dev-only |
| Runner OS | `ubuntu-latest` only | Fast, cheap; headless Qt works well with apt packages; matches cloud agent environments |
| QPA platform | `offscreen` set at job env level | Ensures the variable is in the process environment before any Python import, not just before test collection |

---

## Deliverables

### 1. `requirements-dev.txt` (new file)

```
# Development and test dependencies only.
# Install with: pip install -r requirements-dev.txt
# (Also requires the production deps: pip install -r requirements.txt)

pytest>=7.4.0
pytest-qt>=4.4.0
```

No changes to `requirements.txt`.

### 2. `.github/workflows/ci.yml` (new file)

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  test:
    name: pytest (ubuntu-latest)
    runs-on: ubuntu-latest

    env:
      QT_QPA_PLATFORM: offscreen   # Must be set before Python import, not just in conftest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Qt system dependencies
        run: |
          sudo apt-get update -y
          sudo apt-get install -y \
            libxcb-cursor0 \
            libxcb-xinerama0 \
            libxkbcommon-x11-0 \
            libxcb-icccm4 \
            libxcb-image0 \
            libxcb-keysyms1 \
            libxcb-randr0 \
            libxcb-render-util0 \
            libxcb-shape0 \
            libxcb-xfixes0 \
            libegl1 \
            libgl1

      - name: Install Python dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v
```

### 3. `conftest.py` — scope expansion (modify existing file)

The existing guard only triggers on Linux when `DISPLAY`/`WAYLAND_DISPLAY` is absent.
The workflow sets `QT_QPA_PLATFORM` at the job level, so `conftest.py` becomes a safety
net for local developer machines only. No change strictly required, but tightening it is
good hygiene:

```python
"""Root pytest configuration.

Sets QT_QPA_PLATFORM=offscreen when no display is available so that
PyQt6 widget tests can run in headless CI environments.

Note: In GitHub Actions this variable is set at the job level (ci.yml),
so this block primarily protects local developer environments.
"""

import os
import sys

if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM"):
    has_display = bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )
    if not has_display:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
```

The logic is unchanged; the comment is updated to document the CI relationship.

---

## Dependency & Compatibility Impact

| Concern | Assessment |
|---------|-----------|
| `pytest-qt>=4.4.0` compatible with `PyQt6>=6.4.0` | Yes — pytest-qt 4.x supports PyQt6 via the `qt_api` auto-detection |
| No new runtime deps | `requirements-dev.txt` is never installed in Jordan's installer (PyInstaller reads `requirements.txt` only) |
| `ubuntu-latest` Qt6 xcb deps | The `apt-get` list above covers all plugins Qt6 probes in offscreen mode |
| Python version on runner | `3.11` matches the installer spec; lock to exact minor, not just `3.x`, to avoid surprise ABI changes |

---

## Edge Cases

| Case | Handling |
|------|---------|
| Agent forgets to install `requirements-dev.txt` | `pytest` itself won't be found; error is obvious |
| `faster-whisper` / `openvino` install fails on runner | These are not needed by any test; if install is slow, consider `--no-deps` or stubbing |
| Qt6 version mismatch (`PyQt6>=6.4.0` range) | Pin to a narrow range in `requirements.txt` if a new Qt6 release breaks xcb offscreen — but leave range open for now |
| `libxcb-cursor0` unavailable on older Ubuntu | Only an issue pre-22.04; `ubuntu-latest` is currently 24.04 |

---

## Testing Strategy

This plan has no unit tests (it is infrastructure). Acceptance criteria are:

- [ ] `pytest tests/ -v` passes in a fresh GitHub Actions run with no manual intervention
- [ ] No `qt.qpa.plugin` errors in CI logs
- [ ] `requirements.txt` is unchanged (Jordan's installer is unaffected)
- [ ] `pip install -r requirements.txt && pip install -r requirements-dev.txt && pytest tests/ -v` works locally on a clean venv

---

## Persona Impact

**Jordan** — No impact. `requirements-dev.txt` never enters the installer. The CI
workflow is invisible to end users. Zero risk.

**Alex** — Direct benefit. `pip install -r requirements-dev.txt` gives a clear, documented
path to a working test environment. The CI badge on the README (future) gives confidence
that the main branch is always green.

---

## Sequencing

This plan is infrastructure and is independent of all feature plans (01–04). It can be
delivered in parallel or before any outstanding plan without risk of rework.

---

## Tasks

| Task file | Description |
|-----------|-------------|
| `tasks/01-requirements-dev.md` | Create `requirements-dev.txt` |
| `tasks/02-ci-workflow.md` | Create `.github/workflows/ci.yml` |
| `tasks/03-update-conftest.md` | Update comment in `conftest.py` |
