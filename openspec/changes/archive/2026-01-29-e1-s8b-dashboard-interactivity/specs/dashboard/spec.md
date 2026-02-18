# Delta Spec: e1-s8b-dashboard-interactivity

## ADDED Requirements

### Requirement: Recommended Next Panel

The system SHALL display a Recommended Next panel highlighting the highest priority agent.

#### Scenario: Recommended next displays agent awaiting input

Given agents in various states
When one or more agents have state AWAITING_INPUT
Then the recommended next panel shows the oldest waiting agent
And displays session ID, project name, state, priority score
And displays rationale text

#### Scenario: Recommended next with no agents awaiting input

Given no agents have state AWAITING_INPUT
When the dashboard loads
Then the recommended next panel shows the most recently active agent

#### Scenario: Recommended next with no agents

Given no agents exist
When the dashboard loads
Then the recommended next panel shows "No agents to recommend"

#### Scenario: Recommended next click triggers focus

Given the recommended next panel displays an agent
When user clicks the panel
Then POST request sent to /api/focus/<agent_id>

### Requirement: Sort Controls

The system SHALL provide sort controls for different views.

#### Scenario: By Project view

Given sort mode is "By Project"
When the dashboard renders
Then agents are grouped under project headers
And layout matches Part 1 structure

#### Scenario: By Priority view

Given sort mode is "By Priority"
When the dashboard renders
Then agents display in flat list
And ordered by: AWAITING_INPUT, then COMMANDED/PROCESSING, then IDLE/COMPLETE
And within each group ordered by last_seen_at descending

#### Scenario: Sort preference persistence

Given user selects a sort mode
When page is reloaded
Then the same sort mode is active

### Requirement: SSE Real-time Updates

The system SHALL update dashboard via SSE events.

#### Scenario: SSE connection on load

Given user opens the dashboard
When page load completes
Then EventSource connection to /api/events is established

#### Scenario: State change event

Given SSE connection is active
When agent_state_changed event received
Then agent card state bar updates
And header status counts recalculate
And project traffic light recalculates
And recommended next panel re-evaluates

#### Scenario: Turn created event

Given SSE connection is active
When turn_created event received
Then agent card command summary updates with new turn text

#### Scenario: Activity event

Given SSE connection is active
When agent_activity event received
Then agent card status badge updates (ACTIVE/IDLE)

#### Scenario: SSE reconnection

Given SSE connection is lost
When disconnect detected
Then automatic reconnection attempts with progressive delays
And dashboard remains usable with last known state

### Requirement: Connection Status Indicator

The system SHALL display SSE connection status.

#### Scenario: Connected state

Given SSE connection is active
When status indicator renders
Then displays "● SSE live" with green indicator

#### Scenario: Reconnecting state

Given SSE connection is lost
When reconnection in progress
Then displays "○ Reconnecting..." with grey indicator

#### Scenario: Offline state

Given reconnection attempts exhausted
When connection cannot be established
Then displays "✗ Offline" with red indicator

### Requirement: Click-to-Focus Integration

The system SHALL enable focusing iTerm windows from dashboard.

#### Scenario: Headspace button click

Given an agent card
When user clicks Headspace button
Then POST request sent to /api/focus/<agent_id>

#### Scenario: Focus success

Given focus API returns success
When response received
Then agent card displays brief highlight animation

#### Scenario: Focus failure - permission error

Given focus API returns permission error
When response received
Then toast displays "Grant iTerm automation permission..."

#### Scenario: Focus failure - inactive agent

Given focus API returns inactive agent error
When response received
Then toast displays "Session ended - cannot focus terminal"

#### Scenario: Toast auto-dismiss

Given toast is displayed
When 5 seconds elapse
Then toast automatically dismisses

## MODIFIED Requirements

### Requirement: Header Connection Indicator (Part 1 FR7)

The header hooks/polling indicator SHALL be replaced with live SSE connection indicator.

**Before:** Static "HOOKS polling" placeholder text
**After:** Dynamic indicator showing SSE live / Reconnecting / Offline

#### Scenario: Connection indicator displays SSE status

Given the dashboard is loaded
When SSE connection state changes
Then the header indicator updates to reflect current state

### Requirement: Headspace Button (Part 1 FR20)

The Headspace button SHALL be wired to focus API instead of disabled placeholder.

**Before:** Disabled button with tooltip "coming in Part 2"
**After:** Active button that triggers POST to /api/focus/<agent_id>

#### Scenario: Headspace button is enabled

Given an agent card is displayed
When user views the Headspace button
Then the button is enabled and clickable

## REMOVED Requirements

None.
