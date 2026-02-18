# project-controls Specification

## Purpose
TBD - created by archiving change e4-s2a-project-controls-backend. Update Purpose after archive.
## Requirements
### Requirement: Project CRUD API

The system SHALL provide REST API endpoints for creating, reading, updating, and deleting projects with manual registration.

#### Scenario: List all projects

- **WHEN** `GET /api/projects` is called
- **THEN** the response SHALL return all registered projects with id, name, path, github_repo, description, current_branch, inference_paused, created_at, and agent_count

#### Scenario: Create a project

- **WHEN** `POST /api/projects` is called with valid name and path
- **THEN** a new project SHALL be created and the response SHALL return 201 with the project details

#### Scenario: Create project with duplicate path

- **WHEN** `POST /api/projects` is called with a path that matches an existing project
- **THEN** the response SHALL return 409 Conflict with a descriptive error message

#### Scenario: Get project detail

- **WHEN** `GET /api/projects/<id>` is called with a valid project ID
- **THEN** the response SHALL return the project details including the list of agents and inference settings

#### Scenario: Update project metadata

- **WHEN** `PUT /api/projects/<id>` is called with valid update fields
- **THEN** the project metadata SHALL be updated and the response SHALL return 200

#### Scenario: Delete project with cascade

- **WHEN** `DELETE /api/projects/<id>` is called with a valid project ID
- **THEN** the project and all associated agents SHALL be deleted and the response SHALL return 200

### Requirement: Project Settings API

The system SHALL provide endpoints for managing per-project inference controls.

#### Scenario: Pause inference for a project

- **WHEN** `PUT /api/projects/<id>/settings` is called with `inference_paused: true`
- **THEN** `inference_paused` SHALL be set to true
- **AND** `inference_paused_at` SHALL be set to the current UTC timestamp
- **AND** a `project_settings_changed` SSE event SHALL be broadcast

#### Scenario: Resume inference for a project

- **WHEN** `PUT /api/projects/<id>/settings` is called with `inference_paused: false`
- **THEN** `inference_paused` SHALL be set to false
- **AND** `inference_paused_at` and `inference_paused_reason` SHALL be cleared to null
- **AND** a `project_settings_changed` SSE event SHALL be broadcast

### Requirement: Inference Gating

The system SHALL skip inference calls for projects with inference paused.

#### Scenario: Summarisation skipped for paused project

- **WHEN** summarise_turn, summarise_task, or summarise_instruction is called for a turn/command belonging to a paused project
- **THEN** the method SHALL return None without calling the inference service
- **AND** a debug log message SHALL be emitted

#### Scenario: Priority scoring excludes paused project agents

- **WHEN** score_all_agents is called
- **THEN** agents belonging to paused projects SHALL be excluded from the scoring batch
- **AND** if all active agents belong to paused projects, scoring SHALL be skipped entirely

### Requirement: SSE Broadcasting for Project Changes

The system SHALL broadcast SSE events when projects are created, updated, deleted, or their settings change.

#### Scenario: Project CRUD broadcasts event

- **WHEN** a project is created, updated, or deleted via the CRUD API
- **THEN** a `project_changed` SSE event SHALL be broadcast with the action and project ID

