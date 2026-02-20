---
validation:
  status: valid
  validated_at: '2026-02-20T15:34:35+11:00'
---

## Product Requirements Document (PRD) — Role and Persona Database Models

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 1 — Foundational data models for named agent identity
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace currently identifies agents by anonymous session UUIDs — meaningless strings like "4b6f8a" that carry no identity, no memory, and no continuity. Epic 8 (Personable Agents) transforms agents into recognisable team members — Con the backend developer, Robbo the architect, Verner the tester — each with persistent skills and accumulating experience.

This PRD covers Sprint 1: the Role and Persona database tables. Role is a shared lookup table of agent specialisations (developer, tester, pm, architect). Persona is a named identity that references a Role and maps to filesystem-based skill assets. These two tables are the foundation for everything in Epic 8 — without them, nothing downstream (registration, skill injection, dashboard identity, handoffs) can be built.

The deliverable is deliberately narrow: two new SQLAlchemy models, one Alembic migration, and bidirectional relationships. No services, no APIs, no UI changes. Clean foundation for the 13 sprints that follow.

---

## 1. Context & Purpose

### 1.1 Context

All 10 existing domain models in Claude Headspace use integer primary keys, Flask-SQLAlchemy with `Mapped` type annotations, and PostgreSQL via Alembic migrations. The Agent model currently has 17 fields but no concept of persona identity — agents are identified solely by `session_uuid` and `claude_session_id`.

Epic 8 introduces named personas as first-class entities. The Role and Persona models are the first step: establishing the vocabulary of agent specialisations (Role) and the registry of named identities (Persona) that will be referenced throughout the system.

Design decisions for these models were resolved in the Agent Teams Design Workshop (16-20 February 2026) — specifically decisions 1.1 (Persona Storage Model), 1.2 (Config Location), and 2.1 (Persona Table Schema). See `docs/workshop/agent-teams-workshop.md`.

### 1.2 Target User

The operator (Sam) who registers and manages personas, and the Claude Headspace application which queries persona data for agent identity, dashboard display, and skill file resolution.

### 1.3 Success Moment

After running the migration, the operator can create a Role record (e.g., "developer") and a Persona record (e.g., "Con" with role "developer"), and the system generates a unique slug ("developer-con-1") that will serve as the filesystem path key for persona skill assets in later sprints.

---

## 2. Scope

### 2.1 In Scope

- New `Role` SQLAlchemy model with integer PK, unique name, description, and created_at timestamp
- New `Persona` SQLAlchemy model with integer PK, unique slug, name, description, status field, role_id FK, and created_at timestamp
- Bidirectional relationship: `Role.personas` (one-to-many) and `Persona.role` (many-to-one)
- Both models registered in `src/claude_headspace/models/__init__.py`
- Single Alembic migration creating both tables
- Slug format: `{role_name}-{persona_name}-{id}` (e.g., "developer-con-1")
- Slug uniqueness enforced at database level
- Status field with values "active" or "archived"

### 2.2 Out of Scope

- Organisation model (E8-S2)
- Position model (E8-S3)
- Agent model extensions — persona_id, position_id, previous_agent_id FKs (E8-S4)
- Filesystem asset directories or skill/experience files (E8-S5)
- Registration CLI or API endpoints (E8-S6)
- Any service layer, routes, or dashboard changes
- Pool membership modelling
- Config.yaml changes (persona definitions are domain data, not app config — workshop decision 1.2)
- Any changes to existing models (Agent, Command, Turn, etc.)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Role table exists in the database after running the Alembic migration
2. Persona table exists in the database after running the Alembic migration
3. A Role record can be created with a unique name (e.g., name="developer", description="Backend Python development")
4. A Persona record can be created with a role_id FK referencing an existing Role (e.g., name="Con", role_id=1)
5. Persona slug is generated in the format `{role_name}-{persona_name}-{id}` (e.g., "developer-con-1") — lowercase, hyphen-separated
6. Persona slug is unique at the database level — duplicate persona names with the same role produce different slugs via the id component
7. The `Persona.role` relationship returns the associated Role object
8. The `Role.personas` relationship returns a list of Persona objects associated with that Role
9. Persona status defaults to "active" and accepts "active" or "archived"
10. Existing Agent, Command, Turn, Event, and all other tables are unaffected by the migration

### 3.2 Non-Functional Success Criteria

1. Models follow existing codebase conventions: `Mapped` type annotations, `DateTime(timezone=True)`, UTC defaults, `db.Model` inheritance
2. Migration is additive and non-destructive — can be applied to a database with existing data without data loss
3. Migration is reversible (downgrade drops both tables cleanly)

---

## 4. Functional Requirements (FRs)

**FR1: Role Model**
The system must provide a Role database model representing an agent specialisation (e.g., "developer", "tester", "pm", "architect"). Role is a shared lookup table — it defines the vocabulary of specialisations referenced by both Persona ("I am a developer") and, in future sprints, Position ("this seat needs a developer").

Fields:
- `id` — integer, primary key, auto-increment
- `name` — string, unique, not null (e.g., "developer", "tester", "pm", "architect")
- `description` — text, nullable (human-readable description of the role)
- `created_at` — datetime with timezone, defaults to current UTC time

