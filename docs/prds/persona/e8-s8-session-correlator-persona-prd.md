---
validation:
  status: valid
  validated_at: '2026-02-20T17:23:58+11:00'
---

## Product Requirements Document (PRD) — SessionCorrelator Persona Assignment

**Project:** Claude Headspace
**Scope:** Extend SessionCorrelator and hook receiver to assign persona identity to agents at registration time
**Author:** Sam (workshopped with Claude)
**Status:** Draft
**Epic:** 8 — Personable Agents
**Sprint:** 8 (E8-S8)

---

## Executive Summary

This PRD defines the requirements for connecting Persona database records to running agents by detecting a persona slug in the `session-start` hook payload and setting `agent.persona_id` at registration time. This is a surgical extension to the existing SessionCorrelator and hook receiver — it adds persona lookup and assignment to the agent creation path without altering the existing 6-strategy correlation cascade.

This capability is the pivotal link in the persona pipeline. Prior sprints establish the Persona model (E8-S1), Agent.persona_id FK (E8-S4), persona filesystem assets (E8-S5), and persona-aware agent creation API (E8-S7). This sprint wires the hook receiver — the primary agent creation path for Claude Code sessions — to those foundations. Without it, personas exist in the database but are never connected to running sessions.

Downstream sprints depend on this: skill file injection (E8-S9) reads `agent.persona_id` to locate skill files; dashboard identity (E8-S10) reads `agent.persona` to display persona names. This sprint is on the critical path.

---

## 1. Context & Purpose

### 1.1 Context

Agents in Claude Headspace are currently anonymous — identified only by UUID. The Agent Teams Workshop (Decision 4.1) resolved that persona assignment happens at registration time, not post-hoc: when a `session-start` hook fires with a persona slug in the payload, the SessionCorrelator looks up the Persona record and sets `agent.persona_id` on the newly created Agent. Anonymous agents (no persona slug) continue working exactly as before.

The two assignment paths that converge here:
1. **CLI-initiated:** `claude-headspace start --persona con` — operator's ad-hoc launch. The CLI passes persona slug in the session-start hook payload.
2. **System-initiated:** `create_agent(persona_slug="con")` — the production path for dashboard or automation. Also passes persona slug through to the hook payload.

Both paths result in the same outcome: SessionCorrelator creates an Agent with `persona_id` set.

### 1.2 Target User

Operators (Sam) launching Claude Code sessions with persona identity, and the downstream persona pipeline (skill injection, dashboard identity, handoff) that depends on `agent.persona_id` being set at registration.

### 1.3 Success Moment

Operator runs `claude-headspace start --persona con`. The session-start hook fires with `persona_slug: "con"`. SessionCorrelator looks up the Con persona, creates the agent with `persona_id` set, and logs "Persona assigned: con (id=1) to agent 42." The agent is now a named team member, ready for skill injection and dashboard identity.

---

## 2. Scope

### 2.1 In Scope

- Extract persona slug from the `session-start` hook payload
- Pass persona slug through the hook processing chain to SessionCorrelator
- Look up Persona record by slug when creating a new agent
- Set `agent.persona_id` on the Agent record at creation time
- Log persona assignment (persona slug, persona ID, agent ID)
- Graceful degradation when persona slug is present but Persona record not found in DB (log warning, create agent without persona, do not block registration)
- Backward compatibility: no persona slug in payload results in `persona_id = NULL` (existing behaviour unchanged)

### 2.2 Out of Scope

