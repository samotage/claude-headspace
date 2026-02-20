---
validation:
  status: valid
  validated_at: '2026-02-20T15:37:08+11:00'
---

## Product Requirements Document (PRD) — Organisation Database Model

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 2 — Minimal Organisation table for future multi-org support
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace's platform vision introduces Organisations as first-class entities with hierarchy, workflow patterns, and role assignments. In v1, there is one organisation — the development org — but the architecture must not make this assumption permanent.

This PRD covers Sprint 2: a minimal Organisation database table with a single seed record. The table exists to avoid a disruptive migration later when multi-org support arrives. Position (E8-S3) will reference Organisation via a foreign key, so this table must exist first. The deliverable is deliberately minimal: one new SQLAlchemy model, one Alembic migration with seed data, and model registration. No services, no APIs, no UI changes, no config.yaml involvement.

The three-state status field (active, dormant, archived) provides enough lifecycle granularity for organisations without over-engineering. "Dormant" captures the state where an org exists but is not actively running agents — distinct from "archived" which is a permanent end-state.

---

## 1. Context & Purpose

### 1.1 Context

The Agent Teams Design Workshop (Decision 1.3) resolved that a minimal Organisation table should exist in v1. The reasoning: one small migration now avoids a potentially disruptive one later when Position records, Agent references, and other downstream tables already contain data that would need to be retroactively linked to an Organisation.

All existing domain models in Claude Headspace use integer primary keys, Flask-SQLAlchemy with `Mapped` type annotations, and PostgreSQL via Alembic migrations. The Organisation model follows the same conventions.

Design decisions for this model were resolved in the Agent Teams Design Workshop (Decision 1.3: Organisation Model — v1 Scope) and the ERD workshop (three-state status). See `docs/workshop/agent-teams-workshop.md`.

### 1.2 Target User

The Claude Headspace application, which will reference Organisation from Position records (E8-S3). In v1, the operator does not interact with Organisation directly — it is infrastructure for future multi-org capability.

### 1.3 Success Moment

After running the migration, the database contains an Organisation table with one seed record: the "Development" organisation in "active" status. Position records (E8-S3) can reference it via foreign key. The operator sees no visible changes — the table is invisible plumbing.

---

## 2. Scope

### 2.1 In Scope

- New `Organisation` SQLAlchemy model with integer PK, name, description, status field, and created_at timestamp
- Status field supporting three values: "active", "dormant", "archived"
- Model registered in `src/claude_headspace/models/__init__.py`
- Alembic migration creating the Organisation table
- Seed data: one Organisation record (name="Development", status="active") created via migration data operation
- No relationships defined in this sprint (Position will reference Organisation in E8-S3)

### 2.2 Out of Scope

- Position model and `org_id` FK referencing Organisation (E8-S3)
- Agent model extensions (E8-S4)
- Any service layer, routes, API endpoints, or dashboard changes
- Organisation-level configuration in config.yaml (config.yaml is app config only — workshop decision 1.2)
- Any changes to existing models (Agent, Command, Turn, etc.)
- Multi-org management UI or workflows (Phase 2+)
- Relationships from Organisation to other tables (defined when those tables are created)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Organisation table exists in the database after running the Alembic migration
2. An Organisation record can be created with name, description, and status fields
3. Organisation status defaults to "active" and accepts "active", "dormant", or "archived"
4. The dev org seed record is present after migration: name="Development", status="active"
5. Existing Agent, Command, Turn, Event, Project, Role, Persona, and all other tables are unaffected by the migration

### 3.2 Non-Functional Success Criteria

1. Model follows existing codebase conventions: `Mapped` type annotations, `mapped_column()`, `DateTime(timezone=True)`, UTC defaults, `db.Model` inheritance
2. Migration is additive and non-destructive — can be applied to a database with existing data without data loss
3. Migration is reversible (downgrade drops the Organisation table and its seed data cleanly)

---

