"""Tests for Plan 03 Task 03-05 — build artefacts."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_requirements_contains_torch():
    content = (REPO / "requirements.txt").read_text()
    assert "torch>=" in content


def test_requirements_contains_torchaudio():
    content = (REPO / "requirements.txt").read_text()
    assert "torchaudio>=" in content


def test_requirements_contains_pyannote():
    content = (REPO / "requirements.txt").read_text()
    assert "pyannote.audio>=" in content


def test_spec_contains_pyannote_models():
    content = (REPO / "installer" / "recording_transcriber.spec").read_text()
    assert "models/pyannote" in content


def test_download_script_exists():
    assert (REPO / "installer" / "download_pyannote_models.py").exists()


def test_download_script_is_valid_python():
    import ast
    src = (REPO / "installer" / "download_pyannote_models.py").read_text()
    ast.parse(src)  # raises SyntaxError if invalid


def test_third_party_licenses_exists():
    assert (REPO / "THIRD_PARTY_LICENSES.md").exists()


def test_third_party_licenses_contains_cnrs():
    content = (REPO / "THIRD_PARTY_LICENSES.md").read_text()
    assert "CNRS" in content
