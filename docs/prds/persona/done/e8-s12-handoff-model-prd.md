---
validation:
  status: valid
  validated_at: '2026-02-20T17:23:59+11:00'
---

## Product Requirements Document (PRD) — Handoff Database Model

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 12 — Handoff table for agent context handoff metadata
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

When a Claude Code agent hits its context limit during long-running work, the operator triggers a handoff: the outgoing agent writes a first-person context document, and a successor agent picks up where it left off. The Handoff database model is the metadata layer that makes this possible — storing the reason for the handoff, the path to the handoff document on disk, and the injection prompt sent to the successor agent via tmux bridge.

This sprint creates a single new table: `Handoff`. Each record belongs to an outgoing agent (the one that produced the handoff) and captures the orchestration metadata needed by Sprint 13's trigger UI and Sprint 14's execution flow. The model follows the hybrid storage design from workshop decision 5.1 — the database stores lightweight metadata and the injection prompt, while the detailed handoff document lives on the filesystem at `data/personas/{slug}/handoffs/`.

The successor agent discovers the handoff in two ways: it receives the `injection_prompt` directly via tmux bridge (immediate bootstrap), and it can find the handoff record via the `previous_agent_id` chain on Agent (for system/operator querying). This sprint is purely the data model and migration — no service layer, no UI, no execution logic.

---

## 1. Context & Purpose

### 1.1 Context

The Agent Teams Design Workshop (decision 5.1) resolved the handoff storage strategy as a hybrid approach: database for orchestration metadata, filesystem for rich context content. The Agent model already supports continuity chains via `previous_agent_id` (E8-S4), which links consecutive agents working on the same body of work. What's missing is the record of *what was handed off* between those agents — the reason, the file location, and the prompt used to bootstrap the successor.

The existing data model has no concept of handoff. Without this table, Sprint 13 (handoff trigger UI) has nowhere to write handoff metadata, and Sprint 14 (handoff execution) has no record to read the injection prompt from.

Design decisions for this model were resolved in workshop decision 5.1 (Handoff Design Hooks). See `docs/workshop/agent-teams-workshop.md`.

### 1.2 Target User

The Claude Headspace application, which needs to persist handoff metadata for the handoff execution pipeline (S14) and provide queryable handoff history for operator inspection. The operator benefits through auditable handoff records — reviewing what was handed off, why, and what prompt was sent to the successor.

### 1.3 Success Moment

After running the migration, a Handoff record can be created for an outgoing agent with a reason, file path, and injection prompt. `Handoff.agent` navigates to the Agent that produced it. `Agent.handoff` returns the handoff record if one exists. Existing tables and queries are unaffected.

---

## 2. Scope

### 2.1 In Scope

- New `Handoff` database table with integer primary key
- Fields: `id` (int PK), `agent_id` (int FK to Agent, not null), `reason` (str, not null), `file_path` (str, nullable), `injection_prompt` (text, nullable), `created_at` (datetime)
- `reason` captures why the handoff occurred — one of: "context_limit", "shift_end", "task_boundary"
- `file_path` stores the path to the handoff document on disk (e.g., `data/personas/developer-con-1/handoffs/20260220T143025-4b6f8a2c.md`)
- `injection_prompt` stores the full orchestration prompt sent to the successor agent via tmux bridge
- Relationship: `Handoff.agent` → Agent (many-to-one — the outgoing agent that produced this handoff)
- Relationship: `Agent.handoff` → Handoff (one-to-one — an agent produces at most one handoff)
- Single Alembic migration creating the `handoff` table
- Model registration in the models package
- All existing tables, queries, services, and routes unaffected

### 2.2 Out of Scope

- Handoff trigger UI or context threshold monitoring (E8-S13)
- Handoff execution flow, orchestration logic, or tmux bridge integration (E8-S14)
- Handoff file creation or filesystem management (E8-S14)
- Any service layer for handoff operations
- Dashboard display of handoff data
- Handoff file cleanup or lifecycle management (deferred to future system management PRD)
- Agent model changes — `previous_agent_id` already exists from E8-S4
- Enforcement of the one-to-one constraint at database level — application-level check is sufficient
- Validation or enum constraint on `reason` values at database level — application-level validation

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Handoff table exists in the database after running the Alembic migration
2. A Handoff record can be created with `agent_id`, `reason`, `file_path`, and `injection_prompt`
3. `Handoff.agent` relationship navigates to the Agent that produced the handoff
4. `Agent.handoff` relationship returns the Handoff record when one exists, and `None` when it does not
5. Multiple handoff records can reference different agents
6. Existing Agent, Command, Turn, Event, and all other tables are unaffected by the migration

