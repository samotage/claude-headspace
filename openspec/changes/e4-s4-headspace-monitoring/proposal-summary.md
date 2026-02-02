# Proposal Summary: e4-s4-headspace-monitoring

## Architecture Decisions
- Use integer PKs for HeadspaceSnapshot (matching codebase convention, not UUID as PRD suggests)
- Frustration extraction piggybacks on existing turn summarisation LLM call — enhanced prompt returns JSON `{"summary": "...", "frustration_score": N}`
- Graceful fallback: if JSON parse fails, treat entire response as plain text summary with null frustration_score
- HeadspaceMonitor is a stateful service (not a background thread) — it's triggered on each user turn after summarisation completes
- Alert cooldown and suppression state maintained in-memory on the service instance (acceptable for MVP; resets on server restart)
- Traffic light indicator added to the existing stats bar in _header.html
- Flow state detection calculates turn rate directly from Turn timestamps (no dependency on E4-S3 ActivityMetric)

## Implementation Approach
- **Data layer first:** Add Turn.frustration_score column, create HeadspaceSnapshot model, create migration
- **Prompt enhancement:** Add new frustration-aware prompt template to prompt_registry.py; modify summarise_turn to use it for USER turns when headspace is enabled, parse JSON response
- **Core service:** HeadspaceMonitor service handles all logic — rolling averages, threshold detection, alert management, flow detection, snapshot persistence, SSE broadcasting
- **Integration:** After summarise_turn extracts frustration_score, it calls headspace_monitor.recalculate(turn) to trigger the full pipeline
- **UI:** Traffic light in stats bar updated via SSE; alert banners and flow toasts rendered client-side from SSE events
- **Configuration:** New headspace section in config.yaml with defaults matching PRD specifications

## Files to Modify
- Models:
  - `src/claude_headspace/models/turn.py` — add frustration_score column
  - `src/claude_headspace/models/headspace_snapshot.py` — new model
  - `src/claude_headspace/models/__init__.py` — register HeadspaceSnapshot
- Services:
  - `src/claude_headspace/services/prompt_registry.py` — add frustration-aware turn prompt
  - `src/claude_headspace/services/summarisation_service.py` — enhanced JSON parsing for user turns
  - `src/claude_headspace/services/headspace_monitor.py` — new service (core logic)
- Routes:
  - `src/claude_headspace/routes/headspace.py` — new blueprint (API endpoints)
  - `src/claude_headspace/app.py` — register blueprint + init service
- Templates/Static:
  - `templates/partials/_header.html` — traffic light indicator in stats bar
  - `static/js/headspace.js` — SSE listeners for traffic light, alerts, flow messages
  - `static/css/main.css` — traffic light and alert banner styles
- Config:
  - `config.yaml` — headspace section
- Migration:
  - `migrations/versions/k3l4m5n6o7p8_add_headspace_monitoring.py`

## Acceptance Criteria
1. User turns have frustration_score (0-10) extracted within same LLM call latency
2. Traffic light indicator in stats bar reflects current state (green/yellow/red)
3. Progressive prominence: subtle green, visible yellow, prominent red
4. Alert banner on threshold breach with randomly selected gentle message
5. Dismiss closes banner; "I'm fine" suppresses for 1 hour
6. 10-minute default cooldown between consecutive alerts
7. Flow state detected when turn rate > 6/hr, frustration < 3, sustained 15+ min
8. Flow messages every 15 minutes during sustained flow
9. HeadspaceSnapshot persisted after each recalculation, 7-day retention with pruning
10. GET /api/headspace/current returns full state
11. GET /api/headspace/history returns filtered time-series
12. Configurable/disableable via config.yaml
13. Graceful degradation on malformed LLM response
14. All updates via SSE (no page refresh)

## Constraints and Gotchas
- **JSON parse fallback is critical:** The existing summarisation must never break if JSON parsing fails. Always wrap in try/except with fallback to treating the raw response as the summary
- **Prompt registry pattern:** All prompts go through `build_prompt()` in prompt_registry.py — don't build prompts inline
- **Inference paused check:** Must respect `project.inference_paused` flag from E4-S2 Project Controls
- **SSE event types:** Use broadcaster.broadcast() with the three new event types (headspace_update, headspace_alert, headspace_flow)
- **Stats bar integration:** The traffic light goes INTO the existing stats bar div, not a separate element
- **Integer PKs:** Use integer PK for HeadspaceSnapshot (not UUID as PRD suggests) to match codebase convention
- **Nullable rolling averages:** frustration_rolling_30min can be null when no turns exist in window — handle in both service and API response
- **Thread safety:** HeadspaceMonitor state (cooldown, suppression) must be thread-safe since it may be called from hook processing threads

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/turn.py`, `src/claude_headspace/models/__init__.py`
- Services: `src/claude_headspace/services/summarisation_service.py`, `src/claude_headspace/services/prompt_registry.py`, `src/claude_headspace/services/broadcaster.py`
- Routes: `src/claude_headspace/routes/` (pattern reference)
- Templates: `templates/partials/_header.html` (stats bar)
- Static: `static/js/dashboard-sse.js` (SSE pattern reference), `static/css/main.css`
- Config: `config.yaml`

### OpenSpec History
- No previous OpenSpec changes to this subsystem

### Implementation Patterns
- Model pattern: Integer PK, mapped_column, DateTime(timezone=True), ForeignKey with CASCADE
- Service pattern: Constructor takes dependencies (app, config, inference_service), registered in app.extensions
- Route pattern: Flask Blueprint, registered in app.py register_blueprints()
- Prompt pattern: Templates in prompt_registry.py, accessed via build_prompt()
- SSE pattern: broadcaster.broadcast(event_type, data_dict)

## Q&A History
- No clarifications needed. PRD was sufficiently detailed and internally consistent.
- Decision: Use integer PK for HeadspaceSnapshot instead of UUID (PRD suggests UUID but codebase convention uses integers)

## Dependencies
- No new packages required
- Uses existing OpenRouter/inference infrastructure
- Uses existing SSE/broadcaster infrastructure
- Database migration: add column to turns table + new headspace_snapshots table

## Testing Strategy
- Unit tests for HeadspaceMonitor: rolling average edge cases, all 5 threshold triggers, cooldown logic, suppression logic, flow state entry/exit/periodic messages
- Unit tests for enhanced summarisation: JSON parse success, JSON parse failure fallback, headspace-disabled passthrough
- Route tests for /api/headspace/current and /api/headspace/history endpoints
- All tests mock the database layer (unit tests don't need real DB)

## OpenSpec References
- proposal.md: openspec/changes/e4-s4-headspace-monitoring/proposal.md
- tasks.md: openspec/changes/e4-s4-headspace-monitoring/tasks.md
- spec.md: openspec/changes/e4-s4-headspace-monitoring/specs/headspace-monitoring/spec.md
