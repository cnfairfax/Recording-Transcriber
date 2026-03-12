# Plan 09 — Pyannote Windows Compatibility (Dependency Pin + Model Setup)

## Status
⚠️ PENDING HUMAN APPROVAL — Dependency pin required (AGENT_CONSTITUTION §2)

---

## Goal

Get speaker diarization actually working on a Windows development machine so
that `diarize=True` produces speaker-labelled transcripts rather than silently
falling back to no labels.

---

## Root Cause

### pyannote.audio 4.x requires torchcodec, which requires FFmpeg DLLs

`requirements.txt` specifies `pyannote.audio>=3.1`. pip resolved this to
`4.0.4` (the latest). pyannote.audio 4.0 replaced the soundfile/torchaudio
audio I/O backend with `torchcodec`, which requires a "full-shared" FFmpeg
installation with DLL files on Windows. Without FFmpeg DLLs, the pipeline
import emits:

```
UserWarning: torchcodec is not installed correctly so built-in audio
decoding will fail.
```

and then crashes when `pipeline(audio_path)` tries to decode the audio file.

### pyannote models are not present

`models/pyannote/speaker-diarization-3.1/` does not exist in the workspace.
The existing `installer/download_pyannote_models.py` script handles the
download, but it requires a HuggingFace token and has not been run on this
machine. Without models, `_load_diarization_pipeline()` raises
`FileNotFoundError`, which is caught and logged, but diarization silently
degrades to no speaker labels with no UI feedback to the user.

---

## Proposed Fix

### Part A — Pin `pyannote.audio` to `<4.0` (requires approval)

In `requirements.txt`, change:

```
pyannote.audio>=3.1
```

to:

```
# Pin <4.0: pyannote 4.x requires torchcodec (FFmpeg DLLs) on Windows.
# pyannote 3.x uses soundfile/torchaudio which work with the Windows
# CPU torch build without additional system dependencies.
pyannote.audio>=3.1,<4.0
```

pip will install `3.4.0` (the latest 3.x). This eliminates the torchcodec
requirement entirely. soundfile and torchaudio (already required) handle
WAV and MP3 decoding on Windows.

**This is the architectural decision requiring approval.** Options considered:

| Option | Pro | Con |
|--------|-----|-----|
| **Pin `<4.0`** (recommended) | No FFmpeg system dep; works on stock Windows install | Stays on older pyannote; may miss future 4.x improvements |
| Pin `==4.0.4` + bundle FFmpeg DLLs | Latest pyannote features | Adds ~30 MB of DLLs to installer; FFmpeg licence compliance effort |
| Drop pyannote requirement altogether | Simplifies deps | Removes speaker diarization — unacceptable |

### Part B — Developer setup documentation update

Add a clear "First-time diarization setup" section to `README.md` explaining:
1. You need a HuggingFace account and token
2. Accept the model licence at huggingface.co/pyannote/speaker-diarization-3.1
3. Run `python installer/download_pyannote_models.py --token YOUR_HF_TOKEN`
4. Models will appear in `models/pyannote/` and are .gitignored

### Part C — Improve diarization-degraded UX

When diarization fails (any reason), the current code emits a `_log(...)` message
that appears in the log pane. For Jordan (non-technical), this message is easy
to miss. Plan 09 should also:
- Emit a `file_error`-level visual cue (or at least a more prominent log line)
  when diarization fails on a file that was requested with `diarize=True`
- Include actionable advice in the message (e.g. "Download diarization models;
  see README for setup instructions")

---

## Decisions Required from Human

1. **Approve pyannote.audio pin to `<4.0`?** (recommended default: Yes)
2. **Accept the UX change for diarization-degraded messaging?** This changes
   what text appears in the log pane when diarization is requested but fails.
   (AGENT_CONSTITUTION §2 — UX wording change requires approval)

---

## Files Affected (pending approval)

| File | Change |
|------|--------|
| `requirements.txt` | Pin `pyannote.audio>=3.1,<4.0` |
| `README.md` | Add diarization first-time setup section |
| `src/transcribe_task.py` | Improve diarization-degraded log/error message |
| `tests/test_diarization_helpers.py` | Verify improved message text |

---

## Sequencing

Depends on: none (independent of Plans 07 and 08)
Blocks: nothing

Human approval of the pyannote pin must be obtained before any agent touches
`requirements.txt`.
