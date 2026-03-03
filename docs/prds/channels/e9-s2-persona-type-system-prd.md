---
validation:
  status: pending
---

## Product Requirements Document (PRD) — PersonaType System

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 2 — PersonaType lookup table, Persona FK, operator Persona creation
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The channel infrastructure (Sprints 3–8) requires every Persona to be classified into one of four quadrants: agent/internal, agent/external, person/internal, person/external. This classification determines delivery mechanism, trust boundaries, visibility scope, and channel creation capability. The classification also enables the operator (Sam) to be modelled as a first-class Persona — a prerequisite for channel participation.

This sprint introduces the PersonaType lookup table (4 rows), adds a NOT NULL foreign key from Persona to PersonaType, backfills all existing personas as agent/internal, creates the "operator" Role and a person/internal Persona for Sam, and adds a service-layer `can_create_channel` method. No channel tables, no channel logic — just the identity infrastructure that channels depend on.

All design decisions are resolved in the Inter-Agent Communication Workshop, Section 1 (Decision 1.1). See `docs/workshop/interagent-communication/sections/section-1-channel-data-model.md`.

---

## 1. Context & Purpose

### 1.1 Context

The existing Persona model has no type classification. All personas are implicitly AI agent personas running on the operator's hardware. There is no mechanism to represent the operator (a human) as a Persona, and no mechanism to distinguish internal participants from future external collaborators.

The channel system (Sprint 3+) needs to know what a Persona IS to determine how to deliver messages (tmux for agents, SSE for the operator), what visibility rules apply (god-mode for the operator, scoped for external), and whether a persona can create channels. Without a type system, every channel operation would need ad-hoc "is this the operator?" checks scattered across the service layer.

The PersonaType lookup table provides a clean 2x2 matrix (agent/person x internal/external) that answers these questions structurally. The four quadrants are seeded in the migration. v1 exercises only agent/internal and person/internal; the external quadrants are modelled but not exercised.

### 1.2 Target User

The operator (Sam), who needs to participate in channels as a first-class identity alongside agent personas, and the building agents implementing Sprint 3+ channel infrastructure, who need the PersonaType FK to exist on Persona before they can build membership and delivery logic.

### 1.3 Success Moment

The operator runs `flask shell` and queries `Persona.query.all()`. Every existing persona (Robbo, Con, Paula, etc.) has `persona_type_id` pointing to agent/internal. A new "Sam" persona exists with `persona_type_id` pointing to person/internal. The `can_create_channel` method returns `True` for Sam and for any configured agent persona. The schema is ready for Sprint 3 to build Channel, ChannelMembership, and Message tables on top of it.

---

## 2. Scope

### 2.1 In Scope

- PersonaType model (new lookup table with 4 seeded rows)
- `persona_type_id` FK on Persona (NOT NULL, FK to PersonaType)
- Alembic migration: create `persona_types` table, seed 4 rows, add `personas.persona_type_id` column with backfill
- Backfill: all existing Persona records get `persona_type_id` pointing to the agent/internal row
- Create "operator" Role (if it does not already exist)
- Create operator Persona record (name "Sam", role "operator", persona_type = person/internal)
- `can_create_channel` method on the Persona model (service-layer capability check)
- Model registration in `__init__.py`
- Relationship wiring (PersonaType -> Persona, Persona -> PersonaType)

### 2.2 Out of Scope

