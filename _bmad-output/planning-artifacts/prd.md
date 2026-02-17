---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-03-success
  - step-04-journeys
  - step-05-domain-skipped
  - step-06-innovation-skipped
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
classification:
  projectType: web_app
  domain: general_developer_tooling
  complexity: medium
  projectContext: brownfield
inputDocuments:
  - docs/reviews_remediation/turn-capture-reliability-prd-briefing.md
  - docs/architecture/transcript-chat-sequencing.md
  - docs/architecture/claude-code-hooks.md
  - docs/architecture/known-limitations.md
  - docs/architecture/tmux-bridge.md
  - docs/bugs/voice-chat-agent-response-rendering.md
  - docs/prds/events/done/e1-s13-hook-receiver-prd.md
  - docs/prds/state/done/e1-s6-state-machine-prd.md
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 8
workflowType: 'prd'
---

# Turn Capture Reliability — Product Requirements Document

**Project:** Claude Headspace
**Author:** Sam
**Date:** 2026-02-18
**Status:** Draft

## Executive Summary

Claude Headspace's voice chat dashboard silently loses agent turns. The root cause is architectural: hooks are treated as the primary source of truth for turn creation, but hooks are unreliable — they may not fire, arrive late, or trigger state machine exceptions that roll back the turn data.

The system has three sources of turn data with different reliability/latency trade-offs:

| Source | Latency | Reliability | Current Role |
|--------|---------|-------------|--------------|
| **Hooks** | <100ms | Unreliable | Primary (wrong) |
| **JSONL Transcripts** | 2-10s | Authoritative | Safety net (broken) |
| **Tmux Pane** | ~1s | Visual ground truth | Not used for turns |

**The reliability inversion:** Hooks should be the fast path for optimistic UI updates. The JSONL transcript should be the authoritative source that guarantees completeness. Tmux should be the real-time watchdog that bridges the gap between "hook didn't fire" and "transcript hasn't arrived yet."

This PRD defines the requirements for fixing the turn capture pipeline so that every agent turn recorded in the JSONL transcript is guaranteed to appear in the voice chat — with zero silent failures and automatic self-healing.

## Success Criteria

### User Success

- **No silent turn loss:** Every agent turn in the JSONL transcript appears in the voice chat. Zero tolerance for missing turns.
- **Complete chat history:** When a user returns to check on an agent, the chat contains the full, accurate conversation — no gaps.
- **Invisible recovery:** Recovered turns appear as normal turns with no visual distinction. Users never see recovery mechanics.

### Technical Success

- **Three-tier reliability pipeline operational:**
  - Hooks deliver optimistic turns in <100ms (when they fire)
  - Tmux watchdog detects unrepresented agent output within 5 seconds
  - Transcript reconciler guarantees completeness within 10 seconds of JSONL write
- **Reconciler creates missing turns:** When a JSONL entry has no matching database turn (e.g., rolled back by exception), the reconciler creates a new turn — no silent skipping.
- **State machine does not destroy data:** If a state transition fails, the turn is still committed. State stays unchanged; turn gets saved. Decoupled operations.
- **Recovered turns trigger state transitions:** Turns created via reconciliation feed back into the task lifecycle — a recovered QUESTION turn transitions the agent to AWAITING_INPUT.
- **No silent failures:** Every turn creation failure logged at WARNING+. Recovery actions at INFO. Diagnostics at DEBUG.

### Measurable Outcomes

- **Turn capture rate:** 100% of JSONL transcript entries have a corresponding database Turn record
- **Recovery latency:** Missed turns appear in chat within 10 seconds of JSONL write (hard ceiling: 60 seconds)
- **Self-healing rate:** 100% automatic recovery from hook failures when JSONL data exists
- **Zero rollback data loss:** No database turn destroyed by a state machine exception

## User Journeys

### Journey 1: Sam — Monitoring Agents, Everything Works

