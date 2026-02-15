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

### Requirement: Agent Hero Style Identity

The dashboard and all agent-referencing views SHALL display agent identity using a two-character hero style: the first two hex characters of the session UUID rendered prominently, with the remaining characters rendered smaller trailing behind. The `#` prefix MUST be removed from all agent identity displays.

#### Scenario: Dashboard agent card identity

- **WHEN** an agent card is rendered on the dashboard
- **THEN** the agent identity displays the first 2 characters of the session UUID in large text, followed by the remaining 6 characters in smaller text, with no `#` prefix

#### Scenario: Agent identity in logging tables

- **WHEN** an event or inference log row displays an agent reference
- **THEN** the agent column renders using the hero style (2-char large + remainder small)

#### Scenario: Logging agent filter dropdown

- **WHEN** the agent filter dropdown is populated in the logging page
- **THEN** each option displays in the format `0a - 0a5510d4` (hero chars, separator, full truncated UUID)

#### Scenario: Agent identity in activity page

- **WHEN** agent metrics are displayed on the activity page
- **THEN** agent identity uses the hero style rendering

#### Scenario: Agent identity in project detail page

- **WHEN** agents are listed on the project detail page
- **THEN** agent identity uses the hero style rendering

### Requirement: Dashboard Card Header Reorder

The dashboard agent card header MUST reorder elements: agent hero identity (left), project name, with uptime and active indicator pushed to the far right.

#### Scenario: Card header layout

- **WHEN** an agent card is rendered
- **THEN** the header shows: hero identity (left) -> project name -> spacer -> uptime -> active indicator (far right)

### Requirement: Kanban Sort Mode

The dashboard MUST support a "Kanban" sort mode as the first/default option in the sort controls.

#### Scenario: Default sort mode

- **WHEN** a user visits the dashboard without a sort preference
- **THEN** the Kanban view is displayed as the default

#### Scenario: Sort mode selection

- **WHEN** the user selects the "Kanban" sort option
- **THEN** the dashboard displays tasks organised into lifecycle state columns

### Requirement: Kanban Column Layout

The Kanban view MUST display columns for each task lifecycle state: IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE.

#### Scenario: Idle agents

- **WHEN** an agent has no active tasks
- **THEN** the agent appears in the IDLE column as its current agent card representation

#### Scenario: Active task placement

- **WHEN** an agent has an active task in PROCESSING state
- **THEN** a task card appears in the PROCESSING column with agent hero identity, task instruction/summary, and metadata

#### Scenario: Multiple tasks per agent

- **WHEN** an agent has tasks in different lifecycle states
- **THEN** the agent appears in multiple columns simultaneously (one card per task)

#### Scenario: Priority ordering

- **WHEN** prioritisation is enabled
- **THEN** tasks within each column are ordered by their agent's priority score (highest first)

### Requirement: Kanban Multi-Project Sections

When multiple projects have active agents, the Kanban view MUST display horizontal sections for each project, each containing its own set of state columns.

#### Scenario: Multiple active projects

- **WHEN** agents from 3 different projects are active
- **THEN** the Kanban view shows 3 horizontal sections, each with its own IDLE/COMMANDED/PROCESSING/AWAITING_INPUT/COMPLETE columns

### Requirement: Kanban Complete Column

Completed tasks in the COMPLETE column MUST render as collapsed accordions and the column MUST scroll independently.

#### Scenario: Completed task display

- **WHEN** a task reaches COMPLETE state
- **THEN** it appears as a collapsed accordion in the COMPLETE column showing agent hero identity and completion summary

#### Scenario: Accordion expansion

- **WHEN** a user clicks a collapsed completed task
- **THEN** the accordion expands to reveal full task details

#### Scenario: Column scrolling

- **WHEN** the COMPLETE column accumulates many completed tasks
- **THEN** the column scrolls independently with a fixed height

#### Scenario: Task retention

- **WHEN** a completed task's parent agent has not been reaped
- **THEN** the completed task remains visible in the COMPLETE column

#### Scenario: Task removal on reap

- **WHEN** the agent reaper removes an agent
- **THEN** all completed tasks for that agent are removed from the COMPLETE column

### Requirement: Dashboard Activity Metrics Bar

The dashboard MUST display overall activity metrics in a compact bar below the main menu and above the state summary bar.

#### Scenario: Metrics display

- **WHEN** the dashboard loads
- **THEN** an activity metrics bar shows: Total Turns, Turns/Hour, Avg Turn Time, Active Agents, Frustration (immediate)

#### Scenario: Real-time updates

- **WHEN** a new turn is recorded
- **THEN** the dashboard activity metrics update via SSE without page reload

### Requirement: Agent Card Tmux Session Display

The dashboard agent card SHALL display the tmux session name when available, providing the user with the session identifier for manual use.

#### Scenario: Card state includes tmux_session

- **WHEN** `build_card_state()` is called for an agent with `tmux_session` set
- **THEN** the returned dict SHALL include `tmux_session` with the session name string

#### Scenario: Card state with no tmux_session

- **WHEN** `build_card_state()` is called for an agent with `tmux_session` NULL
- **THEN** the returned dict SHALL include `tmux_session` with value `null`

---

### Requirement: Agent Card Attach Action

The dashboard agent card SHALL display an attach button for agents with a tmux session, allowing one-click terminal attachment.

#### Scenario: Attach button visible

- **WHEN** an agent card is rendered
- **AND** the agent has a non-null `tmux_session` in card state
- **THEN** an attach action button SHALL be visible on the card

#### Scenario: Attach button hidden

- **WHEN** an agent card is rendered
- **AND** the agent has a null `tmux_session` in card state
- **THEN** the attach action button SHALL NOT be visible

#### Scenario: Attach button click

- **WHEN** the user clicks the attach button on an agent card
- **THEN** a `POST /api/agents/<id>/attach` request SHALL be sent
- **AND** success/failure feedback SHALL be displayed to the user

#### Scenario: Attach button on SSE card refresh

- **WHEN** a `card_refresh` SSE event is received with `tmux_session` set
- **THEN** the attach button SHALL appear on the refreshed card
- **WHEN** a `card_refresh` SSE event is received with `tmux_session` null
- **THEN** the attach button SHALL be hidden on the refreshed card

---

### Requirement: Immediate Frustration Metric

The frustration metric on both the dashboard and activity page MUST represent immediate frustration (rolling average of the last 10 turns).

#### Scenario: Dashboard frustration

- **WHEN** the dashboard activity bar displays frustration
- **THEN** it shows the rolling average of the last 10 turns' frustration scores

#### Scenario: Activity page frustration

- **WHEN** the activity page displays frustration in overall, project, or agent sections
- **THEN** it represents immediate frustration (last 10 turns) instead of averaged frustration

