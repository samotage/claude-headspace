# activity-monitoring Specification

## Purpose
TBD - created by archiving change e4-s3-activity-monitoring. Update Purpose after archive.
## Requirements
### Requirement: Activity Metrics Calculation

The system SHALL calculate turn rate and average turn time metrics at agent, project, and overall levels.

#### Scenario: Agent turn rate calculation

- **WHEN** turns exist for an agent within the aggregation window
- **THEN** the system SHALL compute turns per hour for that agent

#### Scenario: Agent average turn time calculation

- **WHEN** multiple turns exist for an agent within the aggregation window
- **THEN** the system SHALL compute the mean elapsed time between consecutive turns

#### Scenario: Project-level metric aggregation

- **WHEN** agent-level metrics exist for agents within a project
- **THEN** the system SHALL aggregate those metrics to produce project-level turn rate, average turn time, and active agent count

#### Scenario: Overall metric aggregation

- **WHEN** project-level metrics exist
- **THEN** the system SHALL aggregate those metrics to produce system-wide turn rate, average turn time, and total active agent count

### Requirement: Time-Series Metric Storage

The system SHALL store metrics at hourly bucket granularity for historical trend analysis.

#### Scenario: Hourly metric storage

- **WHEN** the aggregation job runs
- **THEN** metric records SHALL be stored with a `bucket_start` timestamp aligned to the start of the hour

#### Scenario: Metric scoping

- **WHEN** a metric record is created
- **THEN** it SHALL be scoped to exactly one of: a specific agent, a specific project, or overall (system-wide)

#### Scenario: Periodic aggregation

- **WHEN** the application is running
- **THEN** the system SHALL automatically aggregate and store new metric records at regular intervals

#### Scenario: Data retention pruning

- **WHEN** the aggregation job runs
- **THEN** metric records older than 30 days SHALL be automatically deleted

### Requirement: Activity Page

The system SHALL provide a dedicated Activity page for viewing agent productivity metrics and historical trends.

#### Scenario: Activity page loads

- **WHEN** `GET /activity` is accessed
- **THEN** the page SHALL render with overall summary, time-series chart, and project/agent metric panels

#### Scenario: Time-series chart display

- **WHEN** the Activity page is rendered with historical data
- **THEN** a time-series chart SHALL display turn activity over time with day, week, and month view toggles

#### Scenario: Chart tooltips

- **WHEN** the user hovers over a chart data point
- **THEN** a tooltip SHALL display the exact metric value and the time period it represents

#### Scenario: Empty state

- **WHEN** no activity data exists for an agent, project, or overall
- **THEN** the page SHALL display a clear empty state message

### Requirement: Metrics API Endpoints

The system SHALL provide API endpoints for retrieving current and historical metrics.

#### Scenario: Agent metrics endpoint

- **WHEN** `GET /api/metrics/agents/<id>` is requested
- **THEN** the system SHALL return current and historical metrics for the specified agent

#### Scenario: Project metrics endpoint

- **WHEN** `GET /api/metrics/projects/<id>` is requested
- **THEN** the system SHALL return current and historical aggregated metrics for the specified project

#### Scenario: Overall metrics endpoint

- **WHEN** `GET /api/metrics/overall` is requested
- **THEN** the system SHALL return current and historical system-wide aggregated metrics

### Requirement: Activity Navigation Tab

The header navigation SHALL include an "Activity" tab for accessing the Activity page.

#### Scenario: Activity tab in navigation

- **WHEN** the header navigation is rendered
- **THEN** an "Activity" tab SHALL appear in the navigation menu

#### Scenario: Active state on Activity page

- **WHEN** the user is on the `/activity` page
- **THEN** the Activity tab SHALL display active state styling consistent with other navigation tabs