Sam kicks off three agents across different projects. He tells one to refactor a service, switches to another to review its output, then checks on the third. Each time he opens the voice chat, the conversation is complete — agent responses are there, questions are visible, state indicators are accurate. He responds to one agent's question, sees it transition to PROCESSING, and moves on. The dashboard is a reliable command center. He never thinks about the plumbing.

**Capabilities revealed:** Real-time turn delivery via hooks, accurate state display, seamless multi-agent switching.

### Journey 2: Sam — Hook Fails, System Self-Heals

Sam sends a command to an agent running a complex multi-step task. The agent spawns a background Explore sub-agent, finishes its work, and outputs a response. The `stop` hook fires but hits a state machine edge case — the turn creation is rolled back. Sam doesn't see the response appear immediately, but within 10 seconds the transcript reconciler reads the JSONL, detects the missing turn, creates it, triggers the appropriate state transition, and broadcasts it via SSE. The turn slides into the chat as if nothing happened. Sam, who was checking another agent anyway, comes back and sees the complete conversation. He never knew anything went wrong.

**Capabilities revealed:** Transcript reconciliation creating missing turns, decoupled turn persistence from state transitions, recovered turns feeding back into the task lifecycle, SSE broadcast of recovered turns.

### Journey 3: Sam — Delayed Recovery, Still Complete

Sam starts an agent on a long-running task and walks away. While he's gone, the agent produces several responses. Some hooks fire, some don't. The JSONL transcript writes are delayed by a few seconds each. Over the next minute, the reconciler processes each JSONL entry as it arrives — creating turns for the ones hooks missed, correcting timestamps on the ones hooks got. When Sam comes back 20 minutes later, the chat is complete and in correct chronological order. Every turn is there.

**Capabilities revealed:** Reconciler handling multiple recovery events over time, timestamp correction, chronological ordering resilience, completeness guarantee regardless of hook reliability.

### Journey 4: Agent — Debugging Recovery Events

A Claude Code agent is asked to investigate why a turn appeared with a slight delay. It reads the application logs filtered at INFO level and sees a clear chain: `[RECONCILER] No matching turn found for JSONL entry hash abc123 — creating new turn (turn_id=456, agent_id=583, intent=QUESTION)`. At DEBUG level, it sees the preceding hook failure: `[HOOK_RECEIVER] process_stop failed: InvalidTransitionError(AWAITING_INPUT, AGENT, QUESTION) — turn rolled back`. The agent can trace the full sequence: hook arrived → turn created → state transition failed → rollback → JSONL arrived → reconciler created turn → state transition applied → SSE broadcast. Clean, readable, actionable.

**Capabilities revealed:** Structured logging at appropriate levels, full recovery chain traceability, agent-readable diagnostics.

### Journey Requirements Summary

| Capability | Revealed By |
|------------|-------------|
| Hook-based optimistic turn delivery | Journey 1 |
| Transcript reconciler creating missing turns | Journeys 2, 3 |
| Decoupled turn persistence from state transitions | Journey 2 |
| Recovered turns triggering state transitions | Journeys 2, 3 |
| SSE broadcast of recovered turns | Journeys 2, 3 |
| Timestamp correction & chronological ordering | Journey 3 |
| Structured recovery logging (INFO/DEBUG) | Journey 4 |
| Full recovery chain traceability | Journey 4 |
| Tmux watchdog for early gap detection (when available) | Journeys 2, 3 |

## Product Scope

### Scope

**Approach:** Problem-solving — fix the reliability pipeline so turns are never silently lost.

**Resource Requirements:** Single developer. Changes to existing Python services only — no new infrastructure, dependencies, or frontend changes.

**Core Journeys Supported:** All four journeys.

**Must-Have Capabilities:**

