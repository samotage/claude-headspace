# channels-api Specification

## Purpose
REST API blueprint exposing ChannelService operations over HTTP and defining SSE event schemas for real-time channel updates. Provides the HTTP interface layer for dashboard, remote agents, and embed widgets to interact with channels.

## ADDED Requirements

### Requirement: Blueprint Registration
The `channels_api` blueprint SHALL be registered at `/api/channels` in the Flask app factory alongside the other 26 blueprints.

#### Scenario: Blueprint available
- **WHEN** the Flask app is created
- **THEN** routes under `/api/channels` are accessible

---

### Requirement: Dual Authentication (FR16, FR17)
Every endpoint SHALL accept either a Flask session cookie (dashboard/operator) or an `Authorization: Bearer <token>` header (remote agents/embed widgets). A `_resolve_caller()` helper SHALL resolve the caller's identity to a `(persona, agent)` tuple.

#### Scenario: Bearer token authentication
- **WHEN** a request includes `Authorization: Bearer <valid_token>`
- **THEN** the token is validated via `SessionTokenService`
- **AND** the caller is resolved to the agent's persona

#### Scenario: Session cookie authentication
- **WHEN** a request includes a Flask session cookie (no Bearer token)
- **THEN** the caller is resolved to the operator persona via `Persona.get_operator()`
- **AND** the agent is `None`

#### Scenario: No authentication
- **WHEN** a request has neither a valid Bearer token nor a session cookie
- **THEN** the endpoint returns 401 with error code `unauthorized`

---

### Requirement: Error Envelope (FR18)
All error responses SHALL use the envelope format: `{error: {code, message, status}}`.

#### Scenario: Standard error response
- **WHEN** any error occurs on a channels API endpoint
- **THEN** the response body matches `{"error": {"code": "<code>", "message": "<human-readable>", "status": <http_status>}}`

#### Scenario: ChannelService exception mapping
- **WHEN** a ChannelService exception is raised
- **THEN** it is mapped to the appropriate HTTP status code and error code:
  - `ChannelNotFoundError` -> 404, `channel_not_found`
  - `NotAMemberError` -> 403, `not_a_member`
  - `NotChairError` -> 403, `not_chair`
  - `ChannelClosedError` -> 409, `channel_not_active`
  - `AlreadyMemberError` -> 409, `already_a_member`
  - `NoCreationCapabilityError` -> 403, `no_creation_capability`
  - `AgentChannelConflictError` -> 409, `agent_already_in_channel`

---

### Requirement: Create Channel — `POST /api/channels` (FR1)
The endpoint SHALL accept a JSON body with `{name, channel_type, description?, intent_override?, organisation_slug?, project_slug?, members?: [persona_slug, ...]}`, delegate to `ChannelService.create_channel()`, and return 201 with channel JSON.

#### Scenario: Successful creation
- **WHEN** a POST to `/api/channels` includes valid `name` and `channel_type`
- **THEN** `ChannelService.create_channel()` is called with the resolved persona as creator
- **AND** the response is 201 with the channel JSON

#### Scenario: Missing required fields
- **WHEN** `name` or `channel_type` is missing
- **THEN** 400 is returned with error code `missing_fields`

#### Scenario: No creation capability
- **WHEN** the caller's persona cannot create channels
- **THEN** 403 is returned with error code `no_creation_capability`

---

### Requirement: List Channels — `GET /api/channels` (FR2)
The endpoint SHALL return channels for the calling persona and SHALL support `?status`, `?type`, `?all=true` query parameters. The `?all=true` flag SHALL be operator-only with silent fallback for non-operators.

#### Scenario: Member-scoped listing
- **WHEN** a GET to `/api/channels` is made without `?all=true`
- **THEN** only channels where the calling persona has active membership are returned

#### Scenario: Operator all-visible listing
- **WHEN** the operator persona requests `?all=true`
- **THEN** all non-archived channels are returned

#### Scenario: Non-operator all=true silent fallback
- **WHEN** a non-operator persona requests `?all=true`
- **THEN** the `?all=true` flag is silently ignored
- **AND** member-scoped results are returned (no 403)

---

### Requirement: Get Channel Detail — `GET /api/channels/<slug>` (FR3)
The endpoint SHALL return channel details by delegating to `ChannelService.get_channel()` and SHALL return 404 if the channel does not exist.

