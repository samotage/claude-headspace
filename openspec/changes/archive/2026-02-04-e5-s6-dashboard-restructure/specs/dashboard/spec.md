## ADDED Requirements

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

The Kanban view MUST display columns for each command lifecycle state: IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE.

#### Scenario: Idle agents

- **WHEN** an agent has no active commands
- **THEN** the agent appears in the IDLE column as its current agent card representation

#### Scenario: Active task placement

- **WHEN** an agent has an active command in PROCESSING state
- **THEN** a command card appears in the PROCESSING column with agent hero identity, command instruction/summary, and metadata

#### Scenario: Multiple tasks per agent

- **WHEN** an agent has tasks in different lifecycle states
- **THEN** the agent appears in multiple columns simultaneously (one card per command)

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

#### Scenario: Command retention

- **WHEN** a completed task's parent agent has not been reaped
- **THEN** the completed task remains visible in the COMPLETE column

#### Scenario: Command removal on reap

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

### Requirement: Immediate Frustration Metric

The frustration metric on both the dashboard and activity page MUST represent immediate frustration (rolling average of the last 10 turns).

#### Scenario: Dashboard frustration

- **WHEN** the dashboard activity bar displays frustration
- **THEN** it shows the rolling average of the last 10 turns' frustration scores

#### Scenario: Activity page frustration

- **WHEN** the activity page displays frustration in overall, project, or agent sections
- **THEN** it represents immediate frustration (last 10 turns) instead of averaged frustration

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
