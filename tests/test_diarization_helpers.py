"""Tests for diarization helper functions in transcribe_task.py."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is importable even without an installed package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transcribe_task import (
    _assign_speakers,
    _load_diarization_pipeline,
    _pyannote_model_dir,
)


# ---------------------------------------------------------------------------
# 1. _pyannote_model_dir — dev mode
# ---------------------------------------------------------------------------

def test_pyannote_model_dir_dev_mode():
    """In a non-frozen process _pyannote_model_dir ends with models/pyannote."""
    # Make sure the frozen flag is absent (normal dev / CI run)
    assert not getattr(sys, "frozen", False), "Test must run outside a PyInstaller bundle"
    result = _pyannote_model_dir()
    assert isinstance(result, Path)
    # The last two components must be models/pyannote
    assert result.parts[-1] == "pyannote"
    assert result.parts[-2] == "models"


# ---------------------------------------------------------------------------
# 2. _load_diarization_pipeline — raises when model dir is missing
# ---------------------------------------------------------------------------

def test_load_diarization_pipeline_raises_when_missing():
    """_load_diarization_pipeline raises FileNotFoundError when the bundled
    model directory does not exist."""
    with patch("src.transcribe_task._pyannote_model_dir") as mock_dir:
        mock_path = MagicMock(spec=Path)
        # __truediv__ (/) must return the same mock so .exists() is reachable
        mock_path.__truediv__ = lambda self, other: mock_path
        mock_path.exists.return_value = False
        mock_dir.return_value = mock_path

        # Provide a stub for pyannote.audio so the import inside the function
        # does not fail due to the package being absent in CI.
        with patch.dict("sys.modules", {"pyannote.audio": MagicMock()}):
            with pytest.raises(FileNotFoundError):
                _load_diarization_pipeline()


# ---------------------------------------------------------------------------
# 3-5. _assign_speakers
# ---------------------------------------------------------------------------

def test_assign_speakers_correct_speaker():
    """Segment fully covered by a single turn gets that speaker label."""
    seg = SimpleNamespace(start=0.0, end=3.0)
    turns = [(0.0, 3.0, "SPEAKER_00")]
    result = _assign_speakers([seg], turns)
    assert len(result) == 1
    assert result[0] == (seg, "SPEAKER_00")


def test_assign_speakers_unknown_for_no_overlap():
    """Segment with no overlapping turns is labelled 'Unknown'."""
    seg = SimpleNamespace(start=10.0, end=12.0)
    turns = [(0.0, 5.0, "SPEAKER_00")]
    result = _assign_speakers([seg], turns)
    assert result[0][1] == "Unknown"


def test_assign_speakers_picks_greatest_overlap():
    """When multiple turns overlap a segment the one with the most overlap wins."""
    seg = SimpleNamespace(start=2.0, end=8.0)
    turns = [
        (0.0, 4.0, "SPEAKER_00"),   # overlap = 2 s  (2.0–4.0)
        (3.0, 9.0, "SPEAKER_01"),   # overlap = 5 s  (3.0–8.0)
    ]
    result = _assign_speakers([seg], turns)
    assert result[0][1] == "SPEAKER_01"
