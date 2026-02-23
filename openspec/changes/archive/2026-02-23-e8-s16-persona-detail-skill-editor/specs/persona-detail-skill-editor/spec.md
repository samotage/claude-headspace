## ADDED Requirements

### Requirement: Persona Detail Page

The application SHALL provide a detail page at `/personas/<slug>` displaying the full profile of a persona including metadata, skill content, experience log, and linked agents.

#### Scenario: Valid persona slug

- **WHEN** a user navigates to `/personas/<slug>` with a valid persona slug
- **THEN** the page renders with persona metadata (name, role, slug, status, description, created date), skill section, experience section, and linked agents section

#### Scenario: Invalid persona slug

- **WHEN** a user navigates to `/personas/<slug>` with a non-existent slug
- **THEN** a 404 error page is returned

#### Scenario: Back navigation

- **WHEN** a user clicks the "Back to Personas" link on the detail page
- **THEN** the browser navigates to `/personas` (the persona list page)

---

### Requirement: Skill File Editor

The skill section SHALL provide view, edit, and preview modes following the waypoint editor pattern (Edit/Preview tabs, monospace textarea, prose-styled markdown preview).

#### Scenario: View mode (default)

- **WHEN** the detail page loads and skill.md exists
- **THEN** the skill content is displayed as rendered markdown in prose styling
- **AND** an "Edit" button is visible

#### Scenario: Skill file does not exist

- **WHEN** the detail page loads and skill.md does not exist for the persona
- **THEN** an empty state message is shown with an option to create the skill file

#### Scenario: Switch to edit mode

- **WHEN** the user clicks the "Edit" button
- **THEN** the skill section switches to edit mode showing the raw markdown in a monospace textarea
- **AND** Edit/Preview tab buttons, Save button, and Cancel button are visible

#### Scenario: Preview mode

- **WHEN** the user clicks the "Preview" tab in edit mode
- **THEN** the current textarea content is rendered as markdown without saving
- **AND** the user can switch back to the "Edit" tab to continue editing

#### Scenario: Save skill content

- **WHEN** the user clicks "Save" in edit mode
- **THEN** the textarea content is sent via `PUT /api/personas/<slug>/skill`
- **AND** the skill.md file is written to the filesystem at `data/personas/{slug}/skill.md`
- **AND** the section returns to view mode showing the saved content rendered as markdown
- **AND** a success toast notification is displayed

#### Scenario: Save fails

- **WHEN** the save API call fails (network error, server error)
- **THEN** an error toast notification is displayed
- **AND** the editor remains in edit mode with the user's content preserved

#### Scenario: Cancel edit

- **WHEN** the user clicks "Cancel" in edit mode
- **THEN** the edits are discarded and the section returns to view mode with the last saved content

#### Scenario: Unsaved changes indicator

- **WHEN** the user modifies the textarea content
- **THEN** an "Unsaved changes" indicator is displayed
- **AND** the indicator disappears after save or cancel

---

### Requirement: Experience Log Viewer

The experience section SHALL display experience.md content as read-only rendered markdown with a last-modified timestamp.

#### Scenario: Experience file exists

- **WHEN** the detail page loads and experience.md exists
- **THEN** the content is rendered as markdown in prose styling (read-only, no edit controls)
- **AND** the last-modified timestamp is shown below the content

#### Scenario: Experience file does not exist or is empty

- **WHEN** the detail page loads and experience.md does not exist or is empty
- **THEN** an informational empty state message is shown: "No experience recorded yet. Experience is accumulated automatically as this persona works across sessions."

---

### Requirement: Linked Agents Display

The linked agents section SHALL list all agents currently assigned to the persona with their status details.

#### Scenario: Agents linked to persona

- **WHEN** the detail page loads and agents are linked to the persona
- **THEN** a list/table is displayed with each agent's display name or session ID, project name, current state, and last seen time

#### Scenario: No agents linked

- **WHEN** the detail page loads and no agents are linked to the persona
- **THEN** an empty state message is shown: "No agents are currently using this persona."

#### Scenario: Agent entry clickable

- **WHEN** the user clicks an agent entry in the linked agents list
- **THEN** the user is navigated to the dashboard or the agent's relevant view

---

### Requirement: Skill File API Endpoints

The application SHALL expose REST API endpoints for reading and writing persona skill files.

#### Scenario: Read skill content

- **WHEN** `GET /api/personas/<slug>/skill` is called with a valid persona slug
- **THEN** the response contains `{content: "<markdown>", exists: true}` with status 200
- **AND** if skill.md does not exist, `{content: null, exists: false}` with status 200

#### Scenario: Read skill for non-existent persona

- **WHEN** `GET /api/personas/<slug>/skill` is called with a slug not in the database
- **THEN** a 404 response is returned with `{error: "Persona not found"}`

#### Scenario: Write skill content

- **WHEN** `PUT /api/personas/<slug>/skill` is called with `{content: "<markdown>"}`
- **THEN** the content is written to `data/personas/{slug}/skill.md`
- **AND** the response contains `{saved: true}` with status 200

#### Scenario: Write skill with empty body

- **WHEN** `PUT /api/personas/<slug>/skill` is called without a JSON body or without content field
- **THEN** a 400 response is returned with `{error: "Content is required"}`

---

### Requirement: Experience File API Endpoint

The application SHALL expose a REST API endpoint for reading persona experience files.

#### Scenario: Read experience content

- **WHEN** `GET /api/personas/<slug>/experience` is called with a valid persona slug
- **THEN** the response contains `{content: "<markdown>", exists: true, last_modified: "<ISO timestamp>"}` with status 200
- **AND** if experience.md does not exist, `{content: null, exists: false, last_modified: null}` with status 200

---

### Requirement: Asset Status API Endpoint

The application SHALL expose a REST API endpoint for checking persona asset file existence.

#### Scenario: Check asset status

- **WHEN** `GET /api/personas/<slug>/assets` is called with a valid persona slug
- **THEN** the response contains `{skill_exists: <bool>, experience_exists: <bool>, directory_exists: <bool>}` with status 200

---

### Requirement: Linked Agents API Endpoint

The application SHALL expose a REST API endpoint returning agents linked to a persona.

#### Scenario: Agents exist

- **WHEN** `GET /api/personas/<slug>/agents` is called for a persona with linked agents
- **THEN** the response contains a JSON array of agent objects with `session_uuid`, `project_name`, `state`, `last_seen_at` with status 200

#### Scenario: No agents linked

- **WHEN** `GET /api/personas/<slug>/agents` is called for a persona with no linked agents
- **THEN** the response contains an empty array `[]` with status 200

---

<!-- NOTE: The persona list name column modification (names become clickable links to detail page) -->
<!-- is implemented in static/js/personas.js but applies to the existing persona-list-crud spec. -->
<!-- Captured here as documentation only since the target spec (persona-list-crud) is already archived. -->
