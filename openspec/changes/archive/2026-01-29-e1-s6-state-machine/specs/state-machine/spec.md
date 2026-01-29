# Delta Spec: e1-s6-state-machine

## ADDED Requirements

### Requirement: State Transition Logic

The system SHALL enforce valid state transitions between the 5 task states (idle, commanded, processing, awaiting_input, complete).

#### Scenario: Valid user command from idle

Given an agent with no active task (idle state)
When a user issues a command
Then a new Task is created in commanded state
And a state_transition event is written

#### Scenario: Valid agent progress from commanded

Given a task in commanded state
When the agent responds with progress
Then the task transitions to processing state
And a state_transition event is written

#### Scenario: Valid agent question

Given a task in processing or commanded state
When the agent asks a question (detected via regex)
Then the task transitions to awaiting_input state
And a state_transition event is written

#### Scenario: Valid user answer

Given a task in awaiting_input state
When the user provides an answer
Then the task transitions to processing state
And a state_transition event is written

#### Scenario: Valid agent completion

Given a task in processing or commanded state
When the agent signals completion (detected via regex)
Then the task transitions to complete state
And completed_at timestamp is set

#### Scenario: Invalid transition rejected

Given a task in idle state
When the agent attempts to act
Then the transition is rejected
And a warning is logged
And the state remains unchanged

### Requirement: Intent Detection Service

The system SHALL detect turn intent using regex pattern matching.

#### Scenario: Question detected by question mark

Given an agent turn ending with "?"
When intent detection runs
Then the intent is classified as question

#### Scenario: Question detected by phrase

Given an agent turn containing "Would you like" or "Should I"
When intent detection runs
Then the intent is classified as question

#### Scenario: Completion detected

Given an agent turn containing "Done" or "Complete" or "Finished"
When intent detection runs
Then the intent is classified as completion

#### Scenario: Progress by default

Given an agent turn that matches no question or completion patterns
When intent detection runs
Then the intent is classified as progress

### Requirement: Task Lifecycle Management

The system SHALL manage task creation and completion.

#### Scenario: Task created on command

Given an agent with no incomplete task
When a user command is detected
Then a new Task is created with state=commanded

#### Scenario: Task completed

Given a task transitioning to complete state
When the transition is applied
Then completed_at is set to current timestamp

#### Scenario: Agent state derived from task

Given an agent with an incomplete task
When agent.state is queried
Then it returns the current task's state

### Requirement: State Transition Event Logging

The system SHALL write state_transition events for every valid transition.

#### Scenario: Event written on transition

Given a valid state transition occurs
When the transition is applied
Then a state_transition event is written with agent_id, task_id, from_state, to_state, trigger, confidence

#### Scenario: Confidence tracking

Given a regex-matched intent detection
When the state_transition event is written
Then confidence is set to 1.0

### Requirement: Error Handling

The system SHALL handle edge cases gracefully.

#### Scenario: Unknown session

Given a turn_detected event with unknown session_uuid
When processing is attempted
Then a warning is logged
And processing is skipped

#### Scenario: Missing text

Given a turn with empty or missing text
When intent detection runs
Then the intent defaults to progress

### Requirement: Transition Validation

The system SHALL validate all transitions before applying.

#### Scenario: Validate actor/intent combination

Given a proposed transition with actor and intent
When validation runs
Then it checks if the combination is valid for current state
And returns validation result with reason

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
