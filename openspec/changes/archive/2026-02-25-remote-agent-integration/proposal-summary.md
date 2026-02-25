# Remote Agent Integration — Proposal Summary

## Architecture Decisions

1. **Separate API namespace** — `/api/remote_agents/` is completely independent of `/api/voice/*`. No shared routes, no shared auth model, no shared response format. This prevents coupling between internal (voice bridge PWA) and external (third-party application) consumers.

2. **Blocking creation semantics** — Unlike the voice bridge's fire-and-forget `create_agent()` which returns immediately, the remote agent creation endpoint blocks until the agent is fully ready (registered in DB, persona skill injected, initial prompt delivered). This eliminates the need for the calling application to poll or listen for readiness events.

3. **Session token authentication** — Per-agent opaque tokens using `secrets.token_urlsafe()`. Tokens are stored in an in-memory dictionary keyed by token, mapping to agent_id and feature flags. No database migration required — tokens are scoped to the server process lifetime (agents created by remote API don't survive server restarts anyway, so tokens don't need to persist).

4. **Embed view as a stripped-down chat** — The embed view reuses the same conceptual patterns as the voice bridge chat (SSE-driven message thread, question/option rendering) but is a separate implementation with no Headspace chrome. It is a new template and JS module, not a conditional rendering of the voice bridge.

5. **CORS via manual headers** — Rather than adding a flask-cors dependency, CORS headers are applied in a `@remote_agents_bp.after_request` hook using the configured allowed origins from `config.yaml`. This keeps the dependency footprint minimal.

6. **No database migration** — Session tokens and feature flags are in-memory. The Agent model already has all fields needed (tmux_session, persona_id, etc.). No new models or columns required.

## Implementation Approach

The implementation follows the established Flask blueprint pattern used by all 22+ existing blueprints:

1. **Service layer first** — `session_token.py` (generate/validate/revoke tokens) and `remote_agent_service.py` (blocking creation with readiness polling, liveness, shutdown orchestration) are pure services with no Flask dependencies except `current_app` for config access.

2. **Route layer** — `remote_agents.py` blueprint handles HTTP concerns (request parsing, auth decoration, response formatting, CORS, error envelopes) and delegates to services.

3. **Embed view** — Separate template and static assets in `templates/embed/` and `static/embed/`, following the same separation pattern as `static/voice/`.

4. **App integration** — Blueprint registration, CSRF exemption, and service init follow the exact same patterns visible in `app.py` (register in `register_blueprints()`, add to `_CSRF_EXEMPT_PREFIXES`, init in `create_app()`).

### Blocking Creation Flow

```
POST /api/remote_agents/create
  -> Validate project_name, persona_slug
  -> Call create_agent(project_id, persona_slug) [existing service]
  -> Poll for agent readiness (loop with sleep):
       - Query Agent by tmux_session (returned by create_agent)
       - Check: agent exists in DB AND persona.prompt_injected_at is set
       - Timeout after configured seconds (default 15s)
  -> Send initial_prompt via tmux_bridge.send_text()
  -> Generate session token
  -> Return {agent_id, embed_url, session_token, metadata}
```

## Files to Modify

### New Files (Backend)

- `src/claude_headspace/services/session_token.py` — Token generation, validation, revocation, and in-memory storage
- `src/claude_headspace/services/remote_agent_service.py` — Blocking agent creation, readiness polling, initial prompt delivery, liveness check
- `src/claude_headspace/routes/remote_agents.py` — Blueprint with 4 routes: create, alive, shutdown, embed view

### New Files (Frontend)

- `templates/embed/chat.html` — Minimal Jinja2 template for iframe embedding
- `static/embed/embed-app.js` — Chat controller, message rendering, question/option UI
- `static/embed/embed-sse.js` — SSE connection scoped to single agent
- `static/embed/embed.css` — Responsive CSS for iOS Safari iframe

### Modified Files

- `src/claude_headspace/app.py` — Blueprint import/registration, CSRF exemption (`/api/remote_agents/`), service init
- `config.yaml` — New `remote_agents` section (allowed_origins, embed_defaults, creation_timeout)

### Test Files

- `tests/services/test_session_token.py` — Token service unit tests
- `tests/services/test_remote_agent_service.py` — Remote agent service unit tests (mocked tmux/db)
- `tests/routes/test_remote_agents.py` — Route tests for all endpoints
- `tests/integration/test_remote_agent_flow.py` — End-to-end flow test (mocked tmux)

## Acceptance Criteria

