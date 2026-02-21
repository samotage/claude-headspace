# Proposal Summary: e8-s6-persona-registration

## Architecture Decisions
- Registration logic in a standalone service function (`register_persona`) — testable without CLI/HTTP context
- Flask CLI command via Click (`flask persona register`) as the primary interface — agent-operable via tools
- Optional REST API endpoint (`POST /api/personas/register`) for programmatic access
- Partial failure strategy: report error with persona ID, do not rollback DB record
- Role name lowercased on input for storage and lookup; persona name preserves original case
- This is the first Flask CLI command group in the project — establishes the pattern for future CLI extensions

## Implementation Approach
- Create `persona_registration.py` service with `register_persona()` function that orchestrates: validate inputs → lookup/create role → insert persona → create filesystem assets
- Create `persona_cli.py` with Click-based CLI command group registered on `app.cli`
- Create `personas.py` route blueprint for the API endpoint
- Both CLI and API are thin wrappers delegating to the service function
- Returns a `RegistrationResult` dataclass with slug, id, and path

## Files to Modify
- **NEW** `src/claude_headspace/services/persona_registration.py` — core service
- **NEW** `src/claude_headspace/cli/persona_cli.py` — Flask CLI command group
- **NEW** `src/claude_headspace/routes/personas.py` — REST API blueprint
- **MODIFIED** `src/claude_headspace/app.py` — register CLI group + personas blueprint
- **Consumed** `src/claude_headspace/models/persona.py` — Persona model with slug generation
- **Consumed** `src/claude_headspace/models/role.py` — Role model
- **Consumed** `src/claude_headspace/services/persona_assets.py` — filesystem asset utilities

## Acceptance Criteria
- `flask persona register --name Con --role developer` creates Role, Persona, directory, template files
- Re-running creates a second persona with unique slug
- Existing roles are reused via case-insensitive matching
- Missing --name or --role gives clear error, no records created
- Output displays slug, ID, and filesystem path
- API endpoint returns 201 JSON on success, 400 on validation error
- Service function testable without CLI/HTTP

## Constraints and Gotchas
- Slug is generated post-insert (uses DB primary key) via SQLAlchemy `after_insert` event — the slug isn't available until after `db.session.flush()`
- The `_temp_slug` default in Persona model handles the insert-before-slug-is-known issue
- Role name case: always lowercase for DB storage; persona name preserves original case
- Filesystem creation is not atomic with DB — intentional design decision (report error, don't rollback)
- This project has NO existing Flask CLI commands — this establishes the pattern (Click group on `app.cli`)

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/role.py`
- Services: `src/claude_headspace/services/persona_assets.py`
- Migrations: `migrations/versions/0462474af024_add_role_and_persona_tables.py`
- Tests: `tests/integration/test_role_persona_models.py`, `tests/services/test_persona_assets.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) — created Role + Persona models
- `e8-s5-persona-filesystem-assets` (2026-02-21) — created asset utility functions

### Implementation Patterns
- Modules + tests (no templates, static, bin, or config changes)
- Service functions with `project_root` parameter for testability (E8-S5 pattern)
- SQLAlchemy `after_insert` event for slug generation (E8-S1 pattern)

## Q&A History
- No clarifications needed — PRD design decisions were pre-resolved in the Agent Teams Design Workshop

## Dependencies
- No new packages needed
- Consumes E8-S1 models (Role, Persona) and E8-S5 asset utilities (persona_assets.py)
- Click is already available via Flask's dependency

## Testing Strategy
- **Unit tests** (`tests/services/test_persona_registration.py`): Test service function with mocked DB session — role create/reuse, persona creation, validation errors, partial failure, duplicate handling
- **Route tests** (`tests/routes/test_personas.py`): Test API endpoint responses — 201, 400, JSON format
- **Integration tests** (`tests/integration/test_persona_registration.py`): End-to-end with real DB + filesystem via `tmp_path`

## OpenSpec References
- proposal.md: openspec/changes/e8-s6-persona-registration/proposal.md
- tasks.md: openspec/changes/e8-s6-persona-registration/tasks.md
- spec.md: openspec/changes/e8-s6-persona-registration/specs/persona-registration/spec.md
