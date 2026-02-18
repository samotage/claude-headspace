## MODIFIED Requirements

### Requirement: Agent Cards

The agent card SHALL display command context as a two-line layout with instruction and turn summary.

#### Scenario: Active task with instruction and turn summary

- **WHEN** an agent has an active command with a populated instruction
- **AND** the task has turns with summaries
- **THEN** the agent card SHALL display the command instruction as the primary line
- **AND** the latest turn summary as the secondary line

#### Scenario: Active task with instruction but no turn summary yet

- **WHEN** an agent has an active command with a populated instruction
- **AND** no turn summaries are available yet
- **THEN** the agent card SHALL display the command instruction as the primary line
- **AND** an appropriate placeholder as the secondary line

#### Scenario: Active task before instruction is generated

- **WHEN** an agent has an active command but instruction is still being generated
- **THEN** the agent card SHALL display appropriate placeholder text until the instruction_summary SSE event arrives

#### Scenario: Idle state preserved

- **WHEN** an agent has no active command (IDLE state)
- **THEN** the agent card SHALL display the existing idle message or completed command summary

#### Scenario: SSE updates instruction line independently

- **WHEN** an `instruction_summary` SSE event is received for an agent
- **THEN** the instruction line in the agent card SHALL be updated
- **AND** the turn summary line SHALL NOT be affected

#### Scenario: SSE updates turn summary line independently

- **WHEN** a `turn_summary` or `command_summary` SSE event is received for an agent
- **THEN** the turn summary line in the agent card SHALL be updated
- **AND** the instruction line SHALL NOT be affected
