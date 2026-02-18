# Proposal Summary: e4-s2a-project-controls-backend

## Architecture Decisions
- New `routes/projects.py` blueprint following the established route pattern (17 existing blueprints). No separate service layer needed — CRUD logic is simple enough for the route layer with direct db.session access.
- Inference gating added at the caller level (summarisation_service.py, priority_scoring.py) not in the inference service itself — avoids circular imports and keeps inference service generic.
- Per-project inference pause stored in the database (not config.yaml) so it persists across restarts and is per-project.
- Auto-discovery disabled by changing existing code to raise/return errors rather than creating a new middleware layer — minimal surface area change.
- SSE events broadcast using existing `get_broadcaster()` lazy import pattern.

## Implementation Approach
- Add new database columns to Project model via Alembic migration first (description, inference_paused, inference_paused_at, inference_paused_reason).
- Create projects blueprint with CRUD + settings endpoints.
- Modify session_correlator.py and sessions.py to reject unregistered projects (raise ValueError / return 404).
- Add inference gating checks in summarisation and priority scoring services.
- Broadcast SSE events on project CRUD and settings changes.

## Files to Modify

### New Files
- `src/claude_headspace/routes/projects.py` — project CRUD and settings API endpoints
- `migrations/versions/xxx_add_project_management_fields.py` — Alembic migration for new columns
- `tests/routes/test_projects.py` — route tests for CRUD and settings
- `tests/services/test_inference_gating.py` — inference gating unit tests

### Modified Files
- `src/claude_headspace/models/project.py` — add description, inference_paused, inference_paused_at, inference_paused_reason fields
- `src/claude_headspace/app.py` — register projects_bp in register_blueprints()
- `src/claude_headspace/services/session_correlator.py` — remove auto-create in _create_agent_for_session(), raise ValueError for unregistered
- `src/claude_headspace/routes/sessions.py` — remove auto-create in create_session(), return 404 for unregistered
- `src/claude_headspace/services/summarisation_service.py` — add inference pause check before summarise_turn(), summarise_task(), summarise_instruction()
- `src/claude_headspace/services/priority_scoring.py` — filter out paused project agents in score_all_agents()
- `tests/services/test_session_correlator.py` — update for auto-discovery removal
- `tests/routes/test_sessions.py` — update for auto-discovery removal

## Acceptance Criteria
- GET /api/projects returns list with agent_count
- POST /api/projects creates project (201), rejects duplicate path (409)
- GET /api/projects/<id> returns detail with agents
- PUT /api/projects/<id> updates metadata (200), path conflict (409)
- DELETE /api/projects/<id> cascade deletes project and agents (200)
- PUT /api/projects/<id>/settings with inference_paused=true pauses inference, sets timestamp
- PUT /api/projects/<id>/settings with inference_paused=false resumes, clears timestamp/reason
- Unregistered project sessions rejected with clear error message
- Summarisation skips paused projects
- Priority scoring excludes paused project agents
- CRUD and settings changes broadcast SSE events

## Constraints and Gotchas
- **Session correlator auto-discovery is in TWO places** — both `_create_agent_for_session()` in session_correlator.py AND `create_session()` in routes/sessions.py. Both must be updated.
- **routes/__init__.py only exports 3 of 17 blueprints** — don't add projects_bp there; just import directly in app.py register_blueprints()
- **Inference gating must traverse ORM relationships** — turn.command.agent.project for summarisation, agent.project for priority scoring. Use already-loaded relationships to avoid N+1 queries.
- **Cascade delete already configured** — Project.agents relationship has `cascade="all, delete-orphan"`. No additional configuration needed.
- **Priority scoring already has a disabled check** — uses `objective.priority_enabled`. The inference_paused check is a different gate (per-project vs global).
- **Summarisation availability check pattern** — existing pattern is `if not self._inference.is_available: return None`. The pause check should follow the same pattern.
- **Error messages for unregistered projects** must include the rejected path AND reference to /projects page per FR12.
- **migration must handle existing data** — inference_paused defaults to false so existing projects are unaffected.

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/project.py` (5 fields currently, needs 4 more)
- Routes: `src/claude_headspace/routes/sessions.py` (auto-creates projects)
- Services:
  - `src/claude_headspace/services/session_correlator.py` (auto-creates projects)
  - `src/claude_headspace/services/summarisation_service.py` (inference calls)
  - `src/claude_headspace/services/priority_scoring.py` (inference calls)
  - `src/claude_headspace/services/broadcaster.py` (SSE events)
- App: `src/claude_headspace/app.py` (blueprint registration, service init)
- Tests:
  - `tests/services/test_session_correlator.py`
  - `tests/routes/test_sessions.py`

### OpenSpec History
- No prior project-controls OpenSpec changes
- Related changes: e1-s2-database-setup (initial DB and project model), e1-s3-domain-models (model relationships)

### Implementation Patterns
- Blueprint pattern: Flask Blueprint with url_prefix, registered in register_blueprints()
- Route pattern: JSON responses, db.session for queries, commit/rollback error handling
- SSE pattern: get_broadcaster().broadcast(event_type, data_dict) with lazy import
- Inference gating: check boolean flag, return None/skip if disabled, debug log
- Error handling: JSON error responses with appropriate HTTP status codes (400, 404, 409, 500)

## Q&A History
- No clarifications needed — PRD is comprehensive with code examples for all key patterns

## Dependencies
- No new packages required
- Alembic migration needed for database schema changes
- No external services/APIs involved

## Testing Strategy
- Route tests for all CRUD endpoints (list, create, read, update, delete) with success and error cases
- Route tests for settings endpoints (get, put) including auto-timestamp behavior
- Unit tests for inference gating in summarisation and priority scoring
- Updated existing tests for session_correlator and sessions.py to verify auto-discovery is disabled
- SSE broadcast verification in route tests

## OpenSpec References
- proposal.md: openspec/changes/e4-s2a-project-controls-backend/proposal.md
- tasks.md: openspec/changes/e4-s2a-project-controls-backend/tasks.md
- spec.md: openspec/changes/e4-s2a-project-controls-backend/specs/project-controls/spec.md
