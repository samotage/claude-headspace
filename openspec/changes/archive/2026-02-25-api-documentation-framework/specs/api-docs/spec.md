## ADDED Requirements

### Requirement: OpenAPI 3.1 Specification for Remote Agent API

The system SHALL serve an OpenAPI 3.1 specification file as a static asset that completely documents the remote agent API for machine consumption.

#### Scenario: Spec file served at stable URL

- **WHEN** a consumer sends `GET /static/api/remote-agents.yaml`
- **THEN** the response MUST be a valid OpenAPI 3.1 YAML document
- **AND** the response Content-Type MUST indicate YAML
- **AND** the document MUST validate against the OpenAPI 3.1 JSON Schema

#### Scenario: Spec documents all remote agent endpoints

- **WHEN** the spec is parsed
- **THEN** it MUST contain path definitions for:
  - `POST /api/remote_agents/create`
  - `GET /api/remote_agents/{agent_id}/alive`
  - `POST /api/remote_agents/{agent_id}/shutdown`
  - `GET /embed/{agent_id}`
- **AND** each path MUST include the correct HTTP method, parameters, request body (where applicable), and response schemas

#### Scenario: Spec includes reusable schema components

- **WHEN** the spec is parsed
- **THEN** `components/schemas` MUST define: CreateRequest, CreateResponse, AliveResponseAlive, AliveResponseNotAlive, ShutdownResponse, ErrorEnvelope
- **AND** endpoint request/response definitions MUST reference these components via `$ref`

#### Scenario: Spec includes authentication documentation

- **WHEN** the spec is parsed
- **THEN** `components/securitySchemes` MUST define the session token mechanism
- **AND** the description MUST explain: how a token is obtained (returned in create response), how it is sent (Authorization: Bearer header or token query param), that each token is scoped to a specific agent_id, and what happens when a token is invalid (401 response)

#### Scenario: Spec includes complete examples

- **WHEN** the spec is parsed
- **THEN** each endpoint MUST include at least one example for successful responses
- **AND** each endpoint MUST include at least one example for relevant error responses
- **AND** examples MUST use realistic values (not placeholder text)

#### Scenario: Spec documents error envelope

- **WHEN** the spec is parsed
- **THEN** the ErrorEnvelope schema MUST define: code (string), message (string), status (integer), retryable (boolean), retry_after_seconds (integer, nullable)
- **AND** each error code MUST be documented with its meaning and retryable status

#### Scenario: Spec uses relative paths

- **WHEN** the spec is parsed
- **THEN** the `servers` section MUST NOT contain hardcoded URLs
- **AND** a description MUST instruct consumers to supply the base URL of their target Claude Headspace instance

#### Scenario: Spec documents CORS behaviour

- **WHEN** the spec is parsed
- **THEN** the spec MUST document that CORS is supported with configurable allowed origins
- **AND** that OPTIONS preflight requests are handled on all API endpoints

### Requirement: External API Help Topic

The help system SHALL include a topic documenting the external API for human discoverability.

#### Scenario: Help topic accessible via help routes

- **WHEN** a user navigates to `/help/external-api`
- **THEN** the page MUST render the external API help content
- **AND** the topic MUST appear in `/api/help/topics` list

#### Scenario: Help topic cross-linked with spec

- **WHEN** the help topic is read
- **THEN** it MUST reference the spec URL (`/static/api/remote-agents.yaml`)
- **AND** the spec's `info.description` MUST reference the help topic URL (`/help/external-api`)

#### Scenario: Help topic documents directory convention

- **WHEN** the help topic is read
- **THEN** it MUST document the directory convention for API specs (`static/api/<api-name>.yaml`)
- **AND** explain how future external API specs should follow the same pattern

### Requirement: LLM-Optimised Descriptions

All schema fields and endpoint descriptions SHALL be written with LLM comprehension as the primary concern.

#### Scenario: Field descriptions are self-contained

- **WHEN** an LLM reads any field description in the spec
- **THEN** the description MUST be understandable without external context
- **AND** MUST avoid jargon that requires knowledge of Claude Headspace internals
- **AND** MUST use plain language suitable for automated parsing

#### Scenario: LLM can generate valid API calls from spec alone

- **WHEN** an LLM parses the spec without any supplementary documentation
- **THEN** it MUST have sufficient information to: construct a valid create request, authenticate subsequent requests using the returned token, check agent liveness, and initiate agent shutdown
