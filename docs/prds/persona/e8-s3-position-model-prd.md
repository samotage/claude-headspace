---
validation:
  status: valid
  validated_at: '2026-02-20T17:23:55+11:00'
---

## Product Requirements Document (PRD) — Position Database Model

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 3 — Position table with self-referential hierarchy for org chart structure
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace's organisational model separates people from seats. Personas (E8-S1) are named identities — "Con", "Robbo", "Verner". Organisations (E8-S2) are groupings. Positions are seats in an org chart — "Lead Developer", "Senior Tester", "Chief Architect" — each defined by what role the seat needs, who it reports to, and who it escalates to.

This PRD covers Sprint 3: the Position database table with self-referential hierarchy. The key design feature is dual self-referential foreign keys: `reports_to_id` builds the standard reporting chain (org chart tree), while `escalates_to_id` allows escalation paths to differ from reporting paths. For example, Verner reports to Gavin (PM) for day-to-day management but escalates architectural issues to Robbo (architect) — a common real-world pattern that would be lost with a single hierarchy.

The deliverable is one new SQLAlchemy model, one Alembic migration, and relationships to Role and Organisation (both from prior sprints) plus self-referential relationships. No services, no APIs, no UI changes. Agent model extensions (E8-S4) will add `position_id` FK to Agent, making Agent the join between Persona and Position — but that is the next sprint's concern.

---

## 1. Context & Purpose

### 1.1 Context

Position sits at the intersection of Role and Organisation in the data model. A Position says: "this organisation needs a seat that requires this role, at this level of the hierarchy, reporting to this other seat." It models the org chart — the structure of how work is delegated and escalated.

The self-referential hierarchy pattern (`reports_to_id` pointing back to Position) is well-established in SQLAlchemy and mirrors how real organisations work. The addition of `escalates_to_id` as a second self-referential FK captures the real-world distinction between "who do I report to" and "who do I escalate specialised issues to."

Design decisions were resolved in the Agent Teams Design Workshop (16-20 February 2026) — specifically the ERD workshop (Position entity, self-referential hierarchy) and Decision 2.1 (Role as shared lookup). See `docs/workshop/agent-teams-workshop.md` and `docs/workshop/erds/headspace-org-erd-full.md`.

### 1.2 Target User

The Claude Headspace application, which will reference Position from Agent records (E8-S4) to determine org chart placement, reporting chains, and escalation paths. In v1, positions are infrastructure for the persona-to-org-chart mapping. Future sprints (PM automation, Gavin v3) will use Position hierarchy for task delegation.

### 1.3 Success Moment

After running the migration, the operator can create Position records that form an org chart: a "Lead Architect" position at level 0 with no reports_to (top of hierarchy, implicitly reports to the operator), a "PM" position at level 1 reporting to the architect, and a "Senior Developer" position at level 1 reporting to the PM but escalating architectural issues to the architect. The `direct_reports` relationship on the architect position returns the PM position.

---

## 2. Scope

### 2.1 In Scope

- New `Position` SQLAlchemy model with integer PK
- Fields: id, org_id (FK→Organisation), role_id (FK→Role), title, reports_to_id (self-ref FK, nullable), escalates_to_id (self-ref FK, nullable), level (int), is_cross_cutting (bool)
- Self-referential hierarchy via `reports_to_id` and `escalates_to_id` (both nullable — top-level positions have NULL)
- Relationships: `Position.role` → Role, `Position.organisation` → Organisation, `Position.reports_to` → Position, `Position.escalates_to` → Position, `Position.direct_reports` → list of Positions
- Backref relationships on Organisation and Role: `Organisation.positions`, `Role.positions`
- Model registered in `src/claude_headspace/models/__init__.py`
- Alembic migration creating the Position table

### 2.2 Out of Scope