#### Scenario: Channel found
- **WHEN** a GET to `/api/channels/<slug>` matches an existing channel
- **THEN** 200 is returned with channel JSON including name, type, status, description, intent, member count, message count, timestamps

#### Scenario: Channel not found
- **WHEN** the slug does not match any channel
- **THEN** 404 is returned with error code `channel_not_found`

---

### Requirement: Update Channel — `PATCH /api/channels/<slug>` (FR4)
The endpoint SHALL accept `{description?, intent_override?}` and SHALL restrict updates to the chair or operator persona only.

#### Scenario: Successful update
- **WHEN** the chair or operator PATCHes with a new description
- **THEN** 200 is returned with the updated channel JSON

#### Scenario: Not chair
- **WHEN** a non-chair, non-operator persona attempts to update
- **THEN** 403 is returned with error code `not_chair`

---

### Requirement: Complete Channel — `POST /api/channels/<slug>/complete` (FR5)
The endpoint SHALL delegate to `ChannelService.complete_channel()` and SHALL restrict the operation to the chair or operator persona only.

#### Scenario: Successful completion
- **WHEN** the chair POSTs to `/api/channels/<slug>/complete`
- **THEN** 200 is returned with the updated channel JSON (status: complete)

---

### Requirement: Archive Channel — `POST /api/channels/<slug>/archive` (FR5a)
The endpoint SHALL delegate to `ChannelService.archive_channel()` and SHALL restrict the operation to the chair or operator persona only. The channel MUST be in `complete` state.

#### Scenario: Successful archive
- **WHEN** the chair POSTs to `/api/channels/<slug>/archive` on a complete channel
- **THEN** 200 is returned with the updated channel JSON (status: archived)

#### Scenario: Channel not complete
- **WHEN** the channel is not in `complete` state
- **THEN** 409 is returned with error code `channel_not_active`

---

### Requirement: List Members — `GET /api/channels/<slug>/members` (FR6)
The endpoint SHALL return channel members with status, chair designation, and online/offline indicator by delegating to `ChannelService.list_members()`.

#### Scenario: Members listed
- **WHEN** a GET to `/api/channels/<slug>/members` is made
- **THEN** 200 is returned with an array of member objects

---

### Requirement: Add Member — `POST /api/channels/<slug>/members` (FR7)
The endpoint SHALL accept `{persona_slug}` and SHALL delegate to `ChannelService.add_member()` to add the persona to the channel.

#### Scenario: Successful add
- **WHEN** a POST to `/api/channels/<slug>/members` includes a valid `persona_slug`
- **THEN** 201 is returned with the membership JSON

#### Scenario: Already a member
- **WHEN** the persona is already a member
- **THEN** 409 is returned with error code `already_a_member`

---

### Requirement: Leave Channel — `POST /api/channels/<slug>/leave` (FR8)
The endpoint SHALL delegate to `ChannelService.leave_channel()` to remove the calling persona from the channel.

#### Scenario: Successful leave
- **WHEN** a member POSTs to `/api/channels/<slug>/leave`
- **THEN** 200 is returned

---

### Requirement: Mute Channel — `POST /api/channels/<slug>/mute` (FR9)
The endpoint SHALL delegate to `ChannelService.mute_channel()` to pause delivery for the calling persona.

#### Scenario: Successful mute
- **WHEN** a member POSTs to `/api/channels/<slug>/mute`
- **THEN** 200 is returned

---

### Requirement: Unmute Channel — `POST /api/channels/<slug>/unmute` (FR10)
The endpoint SHALL delegate to `ChannelService.unmute_channel()` to resume delivery for the calling persona.

#### Scenario: Successful unmute
- **WHEN** a muted member POSTs to `/api/channels/<slug>/unmute`
- **THEN** 200 is returned

---

### Requirement: Transfer Chair — `POST /api/channels/<slug>/transfer-chair` (FR11)
The endpoint SHALL accept `{persona_slug}` and SHALL delegate to `ChannelService.transfer_chair()`. Only the current chair SHALL be permitted to transfer.

#### Scenario: Successful transfer
- **WHEN** the current chair POSTs with a valid `persona_slug`
- **THEN** 200 is returned

#### Scenario: Not chair
- **WHEN** a non-chair persona attempts transfer
- **THEN** 403 is returned with error code `not_chair`

---

### Requirement: Get Message History — `GET /api/channels/<slug>/messages` (FR12)
The endpoint SHALL support cursor pagination via `?limit`, `?since`, `?before` query parameters and SHALL delegate to `ChannelService.get_history()`.

