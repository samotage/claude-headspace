---
validation:
  status: pending
---

## Product Requirements Document (PRD) — API + SSE Endpoints

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 5 — `channels_api` blueprint, REST endpoints, and SSE event types
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The channel data model (S3) and ChannelService (S4) provide the persistence and business logic layers for inter-agent communication. This sprint exposes that functionality over HTTP by creating the `channels_api` Flask blueprint — a thin REST wrapper around ChannelService — and adds two new SSE event types (`channel_message` and `channel_update`) to the existing broadcaster stream.

The API follows the exact patterns already established by the `remote_agents` and `voice_bridge` blueprints: JSON request/response, standard HTTP status codes, error envelope `{error: {code, message, status}}`, and dual auth via dashboard session cookies or `Authorization: Bearer` session tokens. Channels are identified by slug in URLs, not integer IDs. All endpoints delegate to ChannelService — no business logic lives in routes.

The two new SSE event types are broadcast on the existing `/api/events/stream` endpoint. Dashboard JS (S7) will subscribe to these types and filter client-side by channel membership. No per-channel SSE streams are created — the single-stream-with-type-filtering pattern matches the existing architecture and respects the broadcaster's 100-connection limit.

All design decisions are resolved in the Inter-Agent Communication Workshop, Section 2.3 (Decision 2.3: API Endpoints). See `docs/workshop/interagent-communication/sections/section-2-channel-operations.md`.

---

## 1. Context & Purpose

### 1.1 Context

ChannelService (S4) encapsulates all channel business logic: creation, membership management, message sending, state transitions, and capability checks. The CLI (also S4) wraps that service for agent use. But the dashboard, remote agents, and embed widgets need HTTP access to the same operations.

The existing codebase already has two API surfaces that follow the same pattern this sprint needs: `remote_agents.py` (session token auth, error envelope, JSON responses) and `voice_bridge.py` (Bearer token auth, service delegation). The `channels_api` blueprint follows the same conventions — no new patterns are introduced.

The SSE broadcaster already supports arbitrary event types via `broadcast(event_type, data)`. Adding `channel_message` and `channel_update` requires no changes to the broadcaster itself — just new `broadcast()` calls from ChannelService when messages are posted or channel state changes.

### 1.2 Target User

Three consumers:

1. **Dashboard JS** — the operator views channels, members, and messages in the browser. Uses Flask session cookie auth.
2. **Remote agents / embed widgets** — external applications interact with channels via session token auth. Same endpoints, different auth mechanism.
3. **Dashboard SSE client** — receives real-time `channel_message` and `channel_update` events to update the UI without polling.

### 1.3 Success Moment

The operator opens the dashboard. A channel card shows its members and recent messages, all loaded via `GET /api/channels/<slug>` and `GET /api/channels/<slug>/messages`. A remote agent posts a message via `POST /api/channels/<slug>/messages` with a session token. The dashboard instantly receives a `channel_message` SSE event and renders the new message — no page refresh, no polling.

---

## 2. Scope

### 2.1 In Scope

- `channels_api` Flask blueprint registered at `/api/channels`
- Channel endpoints: POST create, GET list, GET detail, PATCH update, POST complete
- Membership endpoints: GET members, POST add, POST leave, POST mute, POST unmute, POST transfer-chair
- Message endpoints: GET history (cursor pagination by `sent_at`), POST send
- Dual authentication: Flask session cookie (dashboard) + existing session tokens (remote agents)
- Standard JSON response format with error envelope `{error: {code, message, status}}`
- Slug-based URLs (channels identified by slug, not integer ID)
- Two new SSE event types on existing `/api/events/stream`: `channel_message` and `channel_update`
- SSE event data schemas for both event types

### 2.2 Out of Scope

