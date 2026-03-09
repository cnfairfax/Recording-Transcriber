"""Tests for Plan 03 Task 03-01 — diarize flag plumbed through TranscribeWorker.

Verifies that:
  1. TranscribeWorker accepts a ``diarize`` kwarg (default False).
  2. The JSON job written to the subprocess stdin always contains a
     ``"diarize"`` key.
  3. The value matches what was passed to the constructor (True or False).

The subprocess is mocked so these tests never touch faster-whisper or real
audio files.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

from src.worker import TranscribeWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_worker(diarize: bool = False) -> TranscribeWorker:
    """Return a TranscribeWorker with dummy parameters and the given diarize flag."""
    return TranscribeWorker(
        file_paths=["dummy.wav"],
        model_name="tiny",
        output_dir="/tmp",
        formats={"txt"},
        language=None,
        diarize=diarize,
    )


def _capture_job_json(worker: TranscribeWorker) -> dict:
    """Run worker.run() with a mocked subprocess and return the parsed job JSON."""
    # The subprocess emits only an all_done event so run() exits immediately.
    lines = [json.dumps({"type": "all_done"}) + "\n"]

    fake_proc = MagicMock()
    fake_proc.stdout = iter(lines)
    fake_proc.stderr = io.StringIO("")
    fake_proc.returncode = 0
    fake_proc.wait.return_value = 0

    captured_json: list[str] = []
    fake_proc.stdin = MagicMock()
    fake_proc.stdin.write.side_effect = lambda s: captured_json.append(s)

    with patch("subprocess.Popen", return_value=fake_proc):
        worker.run()

    assert captured_json, "No job JSON was written to stdin"
    return json.loads(captured_json[0])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_diarize_true_in_job_json() -> None:
    """When diarize=True, the JSON sent to stdin has "diarize": true."""
    worker = _make_worker(diarize=True)
    job = _capture_job_json(worker)
    assert job["diarize"] is True


def test_diarize_false_default_in_job_json() -> None:
    """When diarize=False (default), the JSON sent to stdin has "diarize": false."""
    worker = _make_worker(diarize=False)
    job = _capture_job_json(worker)
    assert job["diarize"] is False


def test_diarize_key_always_present() -> None:
    """The 'diarize' key is present in the job JSON for both True and False."""
    for flag in (True, False):
        worker = _make_worker(diarize=flag)
        job = _capture_job_json(worker)
        assert "diarize" in job, f"'diarize' key missing from job JSON when diarize={flag}"
