# handoff-model Specification

## Purpose
Stores handoff metadata for agent context handoffs — reason, file path to the handoff document, and injection prompt sent to the successor agent.

## ADDED Requirements

### Requirement: Handoff table with integer primary key

The system SHALL store handoff records in a dedicated `handoffs` table with an auto-incrementing integer primary key.

#### Scenario: Table creation via migration
- **WHEN** the Alembic migration is applied
- **THEN** the `handoffs` table exists with columns: id, agent_id, reason, file_path, injection_prompt, created_at

### Requirement: Handoff references outgoing agent

Each handoff record SHALL reference the outgoing agent via a non-nullable foreign key to the agents table with ON DELETE CASCADE.

#### Scenario: Handoff created for agent
- **WHEN** a Handoff is created with a valid agent_id
- **THEN** the record is persisted and `handoff.agent` navigates to the referenced Agent

#### Scenario: Agent deleted cascades to handoff
- **WHEN** an Agent with a Handoff record is deleted
- **THEN** the associated Handoff record is also deleted

### Requirement: Handoff reason field

Each handoff record SHALL capture the reason as a non-nullable string field. Valid reasons are "context_limit", "shift_end", and "task_boundary".

#### Scenario: Handoff with reason
- **WHEN** a Handoff is created with reason "context_limit"
- **THEN** the record is persisted with reason="context_limit"

### Requirement: Handoff file path field

Each handoff record SHALL store the filesystem path to the handoff document as a nullable string field.

#### Scenario: Handoff with file path
- **WHEN** a Handoff is created with file_path set
- **THEN** the record stores the path (e.g., "data/personas/developer-con-1/handoffs/20260220T143025-4b6f8a2c.md")

#### Scenario: Handoff without file path
- **WHEN** a Handoff is created without file_path
- **THEN** the file_path field is NULL

### Requirement: Handoff injection prompt field

Each handoff record SHALL store the injection prompt as a nullable text field.

#### Scenario: Handoff with injection prompt
- **WHEN** a Handoff is created with injection_prompt set
- **THEN** the record stores the full orchestration prompt text

### Requirement: Handoff created_at timestamp

Each handoff record SHALL have a created_at timestamp defaulting to the current time.

#### Scenario: Handoff creation timestamp
- **WHEN** a Handoff is created without specifying created_at
- **THEN** created_at is automatically set to the current UTC time

### Requirement: Agent to handoff navigation

The Agent model SHALL provide a `handoff` relationship that returns the associated Handoff record if one exists, or None.

#### Scenario: Agent with handoff
- **WHEN** an Agent has an associated Handoff record
- **THEN** `agent.handoff` returns the Handoff instance

#### Scenario: Agent without handoff
- **WHEN** an Agent has no associated Handoff record
- **THEN** `agent.handoff` returns None

### Requirement: Backward compatibility

All existing tables, queries, services, routes, and tests SHALL continue working without modification after the Handoff model and migration are added.

#### Scenario: Existing functionality preserved
- **WHEN** the migration is applied and the Handoff model is registered
- **THEN** all existing Agent, Command, Turn, Event, and other model operations work identically to before
