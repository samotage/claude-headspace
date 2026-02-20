# position-model Specification

## Purpose
TBD - created by archiving change e8-s3-position-model. Update Purpose after archive.
## Requirements
### Requirement: Position Model

The system SHALL provide a Position database model representing a seat in an organisational chart. Each position belongs to one Organisation, requires one Role, and optionally reports to and escalates to other positions in the same hierarchy.

Fields:
- `id` — integer, primary key, auto-increment
- `org_id` — integer, foreign key to Organisation.id, not null
- `role_id` — integer, foreign key to Role.id, not null
- `title` — string, not null
- `reports_to_id` — integer, foreign key to Position.id, nullable (self-referential reporting chain)
- `escalates_to_id` — integer, foreign key to Position.id, nullable (self-referential escalation path)
- `level` — integer, not null, defaults to 0 (depth in hierarchy)
- `is_cross_cutting` — boolean, not null, defaults to False
- `created_at` — datetime with timezone, defaults to current UTC time

The model SHALL inherit from `db.Model`, use `Mapped[type]` and `mapped_column()` for column definitions, and use `DateTime(timezone=True)` for timestamps.

All foreign keys SHALL use ON DELETE CASCADE.

#### Scenario: Create a Position

- **WHEN** a Position is created with org_id referencing an existing Organisation, role_id referencing an existing Role, and title="Lead Developer"
- **THEN** the Position record is persisted with the given fields and auto-generated id and created_at
- **AND** level defaults to 0 and is_cross_cutting defaults to False

#### Scenario: Position title is required

- **WHEN** a Position is created with title=None
- **THEN** the database SHALL raise an IntegrityError due to the not-null constraint on title

#### Scenario: Position requires organisation and role

- **WHEN** a Position is created without org_id or role_id
- **THEN** the database SHALL raise an IntegrityError due to the not-null constraint

---

### Requirement: Self-Referential Reporting Hierarchy

The system SHALL support a self-referential reporting chain via `reports_to_id`. This foreign key points to another Position record in the same table, building a tree structure representing the org chart. Top-level positions (reports_to_id = NULL) implicitly report to the operator.

#### Scenario: Build reporting chain

- **WHEN** Position A is created with reports_to_id=NULL (top-level)
- **AND** Position B is created with reports_to_id=A.id
- **THEN** B.reports_to SHALL return Position A
- **AND** A.direct_reports SHALL include Position B

#### Scenario: Top-level position

- **WHEN** a Position is created with reports_to_id=NULL
- **THEN** reports_to SHALL return None
- **AND** the position is at the top of the reporting hierarchy

---

### Requirement: Self-Referential Escalation Path

The system SHALL support a separate escalation path via `escalates_to_id`. This foreign key points to another Position record but MAY reference a different position than `reports_to_id`.

#### Scenario: Escalation differs from reporting

- **WHEN** Position A (architect) exists
- **AND** Position B (PM) exists
- **AND** Position C (developer) is created with reports_to_id=B.id and escalates_to_id=A.id
- **THEN** C.reports_to SHALL return Position B
- **AND** C.escalates_to SHALL return Position A

---

### Requirement: Position Relationships

The system SHALL define the following relationships:
- `Position.role` — returns the Role record (many-to-one)
- `Position.organisation` — returns the Organisation record (many-to-one)
- `Position.reports_to` — returns the parent Position (many-to-one, self-referential, nullable)
- `Position.escalates_to` — returns the escalation target Position (many-to-one, self-referential, nullable)
- `Position.direct_reports` — returns all Positions where reports_to_id equals this position's id (one-to-many)

#### Scenario: Navigate relationships

- **WHEN** a Position exists with org_id, role_id, and reports_to_id set
- **THEN** Position.role SHALL return the associated Role object
- **AND** Position.organisation SHALL return the associated Organisation object
- **AND** Position.reports_to SHALL return the parent Position object

---

### Requirement: Backref Relationships on Existing Models

The system SHALL define backref relationships accessible from Organisation and Role:
- `Organisation.positions` — returns all Position records belonging to that organisation
- `Role.positions` — returns all Position records requiring that role

#### Scenario: Organisation has positions

- **WHEN** multiple Positions exist with the same org_id
- **THEN** Organisation.positions SHALL return all those Position records

#### Scenario: Role has positions

- **WHEN** multiple Positions exist with the same role_id
- **THEN** Role.positions SHALL return all those Position records

---

### Requirement: Model Registration

The Position model MUST be registered in `src/claude_headspace/models/__init__.py` following the existing pattern (import + `__all__` entry) so it is discovered by Flask-SQLAlchemy.

#### Scenario: Model discoverable by Flask-SQLAlchemy

- **WHEN** the application starts and Flask-SQLAlchemy initialises
- **THEN** the Position model SHALL be importable from `claude_headspace.models`
- **AND** it SHALL appear in the `__all__` export list

---

### Requirement: Alembic Migration

A single Alembic migration MUST create the Position table with foreign keys to Organisation, Role, and two self-referential foreign keys. No seed data is required.

#### Scenario: Migration upgrade

- **WHEN** the migration is applied (upgrade)
- **THEN** the Position table SHALL be created with all specified columns and foreign keys
- **AND** all existing tables SHALL remain unaffected

#### Scenario: Migration downgrade

- **WHEN** the migration is reversed (downgrade)
- **THEN** the Position table SHALL be dropped
- **AND** all existing tables SHALL remain unaffected