- Channel, ChannelMembership, Message tables (Sprint 3)
- ChannelService, CLI commands, or any channel operations (Sprint 4)
- Behavioural differences by persona type quadrant at the service layer — delivery routing, visibility rules, trust enforcement (Sprint 4+)
- External persona type enforcement or validation (v2 — modelled in schema but not exercised)
- PositionAssignment for the operator (operator sits above the org hierarchy — no position needed)
- Agent instances for the operator (person-type personas have no Agent records)
- Persona filesystem assets for the operator (no skill.md or experience.md — the operator is not an AI agent)
- Changes to PersonaRegistration service (existing registration flow continues to create agent/internal personas by default)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A `persona_types` table exists in PostgreSQL with exactly 4 rows: agent/internal, agent/external, person/internal, person/external
2. The `(type_key, subtype)` unique constraint prevents duplicate quadrant entries
3. Every Persona record has a non-null `persona_type_id` FK pointing to a valid PersonaType row
4. All pre-existing Persona records are backfilled with `persona_type_id` pointing to the agent/internal row (id=1)
5. A Role with name "operator" exists (created by migration if not already present)
6. A Persona with name "Sam", role "operator", and persona_type = person/internal exists
7. The operator Persona has status "active" and a valid auto-generated slug
8. `persona.can_create_channel` returns `True` for person/internal personas
9. `persona.can_create_channel` returns `True` for agent personas (configurable — initially all agent/internal personas can create channels)
10. `persona.persona_type` relationship loads the associated PersonaType record
11. `persona_type.personas` relationship loads all Persona records for that type
12. The PersonaType model is importable from `claude_headspace.models`
13. `Persona.get_operator()` returns the operator Persona (Sam) with persona_type = person/internal

### 3.2 Non-Functional Success Criteria

1. The migration is reversible (downgrade removes the FK column and the PersonaType table)
2. The migration handles the case where `persona_types` table already exists (idempotent seed)
3. Existing Persona creation flows (PersonaRegistration service, CLI) continue to work — new personas default to agent/internal
4. All existing persona-related tests continue to pass
5. The PersonaType table is a true lookup table — no runtime inserts, no admin UI, no API endpoint

---

## 4. Functional Requirements (FRs)

### PersonaType Model

**FR1: PersonaType lookup table**
The system shall provide a `PersonaType` model mapped to the `persona_types` table with three columns: `id` (integer PK), `type_key` (String(16), NOT NULL), and `subtype` (String(16), NOT NULL). A unique constraint on `(type_key, subtype)` ensures no duplicate quadrants.

**FR2: Seeded rows**
The migration shall insert exactly 4 rows into `persona_types`:

| id | type_key | subtype |
|----|----------|---------|
| 1 | agent | internal |
| 2 | agent | external |
| 3 | person | internal |
| 4 | person | external |

IDs are explicitly set to ensure deterministic FK references in the backfill and operator Persona creation.

### Persona FK

**FR3: `persona_type_id` column on Persona**
The `personas` table shall gain a `persona_type_id` column: integer FK to `persona_types.id`, NOT NULL, ondelete RESTRICT. RESTRICT because deleting a PersonaType quadrant with associated personas is a data integrity violation — it should never happen.

**FR4: Backfill existing personas**
The migration shall set `persona_type_id = 1` (agent/internal) for all existing Persona records. The column is added as NULLABLE first, backfilled, then altered to NOT NULL. This is the standard 3-step Alembic pattern for adding NOT NULL FKs to populated tables.

### Operator Persona

**FR5: Operator Role creation**
The migration shall create a Role with `name = "operator"` and `description = "System operator — human identity for channel participation"`. If a Role named "operator" already exists, skip creation (idempotent).

**FR6: Operator Persona creation**
The migration shall create a Persona record with:
- `name`: "Sam"
- `role_id`: the "operator" Role's id
- `persona_type_id`: 3 (person/internal)
- `status`: "active"
- `slug`: auto-generated via the existing after_insert event (`operator-sam-{id}`)

If a Persona named "Sam" with role "operator" already exists, skip creation (idempotent).

### Channel Creation Capability

**FR7: `can_create_channel` method**
The Persona model shall expose a `can_create_channel` property (or method) that returns `True` if the persona is authorised to create channels. Initial logic:
- person/internal: always `True` (operator can always create channels)
- agent/internal: `True` (agents can create channels — configurable per-persona in future, but v1 allows all internal agents)
- agent/external: `False` (not exercised in v1)
- person/external: `False` (not exercised in v1)

This is a model-level method, not a database column. The logic lives in Python, not in the schema.

**FR8: Operator persona runtime accessor**
The Persona model shall expose a `get_operator()` class method that returns the person/internal Persona record (the operator). Implementation:
```python
@classmethod
def get_operator(cls) -> "Persona | None":
    """Return the operator's Persona (person/internal type), or None."""
    return cls.query.join(PersonaType).filter(
        PersonaType.type_key == "person",
        PersonaType.subtype == "internal",
    ).first()
```
This method is used by S5 (API auth resolution) and S7 (dashboard channel cards) to map a Flask session to the operator's identity.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Migration reversibility**
The downgrade path shall: drop the `persona_type_id` column from `personas`, then drop the `persona_types` table. The operator Persona and operator Role created in the upgrade are NOT removed on downgrade (data preservation — they are harmless records).