#### Scenario: History returned
- **WHEN** a GET to `/api/channels/<slug>/messages` is made
- **THEN** 200 is returned with messages in chronological order (oldest first)

#### Scenario: Cursor pagination
- **WHEN** `?before=<ISO>` is provided
- **THEN** only messages sent before that timestamp are returned

#### Scenario: Limit capping
- **WHEN** `?limit=N` is provided with N > 200
- **THEN** the limit is capped at 200

---

### Requirement: Send Message — `POST /api/channels/<slug>/messages` (FR13)
The endpoint SHALL accept `{content, message_type?}` and SHALL delegate to `ChannelService.send_message()`. The `system` message type SHALL NOT be API-callable. Default type SHALL be `message`.

#### Scenario: Successful send
- **WHEN** a POST to `/api/channels/<slug>/messages` includes valid `content`
- **THEN** 201 is returned with the message JSON

#### Scenario: System type rejected
- **WHEN** `message_type` is `system`
- **THEN** 400 is returned with error code `invalid_message_type`

#### Scenario: Invalid message type
- **WHEN** `message_type` is not one of `message`, `delegation`, `escalation`
- **THEN** 400 is returned with error code `invalid_message_type`

---

### Requirement: `channel_message` SSE Event (FR14)
When a message is posted to a channel (via any frontend), a `channel_message` event SHALL be broadcast on the existing `/api/events/stream`.

#### Scenario: Message broadcast
- **WHEN** a message is successfully persisted by ChannelService
- **THEN** ChannelService broadcasts a `channel_message` event with: `channel_slug`, `message_id`, `persona_slug`, `persona_name`, `content_preview`, `message_type`, `sent_at`

**Note:** This broadcast is triggered by ChannelService (S4), not by the route handler. The route's responsibility is only HTTP request/response.

---

### Requirement: `channel_update` SSE Event (FR15)
When channel state changes, a `channel_update` event SHALL be broadcast on the existing `/api/events/stream`.

#### Scenario: State change broadcast
- **WHEN** a channel state change occurs (member join/leave, status transition, chair transfer, mute/unmute)
- **THEN** ChannelService broadcasts a `channel_update` event with: `channel_slug`, `update_type`, `detail`

**`update_type` values:** `member_joined`, `member_left`, `member_muted`, `member_unmuted`, `status_changed`, `chair_transferred`, `channel_updated`

**Note:** This broadcast is triggered by ChannelService (S4), not by the route handler.

---

### Requirement: Slug-Based URLs (NFR3)
All channel-scoped endpoints SHALL use `<slug>` in the URL path, not `<int:id>`.

#### Scenario: Slug in URL
- **WHEN** a channel endpoint URL is constructed
- **THEN** the channel identifier is the slug (e.g., `/api/channels/workshop-persona-alignment-7`)

---

### Requirement: Thin Route Layer (NFR1)
Route handlers SHALL contain only request parsing, auth resolution, ChannelService delegation, and response formatting. No channel business logic, no direct database queries, no state machine transitions.

#### Scenario: No business logic in routes
- **WHEN** a channel operation is requested via the API
- **THEN** the route handler delegates to `ChannelService` for all logic
- **AND** the handler only parses the request, resolves the caller, calls the service, and formats the response

---

### Requirement: Service Unavailable Handling (NFR6)
If `channel_service` is not registered in `app.extensions`, endpoints SHALL return 503.

#### Scenario: Service not available
- **WHEN** `current_app.extensions.get("channel_service")` returns None
- **THEN** 503 is returned with error code `service_unavailable`

---

### Requirement: No New SSE Endpoint (NFR4)
The two new event types SHALL be broadcast on the existing single SSE stream. No new SSE endpoint is created.

#### Scenario: Existing stream carries new events
- **WHEN** a `channel_message` or `channel_update` event is broadcast
- **THEN** it appears on `/api/events/stream` alongside existing event types

---

### Requirement: Backward-Compatible SSE (NFR5)
Existing SSE clients that do not subscribe to `channel_message` or `channel_update` types SHALL be unaffected. The `?types=` filter works for the new types without changes.

#### Scenario: Existing client unaffected
- **WHEN** an existing SSE client subscribes to `state_transition` only
- **AND** a `channel_message` event is broadcast
- **THEN** the client does NOT receive the `channel_message` event
