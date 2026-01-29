# Delta Spec: e1-s10-logging-tab

## ADDED Requirements

### Requirement: Logging Tab Template

The system SHALL provide a logging tab page for viewing system events.

#### Scenario: Logging tab displays event table and filters

Given a user navigates to the logging tab
When the page loads
Then the filter bar is displayed at the top
And the event table is displayed below
And pagination controls are displayed at the bottom
And the page uses dark terminal aesthetic

### Requirement: Event Table Display

The system SHALL display events in a table format.

#### Scenario: Event table columns

Given the logging tab is displayed
When the event table renders
Then columns are displayed: Timestamp, Project, Agent, Event Type, Details

#### Scenario: Timestamp format

Given events exist in the table
When timestamps are displayed
Then they show in human-readable local time format (e.g., "2026-01-29 14:32:05")

#### Scenario: Agent identifier display

Given events exist in the table
When agent column renders
Then it displays truncated session UUID (e.g., "#2e3f...")

#### Scenario: Event ordering

Given events exist in the table
When the table renders
Then events are ordered by timestamp descending (most recent first)

### Requirement: Filter Controls

The system SHALL provide filter controls for narrowing event display.

#### Scenario: Project filter dropdown

Given the logging tab is displayed
When the project filter is shown
Then it lists all projects with events plus "All Projects" option

#### Scenario: Agent filter dropdown

Given the logging tab is displayed
When the agent filter is shown
Then it lists all agents with events plus "All Agents" option

#### Scenario: Event type filter dropdown

Given the logging tab is displayed
When the event type filter is shown
Then it lists all event types plus "All Types" option

#### Scenario: Combined filters

Given user selects project filter AND event type filter
When filters are applied
Then only events matching BOTH criteria are displayed

#### Scenario: Clear filters

Given filters are applied
When user clicks Clear Filters
Then all filters reset to default (all) state
And full event list is displayed

### Requirement: Pagination

The system SHALL paginate events for efficient display.

#### Scenario: Default pagination

Given more than 50 events exist
When logging tab loads
Then 50 events are displayed per page

#### Scenario: Pagination controls

Given paginated events
When pagination controls render
Then previous/next buttons are shown
And page indicator shows "Page X of Y"

#### Scenario: Pagination state on filter change

Given user is on page 3
When a filter is applied
Then pagination resets to page 1

### Requirement: Real-Time Updates

The system SHALL display new events in real-time via SSE.

#### Scenario: New event received

Given logging tab is open
When a new event is logged that matches current filters
Then the event appears at the top of the list automatically

#### Scenario: Visual indicator for new events

Given a new event is received via SSE
When it appears in the list
Then it has a brief highlight animation

#### Scenario: Scroll position preservation

Given user is scrolled down viewing older events
When a new event arrives
Then scroll position is not disrupted

### Requirement: Expandable Event Details

The system SHALL provide expandable rows for event details.

#### Scenario: Expand event row

Given an event row is displayed
When user clicks the row
Then it expands to show full JSON payload

#### Scenario: Collapse event row

Given an event row is expanded
When user clicks the row again
Then it collapses back to summary view

#### Scenario: Single expansion

Given an event row is expanded
When user clicks a different row
Then the previous row collapses
And the clicked row expands

### Requirement: GET /api/events Endpoint

The system SHALL provide endpoint to retrieve paginated events.

#### Scenario: Get events with no filters

Given events exist
When GET /api/events is called
Then paginated list of events is returned
And response includes total, page, pages, has_next, has_previous

#### Scenario: Get events with project filter

Given events exist for multiple projects
When GET /api/events?project_id=1 is called
Then only events for project 1 are returned

#### Scenario: Get events with combined filters

Given events exist
When GET /api/events?project_id=1&event_type=STATE_TRANSITION is called
Then only events matching both criteria are returned

#### Scenario: Pagination parameters

Given many events exist
When GET /api/events?page=2&per_page=25 is called
Then page 2 with 25 events per page is returned

### Requirement: GET /api/events/filters Endpoint

The system SHALL provide endpoint to retrieve filter options.

#### Scenario: Get filter options

Given events exist
When GET /api/events/filters is called
Then available projects, agents, and event types are returned
And only items with events are included

### Requirement: Empty States

The system SHALL handle empty states gracefully.

#### Scenario: No events at all

Given no events exist
When logging tab loads
Then "No events recorded yet" message is displayed

#### Scenario: No matching events

Given events exist but none match filters
When filters are applied
Then "No events match the current filters" message is displayed

### Requirement: Error Handling

The system SHALL handle errors gracefully.

#### Scenario: API error

Given API request fails
When response is received
Then user-friendly error message is displayed

#### Scenario: SSE connection loss

Given SSE connection is lost
When reconnection is attempted
Then exponential backoff is used

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
