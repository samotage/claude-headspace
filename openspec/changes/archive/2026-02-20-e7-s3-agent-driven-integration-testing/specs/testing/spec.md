## ADDED Requirements

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

## NON-FUNCTIONAL Requirements

### NFR1: Generous Timeouts

All interaction waits SHALL use a 60-second default timeout.

### NFR2: Deterministic Prompts

All scenarios SHALL use Haiku model with short, deterministic prompts.

### NFR3: Test Database Only

All tests MUST connect to `claude_headspace_test` database only.

### NFR4: Sequential Execution

Agent-driven tests MUST execute sequentially.

### NFR5: Evidence Preservation

On test failure, tmux panes, database state, and screenshots MUST be preserved.

### NFR6: No New Dependencies

No new pip dependencies SHALL be introduced.

## CONSTRAINTS

### C6: Helpers Must Be Plain Functions

Shared helpers MUST be plain functions. No base classes, no inheritance, no metaclasses, no decorators that hide test logic.

### C7: Declarative Format Uses Standard YAML Only

If a declarative format is implemented, it MUST use standard YAML parsed by `yaml.safe_load`. No custom parser. No markdown processing. The YAML is loaded into a Python dict and the test function iterates over it.

### C8: All Scenarios Writable as Plain pytest

Every scenario MUST also be writable as a plain pytest function. The declarative format is a convenience layer, never a requirement.

### C9: Structural Assertions Only

Tests MUST NOT assert on LLM response content beyond structural requirements.

### C10: Bug Scenarios Must Reference Actual Bugs

Bug-driven scenarios MUST reference the actual bug (commit hash, issue number, or description). No hypothetical bugs.
