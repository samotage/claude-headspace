# testing Specification

## Purpose
TBD - created by archiving change integration-testing-framework. Update Purpose after archive.
## Requirements
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

### Requirement: Agent-Driven Integration Test — Session Launch

The system SHALL provide a pytest fixture (`claude_session`) that launches a real `claude` CLI session in a dedicated tmux pane, configured with hooks pointing to the test server URL and using the Haiku model.

#### Scenario: Successful session launch

- **WHEN** the `claude_session` fixture is invoked
- **THEN** a new tmux session is created with a unique name (`headspace-test-<uuid>`)
- **AND** the `claude` CLI is launched with `--model haiku` and hooks endpoint set to the test server
- **AND** the fixture waits for a `session-start` hook to arrive (Agent record in DB)
- **AND** the fixture yields session info (agent_id, tmux_session_name, tmux_pane_id)

#### Scenario: Session launch timeout

- **WHEN** the `claude_session` fixture is invoked
- **AND** no `session-start` hook arrives within 30 seconds
- **THEN** the fixture SHALL raise a timeout error
- **AND** the tmux session SHALL be preserved for investigation

### Requirement: Agent-Driven Integration Test — Session Isolation

Each test scenario SHALL run in its own tmux session with a unique name to prevent cross-contamination between tests.

#### Scenario: Unique session naming

- **WHEN** two tests run sequentially
- **THEN** each test uses a distinct tmux session name
- **AND** no state leaks between sessions

### Requirement: Agent-Driven Integration Test — Conditional Teardown

The test framework SHALL implement conditional teardown: cleanup on success, preserve on failure.

#### Scenario: Test passes

- **WHEN** a test completes successfully
- **THEN** the tmux session is killed
- **AND** test database state is cleaned

#### Scenario: Test fails

- **WHEN** a test fails
- **THEN** the tmux session is preserved (stays open)
- **AND** database state is preserved for investigation
- **AND** any screenshots are saved

### Requirement: Agent-Driven Integration Test — Voice Chat Round-Trip

The test SHALL navigate Playwright to the voice chat UI, select the agent, send a command, and verify the agent response appears in the DOM.

#### Scenario: Successful command round-trip

- **WHEN** a command is sent via `VoiceAssertions.send_chat_message()`
- **THEN** the command is delivered to the real Claude Code session via tmux
- **AND** Claude Code processes the command and fires hooks back
- **AND** an agent response bubble appears in the voice chat DOM (element with `data-turn-id` and agent actor class)
- **AND** the bubble appears within 60 seconds (configurable timeout)

### Requirement: Agent-Driven Integration Test — State Transition Verification

The test SHALL verify that the command state transitioned through the expected path by querying the database.

#### Scenario: Expected state transitions

- **WHEN** a command is sent and processed
- **THEN** the Command record in the database reaches COMPLETE state
- **AND** the state transition path includes COMMANDED → PROCESSING → COMPLETE

### Requirement: Agent-Driven Integration Test — Cost Control

The test SHALL use Haiku model with short, deterministic prompts to minimise LLM costs.

#### Scenario: Cost-controlled execution

- **WHEN** the test executes
- **THEN** the Claude Code session uses the Haiku model
- **AND** the prompt is a short, deterministic instruction (file creation)
- **AND** only a single interaction is performed per test

### Requirement: Agent-Driven Integration Test — Server Target

The test system SHALL target the real running server. The server URL is read from `config.yaml` (`server.application_url`).

#### Scenario: Server URL configuration

- **WHEN** the test starts
- **THEN** the server URL is read from `config.yaml`
- **AND** Playwright connects to the real running server with `--ignore-https-errors`

### Requirement: Question/Answer Flow Test (FR9)

The test suite SHALL include a scenario that exercises the AskUserQuestion tool flow through the full stack: voice chat UI to Claude Code to hooks to database to SSE to DOM rendering.

#### Scenario: Successful question/answer interaction

- **WHEN** a prompt is sent via voice chat that instructs Claude Code to use AskUserQuestion with specific options
- **THEN** the database Command record MUST reach AWAITING_INPUT state
- **AND** a question bubble MUST be rendered in the voice chat DOM
- **AND** option text MUST be visible in the question bubble
- **WHEN** an option is selected (via tmux send-keys Enter)
- **THEN** the Command record MUST reach COMPLETE state
- **AND** a response bubble MUST be rendered in the voice chat DOM

### Requirement: Multi-Turn Conversation Test (FR10)

The test suite SHALL include a scenario that exercises sequential command/response cycles within a single Claude Code session.

#### Scenario: Two sequential command/response cycles

- **WHEN** a first command is sent via voice chat and completes
- **AND** a second command is sent via voice chat and completes
- **THEN** both Command records MUST reach COMPLETE state in the database
- **AND** the database MUST contain the correct number of user turns and agent turns (at least 2 user turns, at least 2 agent turns)
- **AND** all chat bubbles MUST be rendered in the voice chat DOM in chronological order
- **AND** a command separator MUST be visible between the two command groups in the DOM

### Requirement: DOM/API Consistency Verification (FR11)

