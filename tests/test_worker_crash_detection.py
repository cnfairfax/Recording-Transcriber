"""Tests for Worker crash detection (WER-hang fix).

Covers the guard in the ``except queue.Empty`` branch that polls
``proc.poll()`` so a crashed Windows subprocess doesn't hang the event loop
forever.
"""

import queue
import threading
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _make_fake_popen(poll_sequence):
    """Return a mock Popen whose ``poll()`` returns values from *poll_sequence*.

    After the sequence is exhausted every subsequent call returns the last
    value.  Example:
        [None, None, -1073741819]   → two "still running" calls then crash code
    """
    proc = MagicMock()
    proc.stdout = MagicMock()
    proc.stdin = MagicMock()
    proc.stderr = MagicMock()
    proc.stderr.read.return_value = ""

    side_effects = iter(poll_sequence)
    last = [None]

    def _poll():
        try:
            v = next(side_effects)
            last[0] = v
            return v
        except StopIteration:
            return last[0]

    proc.poll = MagicMock(side_effect=_poll)
    proc.returncode = poll_sequence[-1]
    return proc


def _make_always_empty_queue():
    """Return a mock queue whose ``get()`` always raises ``queue.Empty``."""
    q = MagicMock()
    q.get = MagicMock(side_effect=queue.Empty)
    return q


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWorkerCrashDetection:
    """TranscribeWorker exits the event loop when the subprocess crashes under WER."""

    def test_event_loop_exits_when_proc_crashes_without_eof(self, qtbot):
        """run() must break out of the event loop when proc.poll() is not None,
        even though the queue is always empty (simulating WER keeping stdout open).
        """
        from src.worker import TranscribeWorker

        always_empty = _make_always_empty_queue()

        # Process: alive twice, then crashes with Windows access-violation code
        proc = _make_fake_popen([None, None, -1073741819])

        worker = TranscribeWorker(
            file_paths=["/tmp/a.wav"],
            model_name="tiny",
            output_dir="/tmp",
            formats={"txt"},
            language="en",
            diarize=False,
        )

        result_holder = []

        def _run():
            try:
                worker.run()
                result_holder.append("ok")
            except Exception as exc:
                result_holder.append(exc)

        # Create t BEFORE patching so it uses the real threading.Thread
        t = threading.Thread(target=_run)

        with (
            patch("src.worker.subprocess.Popen", return_value=proc),
            patch("src.worker.queue.Queue", return_value=always_empty),
            # Do NOT patch threading.Thread; the reader thread iterates
            # proc.stdout (a MagicMock) which exhausts immediately, and calls
            # always_empty.put(None) which is a no-op — the sentinel is never
            # delivered, faithfully simulating WER holding stdout open.
        ):
            t.start()
            t.join(timeout=5)

        assert not t.is_alive(), (
            "worker.run() is still running after 5 s — WER hang bug not fixed "
            "(proc.poll() check missing from except queue.Empty branch)"
        )

    def test_event_loop_emits_fatal_error_on_crash(self, qtbot):
        """When the event loop breaks due to a crashed subprocess, a
        ``fatal_error`` signal must be emitted with a non-empty message.
        """
        from src.worker import TranscribeWorker

        always_empty = _make_always_empty_queue()

        # Process: alive once, then crashes
        proc = _make_fake_popen([None, -1073741819])

        worker = TranscribeWorker(
            file_paths=["/tmp/b.wav"],
            model_name="tiny",
            output_dir="/tmp",
            formats={"txt"},
            language="en",
            diarize=False,
        )

        emitted_errors = []
        # DirectConnection: slot runs in the emitting thread so the assertion
        # works without needing the main Qt event loop to process queued signals.
        worker.fatal_error.connect(
            lambda msg: emitted_errors.append(msg),
            Qt.ConnectionType.DirectConnection,
        )

        # Create t BEFORE patching so it uses the real threading.Thread
        t = threading.Thread(target=worker.run)

        with (
            patch("src.worker.subprocess.Popen", return_value=proc),
            patch("src.worker.queue.Queue", return_value=always_empty),
        ):
            t.start()
            t.join(timeout=5)

        assert not t.is_alive(), (
            "worker.run() hung — proc.poll() check missing from event loop"
        )
        assert emitted_errors, (
            "fatal_error signal was not emitted after subprocess crash"
        )
        assert emitted_errors[0], "fatal_error message must not be empty"
