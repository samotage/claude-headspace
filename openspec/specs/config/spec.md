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

### Requirement: Config/UI Parity

The CONFIG_SCHEMA SHALL include definitions for all config.yaml sections and fields, except `openrouter.pricing`.

#### Scenario: tmux_bridge section

- **WHEN** the config page is loaded
- **THEN** the tmux_bridge section SHALL display with fields: health_check_interval (int, default 30), subprocess_timeout (int, default 10), text_enter_delay_ms (int, default 100)

#### Scenario: dashboard section

- **WHEN** the config page is loaded
- **THEN** the dashboard section SHALL display with fields: stale_processing_seconds (int, default 600), active_timeout_minutes (int, default 5)

#### Scenario: archive section

- **WHEN** the config page is loaded
- **THEN** the archive section SHALL display with fields: enabled (bool, default true), retention.policy (string, default "keep_last_n"), retention.keep_last_n (int, default 10), retention.days (int, default 90)

#### Scenario: Missing openrouter fields

- **WHEN** the config page is loaded
- **THEN** the openrouter section SHALL additionally display: retry.base_delay_seconds (float, default 1.0), retry.max_delay_seconds (float, default 30.0), priority_scoring.debounce_seconds (float, default 5.0)

#### Scenario: Missing headspace fields

- **WHEN** the config page is loaded
- **THEN** the headspace section SHALL additionally display: flow_detection.min_turn_rate (int, default 6), flow_detection.max_frustration (float, default 3.0), flow_detection.min_duration_minutes (int, default 15)

#### Scenario: commander defaults in config.yaml

- **WHEN** config.yaml is read
- **THEN** the commander section SHALL have explicit default values matching the CONFIG_SCHEMA defaults

### Requirement: Section Help Icons

Each config section header SHALL display a clickable ⓘ info icon adjacent to the section title.

#### Scenario: Section help icon click

- **WHEN** the user clicks a section help icon
- **THEN** a popover SHALL appear containing a brief description of the section and a "Learn more" link to /help/configuration#section-slug

#### Scenario: Section help icon appearance

- **WHEN** the config page is rendered
- **THEN** section help icons SHALL be visually muted and not compete with the section title for attention

### Requirement: Field Help Icons

Each config field label SHALL display a clickable ⓘ info icon adjacent to the label text.

#### Scenario: Field help icon click

- **WHEN** the user clicks a field help icon
- **THEN** a popover SHALL appear containing: a practical description (1-3 sentences), the default value, the valid range (for numeric fields), and a "Learn more" link

#### Scenario: Field help icon appearance

- **WHEN** the config page is rendered
- **THEN** field help icons SHALL be visually muted and not disrupt field label alignment

### Requirement: Popover Behaviour

The popover component SHALL enforce single-instance display and keyboard accessibility.

#### Scenario: Single popover constraint

- **WHEN** a help icon is clicked while another popover is open
- **THEN** the existing popover SHALL close and the new popover SHALL open

#### Scenario: Dismiss on click outside

- **WHEN** the user clicks outside an open popover
- **THEN** the popover SHALL close

#### Scenario: Dismiss on Escape

- **WHEN** the user presses the Escape key while a popover is open
- **THEN** the popover SHALL close

#### Scenario: Toggle on re-click

- **WHEN** the user clicks the same help icon that opened the current popover
- **THEN** the popover SHALL close

#### Scenario: Keyboard activation

- **WHEN** a help icon is focused via Tab and the user presses Enter or Space
- **THEN** the popover SHALL open

#### Scenario: Viewport-aware positioning

- **WHEN** a popover would overflow the viewport
- **THEN** it SHALL reposition to remain fully visible (e.g., flip above if near bottom)

### Requirement: Help Page Deep-Linking

The help page SHALL support anchor-based deep-linking to specific sections.

#### Scenario: Navigate with anchor

- **WHEN** the user navigates to /help/configuration#headspace
- **THEN** the help page SHALL load the configuration topic and scroll to the headspace section

#### Scenario: Anchor highlight

- **WHEN** a section is scrolled to via anchor
- **THEN** the target section SHALL briefly highlight to orient the user

#### Scenario: Header IDs

- **WHEN** the help page renders markdown content
- **THEN** all heading elements SHALL have id attributes derived from the heading text (slugified)

### Requirement: Configuration Documentation

docs/help/configuration.md SHALL contain comprehensive per-field documentation.

#### Scenario: Field documentation content

- **WHEN** a field's documentation is read
- **THEN** it SHALL include: what the field controls, when a user would want to change it, and consequences of incorrect values (for numeric fields)

#### Scenario: Section introductions

- **WHEN** a configuration section is read
- **THEN** it SHALL begin with a brief introductory paragraph explaining what the section controls