**NFR2: No breaking changes to existing flows**
The `PersonaRegistration.register_persona()` function continues to work. New personas created via registration default to `persona_type_id = 1` (agent/internal). The registration service does not need modification in this sprint — the model default handles it.

**NFR3: Lookup table immutability**
PersonaType is a lookup table. No API endpoint, no CLI command, no admin UI for CRUD operations on PersonaType. The 4 rows are seeded in the migration and never modified at runtime. If a fifth quadrant is ever needed, it is added via a new migration.

**NFR4: Model registration**
PersonaType shall be registered in `src/claude_headspace/models/__init__.py` following the existing pattern: import in the imports section, include in `__all__`.

---

## 6. Technical Context

### 6.1 PersonaType Model Implementation

New file: `src/claude_headspace/models/persona_type.py`

```python
"""PersonaType model — lookup table for persona classification."""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class PersonaType(db.Model):
    """
    Lookup table classifying personas into quadrants.

    2x2 matrix: type_key (agent/person) x subtype (internal/external).
    Four rows seeded by migration, never modified at runtime.
    """

    __tablename__ = "persona_types"
    __table_args__ = (
        UniqueConstraint("type_key", "subtype", name="uq_persona_type_key_subtype"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type_key: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    subtype: Mapped[str] = mapped_column(
        String(16), nullable=False
    )

    # Relationships
    personas: Mapped[list["Persona"]] = relationship(
        "Persona", back_populates="persona_type"
    )

    def __repr__(self) -> str:
        return f"<PersonaType id={self.id} type_key={self.type_key} subtype={self.subtype}>"
```

Key implementation notes:
- Uses `UniqueConstraint` in `__table_args__` tuple (same pattern as other models with composite constraints)
- `TYPE_CHECKING` import for `Persona` not needed — relationship uses string reference
- No `created_at` column — lookup tables don't need temporal tracking
- No `description` column — the type_key/subtype pair is self-documenting

### 6.2 Persona Model Changes

Modify: `src/claude_headspace/models/persona.py`

Add the FK column and relationship:

```python
# New import at top
from sqlalchemy import DateTime, ForeignKey, String, Text, event

# New column (after role_id)
persona_type_id: Mapped[int] = mapped_column(
    ForeignKey("persona_types.id", ondelete="RESTRICT"), nullable=False, default=1
)

# New relationship (after role relationship)
persona_type: Mapped["PersonaType"] = relationship(
    "PersonaType", back_populates="personas"
)
```

Add `PersonaType` to the `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from .agent import Agent
    from .persona_type import PersonaType
    from .role import Role
```

Add the `can_create_channel` property:

```python
@property
def can_create_channel(self) -> bool:
    """Whether this persona can create channels.

    person/internal: always True (operator)
    agent/internal: True (v1 allows all internal agents)
    agent/external, person/external: False (not exercised in v1)
    """
    if not self.persona_type:
        return False
    if self.persona_type.subtype == "external":
        return False
    return True  # Both agent/internal and person/internal can create
```

The `default=1` on `persona_type_id` ensures new Persona records created via `PersonaRegistration.register_persona()` automatically get agent/internal without modifying the registration service.

### 6.3 Model Registration

Modify: `src/claude_headspace/models/__init__.py`

Add import:
```python
from .persona_type import PersonaType
```

Add to `__all__`:
```python
"PersonaType",
```

Add to module docstring models list:
```
    - PersonaType: Persona classification lookup (agent/person x internal/external)
```

### 6.4 Migration Design

Single Alembic migration file. The migration performs 5 operations in sequence:

**Step 1: Create `persona_types` table**

```python
op.create_table(
    "persona_types",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("type_key", sa.String(16), nullable=False),
    sa.Column("subtype", sa.String(16), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("type_key", "subtype", name="uq_persona_type_key_subtype"),
)
```

**Step 2: Seed 4 rows with explicit IDs**

