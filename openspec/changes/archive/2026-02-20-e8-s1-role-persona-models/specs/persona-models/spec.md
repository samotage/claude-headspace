## ADDED Requirements

### Requirement: Role Model

The system SHALL provide a Role database model representing an agent specialisation. Role is a shared lookup table defining the vocabulary of specialisations (e.g., "developer", "tester", "pm", "architect").

Fields:
- `id` — integer, primary key, auto-increment
- `name` — string, unique, not null
- `description` — text, nullable
- `created_at` — datetime with timezone, defaults to current UTC time

The model SHALL inherit from `db.Model`, use `Mapped[type]` and `mapped_column()` for column definitions, and use `DateTime(timezone=True)` for timestamps.

#### Scenario: Create a Role

- **WHEN** a Role is created with name="developer" and description="Backend Python development"
- **THEN** the Role record is persisted with the given name, description, and auto-generated id and created_at

#### Scenario: Role name uniqueness

- **WHEN** a Role with name="developer" already exists and another Role with name="developer" is created
- **THEN** the database SHALL raise an IntegrityError due to the unique constraint on name

---

### Requirement: Persona Model

The system SHALL provide a Persona database model representing a named agent identity. Each Persona MUST reference exactly one Role via a foreign key.

Fields:
- `id` — integer, primary key, auto-increment
- `slug` — string, unique, not null (generated as `{role_name}-{persona_name}-{id}`)
- `name` — string, not null (display name)
- `description` — text, nullable (core identity description)
- `status` — string, defaults to "active" (valid values: "active", "archived")
- `role_id` — integer, foreign key to Role.id, not null
- `created_at` — datetime with timezone, defaults to current UTC time

#### Scenario: Create a Persona

- **WHEN** a Persona is created with name="Con", role_id referencing a "developer" Role, and id=1
- **THEN** the Persona record is persisted with slug="developer-con-1", status="active", and auto-generated created_at

#### Scenario: Persona status default

- **WHEN** a Persona is created without specifying status
- **THEN** the status field SHALL default to "active"

#### Scenario: Persona requires a Role

- **WHEN** a Persona is created without a valid role_id
- **THEN** the database SHALL raise an IntegrityError due to the not-null and foreign key constraints

---

### Requirement: Slug Generation

The Persona slug MUST be generated from the role name, persona name, and persona id in the format `{role_name}-{persona_name}-{id}`. All components SHALL be lowercased and joined with hyphens.

#### Scenario: Standard slug generation

- **WHEN** a Persona with name="Con" is created with Role name="developer" and receives id=1
- **THEN** the slug SHALL be "developer-con-1"

#### Scenario: Slug uniqueness via id

- **WHEN** two Personas with name="Con" and Role "developer" are created with ids 1 and 7
- **THEN** their slugs SHALL be "developer-con-1" and "developer-con-7" respectively

#### Scenario: Slug uniqueness constraint

- **WHEN** a Persona with a duplicate slug is inserted
- **THEN** the database SHALL raise an IntegrityError due to the unique constraint on slug

---

### Requirement: Role-Persona Bidirectional Relationship

The system MUST define a bidirectional relationship between Role and Persona.

#### Scenario: Access Personas from Role

- **WHEN** a Role has associated Persona records
- **THEN** `Role.personas` SHALL return a list of all Persona objects associated with that Role

#### Scenario: Access Role from Persona

- **WHEN** a Persona has a role_id referencing a Role
- **THEN** `Persona.role` SHALL return the associated Role object

#### Scenario: Role with no Personas

- **WHEN** a Role has no associated Persona records
- **THEN** `Role.personas` SHALL return an empty list

---

### Requirement: Model Registration

Both Role and Persona models MUST be registered in `src/claude_headspace/models/__init__.py` following the existing pattern (import + `__all__` entry) so they are discovered by Flask-SQLAlchemy.

#### Scenario: Models discoverable by Flask-SQLAlchemy

- **WHEN** the application starts and Flask-SQLAlchemy initialises
- **THEN** both Role and Persona models SHALL be importable from `claude_headspace.models`
- **AND** both SHALL appear in the `__all__` export list

---

### Requirement: Alembic Migration

A single Alembic migration MUST create both the Role and Persona tables.

#### Scenario: Migration upgrade

- **WHEN** the migration is applied (upgrade)
- **THEN** the Role table SHALL be created first, followed by the Persona table with its role_id FK
- **AND** all existing tables SHALL remain unaffected

#### Scenario: Migration downgrade

- **WHEN** the migration is reversed (downgrade)
- **THEN** the Persona table SHALL be dropped first, followed by the Role table
- **AND** all existing tables SHALL remain unaffected
