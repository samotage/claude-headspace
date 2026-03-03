# Proposal Summary: e9-s5-api-sse-endpoints

## Architecture Decisions
- Single `channels_api` blueprint at `/api/channels` — follows existing `remote_agents` and `voice_bridge` blueprint conventions exactly
- Dual authentication via `_resolve_caller()` helper: Flask session cookie (dashboard operator) or Bearer token (remote agents/embed widgets) — no new auth infrastructure
- Thin route layer: all 14 endpoint handlers delegate to ChannelService — zero business logic in routes
- Slug-based URLs throughout (`/api/channels/<slug>`) — consistent with CLI interface, human-readable
- ChannelService exceptions mapped to standard error envelope `{error: {code, message, status}}` — 7 exception types to 7 error codes
- SSE events (`channel_message`, `channel_update`) broadcast by ChannelService, NOT by route handlers — ensures consistent events regardless of frontend (API, CLI, voice bridge)
- No new SSE endpoint — two new event types on existing `/api/events/stream`, respecting 100-connection limit
- `?all=true` on list endpoint: operator-only with silent fallback for non-operators (no 403, just ignores the flag)
- `system` message type not API-callable — prevents external callers from posting system-level messages
- Cursor pagination by `sent_at` timestamp for message history — avoids offset-based inconsistencies

## Implementation Approach
- Create 1 new file: `channels_api.py` (routes)
- Modify 1 existing file: `app.py` (blueprint registration)
- No changes to: broadcaster.py, session_token.py, sse.py — existing infrastructure supports the new event types and auth patterns
- Route handler pattern: parse request -> `_resolve_caller()` -> `ChannelService.method()` -> format JSON response -> handle exceptions with `_error_response()`
- Reuse `_get_token_from_request()` pattern from `remote_agents.py` for Bearer token extraction

## Files to Modify

### New Files
- `src/claude_headspace/routes/channels_api.py` — `channels_api` Flask blueprint with 14 endpoint handlers, `_resolve_caller()` helper, `_error_response()` helper, `_get_token_from_request()` helper

### Modified Files
- `src/claude_headspace/app.py` — Import and register `channels_api_bp` alongside other blueprints

### Test Files (New)
- `tests/routes/test_channels_api.py` — Route tests for all 14 endpoints, auth tests, error handling tests (~30 test functions)

## Acceptance Criteria
1. `POST /api/channels` creates a channel via ChannelService and returns 201 with channel JSON
2. `GET /api/channels` returns member-scoped channels; `?all=true` returns all non-archived (operator only, silent fallback for others)
3. `GET /api/channels/<slug>` returns channel detail with member/message counts
4. `PATCH /api/channels/<slug>` updates description/intent_override (chair/operator only)
5. `POST /api/channels/<slug>/complete` transitions to complete (chair/operator only)
6. `POST /api/channels/<slug>/archive` transitions to archived (chair/operator only, must be complete)
7. `GET /api/channels/<slug>/members` returns member array with status and chair designation
8. `POST /api/channels/<slug>/members` adds a persona to the channel (201)
9. `POST /api/channels/<slug>/leave` removes the caller from the channel
10. `POST /api/channels/<slug>/mute` and `/unmute` toggle delivery pause
11. `POST /api/channels/<slug>/transfer-chair` transfers chair role (chair only)
12. `GET /api/channels/<slug>/messages` returns cursor-paginated history (oldest first)
13. `POST /api/channels/<slug>/messages` creates a message (201), rejects `system` type (400)
14. Bearer token auth and session cookie auth both work on all endpoints
15. All errors use `{error: {code, message, status}}` envelope
16. ChannelService SSE broadcasts (`channel_message`, `channel_update`) work on existing `/api/events/stream`

## Constraints and Gotchas
- ChannelService must be registered as `app.extensions["channel_service"]` before blueprint routes can function — returns 503 if missing
- `_resolve_caller()` depends on `SessionTokenService` for Bearer auth and `Persona.get_operator()` for session auth
- Bearer token -> agent -> persona chain: if the agent has no persona, auth fails (401)
- Message `limit` query param capped at 200 — prevents unbounded queries
- Channel serialization to JSON needs to handle `datetime` objects (ISO 8601 format)
- Operator check for `?all=true` uses `Persona.get_operator()` comparison — silent fallback, not 403
- FR14/FR15 (SSE events) are already implemented in ChannelService (S4) — this sprint just documents the event schemas

## Git Change History

### Related Files
- `src/claude_headspace/services/channel_service.py` — ChannelService class (S4, already exists)
- `src/claude_headspace/services/session_token.py` — Session token validation (already exists)
- `src/claude_headspace/routes/remote_agents.py` — Pattern reference for error envelope and auth helpers
- `src/claude_headspace/routes/voice_bridge.py` — Pattern reference for Bearer token auth
- `src/claude_headspace/services/broadcaster.py` — SSE broadcaster (already exists, no changes)

### OpenSpec History
- `e9-s4-channel-service-cli` (archived) — Created ChannelService with all business logic methods
- `e9-s3-channel-data-model` (archived) — Created Channel, ChannelMembership, Message models
- `e9-s2-persona-type-system` (archived) — Added PersonaType and channel capabilities

### Implementation Patterns
- Blueprint: Follow `remote_agents.py` pattern (Blueprint instantiation, error helper, auth helpers)
- Auth: Follow dual auth pattern — Bearer token checked first, session cookie fallback
- Error handling: Follow `remote_agents.py` error envelope pattern
- Service access: `current_app.extensions["channel_service"]`
- Response format: `jsonify()` with appropriate HTTP status codes

## Q&A History
- No clarifications needed — all design decisions resolved in Workshop Section 2.3

## Dependencies

### Internal Dependencies (Already Implemented)
- ChannelService (S4) — all business logic
- Channel, ChannelMembership, Message models (S3)
- PersonaType and channel capabilities (S2)
- SessionTokenService (E8-S5) — Bearer token validation
- SSE Broadcaster (E1-S7) — event broadcasting
- Persona model with `get_operator()` (E8)

### No External Dependencies
- No new pip packages required
- No new npm packages required

## Testing Strategy

### Route Tests
- All 14 endpoints: success cases, error cases, edge cases
- Auth: Bearer token, session cookie, no auth, invalid token
- Error envelope format verification
- Service exception -> HTTP error code mapping
- Query parameter handling (pagination, filters)

## OpenSpec References
- proposal.md: openspec/changes/e9-s5-api-sse-endpoints/proposal.md
- tasks.md: openspec/changes/e9-s5-api-sse-endpoints/tasks.md
- specs:
  - openspec/changes/e9-s5-api-sse-endpoints/specs/channels-api/spec.md