**FR2: Persona Model**
The system must provide a Persona database model representing a named agent identity (e.g., "Con", "Robbo", "Gavin"). Each Persona references exactly one Role via a foreign key.

Fields:
- `id` — integer, primary key, auto-increment
- `slug` — string, unique, not null (generated as `{role_name}-{persona_name}-{id}`, e.g., "developer-con-1")
- `name` — string, not null (display name, e.g., "Con")
- `description` — text, nullable (core identity description)
- `status` — string, defaults to "active" (valid values: "active", "archived")
- `role_id` — integer, foreign key to Role.id, not null
- `created_at` — datetime with timezone, defaults to current UTC time

**FR3: Slug Generation**
The Persona slug must be generated from the role name, persona name, and persona id in the format `{role_name}-{persona_name}-{id}`. All components are lowercased and joined with hyphens. The id component guarantees uniqueness even when multiple personas share the same role and name.

Examples:
- Role "developer", Persona "Con", id 1 → slug "developer-con-1"
- Role "developer", Persona "Con", id 7 → slug "developer-con-7"
- Role "tester", Persona "Verner", id 3 → slug "tester-verner-3"

The slug serves as the filesystem path key for persona assets in later sprints (`data/personas/{slug}/`).

**FR4: Role-Persona Relationship**
The system must define a bidirectional relationship between Role and Persona:
- `Role.personas` — returns all Persona records associated with that Role (one-to-many)
- `Persona.role` — returns the Role record for that Persona (many-to-one)

A Role can have zero or many Personas. A Persona must have exactly one Role.

**FR5: Model Registration**
Both Role and Persona models must be registered in `src/claude_headspace/models/__init__.py` following the existing pattern (import + `__all__` entry) so they are discovered by Flask-SQLAlchemy.

**FR6: Alembic Migration**
A single Alembic migration must create both the Role and Persona tables. The migration must:
- Create the Role table first (Persona references it via FK)
- Create the Persona table with the role_id foreign key
- Be reversible (downgrade drops Persona first, then Role)
- Not affect any existing tables or data

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Codebase Consistency**
Both models must follow the established patterns in the existing codebase:
- Inherit from `db.Model`
- Use `Mapped[type]` and `mapped_column()` for column definitions
- Use `DateTime(timezone=True)` for timestamp fields with UTC defaults
- Use `relationship()` with `back_populates` for bidirectional relationships
- Use `TYPE_CHECKING` blocks for forward reference type hints where needed

**NFR2: Backward Compatibility**
The migration must be purely additive. No changes to existing tables. All existing queries, services, and routes must continue functioning without modification.

**NFR3: Data Integrity**
- Role.name uniqueness enforced at database level (unique constraint)
- Persona.slug uniqueness enforced at database level (unique constraint)
- Persona.role_id referential integrity enforced via foreign key constraint
- Persona.name is not-null but not unique (multiple personas can share a name if they have different roles — uniqueness comes from the slug)

---

## 6. Technical Context

### 6.1 Design Decisions (All Resolved)

The following decisions were made in the Agent Teams Design Workshop and are authoritative for this PRD:

| Decision | Resolution | Source |
|----------|-----------|--------|
| Integer PKs (not UUIDs) | Matches existing codebase: Agent, Command, Turn all use int PKs | Workshop 2.1 |
| Slug format `{role}-{name}-{id}` | Natural filesystem sorting by role then name, id guarantees uniqueness | Workshop 1.2, 2.1 |
| Status field (`active\|archived`) not boolean `is_active` | Extensible string field replaces boolean | Workshop 2.1 |
| Role is a shared lookup, not org-scoped | No org_id on Role — org relationship comes through Position via Agent | Workshop 2.1 |
| No pool membership in v1 | Pools may emerge from Position/Role relationships later | Workshop 2.1 |
| No org_id on Persona | Persona is org-independent — org relationship through Position via Agent | Workshop 2.1 |
| Skill file path derived from slug convention | Not stored on the model — `data/personas/{slug}/` is a project convention | Workshop 1.2 |
| Config.yaml not involved | Persona definitions are domain data, not app config | Workshop 1.2 |

### 6.2 Integration Points

- **New files:** `src/claude_headspace/models/role.py`, `src/claude_headspace/models/persona.py`
- **Modified file:** `src/claude_headspace/models/__init__.py` (add imports and `__all__` entries)
- **New migration:** `migrations/versions/xxx_add_role_persona_tables.py`
- **Downstream consumers (future sprints):** E8-S4 (Agent.persona_id FK), E8-S5 (slug → filesystem path), E8-S6 (registration creates Persona records)

### 6.3 Data Model Reference

```python
class Role(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # developer, tester, pm, architect
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())

class Persona(db.Model):
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)  # generated: developer-con-1
    name = Column(String, nullable=False)                # Con
    description = Column(Text)
    status = Column(String, default="active")            # active | archived
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
```

*Note: This is a reference illustration showing field intent. Implementation should use the codebase's established `Mapped`/`mapped_column` patterns.*

### 6.4 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration conflicts with concurrent development | Low | Medium | Epic 8 is sequential — no parallel sprints. Coordinate with any active feature branches. |
| Slug uniqueness edge cases | Low | Low | Generated from role + name + id — the id component guarantees uniqueness regardless of name collisions. |
