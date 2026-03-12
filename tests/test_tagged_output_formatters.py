"""Tests for Plan 03 Task 03-03 — tagged-segment output formatters."""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

import pytest

from src.transcribe_task import (
    _build_speaker_map,
    _save_outputs,
    _to_srt,
    _to_vtt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(start: float = 0.0, end: float = 3.0, text: str = "Hello world"):
    return SimpleNamespace(start=start, end=end, text=text)


# ---------------------------------------------------------------------------
# _build_speaker_map
# ---------------------------------------------------------------------------

def test_build_speaker_map_basic():
    """Two distinct speaker labels are mapped to Speaker 1 and Speaker 2."""
    seg1 = _seg(0.0, 1.0, "Hi")
    seg2 = _seg(1.0, 2.0, "There")
    tagged = [(seg1, "SPEAKER_00"), (seg2, "SPEAKER_01")]

    speaker_map = _build_speaker_map(tagged)

    assert speaker_map["SPEAKER_00"] == "Speaker 1"
    assert speaker_map["SPEAKER_01"] == "Speaker 2"
    assert len(speaker_map) == 2


def test_build_speaker_map_none_speaker_excluded():
    """None speaker values are NOT added to the map."""
    seg = _seg()
    tagged = [(seg, None)]

    speaker_map = _build_speaker_map(tagged)

    assert speaker_map == {}


# ---------------------------------------------------------------------------
# _to_srt
# ---------------------------------------------------------------------------

def test_to_srt_with_speaker_label():
    """SRT output includes [Speaker 1] prefix when speaker is set."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, "SPEAKER_00")]

    result = _to_srt(tagged)

    assert "[Speaker 1]" in result
    assert "Hello world" in result
    assert "00:00:00,000 --> 00:00:03,000" in result


def test_to_srt_no_speaker_label_when_none():
    """SRT output has no [Speaker prefix when speaker is None."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, None)]

    result = _to_srt(tagged)

    assert "[Speaker" not in result
    assert "Hello world" in result


# ---------------------------------------------------------------------------
# _to_vtt
# ---------------------------------------------------------------------------

def test_to_vtt_with_speaker_label():
    """VTT output includes [Speaker 1] prefix when speaker is set."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, "SPEAKER_00")]

    result = _to_vtt(tagged)

    assert result.startswith("WEBVTT")
    assert "[Speaker 1]" in result
    assert "Hello world" in result
    assert "00:00:00.000 --> 00:00:03.000" in result


def test_to_vtt_no_speaker_label_when_none():
    """VTT output has no label when speaker is None."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, None)]

    result = _to_vtt(tagged)

    assert result.startswith("WEBVTT")
    assert "[Speaker" not in result
    assert "Hello world" in result


# ---------------------------------------------------------------------------
# _save_outputs
# ---------------------------------------------------------------------------

def test_save_outputs_txt_with_speaker():
    """Written .txt file contains [Speaker 1] prefix when speaker is set."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, "SPEAKER_00")]

    with tempfile.TemporaryDirectory() as out_dir:
        _save_outputs("/fake/audio.wav", tagged, out_dir, ["txt"])
        txt_path = os.path.join(out_dir, "audio.txt")
        assert os.path.exists(txt_path)
        with open(txt_path, encoding="utf-8") as fh:
            content = fh.read()
        assert "[Speaker 1]" in content
        assert "Hello world" in content


def test_save_outputs_txt_no_speaker_when_none():
    """Written .txt file has no [Speaker prefix when speaker is None."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, None)]

    with tempfile.TemporaryDirectory() as out_dir:
        _save_outputs("/fake/audio.wav", tagged, out_dir, ["txt"])
        txt_path = os.path.join(out_dir, "audio.txt")
        with open(txt_path, encoding="utf-8") as fh:
            content = fh.read()
        assert "[Speaker" not in content
        assert "Hello world" in content


def test_save_outputs_srt_with_speaker():
    """Written .srt file contains [Speaker 1] when speaker is set."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, "SPEAKER_00")]

    with tempfile.TemporaryDirectory() as out_dir:
        _save_outputs("/fake/audio.wav", tagged, out_dir, ["srt"])
        srt_path = os.path.join(out_dir, "audio.srt")
        assert os.path.exists(srt_path)
        with open(srt_path, encoding="utf-8") as fh:
            content = fh.read()
        assert "[Speaker 1]" in content
        assert "Hello world" in content


def test_save_outputs_vtt_with_speaker():
    """Written .vtt file contains [Speaker 1] when speaker is set."""
    seg = _seg(0.0, 3.0, "Hello world")
    tagged = [(seg, "SPEAKER_00")]

    with tempfile.TemporaryDirectory() as out_dir:
        _save_outputs("/fake/audio.wav", tagged, out_dir, ["vtt"])
        vtt_path = os.path.join(out_dir, "audio.vtt")
        assert os.path.exists(vtt_path)
        with open(vtt_path, encoding="utf-8") as fh:
            content = fh.read()
        assert content.startswith("WEBVTT")
        assert "[Speaker 1]" in content
        assert "Hello world" in content
