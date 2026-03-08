# Task 03-04: Diarization Checkbox in main_window.py

- **Plan:** [plans/03_speaker_diarization/03_speaker_diarization.md](../03_speaker_diarization.md)
- **Agent type:** UI
- **MAKER race:** Yes (dual-agent)
- **Depends on:** 03-01 (requires `TranscribeWorker.__init__` to accept `diarize: bool`)
- **Prerequisite plan:** Plan 01 must be complete before merging any Plan 03 task
- **Files to modify:** `src/main_window.py`
- **Files to create:** `tests/test_ui_diarization_checkbox.py`

---

## What to Implement

### 1. Add the checkbox widget
In the settings area of `MainWindow`, alongside the existing format checkboxes (`.txt`, `.srt`, `.vtt`), add:

```python
self._diarize_checkbox = QCheckBox("Speaker Diarization")
self._diarize_checkbox.setChecked(False)
self._diarize_checkbox.setToolTip(
    "Label each segment with a speaker tag (e.g. [Speaker 1]).\n"
    "Adds ~30–60 seconds per file."
)
```

Place it in its own row or group below the format checkboxes — keep it visually separated since it's a processing option, not an output format. The exact layout position is at the agent's discretion, but it must not crowd the format checkboxes.

### 2. Pass `diarize` when constructing the worker
Wherever `TranscribeWorker` is instantiated in `main_window.py`, add the `diarize` argument:

```python
worker = TranscribeWorker(
    ...,
    diarize=self._diarize_checkbox.isChecked(),
)
```

No new signals or event connections are needed for this task.

---

## Tests to Write

File: `tests/test_ui_diarization_checkbox.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | `MainWindow` contains a `QCheckBox` with text `"Speaker Diarization"` | Checkbox absent or wrong text |
| 2 | Checkbox is unchecked by default | Wrong default state |
| 3 | Checkbox has a non-empty tooltip | No tooltip — Jordan needs the hint |
| 4 | When the checkbox is checked and a transcription is started, the worker is constructed with `diarize=True` | Flag not passed |

For test 4, mock `TranscribeWorker` and assert the constructor was called with `diarize=True`.

---

## Acceptance Criteria

1. A "Speaker Diarization" checkbox is visible in the settings UI.
2. It is unchecked by default.
3. It has a tooltip explaining the feature and the time cost.
4. Its state is read and passed as `diarize=` to `TranscribeWorker` at job start.
5. The checkbox is styled consistently with existing checkboxes (same `QCheckBox` stylesheet applies automatically).
6. All 4 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- `TranscribeWorker` does not yet accept a `diarize` parameter (task 03-01 not merged) — wait for 03-01 before wiring the constructor call.
- The settings layout is so crowded that adding the checkbox requires a layout refactor beyond the scope of this task — escalate to Architect.
- The checkbox needs a separate "pyannote not installed" warning state — that's error handling in 03-02/03-03; do not add conditional disabling logic here unless specifically approved.