1. **Transcript reconciler fix** — When a JSONL entry has no matching database turn, create one. No silent skipping. Single most critical fix.
2. **Decouple turn persistence from state transitions** — Turn commit happens before state transition attempt. If the transition fails, the turn is already persisted.
3. **State machine gap-filling** — Add missing transition entries for edge cases (AWAITING_INPUT agent transitions fixed in `179f87c`; audit for other gaps).
4. **Recovered turns feed into lifecycle** — Reconciler-created turns call into `TaskLifecycleManager` to trigger implied state transitions.
5. **Recovery logging** — INFO for recovery actions, WARNING for hook failures, DEBUG for full diagnostic chain.
6. **Force reconciliation** — On-demand reconciliation trigger from agent card kebab menu.
7. **Tmux pane watchdog** — Detects agent output not reflected in the database within 5 seconds, triggers early reconciliation before JSONL arrives. Operates as the real-time bridge between "hook didn't fire" and "transcript hasn't arrived yet." Degrades gracefully when tmux is unavailable (relies on JSONL reconciliation alone).

**Explicit exclusions:**
- No dashboard metrics for recovery health
- No client-side changes
- No new SSE event types
- No changes to file watcher polling interval

### Future Considerations

These are out of scope for this change but noted for reference:

- **Self-tuning reliability** — System learns which hook events are unreliable and pre-emptively triggers transcript checks
- **Hook reliability scoring** — Per-event-type reliability metrics
- **Reconciliation health metrics** — Dashboard visibility into recovery frequency per agent

### Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Refactoring `hook_receiver.py` turn persistence breaks happy path | High | Targeted tests for commit-before-transition pattern; run existing test suite before/after |
| Reconciler creates duplicate turns | Medium | Existing `jsonl_entry_hash` deduplication column on Turn model |
| Regression in hook processing | High | Run existing test suite for affected services (hook_receiver, task_lifecycle, state_machine) |

## Technical Architecture

### Project-Type Overview

This PRD targets the server-side turn capture reliability pipeline within an existing Flask web application. The client-side rendering (voice chat, SSE handling, gap recovery) is already functional and does not need modification. The database is the ultimate source of truth — if a turn exists in the database, it will appear in the chat (via SSE or page reload).

### Real-Time Delivery Model

- SSE remains the primary delivery mechanism for new and recovered turns
- Existing SSE gap recovery (re-fetch transcript on reconnect) is sufficient — no changes needed
- Page reload always reflects complete database state — the fallback guarantee
- No new client-side changes required

### Reconciliation Performance

- Target recovery latency: within 10 seconds of JSONL write
- Hard ceiling: 60 seconds — beyond this indicates a system failure
- On-demand reconciliation: within 5 seconds for a single agent

### Concurrency Model

- Multiple agents produce concurrent JSONL files, each watched and reconciled independently
- No immediate scaling changes needed — address empirically when agent counts create impact
- Design reconciliation changes to be stateless and agent-scoped to minimise concurrency risk

### Brownfield Constraints

- All changes integrate with existing services: `TranscriptReconciler`, `FileWatcher`, `HookReceiver`, `TaskLifecycleManager`, `StateMachine`
- Existing service registration pattern via `app.extensions` maintained
- No new database tables — changes to service logic and possibly new columns on existing Turn model
- SSE event types (`turn_created`, `turn_updated`) already defined and sufficient

## Functional Requirements

### Turn Capture & Persistence

- **FR1:** The system can create a Turn record from a hook event independently of any state transition succeeding or failing
- **FR2:** The system can persist a Turn to the database before attempting a state transition, ensuring the Turn survives state machine exceptions
- **FR3:** The system can broadcast a `turn_created` SSE event for every successfully persisted Turn, regardless of how it was created (hook, reconciliation, or recovery)
- **FR4:** The system can preserve Turn data when a database rollback occurs in a downstream operation by using separate transaction scopes

### Transcript Reconciliation

