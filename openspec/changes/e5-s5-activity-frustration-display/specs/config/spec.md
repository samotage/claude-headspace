## MODIFIED Requirements

### Requirement: Configuration Settings

The configuration system SHALL include frustration display settings.

#### Scenario: Session rolling window configuration

- **WHEN** the headspace configuration section is read
- **THEN** it includes `session_rolling_window_minutes` (default 180) controlling the session-level rolling window duration

#### Scenario: Config UI frustration section

- **WHEN** the configuration editor page is displayed
- **THEN** it includes a frustration settings section showing yellow threshold, red threshold, and session rolling window duration
- **AND** changes are persisted to config.yaml under the headspace section
