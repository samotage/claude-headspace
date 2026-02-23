## ADDED Requirements

### Requirement: Dashboard persona selector in agent creation flow

The dashboard's "New Agent" creation flow SHALL include an optional persona selector field. The selector SHALL display only active personas, grouped by role heading (e.g., "Developer", "Tester"). Each persona option SHALL show the persona name, role badge, and first line of description. A "No persona" option SHALL be the default. The selected persona slug SHALL be included in the `POST /api/agents` request body.

#### Scenario: User selects a persona when creating an agent

- **WHEN** the user clicks "+ Agent", selects a project, then selects a persona from the dropdown
- **THEN** the `POST /api/agents` request includes `persona_slug` matching the selected persona
- **AND** the agent is created with the persona assigned

#### Scenario: User creates an agent without a persona

- **WHEN** the user clicks "+ Agent", selects a project, and leaves the persona selector on "No persona"
- **THEN** the `POST /api/agents` request does not include `persona_slug` (or sends null)
- **AND** the agent is created without a persona (backward compatible)

#### Scenario: Persona selector shows only active personas

- **WHEN** the persona selector dropdown is opened
- **THEN** only personas with status "active" are displayed
- **AND** archived personas are excluded

### Requirement: Agent creation API accepts persona_slug

The `POST /api/agents` endpoint SHALL accept an optional `persona_slug` string parameter in the request body. When provided, the endpoint SHALL pass the slug to the `create_agent()` service function for validation and session creation.

#### Scenario: Valid persona_slug provided

- **WHEN** `POST /api/agents` receives `{ "project_id": 1, "persona_slug": "developer-con-1" }` and persona exists with status "active"
- **THEN** status 201 is returned and the agent session is launched with the persona

#### Scenario: Invalid persona_slug provided

- **WHEN** `POST /api/agents` receives `{ "project_id": 1, "persona_slug": "nonexistent" }` and no active persona with that slug exists
- **THEN** status 422 is returned with an error message naming the slug

#### Scenario: No persona_slug provided (backward compatible)

- **WHEN** `POST /api/agents` receives `{ "project_id": 1 }` without persona_slug
- **THEN** the agent is created without a persona, identical to current behavior

### Requirement: Active personas API endpoint

A `GET /api/personas/active` endpoint SHALL return all active personas with role information, sorted alphabetically by name within each role. The response SHALL include persona id, slug, name, role name, and first line of description.

#### Scenario: Active personas exist

- **WHEN** `GET /api/personas/active` is called and active personas exist
- **THEN** a JSON array is returned with active personas grouped and sorted by role

#### Scenario: No active personas

- **WHEN** `GET /api/personas/active` is called and no active personas exist
- **THEN** an empty JSON array is returned

### Requirement: CLI persona list command

`flask persona list` SHALL display all personas in a formatted table with columns: Name, Role, Slug, Status, Agents (count of linked agents). Output SHALL be sorted alphabetically by name within each role. A summary line SHALL show total count with active/archived breakdown.

#### Scenario: List all personas

- **WHEN** `flask persona list` is executed
- **THEN** all personas are displayed in a formatted table sorted by name within role

#### Scenario: Filter by active status

- **WHEN** `flask persona list --active` is executed
- **THEN** only personas with status "active" are displayed

#### Scenario: Filter by role

- **WHEN** `flask persona list --role developer` is executed
- **THEN** only personas with role "developer" are displayed

#### Scenario: No personas exist

- **WHEN** `flask persona list` is executed and no personas exist in the database
- **THEN** a "No personas found" message is displayed

### Requirement: CLI short-name matching for --persona flag

The `--persona` flag on `claude-headspace start` SHALL accept partial names (short names) in addition to full slugs. Matching SHALL be case-insensitive substring matching against the persona's name field. When exactly one persona matches, it SHALL be used automatically. When multiple match, the CLI SHALL present a numbered disambiguation list. When none match, available personas SHALL be displayed.

#### Scenario: Exact single match

- **WHEN** `claude-headspace start --persona con` is executed and exactly one persona's name contains "con" (case-insensitive)
- **THEN** that persona's slug is resolved and used for the session

#### Scenario: Multiple matches with disambiguation

- **WHEN** `claude-headspace start --persona dev` is executed and multiple personas' names contain "dev"
- **THEN** a numbered list is displayed and the user is prompted to choose

#### Scenario: No match found

- **WHEN** `claude-headspace start --persona xyz` is executed and no persona's name contains "xyz"
- **THEN** an error message is displayed with available personas and the process exits with non-zero code

#### Scenario: Full slug still works

- **WHEN** `claude-headspace start --persona developer-con-1` is executed and the slug exists
- **THEN** the persona is validated by slug (existing behavior, no short-name resolution needed)
