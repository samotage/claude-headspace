# Proposal: e9-s5-api-sse-endpoints

## Why

ChannelService (S4) encapsulates all channel business logic but is only accessible via CLI. The dashboard, remote agents, and embed widgets need HTTP access to the same operations. Without an API layer, the dashboard cannot display channels or messages, and remote agents cannot participate in inter-agent communication programmatically. This sprint creates the `channels_api` Flask blueprint — a thin REST wrapper around ChannelService — and adds two new SSE event types for real-time channel updates.

## What Changes

- Create `channels_api` Flask blueprint registered at `/api/channels` — 14 endpoint handlers covering channel CRUD (6), membership management (6), and messages (2)
- Implement dual authentication: Flask session cookie (dashboard) + `Authorization: Bearer` session token (remote agents/embed widgets)
- Add `_resolve_caller()` helper for persona identity resolution from either auth mechanism
- Add `_error_response()` helper following the same error envelope pattern as `remote_agents.py`
- SSE: Two new event types (`channel_message`, `channel_update`) broadcast by ChannelService (S4) on the existing `/api/events/stream` — no broadcaster changes needed, no new SSE endpoints
- Register the blueprint in `app.py`

## Impact

### Affected specs
- `channel-service` — existing spec (S4). This change wraps its public methods in HTTP endpoints. No service changes required — all business logic stays in the service.
- `sse` — existing spec. Two new event type strings are added. No changes to broadcaster code — `broadcast()` already accepts arbitrary type strings.
- `remote-agents` — existing spec. Auth helpers (`_get_token_from_request`, session token validation) are reused. No changes to remote_agents code.

### Affected code

**New files:**
- `src/claude_headspace/routes/channels_api.py` — `channels_api` Flask blueprint with 14 endpoint handlers, `_resolve_caller()` helper, `_error_response()` helper

**Modified files:**
- `src/claude_headspace/app.py` — Import and register `channels_api_bp`

### Breaking changes
None — this is additive. All new endpoints, no existing behaviour modified. Existing SSE clients unaffected — new event types are additive.
