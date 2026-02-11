# Proposal Summary: e6-s4-agent-lifecycle

## Architecture Decisions
- New `agents` subsystem — first-class concept separate from bridge to support future orchestration growth
- Thin `agent_lifecycle.py` service layer coordinates existing infrastructure (CLI launcher, tmux bridge, capture_pane)
- Separate `context_parser.py` module for parsing tmux statusline — isolated regex logic, easy to test
- On-demand context refresh only (no polling) — keeps SSE clean, user triggers explicitly
- Graceful shutdown via `/exit` command — leverages existing hook lifecycle for state consistency
- Agent creation via `claude-headspace start` CLI in subprocess within new tmux session — reuses all existing registration and bridge wiring

## Implementation Approach
- Build backend services first (context_parser, agent_lifecycle), then API routes, then UI
- Voice bridge extensions follow same patterns as existing voice_bridge.py endpoints
- Dashboard UI uses existing patterns: Tailwind utility classes, vanilla JS, SSE for real-time updates
- No new database models or migrations — uses existing Agent, Project models

## Files to Modify

### New Files
- `src/claude_headspace/services/agent_lifecycle.py` — create/shutdown/context orchestration
- `src/claude_headspace/services/context_parser.py` — tmux pane context usage parsing
- `src/claude_headspace/routes/agents.py` — new blueprint with 3 endpoints
- `tests/services/test_agent_lifecycle.py`
- `tests/services/test_context_parser.py`
- `tests/routes/test_agents.py`

### Modified Files
- `src/claude_headspace/app.py` — register agents blueprint
- `src/claude_headspace/routes/voice_bridge.py` — add 3 voice endpoints (create/shutdown/context)
- `templates/partials/_agent_card.html` — add kill button + context indicator
- `templates/dashboard.html` — add "New Agent" project selector
- `static/voice/voice-api.js` — add createAgent(), shutdownAgent(), getContext() calls
- `static/voice/voice-app.js` — add create/kill/context command handling
- `static/js/` — dashboard JS for create/kill/context actions (possibly new file or extend existing)

## Acceptance Criteria
- Create agent from dashboard or voice bridge → agent appears on dashboard in idle state
- Kill agent from dashboard or voice bridge → `/exit` sent, hooks fire, agent disappears
- Check context from dashboard or voice bridge → shows `XX% used · XXXk remaining` or "unavailable"
- All operations work remotely via voice/text bridge on mobile
- Dashboard state remains consistent (no orphaned cards)

## Constraints and Gotchas
- Agent creation is async — CLI launches in subprocess, agent appears when hooks fire (session-start hook registers it). Need to handle the delay between API response and agent appearing.
- The `[ctx: XX% used, XXXk remaining]` format is from a Claude Code statusline configuration — if the user hasn't configured it, context data will be unavailable. Parser must handle gracefully.
- `/exit` is a Claude Code slash command, not arbitrary text — it must be sent as a literal string via tmux send-keys followed by Enter.
- The tmux pane content may contain ANSI escape codes — context parser must strip them before regex matching.
- NFR1 (idempotency) is left to implementation: creating an agent for a project that already has one should create an additional agent (multiple agents per project is valid).

## Git Change History

### Related Files
- Migrations: agent-related column additions (transcript_path, ended_at, claude_session_id, priority fields)
- No existing agent lifecycle service — this is net-new

### OpenSpec History
- No previous changes to an `agent-lifecycle` capability — this is a new spec

### Implementation Patterns
- Services follow: pure functions or class with `init_app()` registered in `app.extensions`
- Routes follow: Blueprint with `_bp` suffix, registered in `app.py` `create_app()`
- Voice bridge follows: `_voice_error()` helper, `_get_voice_formatter()` for response formatting
- Tmux bridge follows: `send_text()` for input, `capture_pane()` for output reading

## Q&A History
- No clarifications needed — PRD was clear and self-consistent
- Context refresh decision: on-demand only (user preference to avoid noise)
- Graceful shutdown via `/exit` rather than SIGTERM/kill (preserves hook lifecycle)
- New `agents` subsystem rather than extending `bridge` (forward-looking for orchestration)

## Dependencies
- No new packages needed
- Relies on existing: tmux_bridge, claude-headspace CLI, Flask app factory, voice bridge auth
- No database migrations needed

## Testing Strategy
- Unit tests for context_parser: regex parsing, ANSI stripping, edge cases (missing data, malformed lines)
- Unit tests for agent_lifecycle: mock subprocess for creation, mock tmux_bridge for shutdown/context
- Route tests for agents blueprint: mock service layer, test all endpoints + error cases
- Route tests for voice bridge extensions: mock service layer, test voice-formatted responses
- Manual verification: end-to-end create/kill/context from both dashboard and voice bridge

## OpenSpec References
- proposal.md: openspec/changes/e6-s4-agent-lifecycle/proposal.md
- tasks.md: openspec/changes/e6-s4-agent-lifecycle/tasks.md
- spec.md: openspec/changes/e6-s4-agent-lifecycle/specs/agent-lifecycle/spec.md
