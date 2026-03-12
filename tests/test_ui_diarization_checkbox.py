"""Tests for Plan 03 Task 03-04 — Speaker Diarization Checkbox.

Verifies that:
1. MainWindow contains a QCheckBox with text "Speaker Diarization".
2. The checkbox is unchecked by default.
3. The checkbox has a non-empty tooltip.
4. When checked and transcription starts, TranscribeWorker is called with diarize=True.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QCheckBox

from src.main_window import MainWindow


# ---------------------------------------------------------------------------
# Test 1 — Checkbox exists with correct text
# ---------------------------------------------------------------------------

def test_diarization_checkbox_exists(qtbot):
    """MainWindow must expose a QCheckBox named _diarize_checkbox with text 'Speaker Diarization'."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert hasattr(win, "_diarize_checkbox"), (
        "MainWindow is missing attribute '_diarize_checkbox'"
    )
    assert isinstance(win._diarize_checkbox, QCheckBox), (
        f"Expected _diarize_checkbox to be a QCheckBox, got {type(win._diarize_checkbox)}"
    )
    assert win._diarize_checkbox.text() == "Speaker Diarization", (
        f"Expected checkbox text 'Speaker Diarization', got {win._diarize_checkbox.text()!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Checkbox is unchecked by default
# ---------------------------------------------------------------------------

def test_diarization_checkbox_unchecked_by_default(qtbot):
    """The Speaker Diarization checkbox must be unchecked when the window first opens."""
    win = MainWindow()
    qtbot.addWidget(win)

    assert not win._diarize_checkbox.isChecked(), (
        "Expected _diarize_checkbox to be unchecked by default"
    )


# ---------------------------------------------------------------------------
# Test 3 — Checkbox has a non-empty tooltip
# ---------------------------------------------------------------------------

def test_diarization_checkbox_has_tooltip(qtbot):
    """The Speaker Diarization checkbox must have a non-empty tooltip."""
    win = MainWindow()
    qtbot.addWidget(win)

    tooltip = win._diarize_checkbox.toolTip()
    assert tooltip, (
        "Expected _diarize_checkbox to have a non-empty tooltip"
    )


# ---------------------------------------------------------------------------
# Test 4 — Checkbox state is passed as diarize= to TranscribeWorker
# ---------------------------------------------------------------------------

def test_diarization_checkbox_passes_flag_to_worker(qtbot):
    """When the checkbox is checked and transcription starts, TranscribeWorker receives diarize=True."""
    win = MainWindow()
    qtbot.addWidget(win)

    # Add a dummy file so the queue is non-empty (use cross-platform temp dir)
    dummy_wav = os.path.join(tempfile.gettempdir(), "dummy.wav")
    win.add_files([dummy_wav])

    # Check the diarize checkbox
    win._diarize_checkbox.setChecked(True)

    with patch("src.main_window.TranscribeWorker") as MockWorker:
        # Build a mock instance whose signal attributes support .connect()
        mock_instance = MagicMock()
        for signal_name in (
            "file_started",
            "file_done",
            "file_error",
            "log_message",
            "fatal_error",
            "all_done",
            "file_progress",
            "model_loading",
            "model_loaded",
        ):
            signal_mock = MagicMock()
            signal_mock.connect = MagicMock()
            setattr(mock_instance, signal_name, signal_mock)
        mock_instance.start = MagicMock()
        MockWorker.return_value = mock_instance

        win._start_transcription()

        MockWorker.assert_called_once()
        _, kwargs = MockWorker.call_args
        assert kwargs.get("diarize") is True, (
            f"Expected TranscribeWorker to be called with diarize=True, got {kwargs!r}"
        )
