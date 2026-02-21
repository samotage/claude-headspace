# persona-registration Specification

## Purpose
Provides a single-invocation persona registration operation that creates the database record and filesystem assets together. Exposed via Flask CLI command and optional REST API endpoint.

## ADDED Requirements

### Requirement: Registration service function

The system SHALL provide a `register_persona` function that accepts a persona name (required), role name (required), and description (optional) and performs the full creation flow: role lookup/create, persona insert with auto-generated slug, filesystem directory creation, and template file seeding. The function SHALL return the created persona's slug, database ID, and filesystem path.

#### Scenario: Successful registration with new role
- **WHEN** `register_persona(name="Con", role_name="developer")` is called and no "developer" role exists
- **THEN** a Role "developer" is created, a Persona record is inserted with slug "developer-con-{id}", the directory `data/personas/developer-con-{id}/` is created, and skill.md + experience.md are seeded

#### Scenario: Registration reuses existing role
- **WHEN** `register_persona(name="Rob", role_name="developer")` is called and a "developer" role already exists
- **THEN** the existing role is reused (no duplicate created) and a new Persona is created

### Requirement: Role lookup with case-insensitive matching

The registration operation SHALL lowercase the role name on input before lookup and storage. Case-insensitive matching ensures "Developer", "DEVELOPER", and "developer" all resolve to the same role.

#### Scenario: Case-insensitive role matching
- **WHEN** `register_persona(name="Con", role_name="Developer")` is called and a role "developer" exists
- **THEN** the existing "developer" role is reused

### Requirement: Input validation

The registration operation SHALL validate that persona name and role name are provided and non-empty. Missing or empty values SHALL produce a clear error. No database records SHALL be created if validation fails.

#### Scenario: Missing persona name
- **WHEN** `register_persona(name="", role_name="developer")` is called
- **THEN** a validation error is returned and no records are created

#### Scenario: Missing role name
- **WHEN** `register_persona(name="Con", role_name="")` is called
- **THEN** a validation error is returned and no records are created

### Requirement: Flask CLI command

The system SHALL provide `flask persona register` with `--name` (required), `--role` (required), and `--description` (optional) options. The command SHALL output the persona's slug, database ID, and filesystem path on success.

#### Scenario: CLI registration
- **WHEN** `flask persona register --name Con --role developer --description "Backend dev"` is executed
- **THEN** output displays the created slug, ID, and path

### Requirement: REST API endpoint

The system SHALL provide `POST /api/personas/register` accepting JSON `{name, role, description}`. On success it SHALL return 201 with `{slug, id, path}`. On validation failure it SHALL return 400.

#### Scenario: API registration success
- **WHEN** POST `/api/personas/register` with `{"name": "Con", "role": "developer"}` is sent
- **THEN** response is 201 with JSON containing slug, id, and path

#### Scenario: API validation error
- **WHEN** POST `/api/personas/register` with `{"name": ""}` is sent
- **THEN** response is 400 with error message

### Requirement: Partial failure handling

If the Persona DB record is created but filesystem creation fails, the system SHALL report the error with the persona's ID and slug. The DB record SHALL NOT be rolled back.

#### Scenario: Filesystem failure after DB insert
- **WHEN** persona DB record is created but `create_persona_assets` raises an exception
- **THEN** the error is reported with persona ID and slug; DB record remains

### Requirement: Duplicate handling

Registering a persona with the same name and role as an existing persona SHALL succeed, creating a new record with a unique slug.

#### Scenario: Duplicate name and role
- **WHEN** `register_persona(name="Con", role_name="developer")` is called twice
- **THEN** two distinct Persona records exist with different slugs (e.g., developer-con-1, developer-con-2)
