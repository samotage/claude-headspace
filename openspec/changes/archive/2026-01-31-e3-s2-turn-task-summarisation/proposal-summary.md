# Proposal Summary: e3-s2-turn-command-summarisation

## Architecture Decisions
- Summarisation implemented as a service layer consuming the E3-S1 InferenceService (not calling OpenRouter directly)
- Single `summarisation_service.py` with both TurnSummarisationService and TaskSummarisationService (two responsibilities, but tightly related and share patterns)
- Asynchronous execution via `threading.Thread` to avoid blocking the Flask request thread and SSE pipeline
- Summary caching leverages E3-S1's content-based caching — no separate caching layer needed
- SSE events broadcast via existing Broadcaster infrastructure (no changes to SSE transport)
- Summary fields added directly to Turn and Command models (not a separate SummaryResult table) for simplicity and query efficiency

## Implementation Approach
- Add `summary` (Text, nullable) and `summary_generated_at` (DateTime, nullable) columns to both Turn and Command models
- Create `SummarisationService` class that wraps `InferenceService.infer()` with prompt building and result persistence
- Integrate summarisation triggers in `CommandLifecycleManager.process_turn()` and `complete_task()` — fire-and-forget async calls
- Broadcast SSE events after summary generation using the existing Broadcaster
- Dashboard route includes summary data in agent card context; template shows summary or "Summarising..." placeholder or raw text fallback
- API endpoints (POST routes) for manual/programmatic trigger

## Files to Modify

### New Files
- `src/claude_headspace/services/summarisation_service.py` — SummarisationService with turn and command summarisation
- `src/claude_headspace/routes/summarisation.py` — Blueprint with POST /api/summarise/turn/<id> and POST /api/summarise/command/<id>
- `migrations/versions/xxx_add_summary_fields.py` — Migration adding summary columns to turns and tasks tables
- `tests/services/test_summarisation_service.py` — Unit tests for summarisation service
- `tests/routes/test_summarisation.py` — Unit tests for summarisation routes
- `tests/integration/test_summary_persistence.py` — Integration tests for summary field persistence

### Modified Files
- `src/claude_headspace/models/turn.py` — Add summary and summary_generated_at columns
- `src/claude_headspace/models/command.py` — Add summary and summary_generated_at columns
- `src/claude_headspace/services/command_lifecycle.py` — Add summarisation triggers after process_turn() and complete_task()
- `src/claude_headspace/routes/dashboard.py` — Include summary data in agent card rendering
- `src/claude_headspace/app.py` — Register summarisation blueprint, init SummarisationService
- `templates/partials/_agent_card.html` — Display summaries and "Summarising..." placeholder

## Acceptance Criteria
- Turn summaries generated automatically within 2 seconds of turn arrival
- Command summaries generated automatically on command completion
- Cached results returned for identical content without duplicate inference calls
- POST /api/summarise/turn/<id> and /api/summarise/command/<id> return correct summaries
- Summary fields persisted to database and survive page reloads
- All inference calls logged via E3-S1 InferenceCall system with correct level, purpose, and entity associations
- SSE updates continue uninterrupted during summarisation
- Dashboard remains responsive during summarisation processing
- Graceful degradation when inference service unavailable (raw text displayed, no errors)
- "Summarising..." placeholder visible while inference is pending

## Constraints and Gotchas
- Async execution via threading.Thread means we need Flask app context in the spawned thread (`app.app_context()`)
- The CommandLifecycleManager currently doesn't have access to Flask `current_app` — we need to pass the app reference or use a service registry pattern
- FR13 says cached summaries shall be permanent (no expiry) — the E3-S1 cache has TTL. For permanent caching, rely on the DB: if Turn.summary is already set, skip inference entirely
- InferenceService.infer() accepts turn_id, command_id, agent_id, project_id kwargs — use them for InferenceCall logging
- Migration must chain from current head `c5d6e7f8a9b0` (add_inference_calls_table)
- The dashboard route's `get_command_summary()` helper currently returns first 100 chars of most recent turn text — needs updating to prefer the Turn.summary field
- Agent card template uses `command_summary` variable — keep the same variable name but populate with summary when available
- Do NOT modify the Broadcaster class itself — just call `broadcast()` with new event types

## Git Change History

### Related Files
- Models: `turn.py`, `command.py`, `inference_call.py`, `agent.py`, `project.py`
- Services: `command_lifecycle.py`, `inference_service.py`, `broadcaster.py`
- Routes: `dashboard.py`, `inference.py`
- Templates: `_agent_card.html`
- Config: `app.py`

### OpenSpec History
- E3-S1 (2026-01-31): OpenRouter integration and inference service — prerequisite for this sprint
- Integration testing framework: Established test patterns with Factory Boy

### Implementation Patterns
- Models: SQLAlchemy declarative with `db.Model`, standard column types
- Config: Services injected via `app.extensions`
- Routes: Flask blueprints registered in `create_app()` → `register_blueprints()`
- Services: Instantiated in `create_app()`, stored in `app.extensions`
- Tests: pytest fixtures in conftest.py, integration tests use real PostgreSQL
- Existing model patterns: nullable columns for optional fields, DateTime with timezone

## Q&A History
- No clarifications needed — PRD was sufficiently detailed
- Design decision: rely on DB-level caching (Turn.summary not null → skip inference) rather than modifying E3-S1 cache TTL

## Dependencies
- No new packages required (uses existing inference service, SQLAlchemy, Flask)
- E3-S1 inference service must be available (already complete and merged)
- No external API changes (all inference goes through E3-S1's OpenRouter client)
- Database migration required (additive only — nullable columns)

## Testing Strategy
- Unit tests for SummarisationService: mock InferenceService, test prompt building, result persistence, error handling, SSE broadcasting
- Unit tests for summarisation routes: mock service, test success/404/503 responses, existing summary handling
- Integration tests: summary field persistence on Turn and Command models
- Unit tests for CommandLifecycleManager integration: verify summarisation is triggered after turn processing and command completion
- Full suite regression: all existing tests must pass

## OpenSpec References
- proposal.md: openspec/changes/e3-s2-turn-command-summarisation/proposal.md
- tasks.md: openspec/changes/e3-s2-turn-command-summarisation/tasks.md
- spec.md: openspec/changes/e3-s2-turn-command-summarisation/specs/summarisation/spec.md
