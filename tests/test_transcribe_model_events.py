"""Tests for Plan 02 Task 02-01 — Model Loading Progress Indicator.

Verifies that transcribe_task.main() emits ``model_loading`` and
``model_loaded`` events at the correct positions in the event stream.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers (mirrors pattern in test_transcribe_file_progress.py)
# ---------------------------------------------------------------------------

def _make_segment(start: float, end: float, text: str = "hello"):
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.text = text
    return seg


_SEGMENTS = [_make_segment(0.0, 2.0, "Hello"), _make_segment(2.0, 4.0, "World")]
_DURATION = 4.0


def _make_info(duration=_DURATION):
    info = MagicMock()
    info.duration = duration
    return info


def _build_mock_model():
    model = MagicMock()
    model.transcribe.return_value = (iter(_SEGMENTS), _make_info())
    return model


def _job_json(tmp_path, model_name: str = "tiny") -> str:
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF")
    return json.dumps({
        "model_name": model_name,
        "output_dir": str(tmp_path),
        "formats": ["txt"],
        "language": None,
        "file_paths": [str(audio)],
    })


def _run_main(job_json: str, mock_model) -> list[dict]:
    """Run transcribe_task.main() with mocked WhisperModel; return parsed events."""
    import sys
    import types
    from src import transcribe_task

    # Build a stub faster_whisper module so the "from faster_whisper import
    # WhisperModel" inside main() resolves without the real package installed.
    mock_fw = types.ModuleType("faster_whisper")
    mock_fw.WhisperModel = MagicMock(return_value=mock_model)

    captured = io.StringIO()

    with (
        patch("sys.stdin", io.StringIO(job_json)),
        patch("sys.stdout", captured),
        patch.object(transcribe_task, "detect_best_device", return_value=("cpu", "int8")),
        patch.dict(sys.modules, {"faster_whisper": mock_fw}),
    ):
        transcribe_task.main()

    events = []
    for line in captured.getvalue().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Test 1 — model_loading appears before any file_started event
# ---------------------------------------------------------------------------

def test_model_loading_emitted_before_file_started(tmp_path):
    """A model_loading event must appear in the stream before any file_started event."""
    events = _run_main(_job_json(tmp_path), _build_mock_model())
    types = [e.get("type") for e in events]

    assert "model_loading" in types, (
        f"No model_loading event found.\nAll events: {events}"
    )

    loading_idx = types.index("model_loading")
    file_started_indices = [i for i, t in enumerate(types) if t == "file_started"]

    assert file_started_indices, (
        "No file_started event found — cannot verify ordering."
    )
    first_file_started = file_started_indices[0]

    assert loading_idx < first_file_started, (
        f"model_loading (index {loading_idx}) must come before "
        f"file_started (index {first_file_started}).\nTypes: {types}"
    )


# ---------------------------------------------------------------------------
# Test 2 — model_loaded appears after model_loading and before any file_done
# ---------------------------------------------------------------------------

def test_model_loaded_emitted_after_loading_before_file_done(tmp_path):
    """model_loaded must appear after model_loading and before any file_done event."""
    events = _run_main(_job_json(tmp_path), _build_mock_model())
    types = [e.get("type") for e in events]

    assert "model_loading" in types, f"No model_loading event.\nAll events: {events}"
    assert "model_loaded" in types, f"No model_loaded event.\nAll events: {events}"

    loading_idx = types.index("model_loading")
    loaded_idx = types.index("model_loaded")

    assert loaded_idx > loading_idx, (
        f"model_loaded (index {loaded_idx}) must come after "
        f"model_loading (index {loading_idx}).\nTypes: {types}"
    )

    file_done_indices = [i for i, t in enumerate(types) if t == "file_done"]
    assert file_done_indices, "No file_done event — cannot verify ordering."
    first_file_done = file_done_indices[0]

    assert loaded_idx < first_file_done, (
        f"model_loaded (index {loaded_idx}) must come before "
        f"file_done (index {first_file_done}).\nTypes: {types}"
    )


# ---------------------------------------------------------------------------
# Test 3 — both events carry the correct model name
# ---------------------------------------------------------------------------

def test_model_events_include_correct_model_name(tmp_path):
    """Both model_loading and model_loaded events must contain the job's model name."""
    model_name = "base.en"
    events = _run_main(_job_json(tmp_path, model_name=model_name), _build_mock_model())

    loading_events = [e for e in events if e.get("type") == "model_loading"]
    loaded_events = [e for e in events if e.get("type") == "model_loaded"]

    assert loading_events, f"No model_loading event.\nAll events: {events}"
    assert loaded_events, f"No model_loaded event.\nAll events: {events}"

    for evt in loading_events:
        assert "model" in evt, f"model_loading event missing 'model' key: {evt}"
        assert evt["model"] == model_name, (
            f"model_loading.model={evt['model']!r}, expected {model_name!r}"
        )

    for evt in loaded_events:
        assert "model" in evt, f"model_loaded event missing 'model' key: {evt}"
        assert evt["model"] == model_name, (
            f"model_loaded.model={evt['model']!r}, expected {model_name!r}"
        )
