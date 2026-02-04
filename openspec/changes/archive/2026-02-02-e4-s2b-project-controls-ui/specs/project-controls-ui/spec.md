## ADDED Requirements

### Requirement: Projects Management Page

The system SHALL provide a `/projects` management page for registering, editing, deleting projects and controlling inference settings.

#### Scenario: Projects page loads with project list

- **WHEN** `GET /projects` is accessed
- **THEN** the page SHALL render a table of all registered projects showing name, path, active agent count, inference status, and action controls

#### Scenario: Add project via modal form

- **WHEN** the user clicks "Add Project" and submits valid data (name, path)
- **THEN** the project SHALL be created via the API and appear in the list without page reload

#### Scenario: Add project with duplicate path

- **WHEN** the user submits a project with a path that matches an existing project
- **THEN** an inline error message SHALL be displayed without creating a duplicate

#### Scenario: Edit project via modal form

- **WHEN** the user clicks Edit on a project row
- **THEN** a modal SHALL open pre-populated with the project's current values
- **AND** submitting the form SHALL update the project and refresh the list

#### Scenario: Delete project with confirmation

- **WHEN** the user clicks Delete on a project row
- **THEN** a confirmation dialog SHALL appear showing the project name and agent count warning
- **AND** confirming SHALL delete the project and remove it from the list

#### Scenario: Toggle inference pause/resume

- **WHEN** the user clicks the pause/resume control on a project row
- **THEN** the project's inference_paused state SHALL be toggled via the settings API
- **AND** the status indicator SHALL update immediately without page reload

### Requirement: Projects Page Paused Indicator

The projects page SHALL display a visually distinct indicator on projects with inference paused.

#### Scenario: Paused project shows indicator

- **WHEN** a project has `inference_paused = true`
- **THEN** the project row SHALL display a "Paused" label or icon that is visually distinct from active projects

### Requirement: Header Navigation Projects Tab

The header navigation SHALL include a "Projects" tab for accessing the projects management page.

#### Scenario: Projects tab in navigation

- **WHEN** the header navigation is rendered
- **THEN** a "Projects" tab SHALL appear between Dashboard and Objective in both desktop and mobile navigation

#### Scenario: Active state on projects page

- **WHEN** the user is on the `/projects` page
- **THEN** the Projects tab SHALL display active state styling consistent with other navigation tabs

### Requirement: Real-Time Project Updates via SSE

The projects page SHALL update in real-time when project data changes.

#### Scenario: SSE project_changed event

- **WHEN** a `project_changed` SSE event is received while on the projects page
- **THEN** the project list SHALL refresh to reflect the change without page reload

#### Scenario: SSE project_settings_changed event

- **WHEN** a `project_settings_changed` SSE event is received while on the projects page
- **THEN** the affected project's status indicator SHALL update without page reload
