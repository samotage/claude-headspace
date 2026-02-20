---
validation:
  status: invalid
  invalidated_reason: 'PRD amended post-evaluation — handoff-in-progress flag mechanism added (FR7), previous_agent_id via create_agent (FR14-15). Requires revalidation.'
---

## Product Requirements Document (PRD) — Handoff Execution

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 14 — Full handoff execution cycle from operator trigger to successor continuation
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

When a persona-backed agent's context window fills up, the operator triggers a handoff from the dashboard (E8-S13). This sprint implements the full execution cycle that follows: Headspace instructs the outgoing agent to write a first-person handoff document, verifies the document was created, records the handoff in the database, gracefully ends the outgoing session, spins up a successor agent with the same persona, and delivers the handoff context so the successor can continue work seamlessly.

The handoff mechanism is built on two design principles from workshop decision 5.1: **agent-as-author** (the outgoing agent writes its own handoff document because it has the richest understanding of its work) and **two-phase bootstrap** (the successor receives an immediate injection prompt via tmux bridge for quick orientation, then reads the detailed handoff file with its own tools for deep context). This creates context continuity across agent sessions — the persona's knowledge carries forward even when individual sessions end.

This is the capstone sprint of Epic 8. It wires together persona identity (S1-S8), skill injection (S9), the Handoff model (S12), and the trigger UI (S13) into the complete handoff pipeline. All design decisions are resolved in the Agent Teams Workshop (decision 5.1).

---

## 1. Context & Purpose

### 1.1 Context

Without handoff, context saturation means starting from scratch. An agent that has spent hours understanding a codebase, making design decisions, and tracking progress loses all of that when its context window fills. The operator must manually reconstruct the context for the next agent — explaining what was done, what's in progress, and what decisions were made.

The handoff system solves this by having the outgoing agent — the entity with the richest understanding of the work — produce a first-person context document. This document captures not just what happened (which Headspace can reconstruct from DB data) but what the agent *understood*: dead ends explored, reasoning behind approaches, mid-problem state, and intended next steps.

Dependencies from earlier sprints provide the foundation: the Handoff model (S12) stores metadata and injection prompts, the trigger UI (S13) provides the operator-initiated button, skill injection (S9) primes successors with persona identity, and persona-aware agent creation (S7) enables spinning up successors with the same persona.

### 1.2 Target User

The operator (Sam) who manages persona-backed agents through the Claude Headspace dashboard. The operator triggers handoffs when context is saturated, reviews the handoff flow, and benefits from seamless context continuity without manual intervention after the initial trigger.

### 1.3 Success Moment

The operator clicks the handoff button on Con's agent card. Con writes a detailed handoff document. A new Con agent spins up, receives skill injection followed by the handoff context, reads the handoff file, and continues working where the previous Con left off — all automatically after the single button click.

---

## 2. Scope

### 2.1 In Scope

- Handoff orchestration that coordinates the full handoff cycle end-to-end
- API endpoint for the S13 handoff button to trigger the handoff flow
- Handoff instruction delivery to the outgoing agent via tmux bridge, specifying the exact file path to write to
- Handoff file path generation following the naming convention: `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`
- Handoff directory creation (`data/personas/{slug}/handoffs/`) if it doesn't exist
- Handoff confirmation via stop hook followed by file existence verification
- Hard error reporting to the operator when any step fails (no silent failures)
- Handoff DB record creation (using the S12 Handoff model) with reason, file path, and composed injection prompt
- Graceful shutdown of the outgoing agent session
- Successor agent creation with the same persona
- Setting `previous_agent_id` on the successor agent to link to the outgoing agent
- Sequenced delivery: skill injection (S9) completes before the handoff injection prompt is sent
- Injection prompt composition referencing the predecessor agent and pointing to the handoff file path
- Injection prompt delivery to the successor via tmux bridge

### 2.2 Out of Scope