- ChannelService business logic (S4 — this sprint calls it, does not implement it)
- Channel data models / migrations (S3)
- Fan-out delivery engine (S6 — the API writes a message and returns 201; delivery to other members is async, handled by S6)
- Dashboard JS that consumes these endpoints (S7)
- Voice bridge channel routing and semantic picker matching (S8)
- Per-channel SSE streams (rejected — single stream with type filtering)
- Channel-specific rate limiting (deferred — existing rate limiters are sufficient)
- New auth mechanism (none needed — dashboard session + session tokens cover all access patterns)
- CORS configuration for channel endpoints (follows existing `remote_agents` CORS pattern if needed; no new CORS logic)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. All 12 endpoints (5 channel, 6 membership, 2 message — see FR table) return correct HTTP status codes and JSON response bodies
2. POST endpoints that create resources return 201; all others return 200
3. Invalid requests return the standard error envelope `{error: {code, message, status}}`
4. Dashboard session cookie auth grants access to all endpoints (operator identity derived from session)
5. Session token auth (`Authorization: Bearer <token>`) grants access to all endpoints (agent identity derived from token -> persona -> channel membership)
6. Channels are addressed by slug in all URL paths — no integer ID in URLs
7. `GET /api/channels/<slug>/messages` supports cursor pagination via `?before=<ISO>` and `?limit=N` query parameters
8. `POST /api/channels/<slug>/messages` writes a message to the database and returns the message JSON with 201 — fan-out delivery is not this sprint's concern
9. The `channel_message` SSE event is broadcast when a new message is posted to a channel
10. The `channel_update` SSE event is broadcast when channel state changes (member join/leave, status transition, chair transfer)
11. SSE events are broadcast on the existing `/api/events/stream` endpoint — no new SSE endpoint is created
12. Existing SSE `?types=` filter parameter works for the new event types (clients can subscribe to `channel_message` and/or `channel_update` selectively)

### 3.2 Non-Functional Success Criteria

1. No business logic in route handlers — all operations delegate to ChannelService
2. The blueprint follows existing conventions: Blueprint instantiation, `_error_response` helper, `require_session_token` decorator pattern
3. All existing SSE clients and event types are unaffected — the new types are additive
4. No new dependencies are introduced (no new packages, no new auth infrastructure)
5. Endpoints are testable with the existing `client` fixture and mock ChannelService

---

## 4. Functional Requirements (FRs)

### Channel Endpoints

**FR1: Create channel — `POST /api/channels`**
Accept a JSON body with `{name, channel_type, description?, intent_override?, organisation_slug?, project_slug?, members?: [persona_slug, ...]}`. Delegate to `ChannelService.create()`. Creator becomes chair. Return 201 with the channel JSON.

**FR2: List channels — `GET /api/channels`**
Return channels for the calling persona. Support query parameters: `?status=<status>`, `?type=<type>`, `?all=true` (operator only — all visible channels). Delegate to `ChannelService.list()`. Return 200 with an array.

**FR3: Get channel detail — `GET /api/channels/<slug>`**
Return channel details: name, type, status, description, intent, member count, message count, timestamps. Delegate to `ChannelService.get_detail()`. Return 200.

**FR4: Update channel — `PATCH /api/channels/<slug>`**
Accept `{description?, intent_override?}`. Chair or operator only. Delegate to `ChannelService.update()`. Return 200 with updated channel JSON.

**FR5: Complete channel — `POST /api/channels/<slug>/complete`**
Transition channel to `complete` state. Chair or operator only. Delegate to `ChannelService.complete()`. Return 200.

### Membership Endpoints

**FR6: List members — `GET /api/channels/<slug>/members`**
Return channel members with status (active/left/muted), chair designation, and online/offline indicator. Delegate to `ChannelService.list_members()`. Return 200 with an array.

**FR7: Add member — `POST /api/channels/<slug>/members`**
Accept `{persona_slug}`. If the persona has no running agent, Headspace spins one up asynchronously (same pattern as remote agent creation). Delegate to `ChannelService.add_member()`. Return 201.