## 4. Functional Requirements (FRs)

**FR1: Organisation Model**
The system must provide an Organisation database model representing an organisational grouping. In v1, this table holds a single record (the development org). It exists as future-proofing infrastructure — Position records (E8-S3) will reference Organisation via a foreign key.

Fields:
- `id` — integer, primary key, auto-increment
- `name` — string, not null (e.g., "Development", "Marketing")
- `description` — text, nullable (human-readable description of the organisation's purpose)
- `status` — string, not null, defaults to "active" (valid values: "active", "dormant", "archived")
- `created_at` — datetime with timezone, defaults to current UTC time

**FR2: Seed Data**
The Alembic migration must seed one Organisation record as a data operation:
- name: "Development"
- status: "active"
- description: nullable (may be left null or set to a brief description)

The seed ensures the dev org exists immediately after migration, ready for Position records to reference.

**FR3: Model Registration**
The Organisation model must be registered in `src/claude_headspace/models/__init__.py` following the existing pattern (import + `__all__` entry) so it is discovered by Flask-SQLAlchemy.

**FR4: Alembic Migration**
A single Alembic migration must create the Organisation table and seed the dev org record. The migration must:
- Create the Organisation table
- Insert the seed Organisation record
- Be reversible (downgrade deletes the seed record and drops the table)
- Not affect any existing tables or data

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Codebase Consistency**
The Organisation model must follow the established patterns in the existing codebase:
- Inherit from `db.Model`
- Use `Mapped[type]` and `mapped_column()` for column definitions
- Use `DateTime(timezone=True)` for timestamp fields with UTC defaults
- Follow the naming and structural conventions of existing models (e.g., `project.py`, `agent.py`)

**NFR2: Backward Compatibility**
The migration must be purely additive. No changes to existing tables. All existing queries, services, and routes must continue functioning without modification.

**NFR3: Data Integrity**
- Organisation.name is not-null (every organisation must have a name)
- Organisation.status is not-null with a default of "active"
- No unique constraint on name in v1 (not required — only one org exists, and the constraint can be added when multi-org arrives if needed)

---

## 6. Technical Context

### 6.1 Design Decisions (All Resolved)

The following decisions were made in the Agent Teams Design Workshop and are authoritative for this PRD:

| Decision | Resolution | Source |
|----------|-----------|--------|
| Minimal Organisation table in v1 | One small migration now avoids a disruptive one later | Workshop 1.3 |
| Three-state status: active, dormant, archived | Provides lifecycle granularity beyond binary active/inactive | ERD workshop |
| No Organisation-level configuration in config.yaml | Config.yaml is app config only — org definitions are domain data | Workshop 1.2 |
| Integer PK | Matches existing codebase convention | Workshop 2.1 |
| No relationships defined in this sprint | Position (E8-S3) will add the FK reference | Roadmap E8-S3 |

### 6.2 Integration Points

- **New file:** `src/claude_headspace/models/organisation.py`
- **Modified file:** `src/claude_headspace/models/__init__.py` (add import and `__all__` entry)
- **New migration:** `migrations/versions/xxx_add_organisation_table.py`
- **Downstream consumers (future sprints):** E8-S3 (Position.org_id FK to Organisation), E8-S4 (Agent.position_id → Position → Organisation chain)

### 6.3 Data Model Reference

```python
class Organisation(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active")  # active | dormant | archived
    created_at = Column(DateTime, default=func.now())
```

*Note: This is a reference illustration showing field intent. Implementation should use the codebase's established `Mapped`/`mapped_column` patterns.*

### 6.4 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Minimal table may need extension later | Medium | Low | That's the design intent — extend when needed via additive migrations |
| Migration conflicts with E8-S1 migration | Low | Low | Sprints are sequential — S2 runs after S1 is merged |
| Seed data conflicts on repeated migration runs | Low | Low | Migration is a one-time operation; Alembic tracks applied migrations |
