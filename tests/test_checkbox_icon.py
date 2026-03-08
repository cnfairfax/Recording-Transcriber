"""Tests for Plan 04 — Checkbox Checkmark Icon.

Verifies that the STYLESHEET constant in src.main_window embeds a white SVG
checkmark inside the QCheckBox::indicator:checked rule, and that a QCheckBox
widget with that stylesheet applied behaves correctly.
"""

import re

import pytest
from PyQt6.QtWidgets import QApplication, QCheckBox

from src.main_window import STYLESHEET


# ---------------------------------------------------------------------------
# Test 1 — STYLESHEET contains an image: property in the checked block
# ---------------------------------------------------------------------------

def test_stylesheet_contains_image_property():
    """The QCheckBox::indicator:checked block must declare an image: property."""
    # Extract the QCheckBox::indicator:checked block.
    match = re.search(
        r"QCheckBox::indicator:checked\s*\{([^}]+)\}",
        STYLESHEET,
        re.DOTALL,
    )
    assert match is not None, "QCheckBox::indicator:checked block not found in STYLESHEET"
    block = match.group(1)
    assert "image:" in block, (
        "Expected 'image:' property inside QCheckBox::indicator:checked block, "
        f"but got:\n{block}"
    )


# ---------------------------------------------------------------------------
# Test 2 — The embedded SVG references a white stroke
# ---------------------------------------------------------------------------

def test_checkmark_references_white_stroke():
    """The SVG data URI inside STYLESHEET must contain stroke='white' or stroke=\"white\"."""
    has_white_stroke = (
        "stroke='white'" in STYLESHEET or 'stroke="white"' in STYLESHEET
    )
    assert has_white_stroke, (
        "Expected SVG embedded in STYLESHEET to contain stroke='white' or "
        'stroke="white" for the checkmark path, but it was not found.'
    )


# ---------------------------------------------------------------------------
# Test 3 — Applying the full STYLESHEET to a QCheckBox raises no exception
# ---------------------------------------------------------------------------

def test_stylesheet_applies_without_error(qtbot):
    """Instantiating a QCheckBox and applying STYLESHEET must not raise."""
    checkbox = QCheckBox("Test")
    qtbot.addWidget(checkbox)
    # Should not raise
    checkbox.setStyleSheet(STYLESHEET)
    checkbox.show()


# ---------------------------------------------------------------------------
# Test 4 — Checking and unchecking a QCheckBox toggles isChecked()
# ---------------------------------------------------------------------------

def test_checkbox_check_uncheck_toggle(qtbot):
    """setChecked(True) then setChecked(False) must correctly toggle isChecked()."""
    checkbox = QCheckBox("Toggle me")
    qtbot.addWidget(checkbox)
    checkbox.setStyleSheet(STYLESHEET)

    assert not checkbox.isChecked(), "Checkbox should start unchecked"

    checkbox.setChecked(True)
    assert checkbox.isChecked(), "Checkbox should be checked after setChecked(True)"

    checkbox.setChecked(False)
    assert not checkbox.isChecked(), "Checkbox should be unchecked after setChecked(False)"
