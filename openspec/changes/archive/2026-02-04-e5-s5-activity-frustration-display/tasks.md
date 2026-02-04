## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Backend — Model & Migration

- [x] 2.1.1 Create Alembic migration to add `frustration_rolling_3hr` nullable float column to `headspace_snapshots` table
- [x] 2.1.2 Update HeadspaceSnapshot model (`models/headspace_snapshot.py`) to add `frustration_rolling_3hr` mapped column

### 2.2 Backend — HeadspaceMonitor

- [x] 2.2.1 Add `_calc_rolling_3hr()` method to HeadspaceMonitor: query scored USER turns within configurable window (default 180 minutes), return average or None
- [x] 2.2.2 Read `session_rolling_window_minutes` from config (default 180) in `__init__`
- [x] 2.2.3 Include `frustration_rolling_3hr` in `recalculate()` flow — compute and store on HeadspaceSnapshot
- [x] 2.2.4 Include `frustration_rolling_3hr` in SSE `headspace_update` broadcast payload

### 2.3 Backend — Routes

- [x] 2.3.1 Update `routes/headspace.py`: include `frustration_rolling_3hr` in `/api/headspace/current` response
- [x] 2.3.2 Update `routes/activity.py`: compute `frustration_avg` (total_frustration / frustration_turn_count) in metrics API responses; pass `session_rolling_window_minutes` and thresholds to template context
- [x] 2.3.3 Update `routes/config.py`: handle frustration settings in config editor (session_rolling_window_minutes under headspace section)

### 2.4 Backend — Config

- [x] 2.4.1 Update `config.yaml`: add `session_rolling_window_minutes: 180` under headspace section

### 2.5 Frontend — Activity Page Metric Cards

- [x] 2.5.1 Update `static/js/activity.js`: display `frustration_avg` (from API or computed client-side as total/count) instead of raw sum in metric cards; format to 1 decimal place
- [x] 2.5.2 Apply threshold coloring to frustration values: green (< yellow_threshold), yellow (>= yellow, < red), red (>= red)
- [x] 2.5.3 Display "—" (em dash) when no scored turns exist (frustration_turn_count is 0 or null)

### 2.6 Frontend — Activity Page Chart

- [x] 2.6.1 Update chart frustration line to plot per-bucket average (total_frustration / frustration_turn_count) instead of sum
- [x] 2.6.2 Set right Y-axis to fixed 0-10 scale
- [x] 2.6.3 Render gaps in frustration line for buckets with no scored turns
- [x] 2.6.4 Apply threshold-based coloring to frustration line segments or data points

### 2.7 Frontend — Frustration State Widget

- [x] 2.7.1 Add frustration state widget HTML to `templates/activity.html` — three indicators (Immediate, Short-term, Session) with threshold coloring
- [x] 2.7.2 Add frustration state widget JavaScript to `static/js/activity.js` — fetch initial state from `/api/headspace/current`, update via SSE `headspace_update` events
- [x] 2.7.3 Display "—" for null rolling window values; hide widget when headspace monitoring disabled
- [x] 2.7.4 Add hover tooltips showing threshold boundaries (e.g., "Green: < 4 | Yellow: 4-7 | Red: > 7")

### 2.8 Frontend — Config UI

- [x] 2.8.1 Add frustration settings section to `templates/config.html` showing yellow threshold, red threshold, and session rolling window duration
- [x] 2.8.2 Ensure all threshold values in activity page JS come from config (injected via template), not hardcoded

### 2.9 Frontend — CSS

- [x] 2.9.1 Add frustration state widget styles to `static/css/src/input.css` (threshold color classes, widget layout)
- [x] 2.9.2 Rebuild Tailwind CSS output

## 3. Testing (Phase 3)

- [x] 3.1 Update `tests/services/test_headspace_monitor.py` — test `_calc_rolling_3hr()`, test inclusion in recalculate flow, test config reading
- [x] 3.2 Update `tests/routes/test_activity.py` — test `frustration_avg` in API response, test template context
- [x] 3.3 Update `tests/routes/test_headspace.py` — test `frustration_rolling_3hr` in `/api/headspace/current` response

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete (check activity page displays average, chart renders correctly, widget updates via SSE)
