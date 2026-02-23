# Proposal Summary: e8-s17-persona-agent-creation

## Architecture Decisions
- Persona selector uses the existing "New Agent" popover pattern on the dashboard — extends the current project-only menu to include a two-step flow: project selection, then optional persona selection
- The `GET /api/personas/active` endpoint serves the selector (filtered, sorted, grouped), keeping the frontend thin
- The `POST /api/agents` endpoint gains an optional `persona_slug` field — the existing `create_agent()` service already accepts and validates this parameter, so the change is a passthrough
- CLI `flask persona list` follows the existing `flask persona register` CLI pattern (AppGroup in `persona_cli.py`)
- Short-name matching uses the server API (`GET /api/personas`) rather than direct DB access, consistent with how the CLI validates personas via `validate_persona()` already
- Disambiguation uses interactive `click.prompt()` when multiple personas match a short name

## Implementation Approach
- **API layer:** Extend `POST /api/agents` to extract `persona_slug` from request body and pass to `create_agent()`. Add `GET /api/personas/active` endpoint for the selector.
- **Dashboard UI:** Modify the `new-agent-menu` in `dashboard.html` to show a two-step flow. First, the user selects a project (existing behavior). Then a persona selector appears (or is shown alongside). `agent-lifecycle.js` fetches `GET /api/personas/active` and renders options grouped by role.
- **CLI list command:** Add `list` subcommand to the `persona_cli` AppGroup. Query all personas with role joins, apply filters, format as table using click.echo.
- **CLI short-name matching:** Add `resolve_persona_slug()` to `launcher.py`. When `--persona` value doesn't match an exact slug, call `GET /api/personas` to get all personas, filter by substring match on name (case-insensitive). If 1 match, use it. If multiple, present numbered list via `click.prompt`. If 0, show available personas and exit.

## Files to Modify (organized by type)

### Routes
- **MODIFIED** `src/claude_headspace/routes/agents.py` — Extract `persona_slug` from request body in `create_agent_endpoint()`, pass to `create_agent()`
- **MODIFIED** `src/claude_headspace/routes/personas.py` — Add `GET /api/personas/active` endpoint returning active personas with role info

### Services
- No service changes needed — `create_agent()` in `agent_lifecycle.py` already accepts and validates `persona_slug`

### CLI
- **MODIFIED** `src/claude_headspace/cli/persona_cli.py` — Add `list` command with `--active` and `--role` filter flags, formatted table output
- **MODIFIED** `src/claude_headspace/cli/launcher.py` — Add `resolve_persona_slug()` function for short-name matching, integrate into `cmd_start()` validation flow

### Templates
- **MODIFIED** `templates/dashboard.html` — Add persona selector UI to the `new-agent-menu` div

### Static/JS
- **MODIFIED** `static/js/agent-lifecycle.js` — Fetch personas from API, render grouped selector, include `persona_slug` in POST body

### Tests
- **NEW** `tests/routes/test_agents_persona.py` — Tests for POST /api/agents with persona_slug
- **NEW** `tests/routes/test_personas_active.py` — Tests for GET /api/personas/active endpoint
- **NEW** `tests/cli/test_persona_list.py` — Tests for flask persona list command
- **NEW** `tests/cli/test_launcher_shortname.py` — Tests for resolve_persona_slug() short-name matching

## Acceptance Criteria
1. Dashboard "New Agent" flow includes an optional persona selector showing active personas grouped by role
2. Selecting "No persona" (default) creates an agent without persona (backward compatible)
3. Selecting a persona includes persona_slug in the POST request and the agent launches with the persona assigned
4. `flask persona list` displays all personas in a formatted table with Name, Role, Slug, Status, Agents columns
5. `flask persona list --active` filters to active personas only
6. `flask persona list --role developer` filters by role name
7. `claude-headspace start --persona con` resolves short names case-insensitively
8. Multiple matches present a numbered disambiguation prompt
9. No matches display available personas and exit with error
10. Full slugs continue to work via existing validation path

