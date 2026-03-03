## ADDED Requirements

### Requirement: PersonaType Lookup Table (FR1, FR2)

The system SHALL provide a `PersonaType` model mapped to the `persona_types` table with columns: `id` (integer PK), `type_key` (String(16), NOT NULL), and `subtype` (String(16), NOT NULL). A unique constraint on `(type_key, subtype)` MUST prevent duplicate quadrant entries.

The migration SHALL seed exactly 4 rows with deterministic IDs:

| id | type_key | subtype  |
|----|----------|----------|
| 1  | agent    | internal |
| 2  | agent    | external |
| 3  | person   | internal |
| 4  | person   | external |

#### Scenario: Table exists with correct data

- **WHEN** the migration has run
- **THEN** the `persona_types` table contains exactly 4 rows with the above values

#### Scenario: Duplicate quadrant insertion

- **WHEN** an insert attempts to create a row with an existing `(type_key, subtype)` pair
- **THEN** a unique constraint violation is raised

---

### Requirement: Persona FK to PersonaType (FR3, FR4)

The `personas` table SHALL have a `persona_type_id` column: integer FK to `persona_types.id`, NOT NULL, ondelete RESTRICT.

All pre-existing Persona records SHALL be backfilled with `persona_type_id = 1` (agent/internal).

New Persona records created via ORM SHALL default to `persona_type_id = 1` (agent/internal) without modification to existing creation flows.

#### Scenario: Existing personas backfilled

- **WHEN** the migration runs on a database with existing Persona records
- **THEN** every Persona record has `persona_type_id = 1`

#### Scenario: New persona defaults to agent/internal

- **WHEN** a new Persona is created via `PersonaRegistration.register_persona()` without specifying `persona_type_id`
- **THEN** the Persona record has `persona_type_id = 1` (agent/internal)

#### Scenario: PersonaType deletion prevented

- **WHEN** a DELETE is attempted on a `persona_types` row that has associated Persona records
- **THEN** a RESTRICT violation prevents the deletion

---

### Requirement: Operator Role and Persona (FR5, FR6)

The migration SHALL create a Role with `name = "operator"` if one does not already exist.

The migration SHALL create a Persona with `name = "Sam"`, `role = "operator"`, `persona_type_id = 3` (person/internal), `status = "active"`, and slug `operator-sam-{id}`.

Both operations MUST be idempotent.

#### Scenario: Operator created on fresh database

- **WHEN** the migration runs and no "operator" Role or "Sam" Persona exists
- **THEN** both are created with correct attributes

#### Scenario: Operator already exists

- **WHEN** the migration runs and the "operator" Role and "Sam" Persona already exist
- **THEN** no duplicate records are created

#### Scenario: Operator slug format

- **WHEN** the operator Persona is created
- **THEN** the slug follows the pattern `operator-sam-{id}`

---

### Requirement: Channel Creation Capability (FR7)

The Persona model SHALL expose a `can_create_channel` property returning a boolean.

#### Scenario: person/internal can create channels

- **WHEN** a Persona has persona_type = person/internal
- **THEN** `can_create_channel` returns `True`

#### Scenario: agent/internal can create channels

- **WHEN** a Persona has persona_type = agent/internal
- **THEN** `can_create_channel` returns `True`

#### Scenario: external personas cannot create channels

- **WHEN** a Persona has persona_type with subtype = "external"
- **THEN** `can_create_channel` returns `False`

#### Scenario: No persona_type loaded

- **WHEN** a Persona has no `persona_type` relationship loaded (None)
- **THEN** `can_create_channel` returns `False`

---

### Requirement: Operator Runtime Accessor (FR8)

The Persona model SHALL expose a `get_operator()` classmethod that returns the person/internal Persona record.

#### Scenario: Operator exists

- **WHEN** `Persona.get_operator()` is called and the operator Persona exists
- **THEN** the method returns the Persona with persona_type = person/internal

#### Scenario: No operator

- **WHEN** `Persona.get_operator()` is called and no person/internal Persona exists
- **THEN** the method returns `None`

---

### Requirement: Model Registration (NFR4)

PersonaType SHALL be importable from `claude_headspace.models` and included in the `__all__` list.

#### Scenario: Import works

- **WHEN** `from claude_headspace.models import PersonaType` is executed
- **THEN** the import succeeds and returns the PersonaType class

---

### Requirement: Migration Reversibility (NFR1)

The migration downgrade SHALL drop the `persona_type_id` column from `personas` and drop the `persona_types` table. The operator Role and Persona created in the upgrade SHALL NOT be removed on downgrade.

#### Scenario: Clean downgrade

- **WHEN** the migration is downgraded
- **THEN** the `persona_type_id` column is removed from `personas`
- **AND** the `persona_types` table is dropped
- **AND** the "operator" Role and "Sam" Persona records remain intact

---

### Requirement: No Breaking Changes (NFR2)

Existing Persona creation flows (PersonaRegistration service, CLI) SHALL continue to work without modification. The model-level `default=1` on `persona_type_id` provides backward compatibility.

#### Scenario: Existing registration flow

- **WHEN** `PersonaRegistration.register_persona()` is called with existing parameters
- **THEN** a Persona is created with `persona_type_id = 1` (agent/internal)
- **AND** no errors are raised
