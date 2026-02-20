---
validation:
  status: invalid
  invalidated_reason: 'PRD amended post-evaluation — added previous_agent_id parameter, clarified hook extraction ownership. Requires revalidation.'
---

## Product Requirements Document (PRD) — Persona-Aware Agent Creation

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 7 (E8-S7) — Extend agent creation paths with optional persona parameter
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

This PRD covers wiring persona identity through both agent creation paths — the programmatic `create_agent()` function and the CLI `claude-headspace start` command — so that persona slug is carried through to the `session-start` hook payload. This is a plumbing sprint: it connects persona registration (S6) and the Agent model's `persona_id` FK (S4) to the hook-driven registration pipeline, enabling the SessionCorrelator (S8) to set `agent.persona_id` at registration time.

The sprint delivers an optional `persona_slug` parameter on `create_agent()`, an optional `--persona <slug>` flag on the CLI, persona slug validation against the database before session launch, and an extended hook payload that includes the persona slug when present. All changes are backward compatible — omitting the persona parameter preserves existing anonymous agent behaviour identically.

Two creation paths converge to the same pipeline (workshop decision 4.1): `create_agent()` for programmatic/dashboard use, and `claude-headspace start --persona` as the operator's escape hatch for ad-hoc persona sessions. Both pass the persona slug through session metadata to the hook notification script, which includes it in the `session-start` hook payload. The session starts as a vanilla Claude Code session — persona injection is a separate concern (S9).

---

## 1. Context & Purpose

### 1.1 Context

Epic 8 introduces named personas as first-class entities in Claude Headspace. Sprints 1-4 established the data foundation (Role, Persona, Organisation, Position models and Agent extensions). Sprint 5 established the filesystem asset convention. Sprint 6 delivered persona registration — personas now exist in the database with skill files on disk.

The missing link is the agent creation pipeline. Currently, `create_agent()` takes only a `project_id` and spawns an anonymous Claude Code session. The CLI `claude-headspace start` launches sessions without any persona awareness. There is no mechanism to associate a persona with an agent at creation time, and the `session-start` hook payload carries no persona information.

Sprint 7 bridges this gap: it extends both creation paths to accept an optional persona slug, validates it against the database, and carries it through to the hook payload where Sprint 8's SessionCorrelator can consume it.

### 1.2 Target User

- **Operator (Sam):** Uses `claude-headspace start --persona con` for ad-hoc persona sessions — debugging skill files, testing persona behaviour, quick one-off tasks.
- **System (Dashboard/Automation):** Calls `create_agent(project_id=1, persona_slug="con")` for programmatic agent creation — dashboard "create agent" action, future PM automation (Gavin v3).

### 1.3 Success Moment

The operator runs `claude-headspace start --persona con` and the session-start hook payload arrives at the server with `persona_slug: "con"` included. Or: the dashboard triggers `create_agent(project_id=1, persona_slug="con")` and the same hook payload arrives. In both cases, the persona slug is present and ready for Sprint 8's SessionCorrelator to consume. If the persona slug doesn't exist in the database, a clear error appears before any session is launched.

---

## 2. Scope

### 2.1 In Scope

- `create_agent()` gains an optional `persona_slug` parameter
- `create_agent()` gains an optional `previous_agent_id` integer parameter for establishing handoff continuity chains (consumed by E8-S14)
- `create_agent()` validates the persona slug against the Persona table before session launch
- `create_agent()` passes the persona slug to the CLI command when spawning the tmux session
- `claude-headspace start` gains an optional `--persona <slug>` flag
- CLI validates the persona slug against the database before launching the Claude Code session
- Persona slug and `previous_agent_id` are passed through the session environment so the hook notification script can access them
- Hook notification script (`notify-headspace.sh`) reads persona slug and `previous_agent_id` from the environment and includes them in the hook payload when present
- Hook route (`/hook/session-start`) extracts persona slug and `previous_agent_id` from the payload and makes them available to downstream processing (S7 owns this extraction — S8 consumes these values without re-extracting)
- Backward compatibility: all existing behaviour preserved when persona is not specified

