"""Tests for Plan 01 Task 01-02 — file_progress signal on TranscribeWorker.

Verifies that TranscribeWorker correctly dispatches ``file_progress`` JSON
events from the subprocess into the ``file_progress`` PyQt signal.

The subprocess is mocked so these tests are purely unit-level and never
touch faster-whisper or real audio files.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from src.worker import TranscribeWorker


# ---------------------------------------------------------------------------
# Helper: build a minimal TranscribeWorker with dummy arguments
# ---------------------------------------------------------------------------

def _make_worker() -> TranscribeWorker:
    """Return a TranscribeWorker instance with dummy (unused) parameters."""
    return TranscribeWorker(
        file_paths=["dummy.wav"],
        model_name="tiny",
        output_dir="/tmp",
        formats={"txt"},
        language=None,
    )


# ---------------------------------------------------------------------------
# Helper: run the worker's run() method with a fake subprocess that emits
#         a controlled sequence of JSON lines, then terminates cleanly.
# ---------------------------------------------------------------------------

def _run_worker_with_events(worker: TranscribeWorker, events: list[dict]) -> None:
    """
    Patch subprocess.Popen so the worker's run() loop sees *events* as
    stdout lines followed by an all_done event, then exits with code 0.

    The worker is run synchronously (run() is called directly, not via
    QThread.start()) because qtbot signal capture works on the calling
    thread in this pattern.
    """
    # Build the stdout lines the fake proc will yield
    lines = [json.dumps(e) + "\n" for e in events]
    # Always terminate cleanly so the worker doesn't emit an extra fatal_error
    lines.append(json.dumps({"type": "all_done"}) + "\n")

    fake_proc = MagicMock()
    fake_proc.stdout = iter(lines)
    fake_proc.stderr = io.StringIO("")       # no stderr content
    fake_proc.returncode = 0
    fake_proc.wait.return_value = 0
    fake_proc.stdin = MagicMock()

    with patch("subprocess.Popen", return_value=fake_proc):
        worker.run()


# ---------------------------------------------------------------------------
# Test 1 — correct path and percent are emitted for a well-formed event
# ---------------------------------------------------------------------------

def test_file_progress_emits_correct_args(qtbot) -> None:
    """Feeding a well-formed file_progress event emits signal with the right args."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.file_progress, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "file_progress", "path": "a.wav", "percent": 42.7}],
        )

    assert blocker.args == ["a.wav", 42.7]


# ---------------------------------------------------------------------------
# Test 2 — missing "percent" key defaults to 0.0 without raising
# ---------------------------------------------------------------------------

def test_file_progress_missing_percent_defaults_to_zero(qtbot) -> None:
    """A file_progress event without 'percent' must default to 0.0."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.file_progress, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "file_progress", "path": "b.wav"}],
        )

    path, percent = blocker.args
    assert path == "b.wav"
    assert percent == 0.0


# ---------------------------------------------------------------------------
# Test 3 — missing "path" key defaults to "" without raising
# ---------------------------------------------------------------------------

def test_file_progress_missing_path_defaults_to_empty_string(qtbot) -> None:
    """A file_progress event without 'path' must default to an empty string."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.file_progress, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "file_progress", "percent": 55.0}],
        )

    path, percent = blocker.args
    assert path == ""
    assert percent == 55.0


# ---------------------------------------------------------------------------
# Test 4 — integer percent is cast to float
# ---------------------------------------------------------------------------

def test_file_progress_integer_percent_cast_to_float(qtbot) -> None:
    """An integer 'percent' value (e.g. 42) must be emitted as float 42.0."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.file_progress, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "file_progress", "path": "c.wav", "percent": 42}],
        )

    path, percent = blocker.args
    assert path == "c.wav"
    assert isinstance(percent, float)
    assert percent == 42.0
