# Proposal Summary: e6-s1-voice-bridge-server

## Architecture Decisions
- Voice bridge is a separate Flask blueprint (`voice_bridge.py`) with its own `before_request` auth middleware — cleanly isolated from dashboard routes
- Turn model enhanced with 4 new columns (additive, no existing column changes) rather than a separate VoiceQuestion model — simpler, follows existing `tool_input` pattern
- Voice output formatting uses existing InferenceService + PromptRegistry (new prompts registered) — no new LLM infrastructure
- Token-based auth uses Bearer token in config.yaml, not session/cookie auth — stateless, suitable for API clients
- Rate limiting scoped per-token, using existing pattern from InferenceRateLimiter
- Network binding controlled via config.yaml `voice_bridge.network.bind_address` affecting `run.py`'s host parameter

## Implementation Approach
- **Additive-only model changes:** 4 new columns on Turn, backward compatible, no changes to existing columns or queries
- **Reuse existing respond flow:** Voice command endpoint delegates to the same tmux_bridge.send_text() and state transition logic already proven in `/api/respond/<agent_id>`
- **Blueprint isolation:** New `voice_bridge` blueprint with URL prefix `/api/voice/` — no changes to existing routes
- **Service registration:** `voice_formatter` and `voice_auth` registered in `app.extensions` following established pattern

## Files to Modify

### Models
- `src/claude_headspace/models/turn.py` — add `question_text`, `question_options`, `question_source_type`, `answered_by_turn_id` columns

### Migrations
- `migrations/versions/` — new migration for Turn column additions

### New Services
- `src/claude_headspace/services/voice_formatter.py` — LLM-powered voice output formatting (concise/normal/detailed)
- `src/claude_headspace/services/voice_auth.py` — token validation middleware, localhost bypass, access logging

### New Routes
- `src/claude_headspace/routes/voice_bridge.py` — 4 endpoints: command, sessions, output, question

### Modified Services
- `src/claude_headspace/services/hook_receiver.py` — populate new Turn columns (question_text, question_options, question_source_type) in `_handle_awaiting_input()`
- `src/claude_headspace/services/prompt_registry.py` — add voice formatting prompt templates

### Modified Routes
- `src/claude_headspace/routes/respond.py` — populate `answered_by_turn_id` on ANSWER turns

### App Factory
- `src/claude_headspace/app.py` — register voice_bridge blueprint, voice_formatter service, voice_auth service

### Configuration
- `src/claude_headspace/config.py` — add voice_bridge config defaults
- `config.yaml` — add voice_bridge section
- `run.py` — use voice_bridge.network.bind_address for host binding

## Acceptance Criteria
- Voice command submitted via API is delivered to correct agent and agent resumes
- Question turns store full question context (text, options, type) retrievable via API
- Answer turns link to the question they resolve
- Free-text questions (no AskUserQuestion) return full question text
- Voice output follows concise format: status line + key results + next action
- Voice API accessible from LAN with valid token
- Invalid/missing tokens rejected with 401
- Wrong-state requests return helpful voice-friendly errors
- API response latency < 500ms (non-LLM), < 2s (with LLM formatting)
- Token validation < 5ms per request

## Constraints and Gotchas
- **Turn.tool_input already exists** — new `question_options` column is separate from `tool_input` to avoid breaking existing consumers. `tool_input` continues to store the raw AskUserQuestion payload; `question_options` stores the normalized voice-friendly format
- **Respond route race condition** — the existing `_respond_pending_for_agent` guard must also apply to voice commands to prevent duplicate turn creation from hook overlap
- **Hook receiver dedup** — the notification dedup window (< 10s) for QUESTION turns already exists and should work for voice-created answers too
- **tmux_bridge stateless** — no service init needed; accessed directly as module functions
- **Config hot-reload** — voice_bridge config must participate in existing ConfigEditor reload mechanism
- **Network binding change** — changing bind_address requires server restart (not hot-reloadable), documented in config section

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/hook_lifecycle_bridge.py`, `src/claude_headspace/services/tmux_bridge.py`
- Tests: `tests/services/test_hook_lifecycle_bridge.py`, `tests/services/test_tmux_bridge.py`

### OpenSpec History
- e5-s1-input-bridge (2026-02-02) — CLI launcher + bridge flag
- e5-s4-tmux-bridge (2026-02-04) — tmux send-keys integration + commander availability
- e5-s8-cli-tmux-bridge (2026-02-06) — replaced claudec with tmux pane detection

### Implementation Patterns
- Typical structure: modules (services) + tests
- Blueprint registration: import in app.py, `app.register_blueprint(blueprint)`
- Service registration: `app.extensions["service_name"] = ServiceInstance(...)`
- Config access: `app.config["APP_CONFIG"].get("section", {}).get("key", default)`

## Q&A History
- No clarifications needed — PRD is clear and complete
- No gaps or conflicts detected during proposal review

## Dependencies
- No new pip packages required (uses existing Flask, SQLAlchemy, OpenRouter infrastructure)
- No external services beyond existing OpenRouter API
- Database migration required (additive columns only — safe to run on existing data)

## Testing Strategy
- **Unit tests:** Turn model columns, voice_auth token validation, voice_formatter output formatting
- **Route tests:** All 4 voice API endpoints (success, error, auth, edge cases)
- **Integration tests:** hook_receiver populating new columns, respond route setting answered_by_turn_id
- **Manual verification:** curl/httpie against running server from another terminal/device on LAN
- Test database: `claude_headspace_test` (enforced by `_force_test_database` fixture)

## OpenSpec References
- proposal.md: openspec/changes/e6-s1-voice-bridge-server/proposal.md
- tasks.md: openspec/changes/e6-s1-voice-bridge-server/tasks.md
- spec.md: openspec/changes/e6-s1-voice-bridge-server/specs/voice-bridge/spec.md
