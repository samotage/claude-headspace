# archive Specification

## Purpose
TBD - created by archiving change e4-s1-archive-system. Update Purpose after archive.
## Requirements
### Requirement: Centralized Archive Service

The system SHALL provide a centralized archive service that archives brain_reboot artifacts (waypoint, progress_summary, brain_reboot) with second-precision UTC timestamps.

#### Scenario: Archive single artifact on save

- **WHEN** a waypoint is saved or a progress summary is generated
- **THEN** the previous version of that artifact SHALL be archived with filename `{artifact}_{YYYY-MM-DD_HH-MM-SS}.md` using UTC time
- **AND** the archive SHALL complete before the new content is written

#### Scenario: Archive cascade on brain reboot export

- **WHEN** a brain reboot is exported
- **THEN** the previous brain_reboot.md SHALL be archived (if it exists)
- **AND** the current waypoint.md and progress_summary.md SHALL also be archived
- **AND** all three archives SHALL use the same UTC timestamp for the cascade

#### Scenario: Archive directory auto-creation

- **WHEN** an archive operation is triggered and `{project_path}/brain_reboot/archive/` does not exist
- **THEN** the directory SHALL be created automatically

#### Scenario: Archive operation failure (best-effort)

- **WHEN** an individual archive operation fails (e.g., permission error)
- **THEN** the failure SHALL be logged
- **AND** the primary save/generate/export operation SHALL NOT be blocked
- **AND** other archive operations in a cascade SHALL NOT be blocked

### Requirement: Configurable Retention Policy

The system SHALL support configurable retention policies for archived artifacts via `config.yaml`.

#### Scenario: Retention with keep_all policy (default)

- **WHEN** retention policy is `keep_all`
- **THEN** all archived versions SHALL be retained indefinitely

#### Scenario: Retention with keep_last_n policy

- **WHEN** retention policy is `keep_last_n` with value N
- **THEN** only the most recent N versions per artifact type SHALL be retained
- **AND** older versions SHALL be deleted after each archive operation

#### Scenario: Retention with time_based policy

- **WHEN** retention policy is `time_based` with value D days
- **THEN** only versions created within the last D days SHALL be retained
- **AND** older versions SHALL be deleted after each archive operation

#### Scenario: Retention cleanup failure

- **WHEN** retention cleanup fails
- **THEN** the failure SHALL be logged
- **AND** the archive operation and primary operation SHALL NOT be blocked

### Requirement: Archive Retrieval API

The system SHALL provide REST API endpoints for listing and retrieving archived artifacts.

#### Scenario: List all archives for a project

- **WHEN** `GET /api/projects/<id>/archives` is called
- **THEN** the response SHALL return all archived versions grouped by artifact type (waypoint, progress_summary, brain_reboot)
- **AND** each entry SHALL include filename and ISO 8601 timestamp

#### Scenario: List archives when none exist

- **WHEN** `GET /api/projects/<id>/archives` is called and no archives exist
- **THEN** the response SHALL return an empty list (not an error)

#### Scenario: Retrieve specific archive

- **WHEN** `GET /api/projects/<id>/archives/<artifact>/<timestamp>` is called with a valid artifact and timestamp
- **THEN** the response SHALL return the full content of that archived version

#### Scenario: Retrieve nonexistent archive

- **WHEN** `GET /api/projects/<id>/archives/<artifact>/<timestamp>` is called and the archive does not exist
- **THEN** the response SHALL return HTTP 404

