# Task 02-01: Emit model_loading / model_loaded Events from transcribe_task.py

- **Plan:** [plans/02_model_loading_indicator/02_model_loading_indicator.md](../02_model_loading_indicator.md)
- **Agent type:** ML/Audio
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none
- **Files to modify:** `src/transcribe_task.py`
- **Files to create:** `tests/test_transcribe_model_events.py`

---

## What to Implement

In `src/transcribe_task.py`, bracket the `WhisperModel(...)` constructor call with two new JSON events emitted to stdout:

**Before** the blocking `WhisperModel()` call, emit:
```json
{"event": "model_loading", "model": "<model_name>"}
```

**After** it returns successfully, emit:
```json
{"event": "model_loaded", "model": "<model_name>"}
```

The `model_name` value is whatever model name string was passed into the task job (e.g. `"large-v3"`, `"base"`).

These two events bracket the entire blocking load — including the GPU-fallback retry path. If the first `WhisperModel()` attempt fails and retries on CPU, the `model_loading` event has already fired; a second one is not needed. `model_loaded` fires only once on the successful attempt.

---

## Tests to Write

File: `tests/test_transcribe_model_events.py`

| # | Test | Red trigger |
|---|------|------------|
| 1 | When the task processes a job with a given model name, a `model_loading` event appears in stdout before any `file_started` event | `model_loading` absent or after `file_started` |
| 2 | A `model_loaded` event appears after `model_loading` and before any `file_done` event | `model_loaded` absent or wrong order |
| 3 | Both events include the `"model"` key matching the job's model name | Missing or wrong `model` field |

Use a mock/monkeypatch for `WhisperModel` — do not load a real model. Capture emitted JSON lines from `stdout` using the existing subprocess test pattern or by calling the internal task function directly with dependency injection.

---

## Acceptance Criteria

1. Running `transcribe_task.py` with any model config emits `model_loading` before the `WhisperModel` constructor is called.
2. On successful model load, `model_loaded` is emitted with the same `model` name.
3. If `WhisperModel` raises and the task retries on CPU, `model_loaded` still fires exactly once on success.
4. If the task fatals (model load fails entirely), `model_loaded` is never emitted.
5. All 3 new tests pass. All pre-existing tests pass.

---

## Red-Flag Triggers

- The `WhisperModel` constructor is in a code path too entangled to instrument without refactoring — escalate to Lead Engineer for scoping adjustment.
- Emitting the event requires importing Qt or any GUI module — hard stop, wrong architecture.
- A test would need a real GPU or downloaded model weights to pass.