## Constraints and Gotchas
- **Two-step UI flow:** The current new-agent menu is a simple list of projects. Adding persona selection means either a two-step flow (select project, then persona) or a combined form. The two-step approach is simpler and consistent with how other menus work in the dashboard.
- **Persona selector must be optional:** The "No persona" default must be clearly visible and agents must still be creatable without selecting a persona.
- **Short-name matching via API, not DB:** The CLI launcher does not have Flask app context, so it must use the server API to list personas. The existing pattern (validate_persona calls GET /api/personas/{slug}/validate) should be extended.
- **Click prompt for disambiguation:** `click.prompt()` requires stdin — this works in interactive CLI mode but not in automated/background contexts. Since `claude-headspace start` is always interactive, this is acceptable.
- **Persona selector load time:** The PRD requires <500ms. The `GET /api/personas/active` query should be simple and fast (small table, indexed).
- **Frontend JS is vanilla:** No React/Vue — the persona selector must be built with plain DOM manipulation matching the existing codebase patterns.

## Git Change History

### Related Files (from git_context)
- **Models:** `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/agent.py`
- **Routes:** `src/claude_headspace/routes/personas.py`, `src/claude_headspace/routes/agents.py`
- **Services:** `src/claude_headspace/services/persona_registration.py`, `src/claude_headspace/services/persona_assets.py`, `src/claude_headspace/services/agent_lifecycle.py`
- **CLI:** `src/claude_headspace/cli/persona_cli.py`, `src/claude_headspace/cli/launcher.py`
- **Templates:** `templates/dashboard.html`, `templates/personas.html`, `templates/persona_detail.html`
- **Static:** `static/js/agent-lifecycle.js`, `static/js/personas.js`, `static/js/persona_detail.js`
- **Tests:** `tests/services/test_persona_registration.py`, `tests/services/test_persona_assets.py`, `tests/routes/test_personas.py`, `tests/integration/test_persona_registration.py`, `tests/integration/test_role_persona_models.py`, `tests/services/test_agent_lifecycle.py`, `tests/cli/test_launcher.py`
- **Migrations:** `migrations/versions/0462474af024_add_role_and_persona_tables.py`, `migrations/versions/b5c9d3e6f7a8_add_agent_persona_position_predecessor.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) — Role + Persona DB models
- `e8-s5-persona-filesystem-assets` (2026-02-21) — Asset utility functions
- `e8-s6-persona-registration` (2026-02-21) — Registration service, CLI, API
- `e8-s7-persona-aware-agent-creation` (2026-02-21) — CLI --persona flag, create_agent() persona_slug, hook passthrough
- `e8-s8-session-correlator-persona` (2026-02-21) — Session correlator sets agent.persona_id
- `e8-s10-card-persona-identity` (2026-02-21) — Card UI persona display
- `e8-s11-agent-info-persona-display` (2026-02-21) — Agent info persona display
- `e8-s15-persona-list-crud` (2026-02-23) — Persona list page, CRUD API, form modal
- `e8-s16-persona-detail-skill-editor` (2026-02-23) — Persona detail page, skill editor

### Patterns Detected
- Modules + tests + templates + static (full-stack change)
- CLI commands use `flask.cli.AppGroup` pattern with `@click` decorators
- Dashboard JS uses vanilla IIFE modules with `CHUtils.apiFetch()` for API calls
- Persona API follows REST conventions established in S15 (`/api/personas/*`)
- Agent lifecycle API follows pattern in `agents.py` (POST for create, DELETE for shutdown)

## Q&A History
- No clarifications needed — the PRD is clear and all prior design decisions from the Agent Teams Workshop and sprints S1-S16 apply.

## Dependencies
- No new packages needed
- Consumes E8-S1 models (Persona, Role)
- Consumes E8-S7 `create_agent()` persona_slug parameter (already implemented)
- Consumes E8-S15 persona list API endpoints (already implemented)
- Consumes E8-S16 persona detail page (already implemented, not modified)

## Testing Strategy
- **Route tests** for `POST /api/agents` with persona_slug: valid slug, invalid slug, no slug (backward compat)
- **Route tests** for `GET /api/personas/active`: active personas returned, archived excluded, empty list
- **CLI tests** for `flask persona list`: all personas, --active filter, --role filter, no personas
- **CLI tests** for `resolve_persona_slug()`: exact slug match (bypass), single short-name match, multiple matches, no matches
- **Regression**: existing agent creation and persona tests must continue passing

## OpenSpec References
- proposal.md: `openspec/changes/e8-s17-persona-agent-creation/proposal.md`
- tasks.md: `openspec/changes/e8-s17-persona-agent-creation/tasks.md`
- spec.md: `openspec/changes/e8-s17-persona-agent-creation/specs/persona-agent-creation/spec.md`
