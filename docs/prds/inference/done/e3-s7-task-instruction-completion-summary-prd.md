---
validation:
  status: valid
  validated_at: '2026-02-01T22:40:50+11:00'
---

## Product Requirements Document (PRD) — Task Instruction & Completion Summary

**Project:** Claude Headspace
**Scope:** Task model enrichment, summarisation prompt rebuild, agent card display
**Author:** samotage (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Tasks in Claude Headspace currently produce meaningless AI-generated summaries because the summarisation prompts lack context. The task summary prompt receives only timestamps, turn count, and the final turn's text — with no knowledge of what was originally commanded. Turn summaries suffer similarly: when turn text is empty or the prompt lacks task context, the LLM produces filler like "The agent indicated the intention to complete the given task."

This PRD introduces two new task-level concepts: an **instruction** (LLM-derived summary of the initiating command) and a **completion summary** (LLM-derived summary of task outcome with full context). It also rebuilds the turn and task summarisation prompts to produce useful, context-aware summaries, and updates the agent card UI to display both the task instruction and the latest contextual turn summary.

This is the core value proposition of Headspace's intelligence layer — enabling the user to glance at the dashboard and immediately understand what each agent was asked to do and what it's currently doing.

---

## 1. Context & Purpose

### 1.1 Context

The E3-S2 sprint added turn and task summarisation via the inference layer. The E3-S6 sprint added content pipeline support to extract real transcript text into turns. However, the summarisation prompts were written before real content was flowing, and they produce low-quality outputs:

- **Task summary prompt** (`_build_task_prompt`): only passes timestamps, turn count, and `turns[-1].text`. No original command context. When the final turn text is empty (timing issue), the LLM parrots timestamps back.
- **Turn summary prompt** (`_build_turn_prompt`): passes `turn.text`, actor, and intent. When text is None/empty, the LLM generates filler from metadata alone. No task-level context is provided regardless.

The result: summaries that say things like "The task started on 2026-02-01 and was completed, taking 9 turns. The specific details are not given." This is worse than no summary at all.

### 1.2 Target User

The primary user monitoring multiple Claude Code agents across projects via the Headspace dashboard. They need to rapidly scan agent cards and understand: what did I ask this agent to do, and what is it doing right now?

### 1.3 Success Moment

The user glances at an agent card and sees:
- **Line 1:** "Refactor the authentication middleware to use JWT tokens" (task instruction)
- **Line 2:** "Asking: Should I also update the test fixtures for the new token format?" (current turn context)

They immediately know what the agent is working on and what it needs from them, without clicking into any detail view.

---

## 2. Scope

### 2.1 In Scope

- New `instruction` field on Task model — LLM-derived summary of the initiating USER COMMAND turn
- Rename existing `summary` field to `completion_summary` on Task model
- Rebuild task completion summary prompt: primary input is the agent's final message that triggered COMPLETE, with the task instruction as context
- Rebuild turn summarisation prompts with intent-aware templates and task instruction context
- Guard against empty turn text: skip summarisation when turn text is None/empty rather than generating filler
- Ensure transcript content is available before summarisation is triggered (fix timing between content pipeline and summary trigger)
- Agent card UI: two-line display showing task instruction and latest contextual turn summary
- SSE events updated to push instruction field
- Alembic migration for field rename and new field
- Update all service, route, template, and test references from `task.summary` to `task.completion_summary`

### 2.2 Out of Scope

- Changes to turn-level model fields (turn `summary` field remains as-is)
- Priority scoring logic changes (will passively benefit from better data)
- Task state machine changes
- Historical backfill of existing tasks with new instruction/completion_summary
- Mobile-specific layout redesign of agent cards
- Changes to the inference service, rate limiter, or cache infrastructure

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Every new task has an `instruction` field populated via LLM inference within seconds of the initiating USER COMMAND turn
2. Every completed task has a `completion_summary` that references both the original instruction and the agent's final output
3. Task completion summaries describe what was accomplished relative to what was asked — not timestamps or turn counts
4. Turn summaries for empty-text turns are not generated (no filler summaries from metadata alone)
5. Turn summaries include task instruction context, producing summaries that relate to the task being worked on
6. Agent cards display the task instruction as the primary line when a task is active
7. Agent cards display the latest turn summary as a contextual secondary line (question when awaiting input, progress when processing, completion result when complete)
8. SSE pushes instruction updates to the dashboard in real time

### 3.2 Non-Functional Success Criteria

1. Instruction summarisation does not block the hook processing pipeline (remains async)
2. Completion summary generation only fires after transcript content is available in the turn text
3. No increase in inference API error rate from prompt changes

---

## 4. Functional Requirements (FRs)

### Data Model

**FR1:** The Task model has a new `instruction` field (Text, nullable) that stores the LLM-derived summary of what the user commanded.

**FR2:** The Task model has a new `instruction_generated_at` field (DateTime, nullable) that records when the instruction summary was generated.

**FR3:** The existing Task `summary` field is renamed to `completion_summary`. The existing `summary_generated_at` field is renamed to `completion_summary_generated_at`.

**FR4:** An Alembic migration handles the field rename and new field addition.

### Instruction Generation

**FR5:** When a task is created from a USER COMMAND turn, instruction summarisation is triggered asynchronously. The prompt receives the full text of the user's command and produces a 1-2 sentence summary of what was instructed.

**FR6:** The instruction summary is persisted to `task.instruction` and broadcast via SSE as an `instruction_summary` event (or similar).

### Completion Summary

**FR7:** The task completion summary prompt is rebuilt. Its primary inputs are:
- The task instruction (what was commanded)
- The agent's final message that triggered the transition to COMPLETE
The prompt asks the LLM to describe what was accomplished relative to what was asked, in 2-3 sentences.

**FR8:** The completion summary prompt does not include timestamps or turn counts as primary content. These are not useful to the LLM for summarisation.

**FR9:** Completion summarisation only fires after the final turn's text content is confirmed to be populated (non-None, non-empty). If text is not yet available, summarisation is deferred or retried rather than proceeding with empty content.

### Turn Summarisation

**FR10:** Turn summarisation prompts are intent-aware. Different prompt templates are used depending on the turn's intent:
- **COMMAND:** Summarise what the user is asking the agent to do
- **QUESTION:** Summarise what the agent is asking the user
- **COMPLETION:** Summarise what the agent accomplished (with task instruction context)
- **PROGRESS:** Summarise what progress the agent has made
- **ANSWER:** Summarise what information the user provided
- **END_OF_TASK:** Summarise the final outcome of the task

**FR11:** Turn summarisation includes the task instruction as context in the prompt (when available), so summaries are grounded in what the task is about.

**FR12:** Turn summarisation is skipped (returns None) when `turn.text` is None or empty. No summary is generated from metadata alone.

### Agent Card UI

**FR13:** The agent card displays the task instruction as the primary information line when a task is active.

**FR14:** The agent card displays the latest turn summary as a secondary line below the instruction, providing real-time context on what the agent is currently doing or asking.

**FR15:** When no task is active (IDLE state), the agent card displays an appropriate idle message (existing behaviour preserved).

**FR16:** The dashboard SSE handlers update both the instruction line and the turn summary line independently as new data arrives.

### Reference Updates

**FR17:** All references to `task.summary` across services, routes, templates, SSE handlers, and tests are updated to `task.completion_summary`. All references to `task.summary_generated_at` are updated to `task.completion_summary_generated_at`.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Instruction generation is asynchronous and does not block the hook processing pipeline or delay the state transition to COMMANDED/PROCESSING.

**NFR2:** Completion summary generation is resilient to timing issues — if the final turn text is not yet populated when summarisation is triggered, the system defers or retries rather than producing an empty summary.

**NFR3:** The summarisation service handles the transition gracefully — tasks created before this change (with `completion_summary` as NULL and no `instruction`) continue to display without errors.

---

## 6. UI Overview

### Agent Card — Active Task State

```
┌─────────────────────────────────────────────┐
│ ● ACTIVE   a1b2c3d4   Last seen: 2m ago    │
│─────────────────────────────────────────────│
│ ██ Processing...                            │  ← State strip (existing)
│─────────────────────────────────────────────│
│ Refactor auth middleware to use JWT tokens  │  ← Task instruction (NEW)
│ Working on updating token validation logic  │  ← Latest turn summary (NEW)
│─────────────────────────────────────────────│
│ Priority: 85 — Aligned with auth objective  │  ← Priority (existing)
└─────────────────────────────────────────────┘
```

### Agent Card — Awaiting Input State

```
┌─────────────────────────────────────────────┐
│ ● ACTIVE   a1b2c3d4   Last seen: 30s ago   │
│─────────────────────────────────────────────│
│ ██ Input needed                             │  ← State strip (amber)
│─────────────────────────────────────────────│
│ Refactor auth middleware to use JWT tokens  │  ← Task instruction
│ Asking: Update test fixtures for new token  │  ← Agent question summary
│  format?                                    │
│─────────────────────────────────────────────│
│ Priority: 85 — Aligned with auth objective  │  ← Priority (existing)
└─────────────────────────────────────────────┘
```

### Agent Card — Idle State

```
┌─────────────────────────────────────────────┐
│ ● ACTIVE   a1b2c3d4   Last seen: 5m ago    │
│─────────────────────────────────────────────│
│ ██ Idle - ready for task                    │  ← State strip (green)
│─────────────────────────────────────────────│
│ No active task                              │  ← Existing idle message
│─────────────────────────────────────────────│
│ Priority: 50                                │  ← Priority (existing)
└─────────────────────────────────────────────┘
```