**FR8: Leave channel — `POST /api/channels/<slug>/leave`**
Calling persona leaves the channel. Auto-complete if last active member leaves. Delegate to `ChannelService.leave()`. Return 200.

**FR9: Mute channel — `POST /api/channels/<slug>/mute`**
Pause delivery for the calling persona. Delegate to `ChannelService.mute()`. Return 200.

**FR10: Unmute channel — `POST /api/channels/<slug>/unmute`**
Resume delivery for the calling persona. Delegate to `ChannelService.unmute()`. Return 200.

**FR11: Transfer chair — `POST /api/channels/<slug>/transfer-chair`**
Accept `{persona_slug}`. Current chair only. Delegate to `ChannelService.transfer_chair()`. Return 200.

### Message Endpoints

**FR12: Get message history — `GET /api/channels/<slug>/messages`**
Return messages for the channel. Support query parameters: `?limit=50` (default), `?since=<ISO>`, `?before=<ISO>` (cursor pagination by `sent_at`). Delegate to `ChannelService.get_messages()`. Return 200 with an array.

**FR13: Send message — `POST /api/channels/<slug>/messages`**
Accept `{content, message_type?: "delegation"|"escalation"}`. Default type: `message`. The `system` type is not API-callable — it is service-generated only. Optional: `attachment_path`. Delegate to `ChannelService.send_message()`. Return 201 with the message JSON.

### SSE Event Types

**FR14: `channel_message` SSE event**
When a message is posted to a channel (via any frontend — API, CLI, voice bridge), broadcast a `channel_message` event on the existing `/api/events/stream`. Event data schema defined in Technical Context 6.5.

**FR15: `channel_update` SSE event**
When channel state changes (member join, member leave, status transition, chair transfer, mute/unmute), broadcast a `channel_update` event on the existing `/api/events/stream`. Event data schema defined in Technical Context 6.5.

### Authentication

**FR16: Dual auth support**
Every endpoint shall accept either: (a) a Flask session cookie (dashboard/operator), or (b) an `Authorization: Bearer <token>` header (remote agents/embed widgets). The route handler determines the caller's identity from whichever mechanism is present.

**FR17: No new auth mechanism**
No new authentication infrastructure is created. Session tokens already carry agent identity -> persona identity -> channel membership. ChannelService checks membership on every operation.

### Error Handling

**FR18: Standard error envelope**
All error responses shall use the envelope format: `{error: {code, message, status}}`. Machine-readable `code` values are documented in Technical Context 6.7.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Thin route layer**
Route handlers shall contain only: request parsing, auth resolution, ChannelService delegation, and response formatting. No channel business logic, no direct database queries, no state machine transitions.

**NFR2: Blueprint registration pattern**
The blueprint shall follow the existing pattern: `Blueprint("channels_api", __name__)`, registered in `app.py` alongside the other 26 blueprints. Service access via `current_app.extensions["channel_service"]`.

**NFR3: Slug-based URLs**
All channel-scoped endpoints use `<slug>` in the URL path, not `<int:id>`. Slugs are unique, human-readable, and consistent with the CLI interface.

**NFR4: No per-channel SSE streams**
The two new event types are broadcast on the existing single SSE stream. No new SSE endpoint is created. This avoids multiplying connections against the broadcaster's 100-connection limit.

**NFR5: Backward-compatible SSE**
Existing SSE clients that do not subscribe to `channel_message` or `channel_update` types are unaffected. The existing `?types=` filter parameter on `/api/events/stream` works for the new types without any changes to the SSE infrastructure.

**NFR6: Service registration**
The blueprint requires `channel_service` to be registered in `app.extensions` (done by S4). The blueprint does not initialise the service — it expects it to already exist.

---

## 6. Technical Context

### 6.1 Blueprint Structure

New file: `src/claude_headspace/routes/channels_api.py`

```python
from flask import Blueprint, current_app, jsonify, request

channels_api_bp = Blueprint("channels_api", __name__)
```

Registered in `app.py` alongside other blueprints:

