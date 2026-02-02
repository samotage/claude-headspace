## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 ActivityMetric Model

- [ ] 2.1.1 Create `src/claude_headspace/models/activity_metric.py` with:
  - Integer PK (matching existing model pattern)
  - `bucket_start` (datetime) — start of hourly time bucket
  - `agent_id` (FK, nullable) — scope to agent
  - `project_id` (FK, nullable) — scope to project
  - `is_overall` (bool, default False) — scope to system-wide
  - `turn_count` (int) — number of turns in bucket
  - `avg_turn_time_seconds` (float, nullable) — mean time between turns
  - `active_agents` (int, nullable) — for project/overall scope
  - `created_at` (datetime)
  - Composite indexes: (agent_id, bucket_start), (project_id, bucket_start), (is_overall, bucket_start)

- [ ] 2.1.2 Add `ActivityMetric` to `models/__init__.py` exports

- [ ] 2.1.3 Create Alembic migration for `activity_metrics` table

### 2.2 Activity Aggregator Service

- [ ] 2.2.1 Create `src/claude_headspace/services/activity_aggregator.py` with:
  - Background thread following AgentReaper pattern (init, start, stop, _loop)
  - Configurable interval (default 300 seconds / 5 minutes)
  - `aggregate_once()` method that:
    - Queries Turn records for the current hour bucket
    - Computes turn_count and avg_turn_time_seconds per agent
    - Rolls up to project-level and overall-level metrics
    - Upserts ActivityMetric records (update if bucket already exists)
  - `prune_old_records()` method that deletes records older than 30 days
  - Prune runs as part of each aggregation pass

### 2.3 Activity Routes

- [ ] 2.3.1 Create `src/claude_headspace/routes/activity.py` with:
  - `GET /activity` page route (renders activity.html with status_counts)
  - `GET /api/metrics/agents/<int:agent_id>` — current + historical metrics for agent
  - `GET /api/metrics/projects/<int:project_id>` — aggregated metrics for project
  - `GET /api/metrics/overall` — system-wide aggregated metrics
  - All API endpoints accept `?window=day|week|month` query param (default: day)
  - Return JSON with `current` (latest bucket) and `history` (time-series array)

### 2.4 App Registration

- [ ] 2.4.1 Register `activity_bp` blueprint in `app.py`
- [ ] 2.4.2 Initialize and start `ActivityAggregator` in app startup, stop on teardown

### 2.5 Activity Page Template

- [ ] 2.5.1 Create `templates/activity.html` with:
  - Overall summary panel (system-wide turn rate, avg turn time, active agents)
  - Time-series chart container with day/week/month toggle buttons
  - Project sections with per-project and per-agent metrics
  - Empty state message when no activity data exists
  - Script tag loading Chart.js from CDN and activity.js

### 2.6 Activity JavaScript

- [ ] 2.6.1 Create `static/js/activity.js` with:
  - Fetch overall metrics on DOMContentLoaded
  - Render Chart.js line chart with turn count time-series
  - Day/week/month toggle buttons that re-fetch and re-render chart
  - Hover tooltips showing exact values and time period
  - Fetch and render project/agent metric panels
  - Handle empty state display

### 2.7 Header Navigation

- [ ] 2.7.1 Add "Activity" tab to `templates/partials/_header.html` (desktop + mobile)

## 3. Testing (Phase 3)

### 3.1 Route Tests

- [ ] 3.1.1 Create `tests/routes/test_activity.py` with:
  - Test GET /activity returns 200
  - Test GET /api/metrics/overall returns 200 with correct structure
  - Test GET /api/metrics/agents/<id> returns 404 for nonexistent agent
  - Test GET /api/metrics/projects/<id> returns 404 for nonexistent project
  - Test window parameter validation

### 3.2 Service Tests

- [ ] 3.2.1 Create `tests/services/test_activity_aggregator.py` with:
  - Test aggregate_once produces correct turn counts
  - Test aggregate_once computes correct avg turn time
  - Test project-level rollup from agent metrics
  - Test overall-level rollup from project metrics
  - Test prune_old_records removes records older than 30 days
  - Test upsert behavior (existing bucket updated, not duplicated)

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
