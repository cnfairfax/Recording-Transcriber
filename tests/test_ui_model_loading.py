"""Tests for Plan 02 Task 02-03 — Model Loading Progress Indicator.

Verifies that:
1. _on_model_loading puts the progress bar into indeterminate (pulsing) mode.
2. _on_model_loaded restores the progress bar to determinate 0-100 mode.
3. Status label shows the correct "Loading model '...'" text.
4. Status label shows the correct "Model '...' ready — transcribing…" text.
5. Empty model name falls back to generic text without quotes.
"""

from __future__ import annotations

import pytest

from src.main_window import MainWindow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(qtbot) -> MainWindow:
    """Create a MainWindow in a known baseline state for model loading tests."""
    window = MainWindow()
    qtbot.addWidget(window)
    # Put the progress bar into a normal determinate state as _start_transcription would
    window._progress_bar.setRange(0, 100)
    window._progress_bar.setValue(0)
    return window


# ---------------------------------------------------------------------------
# Test 1 — _on_model_loading sets progress bar to indeterminate mode
# ---------------------------------------------------------------------------

def test_model_loading_sets_indeterminate_mode(qtbot):
    """After _on_model_loading('base'), progress_bar min==0 and max==0 (indeterminate)."""
    window = _make_window(qtbot)
    window._on_model_loading("base")
    assert window._progress_bar.minimum() == 0, (
        f"Expected progress_bar.minimum() == 0, got {window._progress_bar.minimum()}"
    )
    assert window._progress_bar.maximum() == 0, (
        f"Expected progress_bar.maximum() == 0 (indeterminate), "
        f"got {window._progress_bar.maximum()}"
    )


# ---------------------------------------------------------------------------
# Test 2 — _on_model_loaded restores progress bar to determinate mode at 0
# ---------------------------------------------------------------------------

def test_model_loaded_restores_determinate_mode(qtbot):
    """After _on_model_loaded('base'), progress_bar.maximum() == 100 and value() == 0."""
    window = _make_window(qtbot)
    # First simulate the indeterminate state that precedes model_loaded
    window._progress_bar.setRange(0, 0)
    window._on_model_loaded("base")
    assert window._progress_bar.maximum() == 100, (
        f"Expected progress_bar.maximum() == 100 after model loaded, "
        f"got {window._progress_bar.maximum()}"
    )
    assert window._progress_bar.value() == 0, (
        f"Expected progress_bar.value() == 0 after model loaded, "
        f"got {window._progress_bar.value()}"
    )


# ---------------------------------------------------------------------------
# Test 3 — _on_model_loading updates status label
# ---------------------------------------------------------------------------

def test_model_loading_status_label(qtbot):
    """After _on_model_loading('base'), status label shows \"Loading model 'base'…\"."""
    window = _make_window(qtbot)
    window._on_model_loading("base")
    label_text = window._status_label.text()
    assert label_text == "Loading model 'base'…", (
        f"Expected \"Loading model 'base'…\", got: {label_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — _on_model_loaded updates status label with ready text
# ---------------------------------------------------------------------------

def test_model_loaded_status_label(qtbot):
    """After _on_model_loaded('base'), status label shows ready/transcribing message."""
    window = _make_window(qtbot)
    window._on_model_loaded("base")
    label_text = window._status_label.text()
    assert label_text == "Model 'base' ready — transcribing…", (
        f"Expected \"Model 'base' ready — transcribing…\", got: {label_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — _on_model_loading with empty model name uses generic fallback text
# ---------------------------------------------------------------------------

def test_model_loading_empty_name_fallback(qtbot):
    """After _on_model_loading(''), status label shows generic 'Loading model…'."""
    window = _make_window(qtbot)
    window._on_model_loading("")
    label_text = window._status_label.text()
    assert label_text == "Loading model…", (
        f"Expected \"Loading model…\" for empty name, got: {label_text!r}"
    )


def test_model_loading_whitespace_name_fallback(qtbot):
    """After _on_model_loading('  '), whitespace-only name also uses generic fallback."""
    window = _make_window(qtbot)
    window._on_model_loading("  ")
    label_text = window._status_label.text()
    assert label_text == "Loading model…", (
        f"Expected \"Loading model…\" for whitespace name, got: {label_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 6 — _on_model_loaded with empty model name uses generic fallback text
# ---------------------------------------------------------------------------

def test_model_loaded_empty_name_fallback(qtbot):
    """After _on_model_loaded(''), status label shows generic 'Model ready — transcribing…'."""
    window = _make_window(qtbot)
    window._on_model_loaded("")
    label_text = window._status_label.text()
    assert label_text == "Model ready — transcribing…", (
        f"Expected \"Model ready — transcribing…\" for empty name, got: {label_text!r}"
    )


def test_model_loaded_whitespace_name_fallback(qtbot):
    """After _on_model_loaded('  '), whitespace-only name also uses generic fallback."""
    window = _make_window(qtbot)
    window._on_model_loaded("  ")
    label_text = window._status_label.text()
    assert label_text == "Model ready — transcribing…", (
        f"Expected \"Model ready — transcribing…\" for whitespace name, got: {label_text!r}"
    )

