# MAKER Protocol — Recording Transcriber

This document defines how the dual-agent MAKER (Multiple Agents with K-step Error Recovery) protocol works in this project.

## Overview

Every implementation task is executed by **two independent developer agents** of the same type (e.g., two UI agents, two Backend agents). They race to complete the task. The first agent to meet all acceptance criteria wins; the other's work is discarded.

This provides **error correction without coordination overhead** — if one agent makes a mistake or gets stuck, the other may succeed independently.

## Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| **N (agents per race)** | 2 | Two agents work each task independently |
| **K (checkpoint interval)** | 3 | Checkpoint after every 3 TDD cycles |
| **Cost multiplier** | ~2× | Roughly double the compute of single-agent |

## Workflow

### 1. Task Assignment (Lead Engineer — Planner)

```
Plan → Decompose → Task definitions → Assign dual agents
```

The Planner creates a task definition file in `plans/tasks/` and assigns it to two agents of the appropriate type. Both agents receive identical task definitions.

### 2. Independent Execution (Developer Agents)

Each agent works independently, following TDD:

```
┌─────────────────────────────────────┐
│  TDD Cycle 1:                       │
│    RED:     Write a failing test     │
│    GREEN:   Write minimal code       │
│    REFACTOR: Clean up                │
├─────────────────────────────────────┤
│  TDD Cycle 2:                       │
│    RED → GREEN → REFACTOR            │
├─────────────────────────────────────┤
│  TDD Cycle 3:                       │
│    RED → GREEN → REFACTOR            │
├─────────────────────────────────────┤
│  ► CHECKPOINT (K=3 reached)         │
│    Submit for review                 │
└─────────────────────────────────────┘
```

### 3. Checkpoint Review (Lead Engineer — PR Review)

At each K=3 checkpoint:

1. **Run all tests.** Every test must pass (not just the new ones).
2. **Verify TDD compliance.** Commit history must show Red→Green→Refactor for each cycle.
3. **Check ownership boundaries.** Only files in the agent's ownership table are modified.
4. **Validate acceptance criteria.** Each criterion from the task definition is met or progressing.

### 4. Race Resolution

| Scenario | Action |
|----------|--------|
| Agent A reaches checkpoint first, passes | **Agent A wins.** Agent B's work is discarded. |
| Agent A reaches checkpoint first, fails review | **Agent A gets feedback.** Agent B continues racing. |
| Both reach checkpoint simultaneously | **Prefer fewer lines changed.** Tie-break: fewer new dependencies. |
| Both fail review | **Both get feedback.** Race continues or Planner re-evaluates the task. |
| One agent red-flags | **Not a failure.** Process the flag, then the agent resumes. The other agent may win during the pause. |

## Red-Flagging

Any agent can **pause and escalate** when they encounter uncertainty. Red-flagging is explicitly encouraged — it is better to flag and wait than to guess and break something.

### Red-flag process:

1. Agent identifies an issue outside its scope or expertise.
2. Agent documents the issue clearly: what's uncertain, what's needed, what options exist.
3. Agent stops work on the affected part (may continue on unrelated parts of the task).
4. The Lead Engineer (Planner) or Architect resolves the flag.
5. Agent receives the resolution and resumes.

### Common red-flag triggers:

- Task requires modifying files outside ownership boundary.
- Interface contract needs to change (new signal, new event type).
- Architectural ambiguity not covered by the plan.
- Dependency concern (size, license, compatibility).
- Test would require external resources (GPU, network, large files).

## File Ownership Model

Each developer agent owns specific files. Ownership means:

- **Primary owner:** Can create, modify, and delete the file. Responsible for its tests.
- **Co-owner:** Can modify specific parts of the file (documented in agent definition).
- **Read-only reference:** Can read the file for context. Cannot modify it.

Cross-boundary changes require coordination through the Lead Engineer (Planner).

```
┌─────────────────┐    ┌──────────────────┐
│   UI Agent       │    │  Backend Agent    │
│                  │    │                   │
│  main_window.py  │◄───│  worker.py        │
│  test_ui_*.py    │    │  test_worker.py   │
│                  │    │  test_protocol.py │
└─────────────────┘    └──────────────────┘
        ▲                       ▲
        │ signals               │ JSON events
        │                       │
┌───────┴─────────────────────┴───────────┐
│              ML/Audio Agent              │
│                                          │
│  transcribe_task.py    model_manager.py  │
│  test_transcribe.py    test_model.py     │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│            Build/Installer Agent          │
│                                          │
│  installer/*    setup_env.py             │
│  requirements.txt    test_build_*.py     │
└──────────────────────────────────────────┘
```

## Task Sizing

Each task should be completable in approximately **K=3 TDD cycles**. Guidelines:

| Too small | Right size | Too large |
|-----------|-----------|-----------|
| Single line change | 1–5 new tests | 6+ new tests |
| No branching logic | One clear feature/fix | Multiple features |
| Trivial refactor | Touches 1–3 files | Touches 4+ files |

If a task seems too large, the Planner decomposes it further before assignment.

## Cost Considerations

The dual-agent model costs ~2× a single-agent approach. This is justified when:
- Correctness matters more than speed (always, per the constitution).
- The task has multiple valid implementation approaches.
- The codebase is unfamiliar to the agents.

For trivial tasks (documentation updates, single-line fixes), the Planner may assign a single agent (MAKER race = No in the task definition).
