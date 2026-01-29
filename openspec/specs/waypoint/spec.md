# waypoint Specification

## Purpose
TBD - created by archiving change e2-s2-waypoint-editor. Update Purpose after archive.
## Requirements
### Requirement: Project Selection

The system SHALL provide a project selector for waypoint editing.

#### Scenario: Project dropdown populated

When the waypoint editor opens
Then a dropdown lists all monitored projects
And projects are sorted alphabetically by name

#### Scenario: Project selection loads waypoint

Given a project is selected from the dropdown
When the selection changes
Then the waypoint content for that project is loaded
And the editor displays the content

### Requirement: Waypoint Loading

The system SHALL load waypoint content from project directories.

#### Scenario: Waypoint exists

Given a project with an existing waypoint
When the waypoint is loaded
Then content is returned from `<project.path>/docs/brain_reboot/waypoint.md`
And the file's modification time is recorded

#### Scenario: Waypoint missing

Given a project without an existing waypoint
When the waypoint is loaded
Then the default template is displayed
And an indicator shows this is a new waypoint

#### Scenario: Default template content

When a new waypoint is created
Then it contains sections: Next Up, Upcoming, Later, Not Now
And each section has a placeholder comment

### Requirement: Editing Interface

The system SHALL provide markdown editing with preview.

#### Scenario: Edit mode

When in edit mode
Then a textarea displays the markdown content
And users can modify the content

#### Scenario: Preview mode

When in preview mode
Then the markdown is rendered as HTML
And headings, lists, and code blocks display correctly

#### Scenario: Mode toggle

When the user toggles between modes
Then the view switches between textarea and rendered preview
And content is preserved between toggles

#### Scenario: Unsaved changes indicator

Given content has been modified
When the editor displays
Then an indicator shows unsaved changes exist

### Requirement: Waypoint Saving

The system SHALL save waypoints with automatic archiving.

#### Scenario: Save with archive

Given an existing waypoint
When the user saves
Then the current waypoint is archived to `archive/waypoint_YYYY-MM-DD.md`
Then the new content is written to `waypoint.md`

#### Scenario: Multiple daily archives

Given an archive already exists for today
When the user saves again
Then a counter is appended (e.g., `waypoint_2026-01-29_2.md`)

#### Scenario: New waypoint save

Given no existing waypoint
When the user saves
Then no archive is created
And the content is written to `waypoint.md`

#### Scenario: Directory creation

Given the `docs/brain_reboot/` directory does not exist
When the user saves
Then the directory structure is created
And the archive subdirectory is created

### Requirement: Conflict Detection

The system SHALL detect external file modifications.

#### Scenario: Conflict detected

Given a waypoint was loaded at time T1
And the file was externally modified at time T2 > T1
When the user attempts to save
Then a conflict is detected
And the user is prompted to resolve

#### Scenario: Reload resolution

Given a conflict is detected
When the user selects Reload
Then the current file content is loaded
And the user's changes are discarded

#### Scenario: Overwrite resolution

Given a conflict is detected
When the user selects Overwrite
Then the user's content is saved
And the external changes are replaced

### Requirement: Waypoint API

The system SHALL provide REST API for waypoint operations.

#### Scenario: GET waypoint exists

When GET /api/projects/<id>/waypoint is called
And the waypoint exists
Then response includes content, exists=true, last_modified, path

#### Scenario: GET waypoint missing

When GET /api/projects/<id>/waypoint is called
And the waypoint does not exist
Then response includes template content, exists=false, template=true

#### Scenario: POST waypoint success

When POST /api/projects/<id>/waypoint is called
With valid content and matching expected_mtime
Then the waypoint is saved
And response includes success=true, archived flag, archive_path

#### Scenario: POST waypoint conflict

When POST /api/projects/<id>/waypoint is called
With expected_mtime that does not match current mtime
Then response is 409 conflict
And includes current_mtime and expected_mtime

### Requirement: Error Handling

The system SHALL provide actionable error messages.

#### Scenario: Permission denied

Given the user lacks write permission
When save is attempted
Then error includes the specific path
And suggests checking directory permissions

#### Scenario: Project path inaccessible

Given the project path does not exist
When waypoint load is attempted
Then error includes the specific path
And indicates the path is inaccessible

### Requirement: Dashboard Integration

The system SHALL integrate with the existing dashboard.

#### Scenario: Edit button opens editor

Given the dashboard shows a project with waypoint preview
When the user clicks [Edit]
Then the waypoint editor opens for that project

