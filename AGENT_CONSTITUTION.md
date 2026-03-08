# Agent Constitution

> Governance rules for all AI agents contributing to this project.
> Every agent — whether invoked via chat, CI, PR review, or automation —
> MUST read and comply with this document before writing or modifying code.

---

## 1. Test-Driven Development (Mandatory)

All code changes MUST follow **Red → Green → Refactor** TDD:

### Red
- **Before writing implementation code**, write a failing test that captures the expected behaviour.
- The test must run and **fail for the right reason** (not a syntax error or import failure — an actual assertion failure or expected exception).
- Commit or confirm the failing test before proceeding.

### Green
- Write the **minimum implementation** needed to make the failing test pass.
- Do not add behaviour that isn't covered by a test.
- Run the test suite and confirm the new test passes **and no existing tests break**.

### Refactor
- Clean up the implementation and test code (remove duplication, improve naming, extract helpers).
- Re-run the full test suite after refactoring to confirm nothing regressed.

### Rules
| Rule | Detail |
|------|--------|
| No untested code | Every new function, method, class, signal, and event type must have at least one test. |
| No test-last | Writing tests after implementation is not permitted. If an agent realizes it skipped the Red phase, it must stop, write the test, confirm it fails against the old code, then proceed. |
| Test scope | Unit tests for logic (pure functions, data transforms). Integration tests for subprocess communication (worker ↔ transcribe_task). GUI tests are optional but encouraged for signal/slot wiring. |
| Test location | Tests live in `tests/` mirroring `src/` structure (e.g. `tests/test_worker.py`). |
| Test runner | `pytest`. All tests must pass via `pytest tests/` from the project root. |

---

## 2. Collaborative Decision-Making

Agents do not make unilateral decisions on matters that affect architecture, UX, dependencies, or scope.

### Decision Categories

| Category | Agent Authority | Requires Human Approval |
|----------|----------------|------------------------|
| Bug fix (behaviour unchanged) | ✅ Proceed autonomously | No |
| Refactor (behaviour unchanged, tests pass) | ✅ Proceed autonomously | No |
| New dependency | ❌ Must ask first | Yes |
| API / protocol change (signals, events, subprocess JSON) | ❌ Must ask first | Yes |
| UI layout, wording, or flow change | ❌ Must ask first | Yes |
| Architecture change (new files, new modules, structural reorganisation) | ❌ Must ask first | Yes |
| Deleting or renaming public interfaces | ❌ Must ask first | Yes |
| Performance tradeoff (speed vs. accuracy, memory vs. disk) | ❌ Must ask first | Yes |

### How to Ask
- **In chat:** Use clear, concise questions with options. Propose a recommended default so the human can confirm quickly. Batch related questions (max 4 at a time).
- **In GitHub PRs:** Post decisions as PR comments with a checkbox list. Do not merge until the human has responded.
- **Never guess at intent.** If a requirement is ambiguous, ask. Do not assume.

### Plan-First Protocol
For multi-step work:
1. Draft a plan (markdown in `plans/`) **before** writing code.
2. Get human approval on the plan.
3. Execute the plan, following TDD.
4. Mark plan items as complete as you go.

---

## 3. Empathetic UX

All user-facing changes must be evaluated through the lens of defined personas. Agents must consider how each persona would experience the change.

### Personas

Every user-facing decision must be evaluated against both personas. Ask: *"How would Jordan experience this? How would Alex experience this?"*

#### Persona A — "Jordan" (Non-Technical End User)

- **Who they are:** A content creator, student, or everyday consumer who records interviews, podcasts, lectures, or personal calls and needs text versions. Not a developer — installs software by downloading an installer and clicking Next.
- **Technical comfort:** Low. Has never used a terminal. Knows how to install apps, drag files, and click buttons.
- **Primary goal:** Drag in a recording, click one button, get a clean transcript with speaker labels.

| Priority | Why |
|----------|-----|
| Zero-config start | Defaults must "just work." Choosing models, devices, and formats is intimidating — sensible defaults eliminate decision paralysis. |
| Clear progress | "Is it frozen?" is the #1 anxiety. Every phase (loading model, transcribing, diarizing) must show what's happening, how far along, and roughly how long. |
| Plain-language errors | Jargon like "CTranslate2 backend failed to initialize openvino plugin" means nothing. Errors must say what happened, what to do, and offer a "Copy error details" option for support. |
| Usable output | They'll paste into Google Docs, drop an SRT into a video editor, or upload a VTT to YouTube. Output must be clean, correctly formatted, and obvious where to find. |
| Speaker labels | For interviews and podcasts, knowing who said what is the whole point. Diarization isn't a power feature — it's core. |
| Trust & safety | "Is my audio being uploaded somewhere?" Local processing, no network calls during transcription. Make this visible. |
| Installation isn't scary | The installer must be compact, fast, and not trigger excessive Windows Defender warnings. |

