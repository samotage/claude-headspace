---
validation:
  status: invalid
  invalidated_reason: 'PRD amended post-evaluation — table name fix (agents→agent), ON DELETE CASCADE. Requires revalidation.'
---

## Product Requirements Document (PRD) — Agent Model Extensions

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 4 — Extend Agent with persona, position, and predecessor foreign keys
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

The Agent model is the execution layer of Claude Headspace — it represents a running Claude Code session. Currently, agents are anonymous: identified only by session UUIDs with no connection to the persona system or organisational structure being built in Epic 8.

Sprint 4 extends the existing Agent model with three new nullable foreign keys: `persona_id` (linking to the Persona table from E8-S1), `position_id` (linking to the Position table from E8-S3), and `previous_agent_id` (a self-referential FK establishing handoff continuity chains). These three columns make Agent the join point between identity (Persona), structure (Position), and continuity (predecessor chain).

All three fields are nullable for backward compatibility — existing agents and all current queries, services, and routes continue working unchanged. No services, APIs, or UI changes are included. This is purely a data model extension with relationships, building the foundation for persona-aware agent creation (S7), SessionCorrelator persona assignment (S8), dashboard persona display (S10-S11), and the handoff system (S12-S14).

---

## 1. Context & Purpose

### 1.1 Context

The Agent model currently has 17 fields across identity (`session_uuid`, `claude_session_id`), association (`project_id` FK), terminal (`iterm_pane_id`, `tmux_pane_id`, `tmux_session`), lifecycle (`started_at`, `last_seen_at`, `ended_at`), content (`transcript_path`), scoring (`priority_score`, `priority_reason`, `priority_updated_at`), and context monitoring (`context_percent_used`, `context_remaining_tokens`, `context_updated_at`). The only existing FK is `project_id` to the Project table.

Sprints 1-3 of Epic 8 create three new tables (Role, Persona, Organisation, Position) but none of them are connected to Agent yet. Without the FK extensions in this sprint, the persona infrastructure is isolated — agents cannot be identified by persona, placed in an org chart position, or linked in a continuity chain.

Design decisions for these extensions were resolved in the Agent Teams Design Workshop — specifically decisions 2.2 (Agent Model Extensions), 2.3 (Persona Availability Constraint), and 5.1 (Handoff Design Hooks for the predecessor chain). See `docs/workshop/agent-teams-workshop.md`.

### 1.2 Target User

The Claude Headspace application, which needs to associate agents with personas and positions for identity display, and link agents in continuity chains for handoff. The operator benefits indirectly through named agent identity on the dashboard and handoff continuity.

### 1.3 Success Moment

After running the migration, an existing agent (pre-persona) continues working with all three new fields as NULL. A new agent can be created with `persona_id` set, and `Agent.persona` navigates to the Persona record. Multiple agents can reference the same persona simultaneously. Two agents can be linked via `previous_agent_id` to form a continuity chain.

---

## 2. Scope

### 2.1 In Scope

- Add `persona_id` column to Agent — integer FK to `persona.id`, nullable
- Add `position_id` column to Agent — integer FK to `position.id`, nullable
- Add `previous_agent_id` column to Agent — integer FK to `agent.id` (self-referential), nullable
- Relationship: `Agent.persona` → Persona (many-to-one)
- Relationship: `Agent.position` → Position (many-to-one)
- Relationship: `Agent.previous_agent` → Agent (self-referential many-to-one, the predecessor)
- Relationship: `Agent.successor_agents` → list of Agents that have this agent as `previous_agent_id` (one-to-many)
- Relationship: `Persona.agents` → list of Agents driven by that persona (one-to-many, defined on Persona model)
- Single Alembic migration adding three nullable columns to the existing `agent` table
- All existing Agent records remain unaffected (new fields default to NULL)
- All existing Agent queries, services, and routes continue working without modification

### 2.2 Out of Scope

