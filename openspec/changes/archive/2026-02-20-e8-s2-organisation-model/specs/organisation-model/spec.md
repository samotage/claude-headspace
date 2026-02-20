## ADDED Requirements

### Requirement: Organisation Model

The system SHALL provide an Organisation database model representing an organisational grouping. In v1, this table holds a single seed record. It exists as infrastructure for future multi-org capability — Position records will reference Organisation via a foreign key.

Fields:
- `id` — integer, primary key, auto-increment
- `name` — string, not null
- `description` — text, nullable
- `status` — string, not null, defaults to "active" (valid values: "active", "dormant", "archived")
- `created_at` — datetime with timezone, defaults to current UTC time

The model SHALL inherit from `db.Model`, use `Mapped[type]` and `mapped_column()` for column definitions, and use `DateTime(timezone=True)` for timestamps.

#### Scenario: Create an Organisation

- **WHEN** an Organisation is created with name="Development" and status="active"
- **THEN** the Organisation record is persisted with the given name, status, and auto-generated id and created_at

#### Scenario: Organisation name is required

- **WHEN** an Organisation is created with name=None
- **THEN** the database SHALL raise an IntegrityError due to the not-null constraint on name

#### Scenario: Organisation status values

- **WHEN** an Organisation is created with status="dormant" or status="archived"
- **THEN** the Organisation record is persisted with the given status value

---

### Requirement: Seed Data

The Alembic migration MUST seed one Organisation record with name="Development" and status="active". This ensures the dev org exists immediately after migration.

#### Scenario: Seed data present after migration

- **WHEN** the migration is applied (upgrade)
- **THEN** an Organisation record with name="Development" and status="active" SHALL exist in the database

---

### Requirement: Model Registration

The Organisation model MUST be registered in `src/claude_headspace/models/__init__.py` following the existing pattern (import + `__all__` entry) so it is discovered by Flask-SQLAlchemy.

#### Scenario: Model discoverable by Flask-SQLAlchemy

- **WHEN** the application starts and Flask-SQLAlchemy initialises
- **THEN** the Organisation model SHALL be importable from `claude_headspace.models`
- **AND** it SHALL appear in the `__all__` export list

---

### Requirement: Alembic Migration

A single Alembic migration MUST create the Organisation table and seed the dev org record.

#### Scenario: Migration upgrade

- **WHEN** the migration is applied (upgrade)
- **THEN** the Organisation table SHALL be created
- **AND** one seed record (name="Development", status="active") SHALL be inserted
- **AND** all existing tables SHALL remain unaffected

#### Scenario: Migration downgrade

- **WHEN** the migration is reversed (downgrade)
- **THEN** the seed data SHALL be deleted
- **AND** the Organisation table SHALL be dropped
- **AND** all existing tables SHALL remain unaffected