```python
from claude_headspace.routes.channels_api import channels_api_bp
app.register_blueprint(channels_api_bp)
```

### 6.2 Endpoint Table — Complete Reference

#### Channel Endpoints

| Method | Path | Description | Success Code | Auth |
|--------|------|-------------|:---:|------|
| `POST` | `/api/channels` | Create a channel | 201 | Session / Token |
| `GET` | `/api/channels` | List channels for calling persona | 200 | Session / Token |
| `GET` | `/api/channels/<slug>` | Channel detail | 200 | Session / Token |
| `PATCH` | `/api/channels/<slug>` | Update channel (chair/operator) | 200 | Session / Token |
| `POST` | `/api/channels/<slug>/complete` | Complete channel (chair/operator) | 200 | Session / Token |

#### Membership Endpoints

| Method | Path | Description | Success Code | Auth |
|--------|------|-------------|:---:|------|
| `GET` | `/api/channels/<slug>/members` | List members | 200 | Session / Token |
| `POST` | `/api/channels/<slug>/members` | Add a persona to channel | 201 | Session / Token |
| `POST` | `/api/channels/<slug>/leave` | Calling persona leaves | 200 | Session / Token |
| `POST` | `/api/channels/<slug>/mute` | Mute delivery | 200 | Session / Token |
| `POST` | `/api/channels/<slug>/unmute` | Resume delivery | 200 | Session / Token |
| `POST` | `/api/channels/<slug>/transfer-chair` | Transfer chair role | 200 | Session / Token |

#### Message Endpoints

| Method | Path | Description | Success Code | Auth |
|--------|------|-------------|:---:|------|
| `GET` | `/api/channels/<slug>/messages` | Message history (cursor-paginated) | 200 | Session / Token |
| `POST` | `/api/channels/<slug>/messages` | Send a message | 201 | Session / Token |

### 6.3 Authentication Implementation

Two auth mechanisms, both already existing in the codebase:

**1. Dashboard session cookie** — Flask session set during login. The operator and dashboard JS use this. No changes needed. Caller identity: the operator (person-type persona, or system-level access).

**2. Session token** — `Authorization: Bearer <token>` header. Remote agents and embed widgets use this. The existing `SessionTokenService` (`src/claude_headspace/services/session_token.py`) validates tokens. Token maps to `agent_id` -> Agent record -> `persona_id` -> channel membership.

The route handler resolves caller identity with a helper function:

```python
def _resolve_caller():
    """Resolve the calling persona from session cookie or Bearer token.

    Returns (persona, agent) tuple. persona is always set;
    agent is set for token-authenticated callers, None for dashboard session.

    Raises 401 if neither auth mechanism provides a valid identity.
    """
    # Check Bearer token first
    token = _get_token_from_request()
    if token:
        token_service = current_app.extensions.get("session_token_service")
        if token_service:
            token_info = token_service.validate(token)
            if token_info:
                agent = Agent.query.get(token_info.agent_id)
                if agent and agent.persona:
                    return agent.persona, agent
        abort(401)

    # Fallback: dashboard session (operator)
    from ..models import Persona
    operator = Persona.get_operator()
    if operator:
        return operator, None  # No agent for operator
    abort(401)
```

The `require_session_token` decorator from `remote_agents.py` can be reused for token-only endpoints if needed, but channel endpoints support both auth mechanisms, so they use the `_resolve_caller()` helper instead.

### 6.4 Request/Response Format Examples

#### Create Channel — `POST /api/channels`

Request:
```json
{
  "name": "Persona Alignment Workshop",
  "channel_type": "workshop",
  "description": "Workshop for aligning persona skill files",
  "intent_override": null,
  "organisation_slug": "core-team",
  "project_slug": "claude-headspace",
  "members": ["architect-robbo-3", "con"]
}
```

