# Task 05-02: Create `.github/workflows/ci.yml`

- **Plan:** [plans/05_ci_pytest_qt/05_ci_pytest_qt.md](../05_ci_pytest_qt.md)
- **Agent type:** Build
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 05-01 (`requirements-dev.txt` must exist before this workflow can install from it)
- **Files to modify:** none
- **Files to create:** `.github/workflows/ci.yml`

---

## What to Implement

Create the GitHub Actions workflow file below. The three non-obvious requirements:

1. **`QT_QPA_PLATFORM: offscreen` at the job `env:` level** — not inside a `run:` step. Qt6 probes the platform during module import; the variable must already be set when the Python process starts.
2. **All twelve xcb/egl packages** in the `apt-get` list below — omitting any one of them can cause a silent Qt plugin failure even in offscreen mode.
3. **Both requirements files** installed in the `Install Python dependencies` step.

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
      QT_QPA_PLATFORM: offscreen

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

### Why each xcb package is required

| Package | Reason |
|---------|--------|
| `libxcb-cursor0` | Qt6 xcb plugin hard dependency — missing → plugin fails to load even in offscreen |
| `libxcb-xinerama0` | Multi-monitor screen detection |
| `libxkbcommon-x11-0` | Keyboard input backend |
| `libxcb-icccm4` | ICCCM window properties |
| `libxcb-image0` | Image transfer over xcb |
| `libxcb-keysyms1` | Key symbol mapping |
| `libxcb-randr0` | Screen resolution queries |
| `libxcb-render-util0` | Render extension utilities |
| `libxcb-shape0` | Window shape extension |
| `libxcb-xfixes0` | X Fixes extension |
| `libegl1` | EGL rendering backend |
| `libgl1` | OpenGL (mesa software rasterizer) |

---

## Tests to Write

This task produces CI infrastructure — no unit tests. The acceptance test is a passing GitHub Actions run.

---

## Acceptance Criteria

1. `.github/workflows/ci.yml` exists.
2. Workflow triggers on push to `main` and on all pull requests.
3. `QT_QPA_PLATFORM: offscreen` is present in the job-level `env:` block (not only in a step).
4. All twelve xcb/egl packages are present in the `apt-get install` list.
5. Both `requirements.txt` and `requirements-dev.txt` are installed in the same `pip install` step.
6. A real GitHub Actions run completes green with `pytest tests/ -v` and zero `qt.qpa.plugin` errors in the log.

---

## Red-Flag Triggers

- A `qt.qpa.plugin` or `xcb` error appears in CI logs despite the apt packages being installed — the package list may need updating for a new `ubuntu-latest` image; escalate rather than guessing.
- `pip install -r requirements.txt` fails in CI due to `openvino` or `faster-whisper` build errors — do not silently drop these from the install step; escalate.
- Python version `3.11` is no longer available on `ubuntu-latest` — update to the next stable minor and escalate so the installer spec is kept in sync.
