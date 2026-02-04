# config Specification

## Purpose
TBD - created by archiving change e2-s1-config-ui. Update Purpose after archive.
## Requirements
### Requirement: Config Tab Navigation

The system SHALL provide a Config tab accessible from the main navigation bar.

#### Scenario: Navigation to Config tab

Given the user is on any page in the dashboard
When they click the Config tab in navigation
Then the Config page is displayed
And the Config tab shows active state indicator

### Requirement: Config Form Display

The system SHALL display all config.yaml sections as form fields.

#### Scenario: Form sections displayed

When the Config page loads
Then all 7 config sections are displayed as grouped fieldsets
And each section has a clear heading
And form is pre-populated with current config values

#### Scenario: Section ordering

When the Config page loads
Then sections display in order: Server, Logging, Database, Claude, File Watcher, Event System, SSE

### Requirement: Field Type Rendering

The system SHALL render fields with appropriate input types.

#### Scenario: String field

Given a config field is of type string
When the form renders
Then a text input is displayed

#### Scenario: Numeric field

Given a config field is of type integer
When the form renders
Then a number input is displayed with appropriate min/max constraints

#### Scenario: Boolean field

Given a config field is of type boolean
When the form renders
Then a toggle switch is displayed

#### Scenario: Password field

Given the field is database.password
When the form renders
Then input is masked by default
And a reveal toggle button is displayed

### Requirement: Server-side Validation

The system SHALL validate all config fields server-side before saving.

#### Scenario: Valid configuration

Given all form fields contain valid values
When the user clicks Save
Then the configuration is persisted to config.yaml
And a success toast displays "Configuration saved"

#### Scenario: Invalid field type

Given a numeric field contains non-numeric value
When the user clicks Save
Then validation error is returned
And error displays inline next to the invalid field
And configuration is NOT persisted

#### Scenario: Required field missing

Given a required field is empty
When the user clicks Save
Then validation error is returned
And error displays inline next to the field

### Requirement: Config API

The system SHALL provide API endpoints for config management.

#### Scenario: GET current config

When GET /api/config is called
Then current configuration is returned as JSON
And environment variable overrides are excluded

#### Scenario: POST valid config

Given valid configuration JSON
When POST /api/config is called
Then configuration is validated
And persisted to config.yaml atomically
And 200 status returned

#### Scenario: POST invalid config

Given invalid configuration JSON
When POST /api/config is called
Then validation errors are returned as structured JSON
And 400 status returned
And config.yaml is NOT modified

### Requirement: Atomic File Write

The system SHALL write config changes atomically.

#### Scenario: Atomic save

When configuration is saved
Then changes are written to temporary file first
Then temporary file is renamed to config.yaml
And original file is not corrupted on failure

### Requirement: Password Security

The system SHALL protect password values.

#### Scenario: Password not logged

When a validation error occurs for database section
Then password value is NOT included in logs or error messages

### Requirement: Refresh After Save

The system SHALL provide mechanism to apply config changes.

#### Scenario: Refresh button visibility

When configuration is saved successfully
Then a Refresh button is displayed
And button indicates server restart is required

### Requirement: Configuration Settings

The configuration system SHALL include frustration display settings.

#### Scenario: Session rolling window configuration

- **WHEN** the headspace configuration section is read
- **THEN** it includes `session_rolling_window_minutes` (default 180) controlling the session-level rolling window duration

#### Scenario: Config UI frustration section

- **WHEN** the configuration editor page is displayed
- **THEN** it includes a frustration settings section showing yellow threshold, red threshold, and session rolling window duration
- **AND** changes are persisted to config.yaml under the headspace section