- Persona, Role, Organisation, Position model creation (E8-S1, S2, S3 — prerequisites)
- Any availability constraint or unique index on `persona_id` — multiple agents can share the same persona simultaneously (workshop decision 2.3)
- No `PositionAssignment` join table — Agent has both `persona_id` and `position_id` directly, serving as the assignment record (workshop decision 2.2)
- Persona registration, CLI, or API endpoints (E8-S6)
- Persona-aware agent creation or `create_agent()` changes (E8-S7)
- SessionCorrelator persona assignment logic (E8-S8)
- Skill file injection (E8-S9)
- Dashboard or UI changes (E8-S10, S11)
- Handoff model, trigger UI, or execution (E8-S12, S13, S14)
- Any service layer, route, or business logic modifications
- Any changes to the Agent `name` property — persona-aware naming is a downstream concern (S10)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Migration adds three nullable columns (`persona_id`, `position_id`, `previous_agent_id`) to the `agent` table
2. Existing Agent records are unaffected — all three new fields are NULL after migration
3. An Agent can be created with `persona_id` set to a valid Persona id, and `Agent.persona` returns the associated Persona object
4. An Agent can be created with `position_id` set to a valid Position id, and `Agent.position` returns the associated Position object
5. An Agent can have `previous_agent_id` set to another Agent's id, and `Agent.previous_agent` returns the predecessor Agent
6. `Agent.successor_agents` returns a list of Agents that reference this agent as their `previous_agent_id`
7. `Persona.agents` returns all Agent records that reference that Persona via `persona_id`
8. Multiple agents can reference the same `persona_id` simultaneously — no uniqueness constraint
9. First agent in a continuity chain has `previous_agent_id = NULL`
10. All existing Agent queries and services continue working unchanged — the new nullable fields do not break any existing functionality

### 3.2 Non-Functional Success Criteria

1. Models follow existing codebase conventions: `Mapped` type annotations, `mapped_column()`, `ForeignKey()`, `relationship()` with `back_populates`, `DateTime(timezone=True)` for timestamps
2. Migration is additive and non-destructive — can be applied to a database with existing Agent data without data loss
3. Migration is reversible (downgrade removes the three columns cleanly)
4. Self-referential FK on Agent uses `remote_side` parameter following the same pattern as Position's `reports_to_id` (E8-S3)

---

## 4. Functional Requirements (FRs)

**FR1: persona_id Foreign Key**
The Agent model must gain a `persona_id` column — an integer foreign key referencing `persona.id`. The column must be nullable to maintain backward compatibility with existing agents that have no persona association. When set, it identifies which persona drives this agent.

**FR2: position_id Foreign Key**
The Agent model must gain a `position_id` column — an integer foreign key referencing `position.id`. The column must be nullable to maintain backward compatibility. When set, it identifies which org chart position this agent represents. Combined with `persona_id`, Agent serves as the join between Persona (who) and Position (where) — no separate PositionAssignment table.

**FR3: previous_agent_id Self-Referential Foreign Key**
The Agent model must gain a `previous_agent_id` column — an integer foreign key referencing `agent.id` (self-referential). The column must be nullable. When set, it links this agent to its predecessor in a handoff continuity chain. The first agent in any chain has `previous_agent_id = NULL`.

**FR4: Agent-to-Persona Relationship**
The system must define a bidirectional relationship between Agent and Persona:
- `Agent.persona` — returns the Persona object associated with this agent (many-to-one, nullable)
- `Persona.agents` — returns all Agent records driven by this persona (one-to-many)

A Persona can have zero or many Agents. An Agent can have zero or one Persona.

**FR5: Agent-to-Position Relationship**
The system must define a relationship from Agent to Position:
- `Agent.position` — returns the Position object this agent represents (many-to-one, nullable)

**FR6: Agent Self-Referential Continuity Relationships**
The system must define bidirectional self-referential relationships on Agent:
- `Agent.previous_agent` — returns the predecessor Agent in the continuity chain (many-to-one, nullable)
- `Agent.successor_agents` — returns a list of Agents that have this agent as their `previous_agent_id` (one-to-many)

**FR7: No Availability Constraint**
There must be no unique constraint, partial unique index, or application-level check preventing multiple agents from sharing the same `persona_id` simultaneously. Multiple agents can be driven by the same persona at the same time.

