# Proposal Summary: e4-s3-activity-monitoring

## Architecture Decisions
- Use integer PKs for ActivityMetric model (matches all existing models)
- Background aggregation via daemon thread following AgentReaper pattern (init/start/stop/_loop)
- Hourly bucket granularity stored in PostgreSQL (no dedicated time-series DB needed)
- Chart.js loaded via CDN for time-series visualization (vanilla JS, no build step)
- Upsert strategy for metric records (update existing bucket, don't create duplicates)
- 30-day retention with automatic pruning as part of each aggregation pass
- API endpoints accept `?window=day|week|month` query parameter

## Implementation Approach
- New ActivityMetric model with composite indexes for efficient time-range queries
- ActivityAggregator service runs every 5 minutes, queries Turn records, computes metrics at agent/project/overall levels
- Metrics stored in hourly buckets; each record scoped to exactly one of: agent, project, or overall
- Activity page fetches data from API endpoints client-side (same pattern as Projects page)
- Chart.js renders time-series line chart with toggle for day/week/month view windows

## Files to Modify
- Models:
  - `src/claude_headspace/models/activity_metric.py` — **NEW** ActivityMetric model
  - `src/claude_headspace/models/__init__.py` — add ActivityMetric export
- Services:
  - `src/claude_headspace/services/activity_aggregator.py` — **NEW** background aggregation service
- Routes:
  - `src/claude_headspace/routes/activity.py` — **NEW** Activity page + API endpoints
- App:
  - `src/claude_headspace/app.py` — register blueprint, start/stop aggregator
- Templates:
  - `templates/activity.html` — **NEW** Activity page
  - `templates/partials/_header.html` — add "Activity" tab to navigation
- Static:
  - `static/js/activity.js` — **NEW** Chart.js integration + metrics display
- Migrations:
  - `migrations/versions/xxx_create_activity_metrics.py` — **NEW** create activity_metrics table
- Tests:
  - `tests/routes/test_activity.py` — **NEW** route tests
  - `tests/services/test_activity_aggregator.py` — **NEW** service tests

## Acceptance Criteria
- Turn rate (turns/hour) displayed per agent on Activity page
- Average turn time displayed per agent on Activity page
- Project-level metrics aggregate from all agents within project
- Overall metrics aggregate from all projects
- Time-series chart with day/week/month toggle
- Hover tooltips show exact values and time period
- Metrics API endpoints return current + historical data
- Automatic aggregation every 5 minutes
- Records older than 30 days automatically pruned
- "Activity" tab in header navigation with active state
- Empty states display gracefully

## Constraints and Gotchas
- PRD recommends UUID PKs but codebase uses integer PKs — use integer PKs
- `status_counts` context must be provided by page route for header stats bar
- Header navigation active state detection via `request.endpoint`
- Agent and Project models use integer IDs — FK references must match
- Turn model `created_at` field is the timestamp for turn timing calculations
- Chart.js CDN must be loaded before activity.js
- Aggregation must use app context (`with self._app.app_context()`) for DB access in background thread
- Upsert logic needs care: use `INSERT ... ON CONFLICT` or query-then-update pattern

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/agent.py`, `src/claude_headspace/models/turn.py`, `src/claude_headspace/models/project.py`
- Services: `src/claude_headspace/services/agent_reaper.py` (background thread pattern reference)
- Routes: `src/claude_headspace/routes/projects.py` (page route + API pattern reference)
- Templates: `templates/projects.html` (page template reference), `templates/partials/_header.html` (navigation)
- Static: `static/js/projects.js` (vanilla JS pattern reference)

### OpenSpec History
- 2026-02-02: e4-s2a-project-controls-backend — Backend API, migration, inference gating (PR #32)
- 2026-02-02: e4-s2b-project-controls-ui — Projects page UI (PR #33)

### Implementation Patterns
- Page routes render templates with server-side `status_counts` context
- JavaScript fetches API data on DOMContentLoaded
- Background services follow AgentReaper pattern: `__init__`, `start`, `stop`, `_loop`
- Models use integer PKs, SQLAlchemy mapped_column, Flask-SQLAlchemy db.Model
- Active tab detection via `request.endpoint` in Jinja2 conditionals

## Q&A History
- No clarifications needed — PRD is comprehensive with explicit data model, API schema, formulas, and UI wireframes

## Dependencies
- Chart.js CDN (external JS library for charting — loaded via `<script>` tag, no npm)
- No new Python packages required
- Alembic migration for new table

## Testing Strategy
- Route tests: GET /activity returns 200, API endpoints return correct JSON structure, 404 for nonexistent entities, window param validation
- Service tests: aggregate_once produces correct counts, avg turn time calculation, project/overall rollup, prune removes old records, upsert prevents duplicates

## OpenSpec References
- proposal.md: openspec/changes/e4-s3-activity-monitoring/proposal.md
- tasks.md: openspec/changes/e4-s3-activity-monitoring/tasks.md
- spec.md: openspec/changes/e4-s3-activity-monitoring/specs/activity-monitoring/spec.md
