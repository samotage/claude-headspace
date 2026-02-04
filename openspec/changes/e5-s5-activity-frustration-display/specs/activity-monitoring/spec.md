## MODIFIED Requirements

### Requirement: Activity Frustration Display

The activity page SHALL display frustration as an average per scored turn (0-10 scale) instead of a raw sum.

#### Scenario: Metric card displays average

- **WHEN** the activity page renders frustration metric cards at any scope (overall, project, agent)
- **THEN** the displayed value is `total_frustration / frustration_turn_count`, rounded to 1 decimal place
- **AND** the value is colored green when below the yellow threshold, yellow between yellow and red thresholds, red at or above the red threshold

#### Scenario: No scored turns in period

- **WHEN** a metric card period has `frustration_turn_count` of zero or null
- **THEN** the card displays an em dash character with no threshold coloring

#### Scenario: Chart frustration line uses average

- **WHEN** the Turn Activity chart renders the frustration line overlay
- **THEN** each data point plots the per-bucket average (total_frustration / frustration_turn_count) on a fixed 0-10 right Y-axis

#### Scenario: Chart gap for missing data

- **WHEN** an hourly bucket has no scored turns
- **THEN** no line segment is drawn to or from that bucket (gap in line)

#### Scenario: Chart threshold coloring

- **WHEN** the frustration line is rendered
- **THEN** the line or data points are colored based on the same configurable thresholds as the metric cards
