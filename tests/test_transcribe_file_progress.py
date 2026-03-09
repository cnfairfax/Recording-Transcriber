"""Tests for Plan 01 Task 01-01 — Per-File Transcription Progress Bar.

Verifies that transcribe_task.main() emits ``file_progress`` events
during transcription and that those events have the correct shape and
value semantics.
"""

from __future__ import annotations

import io
import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _make_segment(start: float, end: float, text: str = "hello"):
    """Return a minimal object that looks like a faster-whisper Segment."""
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.text = text
    return seg


# Three known segments whose endpoints we can reason about.
_SEGMENTS = [
    _make_segment(0.0, 3.0, "First"),
    _make_segment(3.0, 6.0, "Second"),
    _make_segment(6.0, 10.0, "Third"),
]
_DURATION = 10.0


def _make_info(duration=_DURATION):
    info = MagicMock()
    info.duration = duration
    return info


def _build_mock_model():
    """WhisperModel mock that yields _SEGMENTS and returns _make_info()."""
    model = MagicMock()
    model.transcribe.return_value = (iter(_SEGMENTS), _make_info())
    return model


def _job_json(tmp_path) -> str:
    """A minimal job JSON for a single dummy audio file."""
    audio = tmp_path / "test.wav"
    # Any non-empty file suffices: model.transcribe() is fully mocked, so the
    # file is never opened as audio — we only need a valid path that exists.
    audio.write_bytes(b"RIFF")          # minimal stub for os.path operations
    return json.dumps({
        "model_name": "tiny",
        "output_dir": str(tmp_path),
        "formats": ["txt"],
        "language": None,
        "file_paths": [str(audio)],
    })


def _run_main(job_json: str, mock_model) -> list[dict]:
    """
    Invoke transcribe_task.main() with *job_json* on stdin.

    Patches out:
    - WhisperModel construction → returns *mock_model*
    - detect_best_device → ("cpu", "int8")
    - sys.stdout → captured so we can parse JSON events

    Returns the list of parsed JSON event dicts emitted to stdout.
    """
    from src import transcribe_task  # local import so patch targets are correct

    captured = io.StringIO()

    with (
        patch("sys.stdin", io.StringIO(job_json)),
        patch("sys.stdout", captured),
        patch.object(transcribe_task, "detect_best_device", return_value=("cpu", "int8")),
        patch("faster_whisper.WhisperModel", return_value=mock_model),
    ):
        transcribe_task.main()

    events = []
    for line in captured.getvalue().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Test 1 — at least one file_progress event is emitted per file
# ---------------------------------------------------------------------------

def test_file_progress_emitted_at_least_once(tmp_path):
    """main() must emit at least one file_progress event for the processed file."""
    mock_model = _build_mock_model()
    events = _run_main(_job_json(tmp_path), mock_model)

    progress_events = [e for e in events if e.get("type") == "file_progress"]
    assert len(progress_events) >= 1, (
        "Expected at least one file_progress event but none were emitted.\n"
        f"All events: {events}"
    )


# ---------------------------------------------------------------------------
# Test 2 — every file_progress event has "path" and "percent" keys
# ---------------------------------------------------------------------------

def test_file_progress_has_path_and_percent(tmp_path):
    """Each file_progress event must contain 'path' and 'percent' keys."""
    mock_model = _build_mock_model()
    events = _run_main(_job_json(tmp_path), mock_model)

    progress_events = [e for e in events if e.get("type") == "file_progress"]
    assert progress_events, "No file_progress events were emitted."

    for evt in progress_events:
        assert "path" in evt, f"Missing 'path' key in event: {evt}"
        assert "percent" in evt, f"Missing 'percent' key in event: {evt}"


# ---------------------------------------------------------------------------
# Test 3 — percent values are monotonically non-decreasing and clamped to 100
# ---------------------------------------------------------------------------

def test_file_progress_percent_monotonic_and_clamped(tmp_path):
    """percent must be non-decreasing across events and never exceed 100.0."""
    mock_model = _build_mock_model()
    events = _run_main(_job_json(tmp_path), mock_model)

    progress_events = [e for e in events if e.get("type") == "file_progress"]
    assert progress_events, "No file_progress events were emitted."

    percents = [e["percent"] for e in progress_events]

    # Non-decreasing
    for i in range(1, len(percents)):
        assert percents[i] >= percents[i - 1], (
            f"percent is not non-decreasing at index {i}: {percents}"
        )

    # Clamped
    for p in percents:
        assert p <= 100.0, f"percent {p} exceeds 100.0"
        assert p >= 0.0, f"percent {p} is negative"


# ---------------------------------------------------------------------------
# Test 4 — None duration does not cause ZeroDivisionError; percent stays valid
# ---------------------------------------------------------------------------

def test_file_progress_none_duration_no_error(tmp_path):
    """When info.duration is None the loop must not raise and percent must be valid."""
    model = MagicMock()
    model.transcribe.return_value = (iter(_SEGMENTS), _make_info(duration=None))

    events = _run_main(_job_json(tmp_path), model)

    # No fatal event should have been emitted
    fatal_events = [e for e in events if e.get("type") == "fatal"]
    assert not fatal_events, f"Unexpected fatal event(s): {fatal_events}"

    progress_events = [e for e in events if e.get("type") == "file_progress"]
    assert progress_events, "No file_progress events were emitted."

    for evt in progress_events:
        assert 0.0 <= evt["percent"] <= 100.0, (
            f"percent out of valid range: {evt['percent']}"
        )


# ---------------------------------------------------------------------------
# Test 5 — accumulated segments list equals list(generator)
# ---------------------------------------------------------------------------

def test_segments_list_contains_all_segments(tmp_path):
    """The loop must collect every segment so downstream formatting is complete."""
    model = MagicMock()
    model.transcribe.return_value = (iter(_SEGMENTS), _make_info())

    events = _run_main(_job_json(tmp_path), model)

    # If all segments were collected, the file_done event must be present
    # (file_error would appear instead if _save_outputs received partial data).
    done_events = [e for e in events if e.get("type") == "file_done"]
    error_events = [e for e in events if e.get("type") == "file_error"]

    assert done_events, (
        "Expected a file_done event indicating all segments were processed.\n"
        f"Events: {events}"
    )
    assert not error_events, (
        f"Unexpected file_error event(s): {error_events}"
    )

    # Exactly 3 progress events — one per segment
    progress_events = [e for e in events if e.get("type") == "file_progress"]
    assert len(progress_events) == len(_SEGMENTS), (
        f"Expected {len(_SEGMENTS)} file_progress events (one per segment), "
        f"got {len(progress_events)}."
    )
