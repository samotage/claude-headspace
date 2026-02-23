# persona-list-crud Specification

## Purpose
TBD - created by archiving change e8-s15-persona-list-crud. Update Purpose after archive.
## Requirements
### Requirement: Personas tab in main navigation

A "Personas" tab SHALL be added to the main navigation bar in both the desktop tab group and the mobile drawer menu. The tab SHALL link to `/personas` and SHALL highlight as active when the current page is the personas page.

#### Scenario: Navigation displays Personas tab
- **WHEN** any page with the shared header is loaded
- **THEN** a "personas" tab link is visible in the navigation bar, positioned after "help"

#### Scenario: Personas tab active state
- **WHEN** the user is on the `/personas` page
- **THEN** the personas tab link has the `active` class and `aria-current="page"` attribute

### Requirement: Persona list page displays all personas

The `/personas` page SHALL display a table of all registered personas ordered by creation date (newest first). Each row SHALL show: persona name, role name, status badge (active = green, archived = muted), count of currently linked agents, and creation date. Each row SHALL have action buttons for Edit and Archive/Delete.

#### Scenario: Personas exist
- **WHEN** the `/personas` page is loaded and personas exist in the database
- **THEN** a table is rendered with one row per persona showing name, role, status badge, agent count, and created date
- **AND** each row has Edit and Archive/Delete action buttons

#### Scenario: No personas exist
- **WHEN** the `/personas` page is loaded and no personas exist in the database
- **THEN** an empty state message is displayed: "No personas yet" with a "Create your first persona" call-to-action

#### Scenario: Archived personas
- **WHEN** the persona list includes archived personas
- **THEN** archived persona rows are visually distinguished with muted text/row styling
- **AND** the status badge shows "Archived" in muted styling

### Requirement: List API returns personas with metadata

The `GET /api/personas` endpoint SHALL return a JSON array of all personas. Each persona object SHALL include: id, slug, name, role_name, status, agent_count, description, and created_at. The list SHALL be ordered by created_at descending.

#### Scenario: Successful list retrieval
- **WHEN** `GET /api/personas` is called
- **THEN** the response is 200 with a JSON array of persona objects
- **AND** each object includes id, slug, name, role_name, status, agent_count, description, created_at

#### Scenario: Empty list
- **WHEN** `GET /api/personas` is called and no personas exist
- **THEN** the response is 200 with an empty JSON array

### Requirement: Get single persona by slug

The `GET /api/personas/<slug>` endpoint SHALL return a single persona's full details including id, slug, name, role_name, role_id, description, status, agent_count, and created_at.

#### Scenario: Persona found
- **WHEN** `GET /api/personas/<slug>` is called with a valid slug
- **THEN** the response is 200 with the persona's full details

#### Scenario: Persona not found
- **WHEN** `GET /api/personas/<slug>` is called with a non-existent slug
- **THEN** the response is 404 with an error message

### Requirement: Create persona via existing register endpoint

Persona creation SHALL use the existing `POST /api/personas/register` endpoint. The create modal SHALL call this endpoint with name, role, and optional description. On success, the list SHALL refresh without page reload.

#### Scenario: Successful creation
- **WHEN** the user submits the create form with a valid name and role
- **THEN** the persona is created via the API and appears in the list immediately

#### Scenario: Create with new role
- **WHEN** the user selects "Create new role..." and enters a new role name
- **THEN** the new role is created alongside the persona

#### Scenario: Validation error on create
- **WHEN** the user submits the create form with empty name or empty role
- **THEN** inline validation errors are displayed on the form
- **AND** the form is not submitted to the API

### Requirement: Update persona via PUT endpoint

The `PUT /api/personas/<slug>` endpoint SHALL accept JSON updates to name, description, and status fields. Role SHALL NOT be updatable. The endpoint SHALL validate that name is non-empty when provided.

#### Scenario: Successful update
- **WHEN** `PUT /api/personas/<slug>` is called with valid fields
- **THEN** the persona is updated and the response is 200 with the updated persona data

#### Scenario: Update with empty name
- **WHEN** `PUT /api/personas/<slug>` is called with an empty name
- **THEN** the response is 400 with a validation error

#### Scenario: Update persona not found
- **WHEN** `PUT /api/personas/<slug>` is called with a non-existent slug
- **THEN** the response is 404 with an error message

#### Scenario: Archive via status update
- **WHEN** `PUT /api/personas/<slug>` is called with `status: "archived"`
- **THEN** the persona's status is set to "archived" and the response is 200

### Requirement: Delete persona only when no agents linked

The `DELETE /api/personas/<slug>` endpoint SHALL remove a persona only if it has zero linked agents. If agents are linked, the endpoint SHALL return 409 with an error listing the linked agents.

#### Scenario: Delete with no linked agents
- **WHEN** `DELETE /api/personas/<slug>` is called for a persona with no linked agents
- **THEN** the persona is deleted and the response is 200

#### Scenario: Delete with linked agents
- **WHEN** `DELETE /api/personas/<slug>` is called for a persona with linked agents
- **THEN** the response is 409 with an error message indicating which agents are using it
- **AND** the persona is NOT deleted

#### Scenario: Delete persona not found
- **WHEN** `DELETE /api/personas/<slug>` is called with a non-existent slug
- **THEN** the response is 404 with an error message

### Requirement: Roles list endpoint

The `GET /api/roles` endpoint SHALL return a JSON array of all roles. Each role object SHALL include: id, name, description, and created_at. This powers the role dropdown in the create/edit modal.

#### Scenario: Roles exist
- **WHEN** `GET /api/roles` is called
- **THEN** the response is 200 with a JSON array of role objects

#### Scenario: No roles exist
- **WHEN** `GET /api/roles` is called and no roles exist
- **THEN** the response is 200 with an empty JSON array

### Requirement: Create/Edit modal follows existing patterns

The persona create and edit modals SHALL follow existing modal patterns (`_project_form_modal.html` styling: fixed position, backdrop blur, header/body/footer layout, z-index 200). The create modal SHALL have Name (required), Role dropdown (required, with "Create new role..." option), and Description (optional). The edit modal SHALL pre-populate fields and make Role read-only.

#### Scenario: Create modal validation
- **WHEN** the user clicks Save with empty required fields
- **THEN** inline error messages appear on the form fields
- **AND** the form is not submitted

#### Scenario: Edit modal role is read-only
- **WHEN** the edit modal is opened for a persona
- **THEN** the Role field displays the current role name but is not editable

### Requirement: Toast notifications for all CRUD operations

All CRUD operations (create, edit, archive, delete) SHALL display toast notifications on success or failure. Success toasts SHALL confirm the action taken. Failure toasts SHALL display the error message from the API.

#### Scenario: Successful operation
- **WHEN** a CRUD operation succeeds
- **THEN** a success toast notification is displayed

#### Scenario: Failed operation
- **WHEN** a CRUD operation fails
- **THEN** an error toast notification is displayed with the error message

### Requirement: Confirmation dialogs for destructive actions

Archive and delete actions SHALL require confirmation before execution. The delete confirmation SHALL state that the action is irreversible.

#### Scenario: Archive confirmation
- **WHEN** the user clicks Archive on a persona
- **THEN** a confirmation dialog appears before the archive action is executed

#### Scenario: Delete confirmation
- **WHEN** the user clicks Delete on a persona with no linked agents
- **THEN** a confirmation dialog appears stating the action is irreversible