**FR8: Alembic Migration**
A single Alembic migration must add three nullable columns to the existing `agent` table:
- `persona_id` (integer, FK to `persona.id`, nullable)
- `position_id` (integer, FK to `position.id`, nullable)
- `previous_agent_id` (integer, FK to `agent.id`, nullable)

The migration must:
- Add columns without affecting existing data (all default to NULL)
- Be reversible (downgrade removes the three columns)
- Not affect any other tables

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Codebase Consistency**
The Agent model extensions must follow established patterns:
- Use `Mapped[int | None]` and `mapped_column()` for nullable FK columns
- Use `ForeignKey()` for foreign key constraints
- Use `relationship()` with `back_populates` for bidirectional relationships
- Use `remote_side` parameter for the self-referential `previous_agent_id` relationship
- Use `TYPE_CHECKING` blocks for forward reference type hints where needed

**NFR2: Backward Compatibility**
The migration must be purely additive. All three new columns are nullable. No changes to existing columns, constraints, or indexes. All existing Agent queries, services, routes, and tests must continue functioning without modification.

**NFR3: Referential Integrity**
- `persona_id` references `persona.id` — FK constraint enforced at database level (ON DELETE CASCADE)
- `position_id` references `position.id` — FK constraint enforced at database level (ON DELETE CASCADE)
- `previous_agent_id` references `agent.id` — FK constraint enforced at database level, self-referential (ON DELETE CASCADE)
- All foreign keys use ON DELETE CASCADE

---

## 6. Technical Context

### 6.1 Design Decisions (All Resolved)

The following decisions were made in the Agent Teams Design Workshop and are authoritative for this PRD:

| Decision | Resolution | Source |
|----------|-----------|--------|
| No PositionAssignment join table | Agent has both `persona_id` and `position_id` directly — Agent IS the assignment | Workshop 2.2 |
| No availability constraint | Multiple agents can share the same persona simultaneously | Workshop 2.3 |
| `previous_agent_id` self-ref FK | Continuity chain on Agent, not from/to on Handoff | Workshop 5.1, ERD |
| All new fields nullable | Backward compatibility with existing agents | Workshop 2.2 |
| Integer PKs | Matches existing codebase — Agent, Command, Turn all use int PKs | Workshop 2.1 |

### 6.2 Dependencies

| Dependency | What It Provides | Status |
|-----------|-----------------|--------|
| E8-S1: Role + Persona Models | `persona.id` target for `persona_id` FK | PRD validated |
| E8-S3: Position Model | `position.id` target for `position_id` FK | PRD pending |
| Existing Agent table | The table being extended with three new columns | Exists in production |

### 6.3 Integration Points

- **Modified file:** `src/claude_headspace/models/agent.py` — add three nullable FK columns and relationships
- **Modified file:** `src/claude_headspace/models/persona.py` — add `agents` back-populates relationship (if not already present from S1)
- **New migration:** `migrations/versions/xxx_add_agent_persona_position_predecessor.py`
- **Downstream consumers (future sprints):**
  - E8-S7 (persona-aware agent creation sets `persona_id`)
  - E8-S8 (SessionCorrelator sets `persona_id` at registration)
  - E8-S10 (card state reads `Agent.persona` for display)
  - E8-S12 (Handoff model references Agent, successor uses `previous_agent_id`)
  - E8-S14 (handoff execution sets `previous_agent_id` on successor agent)

### 6.4 ERD Note

The full ERD at `docs/workshop/erds/headspace-org-erd-full.md` shows Agent extensions including a `context_usage` field and uses UUIDs. Workshop decisions override the ERD: integer PKs are used throughout, and `context_usage` is already covered by the existing `context_percent_used` and `context_remaining_tokens` fields. The ERD also shows a `PositionAssignment` table — workshop decision 2.2 removes this in favour of direct FKs on Agent.

### 6.5 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration on Agent table with existing data | Low | Low | All fields nullable — no data transformation, no NOT NULL constraint. Migration is a pure column addition. |
| Self-referential FK complexity | Low | Low | Well-documented SQLAlchemy pattern using `remote_side`. Same pattern used by Position.reports_to_id in E8-S3. |
| Migration conflicts with concurrent development | Low | Medium | Epic 8 is sequential — no parallel sprints. Coordinate with any active feature branches. |
