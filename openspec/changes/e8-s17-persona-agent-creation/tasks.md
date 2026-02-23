## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend: Agent Creation API

- [ ] 2.1 Extend `POST /api/agents` endpoint to accept optional `persona_slug` parameter from request body
- [ ] 2.2 Pass `persona_slug` from the agents route to `create_agent()` service function (already accepts it)
- [ ] 2.3 Add `GET /api/personas/active` endpoint returning active personas grouped by role for the selector

### Backend: CLI Persona List

- [ ] 2.4 Add `flask persona list` command to `persona_cli.py` with formatted table output
- [ ] 2.5 Add `--active` flag to filter to active personas only
- [ ] 2.6 Add `--role` flag to filter by role name
- [ ] 2.7 Sort output alphabetically by name within each role

### Backend: CLI Short-Name Matching

- [ ] 2.8 Add `resolve_persona_slug()` function to launcher.py for short-name resolution
- [ ] 2.9 Implement case-insensitive substring matching against persona name field via API
- [ ] 2.10 Implement disambiguation prompt when multiple personas match
- [ ] 2.11 Display available personas and exit with error when no match found
- [ ] 2.12 Integrate short-name resolution into the `--persona` flag validation flow

### Frontend: Dashboard Persona Selector

- [ ] 2.13 Add persona selector dropdown to the new-agent menu in `dashboard.html`
- [ ] 2.14 Fetch active personas from API when new-agent menu opens in `agent-lifecycle.js`
- [ ] 2.15 Display personas grouped by role with name and description preview
- [ ] 2.16 Include "No persona" as default option
- [ ] 2.17 Pass selected `persona_slug` in the `POST /api/agents` request body

## 3. Testing (Phase 3)

- [ ] 3.1 Unit tests for `POST /api/agents` with persona_slug parameter (valid, invalid, none)
- [ ] 3.2 Unit tests for `GET /api/personas/active` endpoint
- [ ] 3.3 Unit tests for `flask persona list` command (all, --active, --role filters)
- [ ] 3.4 Unit tests for `resolve_persona_slug()` (exact match, single match, multiple match, no match)
- [ ] 3.5 Regression: verify existing agent creation without persona still works

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