- Handoff trigger UI or context threshold monitoring (E8-S13 — separate PRD)
- Handoff database model or migration (E8-S12 — separate PRD)
- Persona registration, skill files, or skill injection logic (E8-S5/S6/S9 — separate PRDs)
- Persona-aware agent creation internals (E8-S7 — separate PRD)
- SessionCorrelator persona assignment (E8-S8 — separate PRD)
- Auto-triggered handoff — operator-initiated only in v1 (deferred per workshop 5.1)
- Handoff file cleanup or lifecycle management (deferred to system management PRD)
- Handoff quality validation or scoring
- Dashboard display of handoff history or handoff chain visualization

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Operator clicks handoff button → outgoing agent receives a handoff instruction via tmux bridge specifying the file path to write to
2. Outgoing agent writes a handoff document to the correct path under `data/personas/{slug}/handoffs/`
3. After the outgoing agent's stop hook fires, the handoff file is verified to exist on disk
4. If the handoff file does not exist after the stop hook, a hard error is raised and reported to the operator — the flow does not continue
5. Handoff DB record is created with correct `agent_id`, `reason`, `file_path`, and `injection_prompt`
6. Outgoing agent session ends gracefully
7. Successor agent spins up with the same persona as the outgoing agent
8. Successor agent's `previous_agent_id` is set to the outgoing agent's ID
9. Successor receives skill injection (S9) before receiving the handoff injection prompt
10. Successor receives the handoff injection prompt containing a reference to the predecessor and the handoff file path
11. Full handoff cycle completes without manual intervention after the initial trigger (assuming no errors)
12. Handoff files accumulate at `data/personas/{slug}/handoffs/` without issues

### 3.2 Non-Functional Success Criteria

1. Every failure in the handoff pipeline is surfaced to the operator — no silent errors, no automatic retries that mask problems
2. The handoff flow does not interfere with anonymous (non-persona) agents
3. All existing agent lifecycle operations (create, shutdown, hook processing) continue working unchanged
4. The handoff instruction and injection prompt are composed as plain text messages suitable for tmux bridge delivery

---

## 4. Functional Requirements (FRs)

### Handoff Trigger

**FR1:** The system shall provide an API endpoint that the S13 handoff button calls to initiate the handoff flow. The endpoint shall accept the agent ID and handoff reason.

**FR2:** The system shall validate that the agent exists, is active (not ended), has a persona, and has a tmux pane before starting the handoff flow. If any validation fails, the system shall return an error to the caller.

### Handoff Instruction

**FR3:** The system shall generate the handoff file path using the convention `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`, where `{iso-datetime}` is the current time in `YYYYMMDDTHHmmss` format and `{agent-8digit}` is the first 8 characters of the agent's session UUID.

**FR4:** The system shall create the `data/personas/{slug}/handoffs/` directory if it does not already exist.

**FR5:** The system shall compose a handoff instruction message that tells the outgoing agent to write a handoff document to the generated file path. The instruction shall describe the expected content: what was being worked on, current progress, key decisions made and why, blockers encountered, files modified, and next steps.

**FR6:** The system shall send the handoff instruction to the outgoing agent via tmux bridge.

### Handoff Confirmation

**FR7:** After the handoff instruction is sent, the system shall set a handoff-in-progress flag on the outgoing agent (in-memory or on the Agent record) to distinguish this stop hook from normal turn completions. The system shall then wait for the outgoing agent's stop hook to fire. When the stop hook fires for an agent with the handoff-in-progress flag set, the system treats it as the handoff completion signal and proceeds to file verification (FR8). Normal stop hooks (no handoff-in-progress flag) are unaffected.

**FR8:** After the stop hook fires, the system shall verify that the handoff file exists at the expected path on disk.

**FR9:** If the handoff file does not exist after the stop hook, the system shall raise a hard error, notify the operator, and halt the handoff flow. The outgoing agent session shall remain active so the operator can investigate or retry.

**FR10:** If the handoff file exists but is empty (zero bytes), the system shall treat this as a failure — same behaviour as file not found (FR9).

### Handoff Record

**FR11:** After successful file verification, the system shall create a Handoff DB record with the outgoing agent's ID, the handoff reason, the handoff file path, and a composed injection prompt for the successor.

**FR12:** The injection prompt shall reference the predecessor agent, point to the handoff file path, and provide task context. It shall be a plain text message suitable for delivery via tmux bridge.

### Outgoing Agent Shutdown

**FR13:** After the Handoff DB record is created, the system shall gracefully shut down the outgoing agent session.

### Successor Creation

**FR14:** After the outgoing agent session ends, the system shall create a new agent with the same persona as the outgoing agent by calling `create_agent(persona_slug=..., previous_agent_id=outgoing_agent.id)`.

**FR15:** The successor agent's `previous_agent_id` shall be set to the outgoing agent's ID, establishing the continuity chain. This is achieved by passing `previous_agent_id` to `create_agent()` (parameter added by S7), which carries it through the hook pipeline to the SessionCorrelator (S8) for assignment at registration time.

**FR16:** If successor agent creation fails, the system shall raise a hard error and notify the operator. The Handoff DB record shall be preserved (the handoff document and metadata remain available for manual recovery).

### Successor Bootstrap

**FR17:** After the successor agent registers (session-start hook fires) and receives skill injection (S9), the system shall send the injection prompt from the Handoff DB record to the successor via tmux bridge.