- **Frustration triggers:** Silent crashes, jargon in error messages, having to touch a terminal, unclear file output locations, "it looks like nothing is happening."
- **What "good" looks like:** Open app → drag file → click Transcribe → watch progress → find transcript next to the original file. Done in under a minute of user effort.

---

#### Persona B — "Alex" (Open-Source Hobbyist Developer)

- **Who they are:** A developer who found this repo on GitHub, wants to understand how it works, maybe fix a bug or add a feature. Comfortable with Python, git, and the terminal, but not necessarily an expert in ML, audio processing, or Qt.
- **Technical comfort:** High for general development. Medium for domain-specific tech (ML models, Qt internals).
- **Primary goal:** Clone the repo, understand the architecture, make a contribution, and get it merged.

| Priority | Why |
|----------|-----|
| Easy dev environment setup | `git clone` → `pip install -r requirements.txt` → `python app.py` must work in under 5 minutes. If it doesn't, they'll move on. |
| Readable, well-structured code | They learn the codebase by reading it. Clear module boundaries, docstrings, type hints, and logical file layout matter more than cleverness. |
| Test suite they can trust | Before changing anything, they'll run `pytest`. If tests are flaky, missing, or hard to run, they won't know if their change broke something. TDD gives them confidence. |
| Architecture docs | They shouldn't have to reverse-engineer the subprocess protocol or signal wiring. A brief architecture overview (`app.py` → `main_window` → `worker` → `transcribe_task`) saves an hour. |
| Low contribution friction | Clear README with "how to contribute," consistent code style, and this constitution as a reference. No guessing at conventions. |
| Plans folder | Reading plans explains *why* things are built the way they are, not just *what* the code does. |

- **Frustration triggers:** Undocumented magic, `setup_env.py` that fails silently, no tests, "works on my machine" issues, PRs that sit without review.
- **What "good" looks like:** Clone → setup → run tests → read a plan → make a change → tests pass → open PR → get feedback within a day.

---

### How to Apply Personas

When evaluating a change, agents must ask:

1. **Jordan test:** Can Jordan use this feature without reading docs, touching a terminal, or understanding technical details? If not, what needs to change?
2. **Alex test:** Can Alex understand this code, run the tests, and modify it confidently? If not, what's missing (docs, tests, comments)?

If a change serves one persona at the expense of the other, flag it and ask the human how to balance the tradeoff.

### UX Rules (Active Now)
| Rule | Detail |
|------|--------|
| No silent failures | Every error must be visible to the user — in the UI, in the log pane, and in `app_log.txt`. |
| Progress over silence | If an operation takes > 1 second, the user must see feedback (progress bar, spinner, status text). |
| Plain language | Error messages must be understandable by a non-developer. Include what happened, why, and what to do next. |
| Safe defaults | Default settings should produce correct results without configuration. Advanced options are opt-in. |
| Destructive actions require confirmation | File overwrites, queue clears, or cancellations must confirm before executing (or be trivially undoable). |

---

## 4. Code Quality Standards

| Standard | Detail |
|----------|--------|
| Type hints | All function signatures must have type annotations. |
| Docstrings | All public functions and classes must have a docstring. |
| Logging | Use `logging.getLogger("transcriber")` — never bare `print()` in production code. |
| No dead code | Remove commented-out code and unused imports before committing. |
| Atomic commits | Each commit should represent one logical change. Do not mix unrelated changes. |

---

## 5. Dependency Governance

| Rule | Detail |
|------|--------|
| Justify every addition | New dependencies must include a rationale: what it provides, what it costs (size, license, maintenance burden), and what alternatives were considered. |
| License check | Only MIT, BSD, Apache 2.0, and similarly permissive licenses. No GPL dependencies without explicit human approval. |
| Pin versions | All dependencies in `requirements.txt` must have minimum version pins. |
| Document in THIRD_PARTY_LICENSES.md | Any bundled assets or models must have their license text included. |

---

## 6. Amendment Process

This constitution is a living document. To amend it:
1. Propose the change in chat or as a PR.
2. Explain the rationale.
3. Get human approval.
4. Update this file.

Changes to the constitution take effect immediately upon approval.
