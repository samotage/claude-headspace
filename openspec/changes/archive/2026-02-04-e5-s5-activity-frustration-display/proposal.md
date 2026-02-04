## Why

The activity page displays frustration as a raw sum per hourly bucket, making busy-but-calm sessions appear more frustrated than short-but-angry sessions. Users cannot distinguish between high-volume/low-frustration and genuinely frustrating sessions. Meanwhile, real-time rolling frustration averages computed by the headspace monitor are not visible on the activity page.

## What Changes

- **Activity page metric cards:** Display average frustration per scored turn (0-10 scale, 1 decimal) instead of raw sum, at overall, project, and agent levels
- **Activity page chart:** Frustration line plots per-bucket average (0-10, fixed right Y-axis) instead of sum; gaps for buckets with no scored turns; threshold-based line coloring
- **Threshold coloring:** All frustration averages colored green/yellow/red based on configurable thresholds
- **Frustration State widget (new):** Three rolling-window indicators (Immediate ~10 turns, Short-term 30min, Session 3hr) with threshold coloring, SSE updates, hover tooltips
- **HeadspaceSnapshot model:** New `frustration_rolling_3hr` field computed by HeadspaceMonitor
- **HeadspaceMonitor service:** New `_calc_rolling_3hr()` method with configurable duration
- **Config:** New `session_rolling_window_minutes` setting under headspace section
- **Config UI:** Frustration settings section for thresholds and session window duration
- **Activity API:** Include `frustration_avg` in metrics response

## Impact

- Affected specs: activity-monitoring (frustration display changes), headspace-monitoring (new rolling window), config (new settings)
- Affected code:
  - **Modify:** `src/claude_headspace/models/headspace_snapshot.py` (add frustration_rolling_3hr field)
  - **Modify:** `src/claude_headspace/services/headspace_monitor.py` (add _calc_rolling_3hr, include in recalculate)
  - **Modify:** `src/claude_headspace/routes/headspace.py` (include frustration_rolling_3hr in /api/headspace/current)
  - **Modify:** `src/claude_headspace/routes/activity.py` (add frustration_avg to metrics response, pass session_rolling_window config)
  - **Modify:** `templates/activity.html` (frustration state widget, threshold config injection)
  - **Modify:** `static/js/activity.js` (display average instead of sum, chart changes, frustration state widget, SSE handling)
  - **Modify:** `static/css/src/input.css` (frustration state widget styles, threshold color classes)
  - **Modify:** `config.yaml` (add session_rolling_window_minutes under headspace)
  - **Modify:** `templates/config.html` (frustration settings section)
  - **Modify:** `src/claude_headspace/routes/config.py` (handle frustration config section)
  - **Migration:** New Alembic migration for frustration_rolling_3hr column
  - **Tests (update):** `tests/services/test_headspace_monitor.py`, `tests/routes/test_activity.py`, `tests/routes/test_headspace.py`
- Related OpenSpec history:
  - e1-s8-dashboard-ui (archived 2026-01-29) — established dashboard card UI
  - e2-s1-config-ui (archived 2026-01-29) — established config editor
