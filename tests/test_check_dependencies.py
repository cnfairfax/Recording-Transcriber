"""Tests for Plan 07 Task 07-01 — fix Windows startup crash.

Verifies that _check_dependencies() uses importlib.util.find_spec instead of
a bare import, so that torch and ctranslate2 are never loaded in the GUI process.
"""
from __future__ import annotations

import importlib.util

import pytest
from PyQt6.QtWidgets import QMessageBox

from app import _check_dependencies


def test_returns_true_when_package_found(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert _check_dependencies() is True


def test_returns_false_and_shows_dialog_when_missing(monkeypatch, qtbot):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    calls = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: calls.append(args))

    result = _check_dependencies()

    assert result is False
    assert len(calls) == 1, f"Expected QMessageBox.critical called once, got {len(calls)}"
    assert "faster-whisper" in calls[0][2], (
        f"Expected 'faster-whisper' in dialog message, got: {calls[0][2]!r}"
    )


def test_find_spec_called_with_correct_name(monkeypatch):
    captured = []
    def fake_find_spec(name):
        captured.append(name)
        return object()
    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    _check_dependencies()
    assert captured == ["faster_whisper"]
