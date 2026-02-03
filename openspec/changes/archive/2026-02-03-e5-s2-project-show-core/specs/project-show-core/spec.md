## ADDED Requirements

### Requirement: Project Slug Field

The Project model SHALL have a `slug` field that is unique, non-nullable, and indexed. The slug MUST be derived from the project name using URL-safe transformation (lowercase, hyphens for spaces and special characters, collapsed multiple hyphens, stripped leading/trailing hyphens).

#### Scenario: Auto-generate slug on project creation

- **WHEN** a project is created with name "My Cool Project"
- **THEN** a slug "my-cool-project" is automatically generated and stored

#### Scenario: Handle slug collision

- **WHEN** a project is created with name "My Project" and slug "my-project" already exists
- **THEN** the slug "my-project-2" is generated (incrementing numeric suffix)

#### Scenario: Regenerate slug on name update

- **WHEN** a project name is updated from "Old Name" to "New Name"
- **THEN** the slug is regenerated to "new-name"

#### Scenario: Handle special characters in slug

- **WHEN** a project is created with name containing Unicode or special characters
- **THEN** the slug gracefully handles them (transliterate or strip)

### Requirement: Project Show Page Route

The system SHALL provide a project show page at `GET /projects/<slug>` that renders the full project detail view.

#### Scenario: Valid slug navigation

- **WHEN** a user navigates to `/projects/claude-headspace`
- **THEN** the page renders with the project's metadata, waypoint, brain reboot, and progress summary

#### Scenario: Invalid slug navigation

- **WHEN** a user navigates to `/projects/nonexistent-slug`
- **THEN** the system returns a 404 response

### Requirement: Project Show Page Metadata Display

The project show page SHALL display the project's metadata: name, path, GitHub repository (as a clickable link if present), current branch, description (rendered as markdown), and creation date.

#### Scenario: Display project with all metadata

- **WHEN** the show page loads for a project with all fields populated
- **THEN** all metadata fields are visible including a clickable GitHub repo link

#### Scenario: Display project with missing optional fields

- **WHEN** the show page loads for a project without a GitHub repo
- **THEN** the GitHub repo field shows a placeholder or is hidden gracefully

### Requirement: Project Show Page Inference Status

The project show page SHALL display the project's inference status: whether inference is active or paused, and if paused, the paused-at timestamp and reason.

#### Scenario: Active inference

- **WHEN** the project has inference active
- **THEN** the status shows "Active" in green

#### Scenario: Paused inference

- **WHEN** the project has inference paused
- **THEN** the status shows "Paused since [date] — [reason]" in amber

### Requirement: Project Show Page Control Actions

The project show page SHALL provide control actions: Edit, Delete, Pause/Resume, Regenerate Description, and Refetch GitHub Info.

#### Scenario: Edit project metadata

- **WHEN** the user clicks Edit and submits changes including a name change
- **THEN** the metadata updates in place and the page URL updates to reflect the new slug

#### Scenario: Delete project

- **WHEN** the user clicks Delete and confirms in the confirmation dialog
- **THEN** the project is deleted and the user is redirected to `/projects`

#### Scenario: Toggle inference pause

- **WHEN** the user clicks Pause/Resume
- **THEN** the inference status toggles and the display updates immediately

#### Scenario: Regenerate description

- **WHEN** the user clicks "Regenerate Description"
- **THEN** an LLM-based description is generated and the description field updates without full page reload

#### Scenario: Refetch GitHub info

- **WHEN** the user clicks "Refetch GitHub Info"
- **THEN** the git remote URL and branch are re-read and the display updates

### Requirement: Waypoint Section

The project show page SHALL include a Waypoint section that displays the current waypoint content rendered as markdown with an edit link.

#### Scenario: Waypoint exists

- **WHEN** the project has a waypoint
- **THEN** the waypoint content is displayed as rendered markdown with an edit link

#### Scenario: No waypoint exists

- **WHEN** the project has no waypoint
- **THEN** an empty state message is shown with guidance

### Requirement: Brain Reboot Section

The project show page SHALL include a Brain Reboot section that displays the last generated brain reboot content rendered as markdown, with generation timestamp (absolute and relative time-ago), Regenerate button, and Export button.

#### Scenario: Brain reboot exists

- **WHEN** the project has a previous brain reboot
- **THEN** the content is displayed with "Generated 2 hours ago" timestamp, Regenerate, and Export buttons

#### Scenario: No brain reboot exists

- **WHEN** the project has no brain reboot
- **THEN** an empty state with "Generate" button is shown

#### Scenario: Regenerate brain reboot

- **WHEN** the user clicks "Regenerate"
- **THEN** a loading indicator is shown, a new brain reboot is generated, and the content updates

#### Scenario: Export brain reboot

- **WHEN** the user clicks "Export"
- **THEN** the brain reboot is exported to the project's filesystem

### Requirement: Progress Summary Section

The project show page SHALL include a Progress Summary section that displays the current progress summary rendered as markdown with a Regenerate button.

#### Scenario: Progress summary exists

- **WHEN** the project has a progress summary
- **THEN** the content is displayed as rendered markdown with Regenerate option

#### Scenario: No progress summary exists

- **WHEN** the project has no progress summary
- **THEN** an empty state with "Generate" button is shown

### Requirement: Projects List Navigation Changes

The projects list page SHALL make project names clickable links to `/projects/<slug>` and SHALL remove Edit, Delete, and Pause/Resume action buttons from the list. The "Add Project" button SHALL be retained.

#### Scenario: Click project name

- **WHEN** the user clicks a project name on the projects list
- **THEN** the browser navigates to `/projects/<slug>`

#### Scenario: No action buttons in list

- **WHEN** the projects list is rendered
- **THEN** no Edit, Delete, or Pause/Resume buttons appear per project row

### Requirement: Brain Reboot Modal Link

The brain reboot slider modal SHALL include a link to the project show page at `/projects/<slug>`.

#### Scenario: Navigate from modal to show page

- **WHEN** the user is viewing the brain reboot modal
- **THEN** a link to the project show page is visible and navigates correctly when clicked

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
