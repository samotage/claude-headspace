## Why

Users cannot create or destroy Claude Code agents remotely. Agent lifecycle (start/stop) requires direct terminal access, blocking mobile-first remote operation via the voice/text bridge. Additionally, there is no visibility into agent context window usage, which is critical for managing agent quality.

## What Changes

- New `agents` route blueprint with API endpoints for agent creation, graceful shutdown, and context window queries
- New `agent_lifecycle` service module coordinating CLI invocation and tmux operations
- Context parsing utility that reads tmux pane statusline to extract `[ctx: XX% used, XXXk remaining]`
- Dashboard UI additions: project selector with "New Agent" button, per-card kill control, per-card context indicator
- Voice/text bridge extensions: create, kill, and context-check commands
- Agent card partial updated to show context usage inline

## Impact

- Affected specs: `launcher`, `tmux-bridge`, `voice-bridge`, `dashboard`, `voice-bridge-client`
- Affected code:
  - **New files:**
    - `src/claude_headspace/services/agent_lifecycle.py` — orchestrates agent creation and shutdown
    - `src/claude_headspace/services/context_parser.py` — parses context usage from tmux pane content
    - `src/claude_headspace/routes/agents.py` — new blueprint for agent lifecycle API
    - `tests/services/test_agent_lifecycle.py` — service unit tests
    - `tests/services/test_context_parser.py` — parser unit tests
    - `tests/routes/test_agents.py` — route tests
  - **Modified files:**
    - `src/claude_headspace/app.py` — register agents blueprint
    - `src/claude_headspace/routes/voice_bridge.py` — add create/kill/context voice commands
    - `templates/partials/_agent_card.html` — add kill button and context indicator
    - `templates/dashboard.html` — add "New Agent" project selector
    - `static/js/dashboard.js` or similar — JS for create/kill/context actions
    - `static/voice/voice-app.js` — voice bridge create/kill/context commands
    - `static/voice/voice-api.js` — API calls for new endpoints
