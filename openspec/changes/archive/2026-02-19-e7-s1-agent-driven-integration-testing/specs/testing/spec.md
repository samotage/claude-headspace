## ADDED Requirements

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