1. `POST /api/remote_agents/create` with valid project/persona/prompt returns 201 with agent_id, embed_url, session_token, and metadata within 15 seconds
2. `GET /api/remote_agents/<id>/alive` with valid token returns alive/not-alive status
3. `POST /api/remote_agents/<id>/shutdown` with valid token initiates graceful shutdown
4. Requests without valid session token return 401 with `invalid_token` or `missing_token`
5. Embed URL renders a chrome-free chat interface in an iframe
6. SSE updates flow in real-time to the embedded chat, scoped to the single agent
7. Feature flags (file_upload, context_usage, voice_mic) are absent from DOM when disabled
8. CORS headers are correctly applied for configured origins
9. All error responses use the standardised JSON envelope
10. Existing voice bridge endpoints (`/api/voice/*`) are completely unaffected
11. Creation timeout returns 408 with `agent_creation_timeout`
12. Embed view is responsive and functional in iOS Safari iframes

## Constraints and Gotchas

1. **Blocking request thread** — The create endpoint blocks the Flask request thread while polling for readiness. With Werkzeug's default threading, this limits concurrent creation requests. Acceptable for Phase 1 (single consumer, low concurrency) but documented for future scaling.

2. **Agent readiness detection** — The `create_agent()` function starts a tmux session asynchronously. Readiness must be detected by polling the database for the agent record (matched by tmux_session name). The hook pipeline (`session-start` hook -> `SessionCorrelator` -> `Agent` creation) has variable latency (typically 2-5 seconds).

3. **Initial prompt delivery timing** — The initial prompt must be sent AFTER the agent is fully ready (persona skill injected). Sending too early means the agent processes the prompt without persona context. The `prompt_injected_at` field on Agent is the reliable readiness signal.

4. **CSRF exemption** — The remote agents API must be CSRF-exempt because external applications cannot obtain CSRF tokens. The `_CSRF_EXEMPT_PREFIXES` list in `app.py` must include `/api/remote_agents/`.

5. **Session token lifetime** — Tokens live in-memory and are lost on server restart. This is acceptable because agents themselves don't survive restarts. The calling application handles this by creating a new agent.

6. **iOS Safari iframe quirks** — The embed view must handle: keyboard pushing content up (use `visualViewport` API), safe area insets, and potential issues with SSE connections in backgrounded iframes.

7. **CORS and TLS** — Allowed origins in config must include the full TLS origin (e.g., `https://hostname.tailnet.ts.net:port`). Mismatched origins silently fail in browsers.

## Git Change History

### Related Commits

- `3d543378` (2026-02-25) — Added the remote agent integration PRD
- `c18f6f5b` (2026-02-09) — Chat transcript UI restyle of voice bridge (reference implementation for chat rendering)
- `7a1f2b02` (2026-02-06) — CLI auto-setup tmux session for --bridge flag (agent creation patterns)

### OpenSpec History (Related Capabilities)

- `voice-bridge` spec — Server-side voice bridge API patterns (parallel, not modified)
- `voice-bridge-client` spec — Client-side voice chat patterns (reference for embed view)
- `agent-lifecycle` spec — Agent creation and shutdown (reused via service layer)
- `persona-registration` spec — Persona lookup and validation (reused)
- `sse` spec — SSE broadcasting infrastructure (reused with agent filtering)

### Patterns Detected

- Flask blueprint pattern with `register_blueprints()` in `app.py`
- Service injection via `app.extensions["service_name"]`
- CSRF exemption via `_CSRF_EXEMPT_PREFIXES`
- Voice bridge agent creation via `create_agent()` in `agent_lifecycle.py` (fire-and-forget pattern to extend with blocking wrapper)

## Q&A History

No clarifications were needed. The PRD is comprehensive and unambiguous.

## Dependencies

- **No new Python packages** — Uses stdlib (`secrets`, `time`, `threading`) and existing Flask infrastructure
- **No new npm packages** — Embed view uses vanilla JS following the voice bridge pattern
- **No database migrations** — Session tokens are in-memory; all needed Agent model fields exist
- **No external API changes** — Self-contained within Headspace

## Testing Strategy

### Unit Tests (Fast, Isolated)

- `test_session_token.py` — Token CRUD, validation, agent scoping, revocation
- `test_remote_agent_service.py` — Blocking creation logic, readiness polling, timeout handling, liveness check (mocked DB and tmux)

### Route Tests (Flask Test Client)

- `test_remote_agents.py` — All 4 endpoints, auth rejection, error envelopes, CORS headers, feature flags

### Integration Tests (Real DB)

- `test_remote_agent_flow.py` — Create -> check alive -> interact -> shutdown flow with mocked tmux but real PostgreSQL

### Not Covered (Out of Scope)

- E2E Playwright tests for iframe embedding (requires actual iframe and two-origin setup)
- Performance/load testing of concurrent creation requests
- iOS Safari physical device testing

## OpenSpec References

- Proposal: `openspec/changes/remote-agent-integration/proposal.md`
- Tasks: `openspec/changes/remote-agent-integration/tasks.md`
- Spec: `openspec/changes/remote-agent-integration/specs/remote-agents/spec.md`
