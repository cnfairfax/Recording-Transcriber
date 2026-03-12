"""Background worker thread that drives faster-whisper transcription.

Transcription runs in a *child subprocess* (src/transcribe_task.py) rather
than directly in this QThread.  This isolates native crashes inside
ctranslate2 (access violations, SIGABRT, etc.) so they kill only the child
process instead of the entire GUI application.

Backend: faster-whisper (CTranslate2)
GPU support:
  - NVIDIA CUDA  via CTranslate2 CUDA device
  - Intel Arc    via OpenVINO (openvino package)
  - CPU fallback  always available
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import List, Set

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("transcriber")



# Path to the transcription subprocess script
_TASK_SCRIPT = str(Path(__file__).parent / "transcribe_task.py")

# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class TranscribeWorker(QThread):
    """Runs faster-whisper in a background QThread and emits progress signals."""

    file_started    = pyqtSignal(str)        # file_path
    file_done       = pyqtSignal(str)        # file_path
    file_error      = pyqtSignal(str, str)   # file_path, error message
    file_progress   = pyqtSignal(str, float) # file_path, percent 0–100
    log_message     = pyqtSignal(str)        # informational text for the log box
    fatal_error     = pyqtSignal(str)        # unrecoverable error  shown as a dialog
    all_done        = pyqtSignal()
    model_loading   = pyqtSignal(str)        # model_name — emitted when model load begins
    model_loaded    = pyqtSignal(str)        # model_name — emitted when model is ready

    def __init__(
        self,
        file_paths: List[str],
        model_name: str,
        output_dir: str,
        formats: Set[str],
        language: str | None = None,
        diarize: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.file_paths  = list(file_paths)
        self.model_name  = model_name
        self.output_dir  = output_dir
        self.formats     = formats
        self.language    = language or None
        self.diarize     = diarize
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Spawn transcribe_task.py as a subprocess and relay its events."""
        job = {
            "model_name": self.model_name,
            "output_dir": self.output_dir,
            "formats":    list(self.formats),
            "language":   self.language,
            "file_paths": self.file_paths,
            "diarize":    self.diarize,
        }
        job_json = json.dumps(job)

        log.debug("Spawning transcription subprocess: %s", _TASK_SCRIPT)
        try:
            proc = subprocess.Popen(
                [sys.executable, _TASK_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
        except Exception:
            msg = traceback.format_exc()
            log.critical("Failed to start transcription subprocess:\n%s", msg)
            self.fatal_error.emit(
                f"Could not launch the transcription process:\n\n{msg}"
            )
            self.all_done.emit()
            return

        # Send job to child via stdin
        try:
            proc.stdin.write(job_json)
            proc.stdin.close()
        except Exception:
            log.warning("Failed to write job to subprocess stdin", exc_info=True)

        # Read events from stdout via a background reader thread so that
        # _stop_requested is polled regularly even during long silent periods
        # (e.g. while the Whisper model is being loaded / downloaded).
        assert proc.stdout is not None
        _line_queue: queue.Queue[str | None] = queue.Queue()

        def _reader(stdout: object, q: queue.Queue[str | None]) -> None:
            try:
                for raw in stdout:  # type: ignore[union-attr]
                    q.put(raw)
            finally:
                q.put(None)  # sentinel — signals EOF

        _reader_thread = threading.Thread(
            target=_reader, args=(proc.stdout, _line_queue), daemon=True
        )
        _reader_thread.start()

        while True:
            # Poll for stop request between line reads (250 ms granularity)
            if self._stop_requested:
                log.debug("Stop requested; terminating subprocess.")
                proc.terminate()
                self.log_message.emit("Transcription cancelled by user.")
                break

            try:
                raw_line = _line_queue.get(timeout=0.25)
            except queue.Empty:
                # Guard against Windows Error Reporting (WER) holding the
                # subprocess handle alive after a crash.  WER keeps stdout open
                # while it collects a dump, preventing the reader thread from
                # delivering the EOF sentinel.  Polling the process here lets us
                # detect exit without waiting for WER.
                if proc.poll() is not None:
                    log.warning(
                        "Subprocess exited (code %s) without sending EOF; "
                        "breaking event loop.",
                        proc.returncode,
                    )
                    break
                continue

            if raw_line is None:  # EOF sentinel from _reader
                break

            line = raw_line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON output (e.g. native stderr bleed-through) – log it
                log.warning("Subprocess non-JSON output: %s", line)
                continue

            etype = event.get("type")
            if etype == "log":
                self.log_message.emit(event.get("msg", ""))
            elif etype == "file_started":
                self.file_started.emit(event["path"])
            elif etype == "file_done":
                self.file_done.emit(event["path"])
            elif etype == "file_error":
                self.file_error.emit(event["path"], event.get("error", ""))
            elif etype == "file_progress":
                raw_percent = event.get("percent", 0)
                try:
                    percent = float(raw_percent)
                except (TypeError, ValueError):
                    log.warning(
                        "Malformed 'file_progress' percent value %r in event: %s",
                        raw_percent,
                        event,
                    )
                    percent = 0.0
                self.file_progress.emit(
                    event.get("path", ""),
                    percent,
                )
            elif etype == "model_loading":
                self.model_loading.emit(event.get("model", ""))
            elif etype == "model_loaded":
                self.model_loaded.emit(event.get("model", ""))
            elif etype == "fatal":
                self.fatal_error.emit(event.get("msg", "Unknown fatal error"))
            elif etype == "all_done":
                break
            else:
                log.warning("Unknown event from subprocess: %s", event)

        proc.wait()
        exit_code = proc.returncode

        # Collect any stderr output and log it
        try:
            stderr_output = proc.stderr.read().strip()
            if stderr_output:
                log.error("Subprocess stderr:\n%s", stderr_output)
        except Exception:
            pass

        if exit_code not in (0, None) and not self._stop_requested:
            msg = (
                f"The transcription process crashed (exit code {exit_code}).\n\n"
                "This is usually caused by a native library crash (ctranslate2 / GPU driver).\n"
                "Check app_log.txt for a faulthandler traceback.\n\n"
                + (f"stderr:\n{stderr_output}" if stderr_output else "")
            ).strip()
            log.critical("Subprocess exited with code %d", exit_code)
            self.fatal_error.emit(msg)

        self.all_done.emit()
