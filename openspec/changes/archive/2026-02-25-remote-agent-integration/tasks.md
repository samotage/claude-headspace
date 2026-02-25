## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Core Infrastructure

- [x] 2.1.1 Create session token service (`src/claude_headspace/services/session_token.py`) — generate, validate, and revoke cryptographically opaque per-agent tokens using `secrets.token_urlsafe`
- [x] 2.1.2 Create remote agent service (`src/claude_headspace/services/remote_agent_service.py`) — blocking agent creation with readiness polling (register + skill inject + prompt delivery), liveness check, shutdown orchestration
- [x] 2.1.3 Add `remote_agents` configuration section to `config.yaml` — CORS allowed origins, embed feature flag defaults, agent creation timeout (default 15s)

### 2.2 API Endpoints

- [x] 2.2.1 Create remote agents blueprint (`src/claude_headspace/routes/remote_agents.py`) with session token auth decorator
- [x] 2.2.2 Implement `POST /api/remote_agents/create` — validate inputs, call remote agent service, return agent_id/embed_url/session_token/metadata
- [x] 2.2.3 Implement `GET /api/remote_agents/<id>/alive` — session token auth, check agent liveness, return status
- [x] 2.2.4 Implement `POST /api/remote_agents/<id>/shutdown` — session token auth, call shutdown_agent, return confirmation
- [x] 2.2.5 Implement standardised error response helper — consistent JSON envelope with HTTP status, error code, message, retry guidance

### 2.3 Embed View

- [x] 2.3.1 Create embed chat template (`templates/embed/chat.html`) — minimal single-agent chat with no Headspace chrome, loading state, error state
- [x] 2.3.2 Create embed JavaScript (`static/embed/embed-app.js`) — chat controller, text input, message thread rendering, question/option UI
- [x] 2.3.3 Create embed SSE handler (`static/embed/embed-sse.js`) — SSE connection scoped to single agent, real-time turn/state updates
- [x] 2.3.4 Create embed CSS (`static/embed/embed.css`) — responsive styles optimised for iOS Safari iframe rendering
- [x] 2.3.5 Implement embed feature flags — conditional rendering of file upload, context usage, voice microphone based on create request or URL params
- [x] 2.3.6 Implement embed view route — serve chat.html with session token validation and agent scoping

### 2.4 App Integration

- [x] 2.4.1 Register remote agents blueprint in `app.py` — import, register, add to CSRF exemption prefixes
- [x] 2.4.2 Add CORS handling — apply CORS headers to remote agent endpoints and embed view based on config
- [x] 2.4.3 Initialise remote agent service in app factory — register in `app.extensions`

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for session token service — generation, validation, revocation, expiry, agent scoping
- [x] 3.2 Unit tests for remote agent service — blocking creation with readiness polling, timeout handling, liveness check, shutdown
- [x] 3.3 Route tests for remote agent endpoints — create, alive, shutdown, error responses, auth rejection
- [x] 3.4 Route tests for embed view — template rendering, token validation, feature flags, CORS headers
- [x] 3.5 Integration test — end-to-end create-embed-interact-shutdown flow (mocked tmux)

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification: create agent via API, load embed URL in iframe, verify chat works
- [x] 4.4 Verify existing voice bridge endpoints are unaffected
- [x] 4.5 Verify CORS headers work correctly for cross-origin iframe