- **FR5:** The system can match JSONL transcript entries to existing database Turns using content-based hashing
- **FR6:** The system can create a new Turn when a JSONL entry has no matching database Turn, with no edge cases that silently skip creation
- **FR7:** The system can correct Turn timestamps from server-approximate to JSONL-authoritative when a match is found
- **FR8:** The system can process JSONL entries for multiple concurrent agents without interference between reconciliation operations
- **FR9:** The system can complete reconciliation of a JSONL entry within 60 seconds of the entry being written (hard ceiling)
- **FR10:** The system can deduplicate JSONL entries to prevent the same transcript entry from creating multiple Turns

### State Machine Resilience

- **FR11:** The system can handle agent turns from any current state without raising unhandled exceptions that destroy data
- **FR12:** The system can validate state transitions and reject invalid ones while preserving the Turn that triggered the attempt
- **FR13:** The system can maintain correct agent state when a transition is rejected (state remains unchanged, no corruption)
- **FR14:** The system can accept transitions for edge cases where agents produce output from non-standard states (e.g., AWAITING_INPUT → AWAITING_INPUT for follow-up questions)

### Recovery Lifecycle Integration

- **FR15:** The system can feed reconciler-created Turns into the TaskLifecycleManager to trigger appropriate state transitions
- **FR16:** The system can detect the intent of a recovered Turn (QUESTION, COMPLETION, PROGRESS, END_OF_TASK) and apply the corresponding state transition
- **FR17:** The system can transition agent state based on a recovered Turn (e.g., a recovered QUESTION turn transitions agent to AWAITING_INPUT)
- **FR18:** The system can broadcast SSE events for state transitions triggered by recovered Turns

### Observability & Diagnostics

- **FR19:** The system can log every hook processing failure at WARNING level with the error context (state, actor, intent, exception)
- **FR20:** The system can log every recovery action at INFO level (Turn created via reconciliation, state transition applied)
- **FR21:** The system can log full diagnostic chains at DEBUG level (hook arrival → failure → JSONL arrival → reconciliation → recovery)
- **FR22:** An agent can trace a recovery event from hook failure through to Turn creation by reading application logs

### On-Demand Operations

- **FR23:** The user can trigger a forced reconciliation for a specific agent from the agent card's kebab menu in the dashboard

### Tmux Gap Detection

- **FR24:** The system can monitor tmux pane output for agent content not reflected in the database
- **FR25:** The system can trigger early reconciliation when tmux monitoring detects a gap between pane output and database state
- **FR26:** The system can operate without tmux monitoring when tmux is unavailable, relying on JSONL reconciliation alone

## Non-Functional Requirements

### Performance

- **NFR1:** Hook-originated turns persisted to database within 200ms of hook receipt (must not regress)
- **NFR2:** Reconciler-created turns persisted within 10 seconds of JSONL write (target), hard ceiling 60 seconds
- **NFR3:** Decoupling turn persistence from state transitions adds no more than 50ms latency to hook processing
- **NFR4:** Force reconciliation (on-demand) completes within 5 seconds for a single agent's transcript

### Reliability

- **NFR5:** Turn capture rate: 100% — every JSONL transcript entry has a corresponding database Turn
- **NFR6:** Recovery is automatic — no human intervention required when hooks fail and JSONL data exists
- **NFR7:** State machine exceptions never result in data loss — failed transitions do not cascade to Turn rollbacks
- **NFR8:** Reconciler is idempotent — running multiple times against the same JSONL data does not create duplicates
- **NFR9:** Concurrent reconciliation for multiple agents does not corrupt shared state or create cross-agent data leakage

### Testability

- **NFR10:** Each recovery path (hook failure → reconciler recovery, state machine rejection → turn preservation) independently testable with targeted unit tests
- **NFR11:** Reconciler invocable on-demand for a specific agent, enabling manual verification and debugging
- **NFR12:** Recovery events produce sufficient log output at INFO/DEBUG to reconstruct the full recovery chain without source code access