Response (201):
```json
{
  "id": 7,
  "slug": "persona-alignment-workshop-7",
  "name": "Persona Alignment Workshop",
  "channel_type": "workshop",
  "status": "pending",
  "description": "Workshop for aligning persona skill files",
  "intent_override": null,
  "organisation_id": 2,
  "project_id": 1,
  "chair_persona_slug": "architect-robbo-3",
  "member_count": 2,
  "created_at": "2026-03-03T10:00:00Z",
  "completed_at": null,
  "archived_at": null
}
```

#### Send Message — `POST /api/channels/<slug>/messages`

Request:
```json
{
  "content": "The persona_id constraint is resolved.",
  "message_type": "message"
}
```

Response (201):
```json
{
  "id": 42,
  "channel_slug": "workshop-persona-alignment-7",
  "persona_slug": "architect-robbo-3",
  "persona_name": "Robbo",
  "agent_id": 1103,
  "content": "The persona_id constraint is resolved.",
  "message_type": "message",
  "metadata": null,
  "attachment_path": null,
  "source_turn_id": 5678,
  "source_command_id": 234,
  "sent_at": "2026-03-03T10:23:45Z"
}
```

#### List Messages — `GET /api/channels/<slug>/messages?limit=20&before=2026-03-03T10:23:45Z`

Response (200):
```json
[
  {
    "id": 41,
    "channel_slug": "workshop-persona-alignment-7",
    "persona_slug": "con",
    "persona_name": "Con",
    "agent_id": 1087,
    "content": "I disagree with the approach to skill file injection.",
    "message_type": "message",
    "metadata": null,
    "attachment_path": null,
    "source_turn_id": 5670,
    "source_command_id": 230,
    "sent_at": "2026-03-03T10:22:10Z"
  },
  {
    "id": 40,
    "channel_slug": "workshop-persona-alignment-7",
    "persona_slug": null,
    "persona_name": null,
    "agent_id": null,
    "content": "Con joined the channel.",
    "message_type": "system",
    "metadata": {"event": "member_joined", "persona_slug": "con"},
    "attachment_path": null,
    "source_turn_id": null,
    "source_command_id": null,
    "sent_at": "2026-03-03T10:20:00Z"
  }
]
```

#### Error Response

All errors follow this envelope:
```json
{
  "error": {
    "code": "not_a_member",
    "message": "You are not a member of #workshop-persona-alignment-7.",
    "status": 403
  }
}
```

### 6.5 SSE Event Data Schemas

Both event types are broadcast via the existing `broadcaster.broadcast(event_type, data)` method. The broadcaster adds `_eid` (event ID) to the data automatically. No changes to broadcaster code are needed.

#### `channel_message` Event

Broadcast when a new message is posted to a channel (via any frontend — API, CLI, voice bridge).

```json
{
  "channel_slug": "workshop-persona-alignment-7",
  "message_id": 42,
  "persona_slug": "architect-robbo-3",
  "persona_name": "Robbo",
  "content_preview": "The persona_id constraint is resolved.",
  "message_type": "message",
  "sent_at": "2026-03-03T10:23:45Z"
}
```

**Notes:**
- `content_preview` is the full message content for short messages; truncated for long messages (ChannelService determines truncation policy).
- System messages (joins, leaves, state changes) also produce `channel_message` events with `message_type: "system"`.

#### `channel_update` Event

Broadcast when channel state changes: member join/leave, status transition (pending -> active -> complete), chair transfer, mute/unmute.

```json
{
  "channel_slug": "workshop-persona-alignment-7",
  "update_type": "member_joined",
  "detail": {
    "persona_slug": "con",
    "persona_name": "Con"
  }
}
```

**`update_type` values:**

| `update_type` | Trigger | `detail` fields |
|---------------|---------|-----------------|
| `member_joined` | Persona added to channel | `persona_slug`, `persona_name` |
| `member_left` | Persona left channel | `persona_slug`, `persona_name` |
| `member_muted` | Persona muted channel | `persona_slug` |
| `member_unmuted` | Persona unmuted channel | `persona_slug` |
| `status_changed` | Channel status transition | `old_status`, `new_status` |
| `chair_transferred` | Chair role transferred | `from_persona_slug`, `to_persona_slug` |
| `channel_updated` | Description/intent changed | `fields_changed: [...]` |

