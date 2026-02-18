## ADDED Requirements

### Requirement: Command Instruction Summarisation

The system SHALL generate a 1-2 sentence instruction summary from the initiating USER COMMAND turn when a command is created.

#### Scenario: Instruction generated on task creation from USER COMMAND

- **WHEN** a command is created from a USER COMMAND turn with non-empty text
- **THEN** instruction summarisation SHALL be triggered asynchronously
- **AND** the prompt SHALL receive the full text of the user's command
- **AND** the result SHALL be persisted to `command.instruction` and `command.instruction_generated_at`
- **AND** an `instruction_summary` SSE event SHALL be broadcast with command_id, instruction, agent_id, and project_id

#### Scenario: Instruction generation does not block hook pipeline

- **WHEN** instruction summarisation is triggered
- **THEN** it SHALL execute asynchronously via the thread pool
- **AND** the hook processing pipeline SHALL continue without waiting

#### Scenario: Command created with empty command text

- **WHEN** a command is created from a USER COMMAND turn with None or empty text
- **THEN** instruction summarisation SHALL NOT be triggered
- **AND** `command.instruction` SHALL remain NULL

---

### Requirement: Empty Text Guard

Turn and command summarisation SHALL be skipped when text content is unavailable.

#### Scenario: Turn with empty text

- **WHEN** a turn has None or empty text
- **THEN** turn summarisation SHALL be skipped and return None
- **AND** no summary SHALL be generated from metadata alone

#### Scenario: Completion summary deferred when final turn text empty

- **WHEN** a task transitions to COMPLETE but the final turn's text is None or empty
- **THEN** completion summarisation SHALL be deferred or skipped
- **AND** no summary SHALL be generated from metadata alone

---

### Requirement: Reference Rename

All codebase references to `command.summary` SHALL be updated to `command.completion_summary`.

#### Scenario: Field references updated across codebase

- **WHEN** the change is applied
- **THEN** all references to `command.summary` SHALL be updated to `command.completion_summary`
- **AND** all references to `command.summary_generated_at` SHALL be updated to `command.completion_summary_generated_at`
- **AND** this SHALL include models, services, routes, templates, static JS, and all test files

---

## MODIFIED Requirements

### Requirement: Command Summarisation

The command completion summary prompt SHALL be rebuilt to use instruction context instead of timestamps.

#### Scenario: Completion summary with full context

- **WHEN** a task transitions to COMPLETE and the final turn has non-empty text
- **THEN** the completion summary prompt SHALL receive the command instruction and the agent's final message text
- **AND** the prompt SHALL ask the LLM to describe what was accomplished relative to what was asked
- **AND** the result SHALL be 2-3 sentences
- **AND** timestamps and turn counts SHALL NOT be included as primary prompt content

#### Scenario: Completion summary stored with renamed field

- **WHEN** a completion summary is generated
- **THEN** it SHALL be stored in `command.completion_summary` with `command.completion_summary_generated_at`
- **AND** an SSE event SHALL be broadcast to update the agent card

---

### Requirement: Turn Summarisation

Turn summarisation prompts SHALL use intent-specific templates with command instruction context.

#### Scenario: COMMAND intent turn

- **WHEN** a USER turn with COMMAND intent has non-empty text
- **THEN** the prompt SHALL summarise what the user is asking the agent to do

#### Scenario: QUESTION intent turn

- **WHEN** an AGENT turn with QUESTION intent has non-empty text
- **THEN** the prompt SHALL summarise what the agent is asking the user

#### Scenario: COMPLETION intent turn

- **WHEN** an AGENT turn with COMPLETION intent has non-empty text
- **THEN** the prompt SHALL summarise what the agent accomplished with command instruction as context

#### Scenario: PROGRESS intent turn

- **WHEN** an AGENT turn with PROGRESS intent has non-empty text
- **THEN** the prompt SHALL summarise what progress the agent has made

#### Scenario: ANSWER intent turn

- **WHEN** a USER turn with ANSWER intent has non-empty text
- **THEN** the prompt SHALL summarise what information the user provided

#### Scenario: END_OF_COMMAND intent turn

- **WHEN** a turn with END_OF_COMMAND intent has non-empty text
- **THEN** the prompt SHALL summarise the final outcome of the task

#### Scenario: Turn with command instruction context

- **WHEN** a turn is summarised and the parent task has a non-NULL instruction
- **THEN** the command instruction SHALL be included in the summarisation prompt as context

