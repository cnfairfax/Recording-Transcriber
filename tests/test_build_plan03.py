"""Tests for Plan 03 Task 03-05 — build artefacts."""
import importlib.util
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


def test_download_script_calls_snapshot_download():
    """Verify download script invokes snapshot_download for both expected repos."""
    import sys
    import types
    from unittest.mock import MagicMock, patch

    # Stub out huggingface_hub so the import inside main() succeeds
    mock_hub = types.ModuleType("huggingface_hub")
    mock_snapshot = MagicMock()
    mock_hub.snapshot_download = mock_snapshot

    script_path = str(REPO / "installer" / "download_pyannote_models.py")
    spec = importlib.util.spec_from_file_location("download_pyannote_models", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with patch.dict(sys.modules, {"huggingface_hub": mock_hub}):
        with patch("sys.argv", ["download_pyannote_models.py", "--token", "test-token"]):
            mod.main()

    assert mock_snapshot.call_count == 2
    called_repos = [call.kwargs.get("repo_id") or call.args[0] for call in mock_snapshot.call_args_list]
    assert "pyannote/speaker-diarization-3.1" in called_repos
    assert "pyannote/segmentation-3.0" in called_repos
    # Token must be forwarded
    for call in mock_snapshot.call_args_list:
        assert call.kwargs.get("token") == "test-token"


def test_third_party_licenses_exists():
    assert (REPO / "THIRD_PARTY_LICENSES.md").exists()


def test_third_party_licenses_contains_cnrs():
    content = (REPO / "THIRD_PARTY_LICENSES.md").read_text()
    assert "CNRS" in content
