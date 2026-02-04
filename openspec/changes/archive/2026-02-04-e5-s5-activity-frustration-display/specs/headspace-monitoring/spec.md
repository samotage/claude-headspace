## ADDED Requirements

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