### 2.2 Out of Scope

- Setting `agent.persona_id` on the Agent record at registration (Sprint 8: SessionCorrelator)
- Skill file injection via tmux bridge post-registration (Sprint 9)
- Dashboard display of persona identity on agent cards (Sprints 10-11)
- Post-hoc persona reassignment — assigning a persona to an already-running anonymous agent (excluded by design, workshop decision 4.1)
- Persona registration CLI/API (already delivered in Sprint 6)
- Persona model or Agent model changes (already delivered in Sprints 1 and 4)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. `create_agent(project_id=X, persona_slug="con")` launches a tmux session where the hook payload includes `persona_slug: "con"`
2. `create_agent(project_id=X)` (no persona_slug) launches a tmux session with no persona information in the hook payload — identical to current behaviour
3. `claude-headspace start --persona con` launches a session where the hook payload includes `persona_slug: "con"`
4. `claude-headspace start` (no flag) launches a session with no persona information — identical to current behaviour
5. Providing a persona slug that does not exist in the Persona table produces a clear error and does not launch a session
6. The `session-start` hook payload includes `persona_slug` and `previous_agent_id` as optional fields when present
7. The hook route extracts `persona_slug` and `previous_agent_id` from the session-start payload and passes them to downstream processing (S7 owns this extraction)

### 3.2 Non-Functional Success Criteria

1. No change to session startup latency beyond the persona validation query (single indexed lookup)
2. Existing anonymous agent creation continues to work identically — no regression
3. Hook payload remains backward compatible — absence of `persona_slug` is the default, not an error

---

## 4. Functional Requirements (FRs)

**FR1: Programmatic Agent Creation with Persona and Continuity**

`create_agent()` in `agent_lifecycle.py` accepts an optional `persona_slug` string parameter and an optional `previous_agent_id` integer parameter. When `persona_slug` is provided, it is included in the CLI command arguments when spawning the tmux session. When `previous_agent_id` is provided, it is passed through to the session metadata so the hook pipeline can set `agent.previous_agent_id` at registration time (consumed by E8-S14 for handoff continuity chains).

**FR2: Persona Slug Validation (Programmatic Path)**

When `create_agent()` receives a `persona_slug`, it queries the Persona table to verify a record with that slug exists and has status "active". If the persona is not found or is not active, `create_agent()` returns a failure result with a descriptive error message and does not launch a session.

**FR3: CLI Persona Flag**

`claude-headspace start` accepts an optional `--persona <slug>` argument. The flag is optional — omitting it produces the same behaviour as today (anonymous session).

**FR4: Persona Slug Validation (CLI Path)**

When the CLI receives `--persona`, it validates the slug against the database before proceeding with session launch. If the persona is not found or not active, the CLI prints an error message and exits with a non-zero exit code without launching Claude Code.

**FR5: Session Metadata Propagation**

The persona slug and `previous_agent_id` (when provided) are passed through to the Claude Code session environment so that the hook notification script can access them. The propagation mechanism carries these values from the CLI process to the hook script process without requiring changes to Claude Code itself.

**FR6: Hook Payload Extension**

The hook notification script (`notify-headspace.sh`) reads the persona slug and `previous_agent_id` from the session environment and includes them as `persona_slug` and `previous_agent_id` in the JSON payload sent to the `/hook/session-start` endpoint. When either value is not present in the environment, the corresponding field is omitted from the payload (not sent as null or empty).

**FR7: Hook Route Extraction (S7 Owns This)**

The `/hook/session-start` route handler extracts `persona_slug` and `previous_agent_id` from the incoming payload (when present) and passes them to downstream hook processing. S7 owns this extraction — S8 consumes these values as inputs without re-implementing the extraction. This makes both values available for Sprint 8's SessionCorrelator to use when creating/updating the Agent record.

