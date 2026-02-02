## Why

Claude Code frequently blocks on permission prompts requiring physical terminal interaction. The Headspace dashboard already detects these prompts (amber cards, SSE, notifications) but provides no return path — users must context-switch to iTerm to respond. Input Bridge closes this loop by enabling dashboard-to-terminal text injection via claude-commander's Unix domain socket.

This is Phase 1 of the Voice Bridge roadmap: the commander service built here becomes the session-targeting mechanism for future voice input (Phase 2) and voice output (Phase 3).

## What Changes

- **New service:** `commander_service.py` — Unix socket client for claude-commander (send text, health check, derive socket path from `claude_session_id`)
- **New route:** `routes/respond.py` — API endpoint for submitting text responses to agents (`POST /api/respond/<agent_id>`)
- **New client JS:** `static/js/respond-api.js` — dashboard client for response submission with quick-action buttons and free-text input
- **Dashboard UI extension:** Agent cards in AWAITING_INPUT state gain an input widget when commander socket is available
- **Commander availability tracking:** Periodic health checks with SSE broadcast for real-time UI updates
- **Audit trail:** Responses recorded as Turn entities (actor: USER, intent: ANSWER)
- **App registration:** Commander service registered in `app.extensions`, respond blueprint registered

## Impact

- Affected specs: None (new subsystem, no existing specs)
- Affected code:
  - `src/claude_headspace/app.py` — register commander service and respond blueprint
  - `src/claude_headspace/services/commander_service.py` — **NEW** Unix socket client
  - `src/claude_headspace/routes/respond.py` — **NEW** response API endpoint
  - `static/js/respond-api.js` — **NEW** client-side response handler
  - `templates/dashboard.html` — extend agent card with input widget
  - `templates/partials/_agent_card.html` — add input widget partial (if agent cards are partials)
  - `static/css/main.css` — styles for input widget, quick-action buttons
  - Related files from git_context: `hook_receiver.py` (AWAITING_INPUT flow), `state_machine.py` (transition validation), `iterm_focus.py` + `routes/focus.py` + `focus-api.js` (pattern to follow)
