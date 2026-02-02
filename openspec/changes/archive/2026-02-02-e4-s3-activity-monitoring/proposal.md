## Why

The dashboard shows agent state and priority scores but lacks quantitative activity data. Operators cannot see turn rates, average turn times, or workload distribution across agents and projects without manually inspecting logs. Activity Monitoring introduces computed metrics with time-series storage, periodic aggregation, and a dedicated Activity page with interactive charts.

## What Changes

- New model: `ActivityMetric` with hourly bucket time-series storage (integer PK, matching existing pattern)
- New service: `ActivityAggregator` background thread (follows AgentReaper pattern) running every 5 minutes
- New service function: retention pruning of records older than 30 days
- New routes blueprint: `activity_bp` with page route and 3 API endpoints (agent, project, overall metrics)
- New template: `templates/activity.html` Activity page with overall summary, Chart.js time-series chart, project/agent metrics
- New JS: `static/js/activity.js` for chart rendering and time window toggles
- Modify: `templates/partials/_header.html` to add "Activity" tab
- Modify: `src/claude_headspace/models/__init__.py` to export ActivityMetric
- Modify: `src/claude_headspace/app.py` to register activity blueprint and start aggregator service
- New migration: create `activity_metrics` table with composite indexes
- New tests: route tests, service unit tests, model tests

## Impact

- Affected specs: activity-monitoring (new capability)
- Affected code:
  - `src/claude_headspace/models/activity_metric.py` — **NEW** ActivityMetric model
  - `src/claude_headspace/models/__init__.py` — add ActivityMetric export
  - `src/claude_headspace/services/activity_aggregator.py` — **NEW** background aggregation service
  - `src/claude_headspace/routes/activity.py` — **NEW** Activity page + API routes
  - `src/claude_headspace/app.py` — register blueprint, start/stop aggregator
  - `templates/activity.html` — **NEW** Activity page template
  - `static/js/activity.js` — **NEW** Chart.js integration + metrics display
  - `templates/partials/_header.html` — add "Activity" tab to navigation
  - `migrations/versions/xxx_create_activity_metrics.py` — **NEW** migration
  - `tests/routes/test_activity.py` — **NEW** route tests
  - `tests/services/test_activity_aggregator.py` — **NEW** service tests
