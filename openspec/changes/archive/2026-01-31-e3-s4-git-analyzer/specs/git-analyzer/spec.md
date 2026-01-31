## ADDED Requirements

### Requirement: Git Commit Analysis

The system SHALL provide a git analyzer that extracts structured commit history from target project repositories using configurable commit scopes.

#### Scenario: Extract commits with since_last scope

- **WHEN** analysis is requested with `since_last` scope and a previous progress_summary.md exists
- **THEN** the system SHALL extract all commits since the timestamp in the previous summary's metadata header
- **AND** the result SHALL include commit hash, message, author, timestamp, and files changed per commit

#### Scenario: Extract commits with last_n scope

- **WHEN** analysis is requested with `last_n` scope
- **THEN** the system SHALL extract the most recent N commits (N configurable)

#### Scenario: Extract commits with time_based scope

- **WHEN** analysis is requested with `time_based` scope
- **THEN** the system SHALL extract all commits within the last N days (N configurable)

#### Scenario: Fallback when no previous summary exists

- **WHEN** analysis is requested with `since_last` scope but no previous progress_summary.md exists
- **THEN** the system SHALL fall back to `last_n` scope

#### Scenario: Maximum commit cap enforcement

- **WHEN** the commit scope returns more commits than the configured maximum cap
- **THEN** the system SHALL truncate to the most recent commits within the cap

#### Scenario: Structured analysis result

- **WHEN** analysis completes successfully
- **THEN** the result SHALL contain: list of commits, unique files changed, unique authors, date range, and total commit count

---

### Requirement: Progress Summary Generation

The system SHALL generate a 3-5 paragraph narrative progress summary from git analysis results using LLM inference.

#### Scenario: Successful summary generation

- **WHEN** generation is triggered for a project with commits in scope
- **THEN** the system SHALL build a prompt with project name, date range, commit count, commit details, and files changed
- **AND** the system SHALL call the E3-S1 inference service at the "project" level with `purpose="progress_summary"` and `project_id`
- **AND** the generated narrative SHALL be written in past tense focusing on accomplishments

#### Scenario: Zero commits in scope

- **WHEN** generation is triggered but no commits exist in the configured scope
- **THEN** the system SHALL return a clear "No commits found in configured scope" message
- **AND** no inference call SHALL be made

---

### Requirement: File Output and Archiving

The system SHALL write progress summaries as markdown files to target project repositories with archiving of previous versions.

#### Scenario: Write progress summary to target project

- **WHEN** a summary is generated successfully
- **THEN** the system SHALL write `progress_summary.md` to `{project.path}/docs/brain_reboot/`
- **AND** the file SHALL include a metadata header with generation timestamp, scope used, date range, and commit count

#### Scenario: Archive previous summary before overwriting

- **WHEN** a new summary is being written and a previous `progress_summary.md` exists
- **THEN** the system SHALL archive the existing file to `archive/progress_summary_YYYY-MM-DD.md` before writing the new one
- **AND** if a file with the same date-stamped name exists, a numeric suffix SHALL be appended

#### Scenario: Auto-create directory structure

- **WHEN** the `docs/brain_reboot/` or `archive/` directories do not exist in the target project
- **THEN** the system SHALL create them automatically

---

### Requirement: Progress Summary API Endpoints

The system SHALL expose API endpoints for triggering generation and retrieving current summaries.

#### Scenario: Trigger progress summary generation

- **WHEN** POST `/api/projects/<id>/progress-summary` is requested
- **THEN** the system SHALL trigger generation for the specified project
- **AND** the response SHALL include the generated summary content and generation metadata

#### Scenario: Optional scope override

- **WHEN** POST `/api/projects/<id>/progress-summary` includes a scope parameter
- **THEN** the system SHALL use the specified scope instead of the configured default

#### Scenario: Retrieve current summary

- **WHEN** GET `/api/projects/<id>/progress-summary` is requested
- **THEN** the response SHALL return the current `progress_summary.md` content
- **AND** if no summary exists, the response SHALL return a 404 or empty content with status indication

#### Scenario: Project not found

- **WHEN** either endpoint is requested with a non-existent project ID
- **THEN** the system SHALL return a 404 error

#### Scenario: Project is not a git repository

- **WHEN** generation is requested for a project whose path is not a git repository
- **THEN** the system SHALL return a 422 error indicating no git history available

#### Scenario: Generation already in progress

- **WHEN** generation is requested while one is already running for the same project
- **THEN** the system SHALL return a 409 error without starting a duplicate

---

### Requirement: Concurrent Generation Guard

Only one progress summary generation SHALL run per project at a time.

#### Scenario: Guard prevents duplicate generation

- **WHEN** a generation request arrives while one is in progress for the same project
- **THEN** the system SHALL return "generation in progress" status
- **AND** SHALL NOT start a duplicate generation

#### Scenario: Guard cleared on completion

- **WHEN** generation completes (successfully or with error)
- **THEN** the in-progress state SHALL be cleared for that project

---

### Requirement: Error Handling

The system SHALL handle error conditions gracefully without crashing.

#### Scenario: Non-git project

- **WHEN** the target project path is not a git repository
- **THEN** the system SHALL return a clear error indicating no git history

#### Scenario: File permission failure

- **WHEN** a file write or archive operation fails due to permissions
- **THEN** the error SHALL be logged and reported to the user
- **AND** no existing files SHALL be corrupted

#### Scenario: Inference failure

- **WHEN** the LLM inference call fails during generation
- **THEN** the failure SHALL be logged via the E3-S1 InferenceCall system
- **AND** the user SHALL be informed that generation failed

---

### Requirement: Configuration

The system SHALL support configurable settings for progress summary generation.

#### Scenario: Configuration schema

- **WHEN** config.yaml is loaded
- **THEN** the `progress_summary` section SHALL include: default_scope, last_n_count, time_based_days, and max_commits
- **AND** sensible defaults SHALL be provided

---

## MODIFIED Requirements

### Requirement: Dashboard Project Panel

The dashboard project panel SHALL include progress summary generation and display capabilities.

#### Scenario: Generate button displayed

- **WHEN** the dashboard renders a project panel
- **THEN** a "Generate Progress Summary" button SHALL be displayed

#### Scenario: In-progress indicator

- **WHEN** generation is in progress
- **THEN** the button SHALL be disabled and show an in-progress indicator

#### Scenario: Summary displayed after generation

- **WHEN** generation completes successfully
- **THEN** the progress summary content SHALL be displayed in the project panel

#### Scenario: Error displayed on failure

- **WHEN** generation fails
- **THEN** an informative error message SHALL be displayed in the project panel
