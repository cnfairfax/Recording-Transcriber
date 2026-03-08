# Task 03-03: Tagged-Segment Output Formatters + Diarization Integration

- **Plan:** [plans/03_speaker_diarization/03_speaker_diarization.md](../03_speaker_diarization.md)
- **Agent type:** ML/Audio
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 03-02 (requires `_diarize`, `_assign_speakers` to exist)
- **Prerequisite plan:** Plan 01 must be complete — the per-segment loop and `_to_srt` / `_to_vtt` / `_save_outputs` signatures are inherited from Plan 01
- **Files to modify:** `src/transcribe_task.py`
- **Files to create:** `tests/test_tagged_output_formatters.py`

---

## What to Implement

### 1. `_build_speaker_map(tagged_segments) -> dict`
Maps raw pyannote labels to friendly numbered names:
```python
def _build_speaker_map(tagged_segments):
    speaker_map = {}
    counter = 1
    for _, speaker in tagged_segments:
        if speaker and speaker not in speaker_map:
            speaker_map[speaker] = f"Speaker {counter}"
            counter += 1
    return speaker_map
```

### 2. Update `_to_srt` signature
Change from `_to_srt(segments)` → `_to_srt(tagged_segments)`:
```python
def _to_srt(tagged_segments):
    speaker_map = _build_speaker_map(tagged_segments)
    lines = []
    for i, (seg, speaker) in enumerate(tagged_segments, 1):
        label = f"[{speaker_map[speaker]}] " if speaker else ""
        lines.append(
            f"{i}\n{_fmt_srt(seg.start)} --> {_fmt_srt(seg.end)}\n"
            f"{label}{seg.text.strip()}\n"
        )
    return "\n".join(lines)
```

### 3. Update `_to_vtt` signature
Same pattern — `_to_vtt(tagged_segments)` with `[Speaker N]` prefix.

### 4. Update `_save_outputs` signature + `.txt` writer
Change `_save_outputs(file_path, segments, output_dir, formats)` → `_save_outputs(file_path, tagged_segments, output_dir, formats)`.

Update the `.txt` writer:
```python
speaker_map = _build_speaker_map(tagged_segments)
parts = []
for seg, speaker in tagged_segments:
    label = f"[{speaker_map[speaker]}] " if speaker else ""
    parts.append(f"{label}{seg.text.strip()}")
f.write(" ".join(parts))
```

### 5. Integrate diarization into the main per-file flow

After the Plan 01 segment iteration loop (which **must not be modified**), add:

```python
# Plan 03: diarization (runs after the segment loop, uses materialized segments list)
if diarize:
    _log("Running speaker diarization…")
    try:
        from src.transcribe_task import _diarize, _assign_speakers
        turns = _diarize(path)
        tagged = _assign_speakers(segments, turns)
    except FileNotFoundError as exc:
        _log(f"WARNING: {exc}")
        tagged = [(seg, None) for seg in segments]
    except Exception as exc:
        _log(f"Diarization failed, proceeding without speaker labels: {exc}")
        tagged = [(seg, None) for seg in segments]
else:
    tagged = [(seg, None) for seg in segments]

_save_outputs(path, tagged, output_dir, formats)
```

**Critical: do not touch the `for seg in segments_gen:` loop above this block.** That loop is owned by Plan 01.

---

## Tests to Write

File: `tests/test_tagged_output_formatters.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | `_build_speaker_map` returns `{"SPEAKER_00": "Speaker 1", "SPEAKER_01": "Speaker 2"}` for two speakers | Wrong numbering or key order |
| 2 | `_to_srt(tagged)` with speaker labels produces `[Speaker 1]` prefix on each cue | Missing or wrong label |
| 3 | `_to_srt(tagged)` with all `None` speakers produces output identical to the pre-Plan-03 (no labels) | Regression — labels appear when they shouldn't |
| 4 | `_to_vtt(tagged)` with speaker labels includes `[Speaker N]` prefix | Missing label |
| 5 | `.txt` output includes speaker labels when present, no labels when all `None` | Regression or missing labels |

Use mock segments (`SimpleNamespace(start=0.0, end=2.0, text="Hello")`).

---

## Acceptance Criteria

1. `_to_srt`, `_to_vtt`, and `_save_outputs` accept `tagged_segments: list[tuple]` — the old `segments: list` signature is gone.
2. When all speakers are `None`, output is byte-for-byte identical to pre-Plan-03 output (no regressions for non-diarized use).
3. When diarization is enabled, each cue/line is prefixed with `[Speaker N]`.
4. Diarization failure at runtime logs a warning and falls back to unlabelled output — it never fails the whole file.
5. The Plan 01 `for seg in segments_gen:` loop is unchanged.
6. All 5 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- Plan 01 is not yet merged and `_to_srt` / `_to_vtt` still use the old signature — wait for Plan 01 before implementing this task.
- The existing `_save_outputs` signature is used in more places than the one per-file call site — audit before changing.
- `_fmt_srt` or `_fmt_vtt` helpers don't exist under those names — find the actual helper names in the file before writing tests.