```python
persona_types = sa.table(
    "persona_types",
    sa.column("id", sa.Integer),
    sa.column("type_key", sa.String),
    sa.column("subtype", sa.String),
)
op.bulk_insert(persona_types, [
    {"id": 1, "type_key": "agent", "subtype": "internal"},
    {"id": 2, "type_key": "agent", "subtype": "external"},
    {"id": 3, "type_key": "person", "subtype": "internal"},
    {"id": 4, "type_key": "person", "subtype": "external"},
])
```

**Step 3: Add `persona_type_id` column as NULLABLE**

```python
op.add_column("personas", sa.Column("persona_type_id", sa.Integer(), nullable=True))
op.create_foreign_key(
    "fk_personas_persona_type_id",
    "personas",
    "persona_types",
    ["persona_type_id"],
    ["id"],
    ondelete="RESTRICT",
)
```

**Step 4: Backfill all existing personas to agent/internal (id=1)**

```python
op.execute("UPDATE personas SET persona_type_id = 1 WHERE persona_type_id IS NULL")
```

**Step 5: Alter column to NOT NULL**

```python
op.alter_column("personas", "persona_type_id", nullable=False)
```

**Step 6: Create operator Role (idempotent)**

```python
# Use raw SQL for conditional insert
op.execute("""
    INSERT INTO roles (name, description, created_at)
    SELECT 'operator', 'System operator — human identity for channel participation', NOW()
    WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'operator')
""")
```

**Step 7: Create operator Persona (idempotent)**

```python
# Get the operator role id and person/internal type id
op.execute("""
    INSERT INTO personas (name, slug, description, status, role_id, persona_type_id, created_at)
    SELECT
        'Sam',
        '_pending_operator',
        'System operator',
        'active',
        (SELECT id FROM roles WHERE name = 'operator'),
        3,
        NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM personas p
        JOIN roles r ON p.role_id = r.id
        WHERE p.name = 'Sam' AND r.name = 'operator'
    )
""")
```

Note: The slug `_pending_operator` is a temporary value. The after_insert event on the Persona model auto-generates the real slug (`operator-sam-{id}`) when the ORM is involved. However, since this is a raw SQL migration (not ORM), the slug must be updated manually in the same migration:

```python
op.execute("""
    UPDATE personas
    SET slug = 'operator-sam-' || id
    WHERE slug = '_pending_operator'
""")
```

**Downgrade:**

```python
def downgrade():
    op.drop_constraint("fk_personas_persona_type_id", "personas", type_="foreignkey")
    op.drop_column("personas", "persona_type_id")
    op.drop_table("persona_types")
    # Note: operator Role and operator Persona are NOT removed on downgrade
```

### 6.5 Why `ondelete="RESTRICT"` on persona_type_id

The PersonaType table is a fixed lookup with 4 rows. Deleting a quadrant would orphan all personas of that type. RESTRICT prevents accidental deletion at the database level. This differs from most FKs in the codebase which use CASCADE or SET NULL — those are for runtime entities that come and go. PersonaType rows are infrastructure.

### 6.6 Why `default=1` on persona_type_id

The model-level `default=1` means new Persona records created via the ORM (e.g., `PersonaRegistration.register_persona()`) automatically get agent/internal without any code changes to the registration service. This is correct for v1 where all programmatically-created personas are agent-type. If a future sprint needs to create person-type personas programmatically, the caller explicitly sets `persona_type_id=3`.

### 6.7 `can_create_channel` Design Rationale

This is a model property, not a database column, because:
- The logic is simple (check subtype) and doesn't need query-level filtering
- It will likely evolve (per-persona override, role-based rules) — a Python method is easier to extend than a computed column
- Sprint 3's ChannelService will call `persona.can_create_channel` as a precondition check before `Channel` creation
- The workshop (Decision 2.1) specifies: "can_create_channel — service-layer check delegated from Agent to Persona. Not a DB column; implemented as a method on the Persona model that checks persona type and/or role."

### 6.8 Existing Code Patterns (Reference for Building Agent)

**Model file pattern** — see `src/claude_headspace/models/role.py` (43 lines):
- SQLAlchemy 2.0 `Mapped` type annotations
- `mapped_column()` for all columns
- `TYPE_CHECKING` block for circular import prevention
- `relationship()` with string model reference and `back_populates`
- `__repr__` method