### 3.2 Non-Functional Success Criteria

1. Migration is additive — no data transformation, no destructive changes, no downtime required
2. All existing queries and services continue working without modification
3. Model follows established codebase patterns (SQLAlchemy 2.0+ `Mapped` type hints, `mapped_column`, `relationship` with `back_populates`)

---

## 4. Functional Requirements (FRs)

**FR1:** The system shall store handoff records in a dedicated `Handoff` table with an integer primary key.

**FR2:** Each handoff record shall reference the outgoing agent (the agent that produced the handoff) via a non-nullable foreign key to the Agent table (ON DELETE CASCADE).

**FR3:** Each handoff record shall capture the reason for the handoff as a non-nullable string field. Valid reasons are "context_limit" (agent hit context window limit), "shift_end" (operator-initiated end of work session), and "task_boundary" (natural breakpoint between tasks).

**FR4:** Each handoff record shall store the filesystem path to the handoff document as a nullable string field. This path points to the detailed markdown document written by the outgoing agent (e.g., `data/personas/developer-con-1/handoffs/20260220T143025-4b6f8a2c.md`).

**FR5:** Each handoff record shall store the injection prompt as a nullable text field. This is the full orchestration message sent to the successor agent via tmux bridge — e.g., "Continuing from Agent 4b6f8a2c. Read `data/personas/developer-con-1/handoffs/20260220T143025-4b6f8a2c.md` to pick up context."

**FR6:** Each handoff record shall have a `created_at` timestamp defaulting to the current time.

**FR7:** The `Handoff.agent` relationship shall navigate from a handoff record to its outgoing Agent.

**FR8:** The `Agent.handoff` relationship shall navigate from an agent to its handoff record (if one exists). An agent has at most one handoff — if it already has one, the application layer is responsible for handling that case.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The migration shall be additive and non-breaking — creating a new table with no changes to existing tables.

**NFR2:** The model shall follow established codebase conventions: SQLAlchemy 2.0+ declarative syntax with `Mapped` type hints, `mapped_column`, and `relationship` with `back_populates`.

**NFR3:** Backward compatibility — all existing queries, services, routes, and tests shall continue working without modification.

---

## 6. Technical Context

*This section provides implementation guidance for the orchestration engine. These are conventions and patterns, not requirements.*

**New file:** `src/claude_headspace/models/handoff.py`

**Model registration:** Add `Handoff` import and export in `src/claude_headspace/models/__init__.py`

**Agent relationship:** Add `handoff` relationship on the existing Agent model with `back_populates="agent"` and `uselist=False` (one-to-one)

**Migration:** New Alembic migration creating the `handoff` table with columns matching FRs 1-6

**Reference model pattern (from codebase):**

```python
# Example pattern — not prescriptive implementation
class Handoff(db.Model):
    __tablename__ = "handoff"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agent.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    injection_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped["Agent"] = relationship("Agent", back_populates="handoff")
```

**Integration points:**

- Used by E8-S13 (handoff trigger UI creates the button based on agent state)
- Used by E8-S14 (handoff execution creates Handoff records and reads `injection_prompt` for successor bootstrap)
- Queryable via `previous_agent_id` chain — follow Agent.previous_agent → find predecessor's Handoff record

**Design decisions (all resolved — see workshop 5.1):**

- Hybrid handoff storage: DB metadata + filesystem content
- DB stores the injection prompt sent directly to successor
- Filesystem stores the detailed handoff document read by successor via tools
- Handoff belongs to outgoing agent; successor finds via `previous_agent_id` chain
- Integer PK consistent with codebase convention

---

## 7. Dependencies

| Dependency | Sprint | Status | What It Provides |
|------------|--------|--------|------------------|
| Agent.previous_agent_id | E8-S4 | PRD complete | Self-referential FK enabling the continuity chain that handoff records link into |

---

## Document History

| Version | Date       | Author | Changes                              |
|---------|------------|--------|--------------------------------------|
| 1.0     | 2026-02-20 | Sam    | Initial PRD from workshop (E8-S12)   |
