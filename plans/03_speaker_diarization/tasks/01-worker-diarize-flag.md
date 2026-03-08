# Task 03-01: Plumb diarize Flag Through worker.py

- **Plan:** [plans/03_speaker_diarization/03_speaker_diarization.md](../03_speaker_diarization.md)
- **Agent type:** Backend
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none (can run in parallel with 03-02)
- **Prerequisite plan:** Plan 01 must be complete before merging any Plan 03 task
- **Files to modify:** `src/worker.py`
- **Files to create:** `tests/test_worker_diarize_flag.py`

---

## What to Implement

`TranscribeWorker` currently builds a job dict and passes it to the subprocess. Add `diarize: bool` as a constructor parameter and include it in the job JSON.

### 1. Constructor parameter
```python
def __init__(self, files: list[str], ..., diarize: bool = False):
    ...
    self.diarize = diarize
```

### 2. Job dict
In the method that builds the subprocess job, add:
```python
job = {
    ...
    "diarize": self.diarize,
}
```

No new signals are needed. The flag is payload data, not an event.

---

## Tests to Write

File: `tests/test_worker_diarize_flag.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | When `TranscribeWorker(diarize=True)` builds the job dict, `job["diarize"] == True` | Flag missing or wrong default |
| 2 | When `TranscribeWorker(diarize=False)` (default) builds the job dict, `job["diarize"] == False` | Wrong default |
| 3 | The `diarize` key is always present in the job dict (never absent) | Missing key causes subprocess KeyError |

Do not spawn the real subprocess. Test the job-building method directly.

---

## Acceptance Criteria

1. `TranscribeWorker.__init__` accepts `diarize: bool = False`.
2. The subprocess job JSON always contains `"diarize": true` or `"diarize": false`.
3. Existing behaviour (diarize=False) is unchanged — no regression.
4. All 3 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- The job dict is built in multiple places — find all call sites before changing the constructor signature.
- `main_window.py` constructs `TranscribeWorker` and needs to pass `diarize` — coordinate with the UI agent (task 03-04) on the constructor signature before both merge.