**Model registration pattern** — see `src/claude_headspace/models/__init__.py`:
- Import model class at top level
- Add to `__all__` list
- Add to module docstring

**Persona model current state** — see `src/claude_headspace/models/persona.py` (86 lines):
- Uses `_temp_slug()` factory for initial slug, replaced by `after_insert` event
- `role_id` FK with `ForeignKey("roles.id")` — no explicit `ondelete` (defaults to database default)
- `generate_slug()` method builds `{role}-{name}-{id}` pattern
- `_slugify()` static method for text sanitization
- `@event.listens_for(Persona, "after_insert")` wires the slug replacement

**Migration pattern** — see `migrations/versions/` directory:
- Revision IDs are alphanumeric strings (e.g., `z7a8b9c0d1e2`)
- Files use `sa.Column()`, `op.add_column()`, `op.create_table()`, `op.create_foreign_key()`
- Both `upgrade()` and `downgrade()` functions required

### 6.9 Files to Modify

| File | Change |
|------|--------|
| `src/claude_headspace/models/persona.py` | Add `persona_type_id` FK column (NOT NULL, default=1, ondelete RESTRICT). Add `persona_type` relationship. Add `PersonaType` to TYPE_CHECKING imports. Add `can_create_channel` property. |
| `src/claude_headspace/models/__init__.py` | Import `PersonaType`. Add to `__all__`. Update module docstring. |

### 6.10 New Files

| File | Purpose |
|------|---------|
| `src/claude_headspace/models/persona_type.py` | PersonaType model — lookup table with `type_key`, `subtype`, unique constraint, relationship to Persona. |
| `migrations/versions/{rev}_add_persona_type_system.py` | Alembic migration: create table, seed rows, add FK, backfill, create operator Role + Persona. |

### 6.11 Design Decisions (All Resolved — Workshop Section 1, Decision 1.1)

| Decision | Resolution | Source |
|----------|-----------|--------|
| PersonaType structure | Lookup table with `type_key` (agent/person) and `subtype` (internal/external), both NOT NULL | 1.1 |
| Number of quadrants | 4: agent/internal, agent/external, person/internal, person/external | 1.1 |
| FK on Persona | `persona_type_id` NOT NULL — every persona is in exactly one quadrant from creation | 1.1 |
| Backfill strategy | All existing personas get agent/internal (id=1) | 1.1, Section 5 |
| Operator modelling | Person/internal Persona with "operator" Role. No Agent instances, no PositionAssignment | 1.1 |
| External quadrants | Modelled in schema, not exercised in v1 | 1.1 |
| Channel creation capability | Model property, not DB column. person/internal and agent/internal can create | 2.1 |
| ondelete behaviour | RESTRICT — PersonaType rows are infrastructure, not runtime entities | Workshop convention |

### 6.12 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration fails on populated `personas` table due to NOT NULL constraint | Very Low | Medium | 3-step pattern: add NULLABLE, backfill, alter to NOT NULL. Standard Alembic practice. |
| Operator Persona slug collision | Very Low | Low | Idempotent insert checks for existing Sam/operator before creating. Slug uses `operator-sam-{id}` pattern — unique by ID. |
| `default=1` on `persona_type_id` silently creates wrong type for future person personas | Low | Low | v1 only creates agent personas programmatically. Any future person persona creation path must explicitly set `persona_type_id`. Documented in code comments. |
| PersonaType rows deleted accidentally | Very Low | High | `ondelete="RESTRICT"` prevents deletion when associated personas exist. All 4 rows will have at least one persona (backfill guarantees agent/internal has records; operator guarantees person/internal). |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| Persona model | E8-S5 (done) | Existing Persona table to extend with FK |
| Role model | E8-S5 (done) | Existing Role table for operator Role creation |
| Alembic / Flask-Migrate | Infrastructure (done) | Migration framework |
| SQLAlchemy 2.0 mapped columns | Infrastructure (done) | Model definition patterns |

No unresolved dependencies. All prerequisites are shipped.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Decision 1.1, Section 5 migration checklist) |
