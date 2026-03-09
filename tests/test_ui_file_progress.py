"""Tests for Plan 01 Task 01-03 — Two-Tier Progress Bar and _on_file_progress Slot.

Verifies that:
1. _on_file_progress updates the progress bar value to int(round(percent)).
2. _on_file_progress keeps the progress bar in determinate 0-100 mode.
3. _on_file_progress updates the status label to include the percentage.
4. _on_file_done resets the progress bar to 0 for the next file.
5. _on_file_started resets the progress bar to 0 in 0-100 range.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem

from src.main_window import MainWindow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(qtbot) -> MainWindow:
    """Create a MainWindow with a minimal pre-populated state for progress tests."""
    window = MainWindow()
    qtbot.addWidget(window)
    # Pre-set progress state so tests don't depend on _start_transcription
    window._progress_bar_total = 3
    window._file_statuses = {
        "a.wav": "transcribing",
        "b.wav": "queued",
        "c.wav": "queued",
    }
    # Progress bar in 0-100 range (as _start_transcription will configure it)
    window._progress_bar.setRange(0, 100)
    window._progress_bar.setValue(0)
    return window


# ---------------------------------------------------------------------------
# Test 1 — _on_file_progress sets the progress bar value to int(percent)
# ---------------------------------------------------------------------------

def test_file_progress_sets_bar_value(qtbot):
    """After _on_file_progress('a.wav', 42.7), progress_bar.value() == 43 (rounded)."""
    window = _make_window(qtbot)
    window._on_file_progress("a.wav", 42.7)
    assert window._progress_bar.value() == 43, (
        f"Expected progress_bar.value() == 43, got {window._progress_bar.value()}"
    )


# ---------------------------------------------------------------------------
# Test 2 — _on_file_progress keeps the progress bar in determinate 0-100 mode
# ---------------------------------------------------------------------------

def test_file_progress_bar_is_determinate(qtbot):
    """After _on_file_progress('a.wav', 42.7), progress_bar.maximum() == 100."""
    window = _make_window(qtbot)
    window._on_file_progress("a.wav", 42.7)
    assert window._progress_bar.maximum() == 100, (
        f"Expected progress_bar.maximum() == 100, got {window._progress_bar.maximum()}"
    )


# ---------------------------------------------------------------------------
# Test 3 — _on_file_progress updates status label with percentage text
# ---------------------------------------------------------------------------

def test_file_progress_status_label_contains_percent(qtbot):
    """After _on_file_progress('a.wav', 42.0), status label must show 'File N / M — 42%'."""
    window = _make_window(qtbot)
    window._on_file_progress("a.wav", 42.0)
    label_text = window._status_label.text()
    assert "42%" in label_text, (
        f"Expected '42%' in status label text, got: {label_text!r}"
    )
    # Verify the full format: "File N / M  —  P%"
    assert "File" in label_text, (
        f"Expected 'File' in status label text, got: {label_text!r}"
    )
    assert "/ 3" in label_text, (
        f"Expected '/ 3' (total) in status label text, got: {label_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — _on_file_done resets progress bar to 0 for the next file
# ---------------------------------------------------------------------------

def test_file_done_resets_progress_bar(qtbot):
    """After _on_file_done('a.wav'), progress_bar.value() == 0 (reset for next file)."""
    window = _make_window(qtbot)
    # Simulate bar mid-progress before the file finishes
    window._progress_bar.setValue(75)
    # Mark the file as done in statuses so _update_item_status works correctly
    # (add a matching list item so _update_item_status can find it)
    item = QListWidgetItem("a.wav")
    item.setData(Qt.ItemDataRole.UserRole, "a.wav")
    window._file_list.addItem(item)

    window._on_file_done("a.wav")
    assert window._progress_bar.value() == 0, (
        f"Expected progress_bar.value() == 0 after file done, "
        f"got {window._progress_bar.value()}"
    )


# ---------------------------------------------------------------------------
# Test 5 — _on_file_started resets progress bar to 0 in 0-100 range
# ---------------------------------------------------------------------------

def test_file_started_resets_progress_bar(qtbot):
    """After _on_file_started('a.wav'), progress_bar.value() == 0 and maximum() == 100."""
    window = _make_window(qtbot)
    # Simulate bar mid-progress before next file starts
    window._progress_bar.setValue(55)

    item = QListWidgetItem("a.wav")
    item.setData(Qt.ItemDataRole.UserRole, "a.wav")
    window._file_list.addItem(item)

    window._on_file_started("a.wav")
    assert window._progress_bar.value() == 0, (
        f"Expected progress_bar.value() == 0 after file started, "
        f"got {window._progress_bar.value()}"
    )
    assert window._progress_bar.maximum() == 100, (
        f"Expected progress_bar.maximum() == 100 after file started, "
        f"got {window._progress_bar.maximum()}"
    )