- Agent model extensions — position_id FK on Agent (E8-S4)
- PositionAssignment join table (excluded by workshop decision 2.2 — Agent IS the assignment record)
- Position CRUD API or CLI endpoints (future sprint concern)
- Seed data for positions (no default positions — operator creates them when registering personas)
- Circular hierarchy validation (application-level concern for future sprints)
- Dashboard or UI changes
- Any changes to existing models (Agent, Command, Turn, etc.)
- Config.yaml changes (position definitions are domain data — workshop decision 1.2)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Position table exists in the database after running the Alembic migration
2. A Position record can be created with org_id FK referencing an existing Organisation and role_id FK referencing an existing Role
3. Position title is a required string field (e.g., "Lead Developer", "Senior Tester")
4. Position.reports_to_id can be set to another Position's id (self-referential FK)
5. Position.escalates_to_id can be set to a different Position's id than reports_to_id (escalation path differs from reporting path)
6. Top-level positions have reports_to_id = NULL (implicitly report to the operator)
7. Position.level defaults to 0 and accepts integer values representing depth in the hierarchy
8. Position.is_cross_cutting defaults to False
9. The `Position.role` relationship returns the associated Role object
10. The `Position.organisation` relationship returns the associated Organisation object
11. The `Position.reports_to` relationship returns the parent Position (or None for top-level)
12. The `Position.escalates_to` relationship returns the escalation target Position (or None)
13. The `Position.direct_reports` relationship returns a list of Position records where reports_to_id matches this Position's id
14. Existing Agent, Command, Turn, Event, Project, Role, Persona, Organisation, and all other tables are unaffected by the migration

### 3.2 Non-Functional Success Criteria

1. Model follows existing codebase conventions: `Mapped` type annotations, `mapped_column()`, `DateTime(timezone=True)`, UTC defaults, `db.Model` inheritance
2. Migration is additive and non-destructive — can be applied to a database with existing data without data loss
3. Migration is reversible (downgrade drops the Position table cleanly)
4. Self-referential relationships use `remote_side` parameter correctly to avoid SQLAlchemy ambiguity errors

---

## 4. Functional Requirements (FRs)

**FR1: Position Model**
The system must provide a Position database model representing a seat in an organisational chart. Each position belongs to one Organisation, requires one Role, and optionally reports to and escalates to other positions in the same hierarchy.

Fields:
- `id` — integer, primary key, auto-increment
- `org_id` — integer, foreign key to Organisation.id, not null (which organisation this seat belongs to)
- `role_id` — integer, foreign key to Role.id, not null (what specialisation this seat requires)
- `title` — string, not null (human-readable position title, e.g., "Lead Developer", "Senior Tester")
- `reports_to_id` — integer, foreign key to Position.id, nullable (self-referential — the position this seat reports to; NULL for top-level positions)
- `escalates_to_id` — integer, foreign key to Position.id, nullable (self-referential — the position this seat escalates specialised issues to; may differ from reports_to_id; NULL if same as reporting path or not applicable)
- `level` — integer, not null, defaults to 0 (depth in the reporting hierarchy — 0 is top-level)
- `is_cross_cutting` — boolean, not null, defaults to False (marks positions that operate across the hierarchy rather than within a single branch)
- `created_at` — datetime with timezone, defaults to current UTC time

**FR2: Self-Referential Reporting Hierarchy**
The system must support a self-referential reporting chain via `reports_to_id`. This foreign key points to another Position record in the same table, building a tree structure representing the org chart. Top-level positions (reports_to_id = NULL) implicitly report to the operator (Sam), who is not modelled as a Persona.

**FR3: Self-Referential Escalation Path**
The system must support a separate escalation path via `escalates_to_id`. This foreign key also points to another Position record but may reference a different position than `reports_to_id`. This captures the real-world pattern where escalation paths differ from reporting paths (e.g., Verner reports to Gavin for day-to-day management but escalates architectural issues to Robbo).

**FR4: Position Relationships**
The system must define the following relationships:
- `Position.role` — returns the Role record for this position (many-to-one)
- `Position.organisation` — returns the Organisation record for this position (many-to-one)
- `Position.reports_to` — returns the parent Position in the reporting chain (many-to-one, self-referential, nullable)
- `Position.escalates_to` — returns the escalation target Position (many-to-one, self-referential, nullable)
- `Position.direct_reports` — returns all Position records where reports_to_id equals this position's id (one-to-many, reverse of reports_to)

**FR5: Backref Relationships on Existing Models**
The system must define backref relationships accessible from Organisation and Role:
- `Organisation.positions` — returns all Position records belonging to that organisation
- `Role.positions` — returns all Position records requiring that role

**FR6: Model Registration**
The Position model must be registered in `src/claude_headspace/models/__init__.py` following the existing pattern (import + `__all__` entry) so it is discovered by Flask-SQLAlchemy.

