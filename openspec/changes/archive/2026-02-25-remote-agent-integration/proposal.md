## Why

External applications (first consumer: May Belle) need to create purpose-built agents, embed a chat interface via iframe, and manage agent lifecycle through a clean API contract. The existing voice bridge endpoints are tightly coupled to the PWA interaction model and cannot serve external consumers without breaking existing functionality.

## What Changes

- **New `remote_agents` blueprint** (`/api/remote_agents/`) — completely independent API namespace for external agent integration
- **Blocking agent creation endpoint** — `POST /api/remote_agents/create` accepts project name, persona slug, and initial prompt; blocks until agent is fully ready (registered, skill-injected, prompt delivered); returns agent_id, embed_url, session_token, and metadata
- **Agent liveness check** — `GET /api/remote_agents/<id>/alive` for idempotent reuse on page refresh
- **Agent shutdown** — `POST /api/remote_agents/<id>/shutdown` for graceful termination
- **Session token authentication** — cryptographically opaque per-agent token for API calls and iframe access
- **Scoped embed view** — minimal single-agent chat interface for iframe embedding: text input, message thread, question/option rendering, real-time SSE updates; no Headspace chrome
- **Embed feature flags** — file upload, context usage, voice microphone independently controllable (all off by default)
- **CORS configuration** — configurable allowed origins in `config.yaml` for cross-origin iframe embedding over TLS
- **Standardised error envelope** — consistent JSON error format across all remote agent endpoints with HTTP status codes, error codes, and retry guidance
- **Configuration entries** — `remote_agents` section in `config.yaml` for CORS origins, feature flag defaults, creation timeout

## Impact

- Affected specs: agent-lifecycle (reuses `create_agent`/`shutdown_agent`), voice-bridge (parallel but independent), sse (filtered event streams), persona-registration (persona lookup), tmux-bridge (prompt delivery)
- Affected code:
  - **New files:** `src/claude_headspace/routes/remote_agents.py`, `src/claude_headspace/services/remote_agent_service.py`, `src/claude_headspace/services/session_token.py`, `templates/embed/chat.html`, `static/embed/embed-app.js`, `static/embed/embed-sse.js`, `static/embed/embed.css`
  - **Modified files:** `src/claude_headspace/app.py` (blueprint registration, CSRF exemption, CORS), `config.yaml` (remote_agents section)
  - **Test files:** `tests/routes/test_remote_agents.py`, `tests/services/test_remote_agent_service.py`, `tests/services/test_session_token.py`
- No changes to existing voice bridge endpoints (`/api/voice/*`)
- No database migrations required (session tokens are in-memory, scoped to agent lifetime)