### 6.6 SSE Integration — Where Broadcasts Are Triggered

The SSE broadcasts are triggered by ChannelService (S4) as post-commit side effects — not by the route handlers in this blueprint. ChannelService calls `broadcaster.broadcast()` after persisting Messages and after state-changing operations. The route handler's only responsibility is to parse the request, resolve the caller, call the service, and format the HTTP response.

This means the same SSE events fire regardless of which frontend initiated the action (API, CLI, voice bridge). One service, consistent broadcast behaviour.

```
API route -> ChannelService.send_message() -> DB write + broadcaster.broadcast("channel_message", ...)
CLI       -> ChannelService.send_message() -> DB write + broadcaster.broadcast("channel_message", ...)
Voice     -> ChannelService.send_message() -> DB write + broadcaster.broadcast("channel_message", ...)
```

The route handler's only responsibility is to parse the request, resolve the caller, call the service, and format the HTTP response.

### 6.7 Error Codes

Machine-readable `code` values returned in the error envelope:

| Code | HTTP Status | When |
|------|:-----------:|------|
| `missing_fields` | 400 | Required fields missing from request body |
| `invalid_field` | 400 | Field value fails validation (bad type, bad slug format, etc.) |
| `invalid_message_type` | 400 | `message_type` is not one of `message`, `delegation`, `escalation` |
| `unauthorized` | 401 | No valid auth (no session cookie, no Bearer token) |
| `invalid_session_token` | 401 | Bearer token is invalid or expired |
| `not_a_member` | 403 | Caller is not a member of the channel |
| `not_chair` | 403 | Operation requires chair role, caller is not chair |
| `no_creation_capability` | 403 | Caller's persona cannot create channels |
| `channel_not_found` | 404 | Channel slug does not match any channel |
| `persona_not_found` | 404 | Persona slug does not match any persona |
| `already_a_member` | 409 | Persona is already a member of the channel |
| `channel_not_active` | 409 | Operation requires active/pending channel, but channel is complete/archived |
| `agent_already_in_channel` | 409 | Agent's one-channel constraint violated |
| `service_unavailable` | 503 | ChannelService not registered in app.extensions |

### 6.8 Cursor Pagination — Message History

Messages are paginated by `sent_at` timestamp, not by offset. This avoids the inconsistencies of offset-based pagination when new messages arrive during browsing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max messages to return. Capped at 200. |
| `since` | ISO 8601 | — | Return messages sent after this timestamp (exclusive). |
| `before` | ISO 8601 | — | Return messages sent before this timestamp (exclusive). |

Messages are returned in chronological order (oldest first), matching the display order in the dashboard chat panel (S7) and CLI history (S4). The `before` parameter loads older messages: to paginate backward, pass the `sent_at` of the oldest message in the current page as `?before=`.

`since` and `before` can be combined for range queries, but the typical usage is `before` only (scrolling backward through history).

### 6.9 Architectural Notes

| Principle | Detail |
|-----------|--------|
| **One service, many frontends** | CLI, API, voice bridge, dashboard all call `ChannelService`. No logic in routes. |
| **Slug-based URLs** | Channels identified by slug in URLs, not integer IDs. Slugs are unique, human-readable, and match the CLI identifier. |
| **No channel-scoped SSE streams** | Single stream with type filtering. Scales better within the existing 100-connection limit. |
| **No new auth mechanism** | Dashboard session + existing session tokens cover all access patterns. |
| **Fire-and-forget message writes** | API writes message to DB and returns 201. Fan-out delivery to other channel members is async (S6). |
| **`system` messages not API-callable** | Same as CLI — `system` type is service-generated only (joins, leaves, state changes). API callers cannot post system messages. |
| **SSE broadcasts from service, not route** | Ensures consistent event emission regardless of which frontend triggered the action. |