**FR7: Alembic Migration**
A single Alembic migration must create the Position table. The migration must:
- Create the Position table with foreign keys to Organisation, Role, and two self-referential foreign keys
- Be reversible (downgrade drops the Position table)
- Not affect any existing tables or data

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Codebase Consistency**
The Position model must follow the established patterns in the existing codebase:
- Inherit from `db.Model`
- Use `Mapped[type]` and `mapped_column()` for column definitions
- Use `DateTime(timezone=True)` for timestamp fields with UTC defaults
- Use `relationship()` with `back_populates` for bidirectional relationships
- Use `remote_side` parameter on self-referential relationships to resolve FK ambiguity
- Use `TYPE_CHECKING` blocks for forward reference type hints where needed

**NFR2: Backward Compatibility**
The migration must be purely additive. No changes to existing tables. All existing queries, services, and routes must continue functioning without modification. The Organisation and Role models from E8-S1 and E8-S2 gain `positions` relationships but no schema changes.

**NFR3: Data Integrity**
- Position.org_id referential integrity enforced via foreign key constraint to Organisation (ON DELETE CASCADE)
- Position.role_id referential integrity enforced via foreign key constraint to Role (ON DELETE CASCADE)
- Position.reports_to_id referential integrity enforced via self-referential foreign key constraint (ON DELETE CASCADE)
- Position.escalates_to_id referential integrity enforced via self-referential foreign key constraint (ON DELETE CASCADE)
- All foreign keys use ON DELETE CASCADE
- Position.title is not-null (every position must have a title)

---

## 6. Technical Context

### 6.1 Design Decisions (All Resolved)

The following decisions were made in the Agent Teams Design Workshop and ERD sessions and are authoritative for this PRD:

| Decision | Resolution | Source |
|----------|-----------|--------|
| Self-referential hierarchy via reports_to_id and escalates_to_id | Both point to Position — builds org chart tree with separate escalation path | ERD, Workshop |
| Escalation path can differ from reporting path | Verner reports to Gavin but escalates architectural issues to Robbo | ERD |
| Operator (Sam) not modelled as a Persona | Top of every hierarchy implicitly reports to the operator | ERD |
| Role is shared lookup referenced by both Persona and Position | Match on role_id to find personas that can fill a position | Workshop 2.1 |
| No PositionAssignment join table | Agent IS the assignment — has both persona_id and position_id directly | Workshop 2.2 |
| Integer PK | Matches existing codebase convention (Agent, Command, Turn all use int PKs) | Workshop 2.1 |

### 6.2 Dependencies

- **E8-S1 (Role table)** — Position.role_id FK references Role. Must be migrated first.
- **E8-S2 (Organisation table)** — Position.org_id FK references Organisation. Must be migrated first.

### 6.3 Integration Points

- **New file:** `src/claude_headspace/models/position.py`
- **Modified files:** `src/claude_headspace/models/__init__.py` (add import and `__all__` entry), `src/claude_headspace/models/role.py` (add `positions` relationship), `src/claude_headspace/models/organisation.py` (add `positions` relationship)
- **New migration:** `migrations/versions/xxx_add_position_table.py`
- **Downstream consumers (future sprints):** E8-S4 (Agent.position_id FK to Position)

### 6.4 Data Model Reference

```python
class Position(db.Model):
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisation.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
    title = Column(String, nullable=False)
    reports_to_id = Column(Integer, ForeignKey("position.id"), nullable=True)
    escalates_to_id = Column(Integer, ForeignKey("position.id"), nullable=True)
    level = Column(Integer, default=0)  # depth in hierarchy
    is_cross_cutting = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
```

*Note: This is a reference illustration showing field intent. Implementation should use the codebase's established `Mapped`/`mapped_column` patterns.*

### 6.5 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Self-referential FK complexity in SQLAlchemy | Low | Medium | Well-documented pattern — use `remote_side` parameter on relationships. Same pattern used by Position.reports_to and Position.escalates_to (resolved identically). |
| Circular hierarchy (A reports to B reports to A) | Low | Low | Level field provides depth sanity check. Application-level validation deferred to future sprints — not a data model concern. |
| Migration conflicts with E8-S1 or E8-S2 migrations | Low | Low | Sprints are sequential — S3 runs after S1 and S2 are merged |
