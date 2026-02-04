# headspace-monitoring Specification

## Purpose
TBD - created by archiving change e4-s4-headspace-monitoring. Update Purpose after archive.
## Requirements
### Requirement: Frustration Score Extraction

The system SHALL extract a frustration score (integer, 0-10) from each user turn by enhancing the existing turn summarisation prompt to return JSON output containing both summary and frustration_score.

#### Scenario: Successful frustration extraction

- **WHEN** a user turn is summarised and headspace monitoring is enabled
- **THEN** the LLM response is parsed as JSON, the summary is stored on Turn.summary, and the frustration_score is stored on Turn.frustration_score

#### Scenario: Malformed LLM response

- **WHEN** the LLM response cannot be parsed as valid JSON
- **THEN** the response is treated as a plain text summary, stored on Turn.summary, and Turn.frustration_score is set to null

#### Scenario: Agent turn (not user)

- **WHEN** an agent turn is summarised
- **THEN** frustration_score remains null (only user turns are scored)

#### Scenario: Headspace monitoring disabled

- **WHEN** headspace.enabled is false in config
- **THEN** the standard (non-JSON) turn summarisation prompt is used and no frustration score is extracted

### Requirement: Rolling Frustration Calculation

The system SHALL calculate two rolling frustration averages after each user turn with a frustration score: the mean of the last 10 scored user turns, and the mean of scored user turns within the last 30 minutes.

#### Scenario: Fewer than 10 scored turns

- **WHEN** fewer than 10 scored user turns exist
- **THEN** the 10-turn rolling average is calculated over however many scored turns are available (minimum 1)

#### Scenario: No scored turns in last 30 minutes

- **WHEN** no scored user turns exist within the last 30 minutes
- **THEN** the 30-minute rolling average is reported as null

### Requirement: Traffic Light Indicator

The dashboard SHALL display a traffic light indicator in the stats bar reflecting the current frustration state: green (avg 0-3), yellow (avg 4-6), red (avg 7-10). The state is determined by the higher of the two rolling averages.

#### Scenario: No frustration data

- **WHEN** no scored user turns exist
- **THEN** the indicator defaults to green with minimal prominence

#### Scenario: State change

- **WHEN** the traffic light state changes after a recalculation
- **THEN** an SSE event `headspace_update` is broadcast and the indicator updates in real-time

### Requirement: Alert Threshold Detection

The system SHALL detect five alert trigger conditions: absolute spike (single turn >= 8), sustained yellow (avg >= 5 for 5+ min), sustained red (avg >= 7 for 2+ min), rising trend (+3 over last 5 turns), and time-based (avg >= 4 for 30+ min).

#### Scenario: Alert triggered

- **WHEN** a threshold condition is met and cooldown has elapsed and suppression is not active
- **THEN** a dismissable banner with a randomly selected gentle message is displayed via SSE event `headspace_alert`

#### Scenario: Alert during cooldown

- **WHEN** a threshold condition is met but cooldown period has not elapsed
- **THEN** no alert is fired

#### Scenario: Alert during suppression

- **WHEN** a threshold condition is met but user pressed "I'm fine" within the last hour
- **THEN** no alert is fired

### Requirement: Flow State Detection

The system SHALL detect flow state when turn rate exceeds the configured minimum (default 6/hr), rolling frustration average is below the configured maximum (default 3), and these conditions have been sustained for the configured minimum duration (default 15 minutes).

#### Scenario: Flow state entered

- **WHEN** flow conditions are met for the minimum duration
- **THEN** a positive reinforcement message is displayed via SSE event `headspace_flow`

#### Scenario: Sustained flow

- **WHEN** flow state has been sustained beyond 15 minutes
- **THEN** additional flow messages appear every 15 minutes

### Requirement: Headspace Snapshot Persistence

The system SHALL persist a HeadspaceSnapshot record after each recalculation, containing timestamp, rolling averages, traffic light state, turn rate, flow state, flow duration, last alert timestamp, and daily alert count.

#### Scenario: Snapshot retention

- **WHEN** a new snapshot is created
- **THEN** snapshots older than the configured retention period (default 7 days) are pruned

### Requirement: API Endpoints

GET `/api/headspace/current` SHALL return the most recent headspace state. GET `/api/headspace/history` SHALL return a time-series of snapshots supporting `?since` and `?limit` query parameters.

#### Scenario: No headspace data

- **WHEN** no snapshots exist
- **THEN** `/api/headspace/current` returns null current with empty state

### Requirement: Configuration

Headspace monitoring SHALL be configurable via a `headspace` section in config.yaml including: enabled, thresholds (yellow/red), alert_cooldown_minutes, flow_detection params, snapshot_retention_days, and customisable messages.

#### Scenario: Feature disabled

- **WHEN** headspace.enabled is false
- **THEN** no frustration scores extracted, no traffic light shown, no alerts fired, no snapshots created

### Requirement: Session-Level Rolling Frustration Average

The HeadspaceMonitor SHALL compute a session-level rolling frustration average over a configurable time window.

#### Scenario: Compute 3-hour rolling average

- **WHEN** the HeadspaceMonitor recalculates after a USER turn with a frustration score
- **THEN** it computes the average frustration score of all scored USER turns within the configured session rolling window (default 180 minutes)
- **AND** stores the result as `frustration_rolling_3hr` on the HeadspaceSnapshot record

#### Scenario: No scored turns in session window

- **WHEN** the session rolling window contains no scored USER turns
- **THEN** `frustration_rolling_3hr` is stored as null

#### Scenario: Session rolling window in API response

- **WHEN** `/api/headspace/current` is called
- **THEN** the response includes `frustration_rolling_3hr` alongside existing `frustration_rolling_10` and `frustration_rolling_30min`

#### Scenario: Session rolling window in SSE broadcast

- **WHEN** a `headspace_update` SSE event is broadcast
- **THEN** the payload includes `frustration_rolling_3hr`

### Requirement: Frustration State Widget

The activity page SHALL include a frustration state widget displaying three rolling-window frustration averages.

#### Scenario: Widget displays three indicators

- **WHEN** the activity page loads with headspace monitoring enabled
- **THEN** a frustration state widget displays three labeled indicators: Immediate (rolling_10), Short-term (rolling_30min), Session (rolling_3hr)
- **AND** each shows a numeric average on a 0-10 scale with threshold-based coloring

#### Scenario: Widget updates via SSE

- **WHEN** a `headspace_update` SSE event arrives
- **THEN** the widget values and colors update in real-time without page refresh

#### Scenario: Widget hidden when disabled

- **WHEN** headspace monitoring is disabled
- **THEN** the frustration state widget is not rendered

#### Scenario: Null rolling window

- **WHEN** a rolling window value is null
- **THEN** the widget displays an em dash character with no threshold coloring

#### Scenario: Hover tooltip

- **WHEN** the user hovers over any rolling-window indicator
- **THEN** a tooltip displays the threshold boundaries