- Post-hoc persona reassignment (excluded by Workshop Decision 4.1 — no brain transplants)
- Persona or Agent model creation/migration (E8-S1 and E8-S4 respectively — prerequisites)
- Hook payload schema changes on the Claude Code / CLI side (E8-S7 — prerequisite)
- Skill file injection after persona assignment (E8-S9 — downstream)
- Dashboard identity display changes (E8-S10 — downstream)
- Persona assignment via non-hook paths (API-based `create_agent` persona support is E8-S7)
- Event system integration beyond logging (no new Event types required)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A `session-start` hook with `persona_slug` in the payload results in an Agent record with `persona_id` set to the matching Persona's ID
2. A `session-start` hook without `persona_slug` in the payload results in an Agent record with `persona_id = NULL` (existing behaviour preserved)
3. A `session-start` hook with a `persona_slug` that does not match any Persona in the database results in an Agent created without persona, a warning logged, and no error returned to the hook caller
4. The `agent.persona` relationship is navigable after assignment (e.g., `agent.persona.name` returns the persona's display name)
5. SessionCorrelator's existing 6-strategy cascade (cache, DB session ID, headspace UUID, tmux pane, working directory, create) behaves identically for non-persona sessions — no regressions
6. Persona assignment is logged with sufficient detail for debugging (persona slug, persona ID, agent ID)

### 3.2 Non-Functional Success Criteria

1. Persona lookup adds negligible latency to the session-start hook processing path (single DB query by indexed slug column)
2. No additional database round-trips for sessions without a persona slug
3. Thread-safe: persona lookup and assignment are safe under concurrent hook processing

---

## 4. Functional Requirements (FRs)

**FR1: Persona slug received from hook pipeline**
The `session-start` hook processing chain receives `persona_slug` and `previous_agent_id` as optional fields already extracted by S7's hook route extension. When `persona_slug` is present and non-empty, persona assignment proceeds. When absent or empty, persona assignment is skipped entirely. S7 owns the route-level extraction — this sprint consumes the extracted values.

**FR2: Persona slug and previous_agent_id passthrough to SessionCorrelator**
The persona slug and `previous_agent_id` received from the hook processing chain (extracted by S7) shall be passed to the SessionCorrelator's agent creation logic. The persona slug shall not be used for session correlation itself — only for persona assignment after the agent is created. The `previous_agent_id` shall be set directly on the Agent record when provided, establishing the handoff continuity chain.

**FR3: Persona lookup by slug**
When creating a new agent and a persona slug is provided, the system shall look up the Persona record by its `slug` field. The lookup shall use the existing database session (no separate connection).

**FR4: Agent persona_id and previous_agent_id assignment**
When a Persona record is found for the provided slug, the system shall set `agent.persona_id` to the Persona's database ID on the newly created Agent record. When `previous_agent_id` is provided, the system shall set `agent.previous_agent_id` to the given value. Both assignments happen at creation time — before the agent record is committed.

**FR5: Persona not found — graceful degradation**
When a persona slug is provided but no matching Persona record exists in the database, the system shall:
- Log a warning with the unrecognised slug
- Create the agent without a persona (persona_id = NULL)
- Return success to the hook caller (do not block agent registration)

**FR6: No persona slug — existing behaviour unchanged**
When no persona slug is present in the hook payload, the entire persona assignment path is skipped. Agent creation follows the existing logic with `persona_id = NULL`. No additional database queries are made.

**FR7: Persona assignment logging**
When a persona is successfully assigned to an agent, the system shall log the assignment at INFO level with: persona slug, persona database ID, and agent database ID.

**FR8: Correlation cascade unaffected**
The SessionCorrelator's existing 6-strategy correlation cascade (cache lookup, DB session ID, headspace UUID, tmux pane, working directory, create new) shall not be modified for non-persona sessions. Persona assignment only applies when a new agent is being created (strategy 6) and a persona slug is provided.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Performance — minimal overhead**
Persona lookup shall be a single indexed query. No additional database round-trips shall occur for sessions without a persona slug.

**NFR2: Thread safety**
Persona lookup and assignment shall be safe under concurrent hook processing. The existing transaction scope (SessionCorrelator's `db.session.commit()`) shall encompass the persona assignment — no separate commit required.

**NFR3: Backward compatibility**
All existing tests for SessionCorrelator, hook receiver, and hooks route shall continue to pass without modification (except where new persona-specific tests are added). Existing hook payloads without `persona_slug` shall be processed identically to today.

---

## 6. Integration Points

**Modified subsystems (context for orchestrator):**

- **Hook route** (`routes/hooks.py`): Receives `persona_slug` and `previous_agent_id` already extracted by S7's hook route extension — no additional extraction needed in this sprint
- **SessionCorrelator** (`services/session_correlator.py`): Accept `persona_slug` and `previous_agent_id` parameters, perform Persona lookup, set `agent.persona_id` and `agent.previous_agent_id` during agent creation
- **Hook receiver** (`services/hook_receiver.py`): Accept and pass through `persona_slug` and `previous_agent_id` parameters in `process_session_start()`

**Dependencies (must be complete before this sprint):**

- E8-S1: Persona database model with `slug` field (indexed, unique)
- E8-S4: Agent model `persona_id` FK to Persona table
- E8-S7: Hook payload carries `persona_slug` field from CLI/API

**Downstream dependents (consume persona_id set by this sprint):**

- E8-S9: Skill file injection reads `agent.persona_id` to locate skill files
- E8-S10: Dashboard card reads `agent.persona` for identity display

---

## 7. Error Handling Summary

| Scenario | Behaviour |
|----------|-----------|
| `persona_slug` present, Persona found | Set `agent.persona_id`, log assignment |
| `persona_slug` present, Persona not found | Create agent without persona, log warning |
| `persona_slug` absent or empty | Skip persona logic entirely, no extra queries |
| `persona_slug` present, DB error during lookup | Log error, create agent without persona (don't block registration) |
