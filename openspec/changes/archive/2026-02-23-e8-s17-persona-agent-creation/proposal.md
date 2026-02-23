## Why

The persona lifecycle is nearly complete (create, edit skills), but users cannot assign personas when launching agents from the dashboard. The CLI also requires knowing exact slugs with no discovery mechanism. This sprint closes the loop by adding persona selection to the dashboard agent creation flow and enhancing the CLI with persona discovery and short-name matching.

## What Changes

- Add persona selector dropdown to the dashboard "New Agent" creation flow, grouped by role with name/description preview
- Extend the agent creation API (`POST /api/agents`) to accept an optional `persona_slug` parameter and validate it
- Add `flask persona list` CLI command with formatted table output, `--active` and `--role` filters
- Add CLI short-name matching for the `--persona` flag with case-insensitive substring matching and disambiguation prompts
- Add `GET /api/personas/active` endpoint to serve persona list for the dashboard selector (active only, grouped by role)

## Impact

- Affected specs: persona-aware-agent-creation, persona-list-crud
- Affected code:
  - `src/claude_headspace/routes/agents.py` — accept persona_slug in create endpoint
  - `src/claude_headspace/services/agent_lifecycle.py` — pass persona_slug from API to tmux session
  - `src/claude_headspace/routes/personas.py` — new active personas endpoint for selector
  - `src/claude_headspace/cli/persona_cli.py` — add `list` command with filters
  - `src/claude_headspace/cli/launcher.py` — short-name matching + disambiguation for `--persona` flag
  - `templates/dashboard.html` — persona selector in new-agent menu
  - `static/js/agent-lifecycle.js` — fetch personas, include persona_slug in create request
  - `tests/` — unit and route tests for all new functionality
