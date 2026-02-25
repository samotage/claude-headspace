# remote-agents Specification

## Purpose
TBD - created by archiving change remote-agent-integration. Update Purpose after archive.
## Requirements
### Requirement: Remote Agent Creation

The system SHALL provide a `POST /api/remote_agents/create` endpoint that creates a fully ready agent and returns all information the calling application needs.

#### Scenario: Successful agent creation

- **WHEN** a POST to `/api/remote_agents/create` includes valid `project_name`, `persona_slug`, and `initial_prompt`
- **THEN** the endpoint SHALL block until the agent is registered in the database, persona skill injected, and initial prompt delivered
- **AND** the response SHALL include `agent_id`, `embed_url`, `session_token`, `project_name`, `persona_slug`, `tmux_session_name`, and `status: "ready"`

#### Scenario: Agent creation timeout

- **WHEN** the agent fails to become ready within the configured timeout (default 15 seconds)
- **THEN** the endpoint SHALL return HTTP 408 with error code `agent_creation_timeout`
- **AND** the error envelope SHALL include `retryable: true`

#### Scenario: Project not found

- **WHEN** the specified `project_name` does not match any registered project
- **THEN** the endpoint SHALL return HTTP 404 with error code `project_not_found`

#### Scenario: Persona not found

- **WHEN** the specified `persona_slug` does not match any active persona
- **THEN** the endpoint SHALL return HTTP 404 with error code `persona_not_found`

---

### Requirement: Agent Liveness Check

The system SHALL provide a `GET /api/remote_agents/<id>/alive` endpoint for idempotent agent reuse.

#### Scenario: Agent is alive

- **WHEN** a GET to `/api/remote_agents/<id>/alive` is made with a valid session token
- **AND** the agent is still active (not ended)
- **THEN** the response SHALL include `alive: true` and the agent's current state

#### Scenario: Agent is not alive

- **WHEN** a GET to `/api/remote_agents/<id>/alive` is made with a valid session token
- **AND** the agent has ended or is not found
- **THEN** the response SHALL include `alive: false`

#### Scenario: Invalid session token

- **WHEN** a request is made without a valid session token
- **THEN** the endpoint SHALL return HTTP 401 with error code `invalid_token`

---

### Requirement: Agent Shutdown

The system SHALL provide a `POST /api/remote_agents/<id>/shutdown` endpoint for graceful agent termination.

#### Scenario: Successful shutdown

- **WHEN** a POST to `/api/remote_agents/<id>/shutdown` is made with a valid session token
- **THEN** the endpoint SHALL initiate graceful agent shutdown
- **AND** the response SHALL confirm the shutdown was initiated

#### Scenario: Agent already ended

- **WHEN** the target agent has already ended
- **THEN** the response SHALL indicate the agent is already terminated

---

### Requirement: Session Token Authentication

The system SHALL generate cryptographically opaque session tokens scoped to individual agents.

#### Scenario: Token generation on create

- **WHEN** an agent is successfully created via `/api/remote_agents/create`
- **THEN** a unique opaque session token SHALL be generated
- **AND** the token SHALL be returned in the create response

#### Scenario: Token validation

- **WHEN** a request to a remote agent endpoint includes a session token
- **THEN** the system SHALL validate the token against the specific agent
- **AND** SHALL reject tokens that don't match the requested agent

#### Scenario: Token does not leak internal state

- **WHEN** a session token is generated
- **THEN** the token MUST NOT encode agent IDs, database keys, or infrastructure details in a decodable format

---

### Requirement: Scoped Embed View

The system SHALL provide a scoped embed view for iframe embedding of a single-agent chat interface.

#### Scenario: Embed view renders without chrome

- **WHEN** the embed URL is loaded in an iframe
- **THEN** the view SHALL render a chat interface with text input, message thread, and question/option rendering
- **AND** SHALL NOT include any Headspace chrome: no header, no session list, no navigation, no dashboard links

#### Scenario: Embed view authenticates via token

- **WHEN** the embed URL is accessed
- **THEN** the session token in the URL SHALL be validated
- **AND** the view SHALL be scoped to the single agent associated with the token

#### Scenario: Real-time updates via SSE

- **WHEN** the embed view is active
- **THEN** an SSE connection SHALL be maintained, scoped to the single agent
- **AND** agent responses, state transitions, and question events SHALL flow in real-time

---

### Requirement: Embed Feature Flags

The system SHALL support feature flags controlling optional embed view capabilities.

#### Scenario: Default feature flags (all disabled)

- **WHEN** no feature flags are specified on create or embed URL
- **THEN** file upload, context usage display, and voice microphone SHALL be absent from the DOM

#### Scenario: Feature flags enabled via create request

- **WHEN** feature flags are specified in the create request
- **THEN** the corresponding UI elements SHALL be present in the embed view for the agent's lifetime

#### Scenario: Feature flags enabled via URL parameters

- **WHEN** feature flags are specified as URL parameters on the embed URL
- **THEN** the corresponding UI elements SHALL be present in the embed view

---

### Requirement: CORS Configuration

The system SHALL support configurable CORS for cross-origin iframe embedding.

#### Scenario: Request from allowed origin

- **WHEN** a request originates from a configured allowed origin
- **THEN** appropriate CORS headers SHALL be included in the response
- **AND** the iframe SHALL be able to load and interact with the embed view

#### Scenario: Request from disallowed origin

- **WHEN** a request originates from an origin not in the allowed list
- **THEN** CORS headers SHALL NOT include the requesting origin
- **AND** the browser SHALL block cross-origin access

---

### Requirement: Standardised Error Responses

All remote agent endpoints SHALL return errors in a consistent JSON envelope.

#### Scenario: Error response format

- **WHEN** any error occurs on a remote agent endpoint
- **THEN** the response SHALL include: `status` (HTTP status code), `error_code` (machine-readable), `message` (human-readable), and `retryable` (boolean with optional `retry_after_seconds`)

#### Scenario: Specific error codes

- **WHEN** specific error conditions occur
- **THEN** the following error codes SHALL be used:
  - `project_not_found` (404)
  - `persona_not_found` (404)
  - `agent_not_found` (404)
  - `agent_creation_timeout` (408)
  - `invalid_token` (401)
  - `missing_token` (401)
  - `server_error` (500)
  - `service_unavailable` (503)

---

### Requirement: Configuration

The system SHALL provide configuration entries for the remote agent integration.

#### Scenario: Default configuration

- **WHEN** no remote_agents configuration is specified
- **THEN** the system SHALL use defaults: empty allowed origins, all embed features disabled, 15-second creation timeout

#### Scenario: Custom configuration

- **WHEN** `remote_agents` section is present in `config.yaml`
- **THEN** the system SHALL use the configured values for CORS origins, feature flag defaults, and creation timeout

