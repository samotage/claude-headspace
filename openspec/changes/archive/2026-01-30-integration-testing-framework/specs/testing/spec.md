## ADDED Requirements

### Requirement: Test Database Lifecycle Management

The test infrastructure SHALL automatically manage a dedicated Postgres test database for integration tests.

#### Scenario: Test session starts

- **WHEN** `pytest tests/integration/` is invoked
- **THEN** a dedicated Postgres database (`claude_headspace_test`) SHALL be created
- **AND** if the database already exists, it SHALL be dropped and recreated
- **AND** the schema SHALL be created using the project's SQLAlchemy model metadata

#### Scenario: Test session ends

- **WHEN** all integration tests have completed
- **THEN** the test database SHALL be dropped automatically
- **AND** no persistent state SHALL remain

#### Scenario: Per-test isolation

- **WHEN** each individual test function runs
- **THEN** it SHALL operate on a clean database state
- **AND** no data from previous tests SHALL be visible

---

### Requirement: Test Database Configuration

The test database connection SHALL be configurable independently from production.

#### Scenario: Environment variable override

- **WHEN** `TEST_DATABASE_URL` environment variable is set
- **THEN** the integration test fixtures SHALL use that URL for the test database

#### Scenario: Default configuration

- **WHEN** no `TEST_DATABASE_URL` is set
- **THEN** the test fixtures SHALL construct a URL using production config values but with database name `claude_headspace_test`

---

### Requirement: Factory Boy Factories

Factory Boy factories SHALL exist for all domain models and produce valid, persistable instances.

#### Scenario: Factory creates valid model instance

- **WHEN** any factory (Project, Agent, Command, Turn, Event, Objective, ObjectiveHistory) builds an instance
- **THEN** the instance SHALL have all required fields populated with valid values
- **AND** the instance SHALL be persistable to Postgres without constraint violations
- **AND** foreign key relationships SHALL reference valid parent entities

#### Scenario: Factory respects model relationships

- **WHEN** `AgentFactory` creates an Agent
- **THEN** it SHALL automatically create or reference a valid Project via SubFactory
- **WHEN** `CommandFactory` creates a Command
- **THEN** it SHALL automatically create or reference a valid Agent via SubFactory
- **WHEN** `TurnFactory` creates a Turn
- **THEN** it SHALL automatically create or reference a valid Task via SubFactory
- **WHEN** `ObjectiveHistoryFactory` creates an ObjectiveHistory
- **THEN** it SHALL automatically create or reference a valid Objective via SubFactory

#### Scenario: Factory generates valid enum values

- **WHEN** `CommandFactory` generates a Command
- **THEN** the `state` field SHALL be a valid `CommandState` enum value
- **WHEN** `TurnFactory` generates a Turn
- **THEN** the `actor` field SHALL be a valid `TurnActor` enum value
- **AND** the `intent` field SHALL be a valid `TurnIntent` enum value

---

### Requirement: Integration Test Directory

Integration tests SHALL be organized in a dedicated directory and runnable independently.

#### Scenario: Run integration tests only

- **WHEN** `pytest tests/integration/` is executed
- **THEN** only integration tests SHALL run
- **AND** no mock-based unit tests SHALL execute

#### Scenario: Run full test suite

- **WHEN** `pytest` is executed without path arguments
- **THEN** both unit tests and integration tests SHALL run
- **AND** they SHALL not interfere with each other

---

### Requirement: End-to-End Persistence Verification

At least one integration test SHALL verify the complete entity chain persistence.

#### Scenario: Full entity chain persistence

- **WHEN** a test creates Project → Agent → Command → Turn → Event
- **AND** persists all entities to the test database
- **AND** retrieves all entities via fresh database queries
- **THEN** all field values SHALL match the original data
- **AND** all relationships SHALL be correctly linked
- **AND** all foreign keys SHALL reference the correct parent entities

---

### Requirement: Integration Testing Documentation

A pattern document SHALL describe how to write integration tests.

#### Scenario: New developer writes an integration test

- **WHEN** a developer reads the integration testing guide
- **THEN** they SHALL find prerequisites (Postgres requirement)
- **AND** they SHALL find instructions for running integration tests
- **AND** they SHALL find a step-by-step example of writing a new test
- **AND** they SHALL find factory usage patterns and fixture reference
