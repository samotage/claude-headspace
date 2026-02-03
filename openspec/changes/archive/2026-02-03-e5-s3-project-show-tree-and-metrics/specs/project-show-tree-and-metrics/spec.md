## ADDED Requirements

### Requirement: Accordion Object Tree

The project show page SHALL include a three-level accordion object tree: Agents → Tasks → Turns, with lazy data loading on expand.

#### Scenario: Agents accordion collapsed by default

- **WHEN** the project show page loads
- **THEN** the Agents accordion is collapsed and displays a count badge (e.g., "Agents (3)")

#### Scenario: Expand Agents accordion

- **WHEN** the user expands the Agents accordion
- **THEN** the system fetches agent data from the API and displays all agents (active and ended) with state indicator, session ID, priority score, timing, and duration

#### Scenario: Distinguish ended agents

- **WHEN** the Agents accordion is expanded
- **THEN** ended agents are visually distinguished from active agents with muted styling and an "Ended" badge

#### Scenario: Expand agent to show tasks

- **WHEN** the user clicks an agent row
- **THEN** a nested Tasks section expands, fetching and displaying that agent's tasks with state badge, instruction, completion summary, timing, and turn count

#### Scenario: Expand task to show turns

- **WHEN** the user clicks a task row
- **THEN** a nested Turns section expands, fetching and displaying that task's turns with actor badge, intent, summary, and frustration score

#### Scenario: Frustration score highlighting

- **WHEN** a turn has frustration score >= 4 (yellow threshold)
- **THEN** the turn row is highlighted in amber
- **WHEN** a turn has frustration score >= 7 (red threshold)
- **THEN** the turn row is highlighted in red

#### Scenario: Collapse parent collapses children

- **WHEN** the user collapses an agent row
- **THEN** all nested tasks and turns under that agent are also collapsed

### Requirement: Lazy Data Loading

Accordion sections SHALL NOT fetch data until the user expands them. Data SHALL be cached client-side after first fetch.

#### Scenario: Loading indicator

- **WHEN** an accordion section is being expanded and data is loading
- **THEN** a loading indicator is displayed within the section

#### Scenario: Error state with retry

- **WHEN** a data fetch fails for an accordion section
- **THEN** an error message is displayed with a "Retry" button

#### Scenario: Client-side cache

- **WHEN** the user collapses and re-expands a section
- **THEN** cached data is displayed without re-fetching unless invalidated by SSE

### Requirement: Agent Tasks API Endpoint

The system SHALL provide `GET /api/agents/<id>/tasks` returning all tasks for a specific agent.

#### Scenario: Valid agent with tasks

- **WHEN** the client requests tasks for an existing agent
- **THEN** the system returns a list of tasks with state, instruction, completion_summary, started_at, completed_at, and turn count

#### Scenario: Agent not found

- **WHEN** the client requests tasks for a non-existent agent
- **THEN** the system returns 404

### Requirement: Task Turns API Endpoint

The system SHALL provide `GET /api/tasks/<id>/turns` returning all turns for a specific task.

#### Scenario: Valid task with turns

- **WHEN** the client requests turns for an existing task
- **THEN** the system returns a list of turns with actor, intent, summary, frustration_score, and created_at

#### Scenario: Task not found

- **WHEN** the client requests turns for a non-existent task
- **THEN** the system returns 404

### Requirement: Activity Metrics Section

The project show page SHALL include an Activity Metrics section with day/week/month toggle, period navigation, summary cards, and time-series chart.

#### Scenario: Default week view

- **WHEN** the project show page loads
- **THEN** the Activity Metrics section defaults to week (7-day) view

#### Scenario: Toggle time window

- **WHEN** the user clicks Day, Week, or Month toggle
- **THEN** the metrics re-fetch and display for the selected window

#### Scenario: Period navigation

- **WHEN** the user clicks the back arrow
- **THEN** the metrics window shifts to the previous period
- **WHEN** the user clicks the forward arrow (not at current period)
- **THEN** the metrics window shifts to the next period

#### Scenario: Forward arrow disabled at current period

- **WHEN** viewing the current period
- **THEN** the forward arrow is disabled

#### Scenario: Summary cards

- **WHEN** the metrics section loads
- **THEN** summary cards display turn count, average turn time, active agent count, and frustration turn count

### Requirement: Archive History Section

The project show page SHALL include an Archive History section listing archived artifacts with type, timestamp, and view action.

#### Scenario: Archives exist

- **WHEN** the project has archived artifacts
- **THEN** the section lists them with type, timestamp, and view action

#### Scenario: No archives

- **WHEN** the project has no archives
- **THEN** an empty state message is displayed

### Requirement: Inference Metrics Summary

The project show page SHALL display aggregate inference metrics: total calls, total tokens (input + output), and total cost scoped to the project.

#### Scenario: Display inference metrics

- **WHEN** the project show page loads
- **THEN** the inference summary section shows total inference calls, total tokens, and total cost for the project

### Requirement: Project Inference Summary API Endpoint

The system SHALL provide `GET /api/projects/<id>/inference-summary` returning aggregate inference metrics for a project.

#### Scenario: Valid project with inference data

- **WHEN** the client requests inference summary for a project
- **THEN** the system returns total calls, total input tokens, total output tokens, and total cost

#### Scenario: Project not found

- **WHEN** the client requests inference summary for a non-existent project
- **THEN** the system returns 404

### Requirement: SSE Real-Time Updates for Accordion

The project show page SHALL listen for SSE events and update expanded accordion sections in real-time without disrupting the user's expand/collapse state.

#### Scenario: Agent state change

- **WHEN** a `card_refresh` event is received for an agent in this project
- **THEN** the Agents accordion updates if currently expanded

#### Scenario: SSE debouncing

- **WHEN** multiple SSE events arrive in rapid succession
- **THEN** accordion updates are batched every 2 seconds

#### Scenario: Preserve accordion state

- **WHEN** an SSE update refreshes accordion data
- **THEN** the user's current expand/collapse state is preserved

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