At the end of any scenario, a verification step SHALL fetch the API transcript endpoint and compare it against the voice chat DOM.

#### Scenario: DOM and API transcript agree

- **WHEN** the scenario completes and verification runs
- **THEN** the number of substantive turns in the DOM MUST equal the number of turns in the API response (excluding PROGRESS turns with empty text)
- **AND** the set of turn IDs present in the DOM MUST match the set in the API response
- **AND** the actor sequence (USER/AGENT ordering) MUST be consistent between DOM and API

### Requirement: DOM/DB Consistency Verification (FR12)

At the end of any scenario, a verification step SHALL query the database directly and compare against the voice chat DOM.

#### Scenario: DOM and database agree

- **WHEN** the scenario completes and verification runs
- **THEN** Turn records in the database MUST match bubbles in the DOM by turn_id
- **AND** Command records MUST reflect COMPLETE state
- **AND** an Agent record MUST exist with the correct project association

### Requirement: Timestamp Ordering Verification (FR13)

Turns in both the API transcript and the database SHALL be monotonically ordered by timestamp.

#### Scenario: No out-of-order timestamps

- **WHEN** the scenario completes and verification runs
- **THEN** turns in the API transcript response MUST be ordered by ascending timestamp
- **AND** Turn records queried from the database MUST be ordered by ascending timestamp
- **AND** no two adjacent turns SHALL have timestamps where the later turn precedes the earlier turn

### Requirement: Screenshot Capture (FR14)

Every scenario SHALL capture before/after screenshots via Playwright for visual evidence.

#### Scenario: Screenshots saved for scenario stages

- **WHEN** any agent-driven test scenario executes
- **THEN** screenshots MUST be saved to a test-run-specific directory at each key interaction stage
- **AND** screenshots MUST be captured at minimum for: chat ready, command sent, response received, test complete

### Requirement: Shared Helper Functions (FR15)

Common patterns proven across Sprint 1+2 tests SHALL be extracted into shared helper functions in `tests/agent_driven/helpers/`.

#### Scenario: Cross-layer verification as shared helper

- **WHEN** a test needs to verify DOM/API/DB consistency
- **THEN** it SHALL import and call the shared `verify_cross_layer_consistency` function from `tests/agent_driven/helpers/cross_layer.py`
- **AND** the function MUST be a plain function (not a class, decorator, or framework)
- **AND** the function MUST be used by at least 3 test files

#### Scenario: Structured test output helper

- **WHEN** a test scenario executes
- **THEN** it SHALL produce structured output including scenario name, step progress, and elapsed time
- **AND** the output helper MUST be importable from `tests/agent_driven/helpers/output.py`

### Requirement: Permission Approval Flow Test (FR16)

The test suite SHALL include a scenario that exercises the tool permission request flow through the full stack.

#### Scenario: Successful permission approval

- **WHEN** a prompt is sent via voice chat that triggers a tool requiring permission
- **THEN** the database Command record MUST reach AWAITING_INPUT state
- **AND** the permission context MUST be detectable (via DOM UI element or tmux pane content)
- **WHEN** the permission is approved (via voice chat UI or tmux)
- **THEN** the Command record MUST reach COMPLETE state
- **AND** the result MUST be rendered in the voice chat DOM

### Requirement: Bug-Driven Scenario (FR17)

At least one test scenario SHALL be written targeting a real bug that was caught by manual testing but passed all existing automated tests.

#### Scenario: Bug regression test

- **WHEN** the bug-driven test scenario executes
- **THEN** it MUST document which bug it targets (commit hash, issue number, or description)
- **AND** it MUST exercise the specific code path that the bug affected
- **AND** it MUST be designed such that it would have caught the bug if it had existed at the time

### Requirement: pytest Discovery (FR18)

All agent-driven tests SHALL be discoverable and runnable via standard pytest commands.

#### Scenario: Full suite discovery

- **WHEN** `pytest tests/agent_driven/` is executed
- **THEN** all agent-driven test scenarios MUST be collected and executed
- **AND** individual test files MUST be runnable independently (e.g., `pytest tests/agent_driven/test_simple_command.py`)
- **AND** keyword selection MUST work (e.g., `pytest tests/agent_driven/ -k question`)

### Requirement: Structured Test Output (FR19)

Each test SHALL produce clear structured output during execution.

#### Scenario: Structured output during test run

- **WHEN** a test scenario executes
- **THEN** output MUST include the scenario name
- **AND** output MUST include step progress (e.g., "Sending command...", "Waiting for response...")
- **AND** output MUST include pass/fail status per assertion
- **AND** output MUST include total elapsed time

### Requirement: Scenario Format Evaluation (FR20)

After implementing FR15-FR19, an evaluation SHALL be conducted on whether a declarative scenario format (YAML) would reduce duplication.

#### Scenario: Format decision documented

- **WHEN** the format evaluation is complete
- **THEN** a written decision MUST exist (in tests/agent_driven/ README or inline)
- **AND** if the format is implemented, it MUST use plain YAML parsed by `yaml.safe_load`
- **AND** every scenario MUST remain writable as a plain pytest function regardless of format decision