**FR18:** The system shall wait for skill injection to complete before sending the handoff injection prompt, ensuring the successor has persona identity established before receiving handoff context.

**FR19:** The successor agent receives the injection prompt as a conversation message and reads the handoff file using its own tools to continue work.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** All errors in the handoff pipeline shall be surfaced to the operator via appropriate channels (API error responses, SSE broadcasts, or OS notifications). No step shall fail silently.

**NFR2:** The handoff flow shall not block the Flask request handler for the full duration of the cycle. The API endpoint shall initiate the flow and return immediately; orchestration steps proceed asynchronously with status updates.

**NFR3:** The handoff flow shall be idempotent-safe — if an agent already has a Handoff record, the system shall not create a second one.

**NFR4:** Backward compatibility — anonymous agents (no persona) are unaffected. The handoff endpoint shall reject requests for agents without personas.

---

## 6. Technical Context

*This section provides implementation guidance for the orchestration engine. These are conventions and integration points, not requirements. Included to prevent reinvention of existing infrastructure.*

### New Service

**`src/claude_headspace/services/handoff_service.py`** — Orchestration logic for the handoff cycle. Coordinates the steps defined in the functional requirements.

### Existing Services Used (DO NOT recreate)

- **`src/claude_headspace/services/tmux_bridge.py`** — `send_text()` for delivering the handoff instruction to the outgoing agent and the injection prompt to the successor. Battle-tested with ghost text handling, Enter verification, and per-pane locking.
- **`src/claude_headspace/services/agent_lifecycle.py`** — `create_agent()` for spinning up the successor (needs `persona_slug` parameter from S7). `shutdown_agent()` for graceful outgoing agent shutdown via `/exit`.
- **`src/claude_headspace/services/hook_receiver.py`** — Existing `process_stop()` handles the stop hook. The handoff service listens for stop events on the outgoing agent after sending the handoff instruction.
- **E8-S9 skill injection** — The successor receives skill injection automatically post-registration. The handoff service must wait for this to complete before sending the handoff injection prompt.
- **E8-S12 Handoff model** — `Handoff` SQLAlchemy model with `agent_id`, `reason`, `file_path`, `injection_prompt`, `created_at`.

### New API Endpoint

A handoff trigger endpoint called by the S13 button. Accepts agent ID and reason, validates preconditions, initiates the async handoff flow, returns immediately with status.

### Handoff Instruction Template

The message sent to the outgoing agent via tmux bridge. Should instruct the agent to write a first-person handoff document to the specified path, describing:
- What was being worked on
- Current progress and state
- Key decisions made and why
- Blockers encountered
- Files modified
- Next steps and what remains

### Injection Prompt Template

The message sent to the successor agent via tmux bridge after skill injection. Should:
- Reference the predecessor agent
- Point to the handoff file path
- Provide task context
- Instruct the successor to read the handoff file to continue work

### Handoff File Convention

- Path: `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`
- ISO datetime format: `YYYYMMDDTHHmmss` (e.g., `20260220T143025`)
- Agent 8-digit: first 8 characters of the agent's `session_uuid`
- Files are agent-written markdown — content and quality depend on the agent's compliance with the instruction prompt
- Files accumulate without cleanup in v1

### Design Decisions (all resolved — see workshop 5.1)

- **Agent-as-author** — outgoing agent writes its own handoff document (richest context)
- **File-native consumption** — successor reads handoff file via Read tool (natural for agents)
- **Two-phase bootstrap** — DB injection prompt bootstraps immediately, file deepens understanding
- **Handoff files under persona tree** — consistent with skill.md/experience.md asset pattern
- **Operator-initiated** — manual trigger provides human-in-the-loop for prompt tuning
- **Stop hook + file verification** — confirmation method uses existing hook infrastructure

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| Handoff trigger UI | E8-S13 | Dashboard button that calls this sprint's API endpoint |
| Handoff database model | E8-S12 | `Handoff` table for storing metadata and injection prompt |
| Skill file injection | E8-S9 | Successor persona priming — must complete before handoff prompt |
| Persona-aware agent creation | E8-S7 | `create_agent(persona_slug=..., previous_agent_id=...)` for spinning up successor with same persona and continuity chain |
| Agent model extensions | E8-S4 | `previous_agent_id` FK for continuity chain, `persona_id` FK for persona association |
| Persona filesystem assets | E8-S5 | `data/personas/{slug}/` directory convention for handoff file storage |

---

## Document History

| Version | Date       | Author | Changes                              |
|---------|------------|--------|--------------------------------------|
| 1.0     | 2026-02-20 | Sam    | Initial PRD from workshop (E8-S14)   |
