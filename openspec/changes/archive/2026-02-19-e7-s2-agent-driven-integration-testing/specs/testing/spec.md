## ADDED Requirements

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

## NON-FUNCTIONAL Requirements

### NFR1: Generous Timeouts

All interaction waits SHALL use a 60-second default timeout to accommodate real LLM processing variability.

### NFR2: Deterministic Prompts

All scenarios SHALL use Haiku model with short, deterministic prompts that minimize LLM response variability.

### NFR3: Test Database Only

All tests MUST connect to `claude_headspace_test` database only. Production databases MUST NOT be accessed.

### NFR4: Sequential Execution

Agent-driven tests MUST execute sequentially (no parallel test execution).

### NFR5: Evidence Preservation

On test failure, tmux panes, database state, and screenshots MUST be preserved for investigation.

### NFR6: No New Dependencies

No new pip dependencies SHALL be introduced.

## CONSTRAINTS

### C1: No Shared Helper Extraction

Helpers SHALL NOT be extracted into shared modules unless the exact same code appears in 3 or more tests. If only two tests share a pattern, it MUST be inlined.

### C2: No Fixture Format

Scenarios SHALL remain pytest functions with explicit prompts and assertions. No declarative/data-driven fixture format.

### C3: Cross-Layer Verification as Plain Function

Cross-layer verification MAY be a shared function if the check is identical across scenarios, but it MUST be a plain function, not a class or framework.

### C4: Independent Readability

Each test file MUST be independently readable. A developer SHALL be able to understand what a test does by reading that one file alone.

### C5: Structural Assertions Only

Tests MUST NOT assert on LLM response content beyond structural requirements (e.g., presence of a bubble, state transitions). Never assert on specific words or phrases in LLM-generated text.
