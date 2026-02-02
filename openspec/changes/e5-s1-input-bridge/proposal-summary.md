# Proposal Summary: e5-s1-input-bridge

## Architecture Decisions
- Follow the existing **service + route + client JS** pattern established by `iterm_focus.py` + `routes/focus.py` + `focus-api.js`
- Commander service is a **simple Unix socket client** — no dependency on claude-commander internals, just the documented JSON protocol
- Commander availability is tracked **in-memory with periodic health checks** (same threading pattern as `HookReceiverState`)
- State transitions use the **existing state machine** — `(AWAITING_INPUT, USER, ANSWER) → PROCESSING` is already defined
- Audit trail through existing **Turn model** (actor: USER, intent: ANSWER) — no new models needed

## Implementation Approach
- **Backend-first approach:** Build commander service and response endpoint first, then dashboard UI
- Socket communication uses Python's `socket` module with `AF_UNIX` — newline-delimited JSON protocol matching claude-commander's spec
- Response endpoint creates Turn records and triggers state transitions through `TaskLifecycleManager.process_turn()` to stay consistent with hook-driven flows
- Availability tracking runs in a background thread (similar to `AgentReaper`, `ActivityAggregator`) — only in non-testing environments

## Files to Modify

### New Files
- `src/claude_headspace/services/commander_service.py` — Unix socket client (send text, health check, derive path)
- `src/claude_headspace/routes/respond.py` — Response submission API endpoint
- `static/js/respond-api.js` — Client-side response handler
- `tests/services/test_commander_service.py` — Commander service unit tests
- `tests/routes/test_respond.py` — Response endpoint route tests

### Modified Files
- `src/claude_headspace/app.py` — Register commander service in extensions + respond blueprint
- `templates/dashboard.html` — Add input widget to agent cards, load respond-api.js
- `static/css/main.css` (or `static/css/src/input.css`) — Input widget styles

## Acceptance Criteria
1. User can respond to a permission prompt from the dashboard without switching to iTerm
2. iTerm terminal remains fully interactive while dashboard input works simultaneously
3. Quick-action buttons appear for numbered permission choices when pattern is detectable
4. Free-text input is available for arbitrary responses
5. Visual feedback confirms response sent (or shows clear error)
6. Dashboard degrades gracefully when commander socket unavailable
7. Responses recorded as Turn entities in audit trail
8. Response delivery under 500ms for local socket communication

## Constraints and Gotchas
- **Socket path convention:** `/tmp/claudec-<SESSION_ID>.sock` — relies on `claude_session_id` being set on the Agent model (set during session-start hook)
- **Startup delay:** claude-commander has ~2-5 second startup delay before socket is available — availability checker must handle this gracefully
- **No output capture:** Socket is input-only — we cannot confirm Claude Code received or acted on the input, only that the socket accepted it
- **Race condition:** If user responds via dashboard but Claude Code has already moved past the prompt, the text is still delivered (harmless but may cause confusion). State will self-correct on next hook event.
- **Unix permissions:** Socket access relies on file permissions — both Flask process and claude-commander must run as same user
- **No authentication:** Socket has no auth beyond Unix file permissions — acceptable for local-only use
- **Process death detection:** Socket file may persist after process dies — health check via `{"action": "status"}` is the reliable way to check

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/agent.py` (has `claude_session_id`), `models/turn.py` (Turn with ANSWER intent), `models/task.py` (TaskState.AWAITING_INPUT)
- Services: `services/iterm_focus.py` (pattern template), `services/hook_receiver.py` (AWAITING_INPUT flow), `services/state_machine.py` (transition rules), `services/task_lifecycle.py` (Turn processing), `services/broadcaster.py` (SSE)
- Routes: `routes/focus.py` (pattern template)
- Static: `static/js/focus-api.js` (pattern template)
- Templates: `templates/dashboard.html` (agent cards)

### OpenSpec History
- No previous changes to the `input-bridge` capability (new subsystem)
- Related capability: `focus` — iTerm focus control uses similar service+route+JS pattern

### Implementation Patterns
- Service pattern: Pure Python module with NamedTuple results, typed errors, logging (see `iterm_focus.py`)
- Route pattern: Blueprint, `db.session.get()`, `jsonify()` responses, `get_broadcaster().broadcast()` (see `routes/focus.py`)
- Client JS pattern: IIFE with global export, async/await fetch, Toast notifications, DOM `data-agent-id` attributes (see `focus-api.js`)
- Service registration: `app.extensions["name"] = instance` in `create_app()` (see `app.py`)
- Background thread: `start()`/`stop()` pattern with atexit cleanup (see `AgentReaper`, `ActivityAggregator`)

## Q&A History
- No clarifications needed — PRD is comprehensive and internally consistent
- No conflicts with existing codebase detected

## Dependencies
- No new packages needed — Python's `socket` module handles Unix domain sockets natively
- Requires claude-commander (`claudec`) binary installed separately by user
- No database migrations needed — uses existing Turn and Task models

## Testing Strategy
- **Unit tests:** Commander service (mock socket), availability tracking (thread safety)
- **Route tests:** Response endpoint with Flask test client and mocked commander service
- **Integration tests:** End-to-end flow with real DB (factory-created agents) and mock socket
- **Key scenarios:** Happy path, agent not found, wrong state, no session ID, socket unavailable, socket dead, send failure

## OpenSpec References
- proposal.md: openspec/changes/e5-s1-input-bridge/proposal.md
- tasks.md: openspec/changes/e5-s1-input-bridge/tasks.md
- spec.md: openspec/changes/e5-s1-input-bridge/specs/input-bridge/spec.md
