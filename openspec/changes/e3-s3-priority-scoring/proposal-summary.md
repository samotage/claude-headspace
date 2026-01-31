# Proposal Summary: e3-s3-priority-scoring

## Architecture Decisions
- Single batch inference call for all agents (cross-agent comparison, efficient API usage)
- PriorityScoringService follows the same pattern as SummarisationService (E3-S2): constructor takes InferenceService + optional Flask app, async via background threads
- Fallback chain: objective → waypoint → default(50) — no inference call when no context available
- 5-second debounce for state-change triggers, immediate bypass for objective changes
- Thread-safe debounce using threading.Timer + threading.Lock

## Implementation Approach
- Create PriorityScoringService as a new service class, following E3-S2 SummarisationService patterns
- Extend Agent model with 3 nullable fields (priority_score, priority_reason, priority_updated_at)
- New Alembic migration chaining from d6e7f8a9b0c1
- New priority blueprint with POST /api/priority/score and GET /api/priority/rankings
- Integrate triggers into HookLifecycleBridge (state change) and objective routes (objective change)
- Update dashboard route to replace hardcoded priority=50 with real scores

## Files to Modify

### New Files
- `src/claude_headspace/services/priority_scoring.py` — PriorityScoringService
- `src/claude_headspace/routes/priority.py` — Priority API blueprint
- `migrations/versions/e7f8a9b0c1d2_add_priority_fields_to_agents.py` — Migration
- `tests/services/test_priority_scoring.py` — Service unit tests
- `tests/routes/test_priority.py` — Route unit tests
- `tests/integration/test_priority_persistence.py` — Integration tests

### Modified Files
- `src/claude_headspace/models/agent.py` — Add priority fields
- `src/claude_headspace/routes/dashboard.py` — Replace hardcoded priority, update sort/recommend
- `src/claude_headspace/services/hook_lifecycle_bridge.py` — Add scoring triggers
- `src/claude_headspace/app.py` — Register service and blueprint
- `templates/partials/_agent_card.html` — Display priority reason

## Acceptance Criteria
- All active agents receive a priority score (0-100) when scoring is triggered
- Each scored agent has a human-readable priority reason
- Recommended next panel displays highest-priority agent
- Priority badges on agent cards show real scores
- Objective change triggers immediate re-scoring
- State change triggers rate-limited re-scoring (5-second debounce)
- Fallback chain: objective → waypoint → default(50)
- Scores persist to database across page reloads
- Batch scoring via single inference call
- Graceful handling of malformed LLM responses

## Constraints and Gotchas
- **Lazy imports for db**: Route files use `from ..database import db` inside functions (same as E3-S1/E3-S2). Test patches target `src.claude_headspace.database.db`, not the route module.
- **Agent.get_current_task()**: Queries DB directly, requires active session. Use in scoring to get task summary.
- **Waypoint is file-based**: Use `load_waypoint(project.path)` from `services.waypoint_editor`. Returns `WaypointResult` with `.content`, `.exists`. Parse markdown sections for "Next Up" and "Upcoming".
- **Objective is not singleton model**: Query via `db.session.query(Objective).order_by(Objective.set_at.desc()).first()`.
- **Task summaries (E3-S2)**: Available via `turn.summary` on most recent turn. May be None if summarisation hasn't run yet — degrade gracefully.
- **InferenceService.infer()**: Returns InferenceResult with .text field. Level="objective" for priority scoring. Purpose="priority_scoring".
- **Test fixtures need `path` on Project**: All Project() instantiations in tests must include `path="/test/path"` (non-null constraint).
- **MagicMock auto-attributes**: When mocking Agent, explicitly set `mock_agent.priority_score = None`, `mock_agent.priority_reason = None` etc. to prevent truthy MagicMock attributes.
- **Broadcast pattern**: Use `from .broadcaster import get_broadcaster` inside the method (lazy import), same as SummarisationService.

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/agent.py`, `src/claude_headspace/models/objective.py`
- Services: `src/claude_headspace/services/inference_service.py`, `src/claude_headspace/services/summarisation_service.py`, `src/claude_headspace/services/waypoint_editor.py`, `src/claude_headspace/services/hook_lifecycle_bridge.py`
- Routes: `src/claude_headspace/routes/dashboard.py`, `src/claude_headspace/routes/summarisation.py`
- Templates: `templates/partials/_agent_card.html`
- Config: `src/claude_headspace/app.py`

### OpenSpec History
- E3-S1 (openrouter-integration): Added InferenceService, InferenceCall model, inference routes, OpenRouter client
- E3-S2 (turn-task-summarisation): Added SummarisationService, summary fields on Turn/Task models, summarisation routes, SSE broadcast pattern

### Implementation Patterns
- Service: constructor(inference_service, app=None), sync method, async method (thread + app_context), _broadcast method
- Routes: Blueprint, lazy db import, service from app.extensions, error handling for service unavailable (503)
- Migration: chain from previous via `down_revision`, add nullable columns, downgrade drops
- Tests: MagicMock for services, patch targets at import location, integration tests with db_session fixture

## Q&A History
- No clarifications needed — PRD was comprehensive and consistent with existing codebase patterns

## Dependencies
- No new packages — uses existing InferenceService (E3-S1), threading (stdlib), json (stdlib)
- Depends on E3-S1 (inference service) and E3-S2 (task summaries) being complete (both are merged)

## Testing Strategy
- **Unit tests for PriorityScoringService**: prompt building, response parsing, fallback chain, debounce, error handling
- **Unit tests for priority routes**: POST /api/priority/score, GET /api/priority/rankings, error cases
- **Integration tests**: Priority field persistence on Agent model
- **Existing test regression**: Verify all 874+ existing tests still pass

## OpenSpec References
- proposal.md: openspec/changes/e3-s3-priority-scoring/proposal.md
- tasks.md: openspec/changes/e3-s3-priority-scoring/tasks.md
- spec.md: openspec/changes/e3-s3-priority-scoring/specs/priority-scoring/spec.md
