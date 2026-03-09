"""Tests for Plan 04 — Checkbox Checkmark Icon.

Verifies that the STYLESHEET constant in src.main_window includes an image:
property in the QCheckBox::indicator:checked rule, that the programmatic
checkmark helper creates the expected PNG file, and that a QCheckBox widget
with the resolved stylesheet applied behaves correctly.
"""

import os
import re

import pytest
from PyQt6.QtWidgets import QCheckBox

from src.main_window import STYLESHEET, _create_check_icon


# ---------------------------------------------------------------------------
# Test 1 — STYLESHEET template contains an image: property in the checked block
# ---------------------------------------------------------------------------

def test_stylesheet_contains_image_property():
    """The QCheckBox::indicator:checked block must declare an image: property."""
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
# Test 2 — _create_check_icon writes a file named rt_check.png
# ---------------------------------------------------------------------------

def test_create_check_icon_writes_rt_check_png(qapp):
    """_create_check_icon() must return a path ending in rt_check.png and create the file."""
    path = _create_check_icon()
    assert path.endswith("rt_check.png"), (
        f"Expected _create_check_icon() to return a path ending in 'rt_check.png', got: {path}"
    )
    assert os.path.isfile(path), f"Expected file to exist at {path!r} but it was not found."


# ---------------------------------------------------------------------------
# Test 3 — Applying the resolved stylesheet to a QCheckBox raises no exception
# ---------------------------------------------------------------------------

def test_stylesheet_applies_without_error(qtbot):
    """Instantiating a QCheckBox with the resolved (icon-injected) stylesheet must not raise."""
    resolved = STYLESHEET.replace("_CHECK_ICON_PATH_", _create_check_icon())
    checkbox = QCheckBox("Test")
    qtbot.addWidget(checkbox)
    checkbox.setStyleSheet(resolved)
    checkbox.show()


# ---------------------------------------------------------------------------
# Test 4 — Checking and unchecking a QCheckBox toggles isChecked()
# ---------------------------------------------------------------------------

def test_checkbox_check_uncheck_toggle(qtbot):
    """setChecked(True) then setChecked(False) must correctly toggle isChecked()."""
    resolved = STYLESHEET.replace("_CHECK_ICON_PATH_", _create_check_icon())
    checkbox = QCheckBox("Toggle me")
    qtbot.addWidget(checkbox)
    checkbox.setStyleSheet(resolved)

    assert not checkbox.isChecked(), "Checkbox should start unchecked"

    checkbox.setChecked(True)
    assert checkbox.isChecked(), "Checkbox should be checked after setChecked(True)"

    checkbox.setChecked(False)
    assert not checkbox.isChecked(), "Checkbox should be unchecked after setChecked(False)"