### 6.10 Files to Create

| File | Purpose |
|------|---------|
| `src/claude_headspace/routes/channels_api.py` | `channels_api` Flask blueprint — all 13 endpoint handlers, `_resolve_caller()` helper, `_error_response()` helper. |

### 6.11 Files to Modify

| File | Change |
|------|--------|
| `src/claude_headspace/app.py` | Import and register `channels_api_bp`. |

### 6.12 No Changes Required

| File | Why |
|------|-----|
| `src/claude_headspace/services/broadcaster.py` | `broadcast()` already accepts arbitrary event type strings. `channel_message` and `channel_update` are just new type strings — no code change needed. |
| `src/claude_headspace/services/session_token.py` | Session token validation works as-is. Token -> agent_id -> persona -> channel membership. No changes needed. |
| `src/claude_headspace/routes/sse.py` | The SSE stream endpoint already supports `?types=` filtering. New event types work automatically. |

### 6.13 Existing Patterns to Follow

The building agent should reference these files for conventions:

- **`src/claude_headspace/routes/remote_agents.py`** — Blueprint instantiation, `_error_response()` helper, `_get_token_from_request()`, `require_session_token` decorator, JSON response formatting, CORS preflight handling.
- **`src/claude_headspace/routes/voice_bridge.py`** — Bearer token auth, service delegation pattern, request parsing.
- **`src/claude_headspace/services/broadcaster.py`** — `broadcast(event_type: str, data: dict)` method signature. No import changes; use `get_broadcaster()` to access the global instance.

### 6.14 Design Decisions (All Resolved — Workshop Section 2.3)

| Decision | Resolution | Source |
|----------|-----------|--------|
| API surface | Single `channels_api` blueprint, no separate remote agent channel API | 2.3 |
| Auth mechanisms | Dashboard session cookie + existing session tokens, no new auth | 2.3 |
| Channel identifier in URLs | Slug, not integer ID | 2.3 |
| SSE architecture | Two new event types on existing stream, no per-channel streams | 2.3 |
| Response format | Standard JSON, error envelope `{error: {code, message, status}}` | 2.3 |
| Rate limiting | None channel-specific — existing limiters sufficient | 2.3 |
| `system` message type | Not API-callable — service-generated only | 2.3 |
| Message pagination | Cursor-based by `sent_at`, not offset-based | 2.3 |
| Voice bridge routing | Out of scope for this sprint (S8) | 2.3 |

### 6.15 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ChannelService API surface doesn't match expected method signatures | Low | Medium | S4 PRD defines the service interface. If signatures differ, the route layer adapts (thin wrapper — easy to adjust). |
| Dashboard session auth doesn't cleanly resolve to a persona for channel operations | Medium | Low | The operator is a person-type persona (S2). If persona resolution isn't ready, the route can grant operator-level access without persona lookup as a fallback. |
| SSE event volume from busy channels overwhelms broadcaster queue | Low | Low | Broadcaster has per-client queue size (1000 events) and gap detection. Existing infrastructure handles bursts. Monitor in production. |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| Channel data model (Channel, ChannelMembership, Message) | E9-S3 | Database tables the endpoints read/write via ChannelService |
| ChannelService | E9-S4 | Business logic layer — all 13 endpoints delegate to service methods |
| PersonaType system | E9-S2 | Persona identity resolution for auth, capability checks |
| SSE Broadcaster | E1-S7 (done) | `broadcast()` method for SSE event emission — no changes needed |
| Session token service | E8-S5 (done) | Token validation for remote agent auth — no changes needed |
| Flask app factory / blueprint registration | Existing | `app.register_blueprint()` pattern |

S3 and S4 are hard dependencies. S2 is a soft dependency — the blueprint needs persona identity resolution, but could fall back to operator-level access if PersonaType isn't fully wired.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Section 2.3) |
