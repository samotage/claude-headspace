# Delta Spec: e5-s7-config-help-system

## ADDED Requirements

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

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