**FR8: Backward Compatibility**

All existing agent creation flows continue to work unchanged:
- `create_agent(project_id=X)` without persona_slug works identically to today
- `claude-headspace start` without `--persona` works identically to today
- Hook payloads without `persona_slug` are processed identically to today
- No existing tests break

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Validation Performance**

Persona slug validation is a single database lookup on the `slug` column (unique index). The query adds negligible latency to agent creation (<10ms).

**NFR2: Error Clarity**

Invalid persona slug errors clearly state: (a) the slug that was not found, and (b) guidance to register the persona first (referencing Sprint 6's registration capability).

**NFR3: No Claude Code Modifications**

All persona metadata propagation uses environment variables and existing hook infrastructure. No changes to Claude Code itself are required — the persona slug flows through the session environment that Claude Code inherits and passes to hooks via `notify-headspace.sh`.

---

## 6. Technical Decisions (All Decided)

All architectural decisions for this sprint were resolved in the Agent Teams Design Workshop (`docs/workshop/agent-teams-workshop.md`):

| Decision | Resolution | Source |
|----------|-----------|--------|
| Two creation paths converge to same pipeline | CLI for operator ad-hoc, `create_agent()` for programmatic use | Workshop 4.1 |
| Vanilla session starts first | Persona injection is separate (S9) — S7 only carries the slug | Workshop 3.2 |
| No post-hoc persona reassignment | Brain transplants excluded — start with persona or stay anonymous | Workshop 4.1 |
| Persona slug validated before launch | Invalid slugs fail fast, don't launch orphaned sessions | Workshop 4.1, roadmap |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|-----------|--------|-----------------|
| E8-S1 | Role + Persona Models | Persona table to validate slugs against |
| E8-S4 | Agent Model Extensions | `Agent.persona_id` FK (consumed by S8, not S7) |
| E8-S6 | Persona Registration | Personas exist in DB to reference |

---

## 8. Integration Points

| Component | Current State | Change Required |
|-----------|--------------|----------------|
| `agent_lifecycle.py` → `create_agent()` | Takes `project_id` only | Add optional `persona_slug` parameter, validation, pass to CLI args |
| `cli/launcher.py` → `cmd_start()` | `--bridge/--no-bridge` flags only | Add `--persona <slug>` flag, validation, env var propagation |
| `bin/notify-headspace.sh` | Reads session metadata from env vars | Read persona slug env var, include in hook payload |
| `routes/hooks.py` → `hook_session_start()` | Extracts session_id, working_dir, etc. | Extract `persona_slug` and `previous_agent_id` from payload, pass downstream (S7 owns this extraction) |
| `hook_receiver.py` → `process_session_start()` | No persona awareness | Accept and pass through `persona_slug` and `previous_agent_id` parameters (S8 will act on them) |

---

## 9. Acceptance Criteria

- [ ] `create_agent(project_id=X, persona_slug="con")` launches a session with persona metadata
- [ ] `create_agent(project_id=X, persona_slug="nonexistent")` returns failure with clear error
- [ ] `create_agent(project_id=X)` (no persona) works identically to current behaviour
- [ ] `claude-headspace start --persona con` launches a session with persona metadata
- [ ] `claude-headspace start --persona nonexistent` exits with error, does not launch
- [ ] `claude-headspace start` (no flag) works identically to current behaviour
- [ ] `session-start` hook payload includes `persona_slug: "con"` when persona specified
- [ ] `session-start` hook payload has no `persona_slug` field when persona not specified
- [ ] Hook route extracts `persona_slug` and `previous_agent_id` and passes both to downstream processing
- [ ] `create_agent(project_id=X, persona_slug="con", previous_agent_id=42)` passes `previous_agent_id` through to the hook payload
- [ ] `previous_agent_id` absent from hook payload when not specified (backward compatible)
- [ ] All existing agent creation tests continue to pass
- [ ] Invalid persona slug errors clearly name the slug and suggest registration
