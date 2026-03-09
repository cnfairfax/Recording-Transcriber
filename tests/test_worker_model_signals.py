"""Tests for Plan 02 Task 02-02 — model_loading / model_loaded signals.

Verifies that TranscribeWorker correctly dispatches ``model_loading`` and
``model_loaded`` JSON events from the subprocess into the corresponding
PyQt signals.

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
        model_name="base",
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
    lines = [json.dumps(e) + "\n" for e in events]
    lines.append(json.dumps({"type": "all_done"}) + "\n")

    fake_proc = MagicMock()
    fake_proc.stdout = iter(lines)
    fake_proc.stderr = io.StringIO("")
    fake_proc.returncode = 0
    fake_proc.wait.return_value = 0
    fake_proc.stdin = MagicMock()

    with patch("subprocess.Popen", return_value=fake_proc):
        worker.run()


# ---------------------------------------------------------------------------
# Test 1 — model_loading signal emits the model name
# ---------------------------------------------------------------------------

def test_model_loading_emits_model_name(qtbot) -> None:
    """Feeding a model_loading event emits model_loading signal with 'base'."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.model_loading, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "model_loading", "model": "base"}],
        )

    assert blocker.args == ["base"]


# ---------------------------------------------------------------------------
# Test 2 — model_loaded signal emits the model name
# ---------------------------------------------------------------------------

def test_model_loaded_emits_model_name(qtbot) -> None:
    """Feeding a model_loaded event emits model_loaded signal with 'base'."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.model_loaded, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "model_loaded", "model": "base"}],
        )

    assert blocker.args == ["base"]


# ---------------------------------------------------------------------------
# Test 3 — missing "model" key defaults to "" rather than raising
# ---------------------------------------------------------------------------

def test_model_loading_missing_model_defaults_to_empty_string(qtbot) -> None:
    """A model_loading event without 'model' must emit an empty string, not raise."""
    worker = _make_worker()

    with qtbot.waitSignal(worker.model_loading, timeout=5_000) as blocker:
        _run_worker_with_events(
            worker,
            [{"type": "model_loading"}],
        )

    assert blocker.args == [""]
