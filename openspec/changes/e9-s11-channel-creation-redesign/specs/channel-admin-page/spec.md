## MODIFIED Requirements

### Requirement: Dashboard Channel Creation Form — Redesigned

The dashboard channel management modal's "Create New" view SHALL be redesigned with a project picker + channel type selector + persona multi-checkbox, replacing the V0 name/type/description/agent-autocomplete form.

#### Scenario: Create New tab opens

- **WHEN** the operator clicks "Create New" in the channel management modal
- **THEN** the create view MUST show:
  - A project `<select id="channel-create-project">` populated from `GET /api/projects`
  - A channel type `<select id="channel-create-type">` (workshop, delegation, review, standup, broadcast)
  - A persona checkbox list `<div id="channel-create-persona-list">` (populated after project selection)
  - A "Create Channel" submit button (disabled until at least one persona selected)
- **AND** the name text input MUST NOT be present
- **AND** the description textarea MUST NOT be present
- **AND** the existing-agent autocomplete MUST NOT be present

#### Scenario: Project selected — persona list populates

- **WHEN** the operator selects a project
- **THEN** the persona list MUST populate with active personas from `GET /api/personas/active`
- **AND** each persona MUST be shown as a checkbox with name and role

#### Scenario: Create channel submitted (dashboard)

- **WHEN** the operator selects a project, personas, and type, then submits the form
- **THEN** `POST /api/channels` MUST be called with `{project_id, channel_type, persona_slugs}`
- **AND** the modal MUST close and the channel list MUST refresh on success

---

### Requirement: Dashboard Add Member — Project Picker Added

The dashboard channel chat panel's "Add Member" action SHALL include a project picker, supporting cross-project member addition.

#### Scenario: Add member panel opens (dashboard)

- **WHEN** the operator clicks "Add Member" in the channel chat kebab menu (dashboard)
- **THEN** the add-member panel MUST show:
  - A project picker (may differ from channel's project)
  - A persona single-select list
  - A "Add to Channel" submit button

#### Scenario: Add member submitted (dashboard)

- **WHEN** the operator selects a project and persona and clicks "Add to Channel"
- **THEN** `POST /api/channels/<slug>/members` MUST be called with `{persona_slug, project_id}`
- **AND** the panel MUST close on success
