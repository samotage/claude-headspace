# dashboard Specification

## Purpose
TBD - created by archiving change e1-s8-dashboard-ui. Update Purpose after archive.
## Requirements
### Requirement: Dashboard Route

The system SHALL provide a dashboard route for monitoring agents.

#### Scenario: Dashboard loads successfully

Given a user accessing the application
When they navigate to `/` (root URL)
Then they receive HTTP 200
And the dashboard template is rendered
And all projects are displayed as groups
And all agents are displayed within their projects

#### Scenario: Status counts calculated

Given agents in various states
When the dashboard loads
Then INPUT NEEDED count equals agents where state = AWAITING_INPUT
And WORKING count equals agents where state IN (COMMANDED, PROCESSING)
And IDLE count equals agents where state IN (IDLE, COMPLETE)

### Requirement: Header Bar

The system SHALL display a header bar with navigation and status.

#### Scenario: Header displays correctly

Given the dashboard is rendered
Then the header displays "CLAUDE >_headspace" title
And navigation tabs are visible (dashboard, objective, logging)
And status count badges are displayed
And hooks/polling indicator is displayed

### Requirement: Project Groups

The system SHALL display projects as collapsible groups.

#### Scenario: Traffic light indicator

Given a project with agents
When any agent has state AWAITING_INPUT
Then traffic light is RED
When any agent has state COMMANDED or PROCESSING (and none AWAITING_INPUT)
Then traffic light is YELLOW
When all agents have state IDLE or COMPLETE
Then traffic light is GREEN

#### Scenario: Project collapse/expand

Given a project group
When user clicks the collapse toggle
Then agent cards are hidden
When user clicks the expand toggle
Then agent cards are visible

### Requirement: Agent Cards

The agent card SHALL display task context as a two-line layout with instruction and turn summary.

#### Scenario: Active task with instruction and turn summary

- **WHEN** an agent has an active task with a populated instruction
- **AND** the task has turns with summaries
- **THEN** the agent card SHALL display the task instruction as the primary line
- **AND** the latest turn summary as the secondary line

#### Scenario: Active task with instruction but no turn summary yet

- **WHEN** an agent has an active task with a populated instruction
- **AND** no turn summaries are available yet
- **THEN** the agent card SHALL display the task instruction as the primary line
- **AND** an appropriate placeholder as the secondary line

#### Scenario: Active task before instruction is generated

- **WHEN** an agent has an active task but instruction is still being generated
- **THEN** the agent card SHALL display appropriate placeholder text until the instruction_summary SSE event arrives

#### Scenario: Idle state preserved

- **WHEN** an agent has no active task (IDLE state)
- **THEN** the agent card SHALL display the existing idle message or completed task summary

#### Scenario: SSE updates instruction line independently

- **WHEN** an `instruction_summary` SSE event is received for an agent
- **THEN** the instruction line in the agent card SHALL be updated
- **AND** the turn summary line SHALL NOT be affected

#### Scenario: SSE updates turn summary line independently

- **WHEN** a `turn_summary` or `task_summary` SSE event is received for an agent
- **THEN** the turn summary line in the agent card SHALL be updated
- **AND** the instruction line SHALL NOT be affected

### Requirement: State Visualization

The system SHALL colour-code agent states.

#### Scenario: State bar colours

Given an agent with a specific state
When the state bar is rendered
Then IDLE state shows grey bar with "Idle - ready for task"
And COMMANDED state shows yellow bar with "Command received"
And PROCESSING state shows blue bar with "Processing..."
And AWAITING_INPUT state shows orange bar with "Input needed"
And COMPLETE state shows green bar with "Task complete"

### Requirement: Responsive Layout

The system SHALL adapt to different screen sizes.

#### Scenario: Mobile layout

Given viewport width < 768px
When dashboard is rendered
Then agent cards stack in single column
And project groups take full width

#### Scenario: Tablet layout

Given viewport width 768px - 1023px
When dashboard is rendered
Then agent cards display in two-column grid

#### Scenario: Desktop layout

Given viewport width >= 1024px
When dashboard is rendered
Then agent cards display in multi-column grid (3+ columns)

### Requirement: Accessibility

The system SHALL be accessible.

#### Scenario: ARIA labels present

Given state indicators on the page
Then traffic lights have ARIA labels describing state
And state bars have ARIA labels describing state
And interactive elements are keyboard navigable

