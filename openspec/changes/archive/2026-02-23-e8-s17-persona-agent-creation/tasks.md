## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend: Agent Creation API

- [x] 2.1 Extend `POST /api/agents` endpoint to accept optional `persona_slug` parameter from request body
- [x] 2.2 Pass `persona_slug` from the agents route to `create_agent()` service function (already accepts it)
- [x] 2.3 Add `GET /api/personas/active` endpoint returning active personas grouped by role for the selector

### Backend: CLI Persona List

- [x] 2.4 Add `flask persona list` command to `persona_cli.py` with formatted table output
- [x] 2.5 Add `--active` flag to filter to active personas only
- [x] 2.6 Add `--role` flag to filter by role name
- [x] 2.7 Sort output alphabetically by name within each role

### Backend: CLI Short-Name Matching

- [x] 2.8 Add `resolve_persona_slug()` function to launcher.py for short-name resolution
- [x] 2.9 Implement case-insensitive substring matching against persona name field via API
- [x] 2.10 Implement disambiguation prompt when multiple personas match
- [x] 2.11 Display available personas and exit with error when no match found
- [x] 2.12 Integrate short-name resolution into the `--persona` flag validation flow

### Frontend: Dashboard Persona Selector

- [x] 2.13 Add persona selector dropdown to the new-agent menu in `dashboard.html`
- [x] 2.14 Fetch active personas from API when new-agent menu opens in `agent-lifecycle.js`
- [x] 2.15 Display personas grouped by role with name and description preview
- [x] 2.16 Include "No persona" as default option
- [x] 2.17 Pass selected `persona_slug` in the `POST /api/agents` request body

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for `POST /api/agents` with persona_slug parameter (valid, invalid, none)
- [x] 3.2 Unit tests for `GET /api/personas/active` endpoint
- [x] 3.3 Unit tests for `flask persona list` command (all, --active, --role filters)
- [x] 3.4 Unit tests for `resolve_persona_slug()` (exact match, single match, multiple match, no match)
- [x] 3.5 Regression: verify existing agent creation without persona still works

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
