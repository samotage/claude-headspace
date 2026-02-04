# Proposal Summary: e5-s5-activity-frustration-display

## Architecture Decisions
- Compute frustration average at display time from existing `total_frustration` and `frustration_turn_count` fields — no ActivityMetric model or aggregator changes needed
- Add `frustration_rolling_3hr` to HeadspaceSnapshot as a new computed field alongside existing `frustration_rolling_10` and `frustration_rolling_30min`
- Session rolling window duration configurable via `headspace.session_rolling_window_minutes` in config.yaml (default 180 minutes / 3 hours)
- All threshold values read from config at runtime — injected into template via `window.FRUSTRATION_THRESHOLDS` (already exists, extend with session window config)
- Frustration state widget on activity page reuses existing SSE `headspace_update` events — no new SSE connections or event types

## Implementation Approach
- **Backend-first:** Add migration + model field + HeadspaceMonitor computation + API response changes
- **Frontend-second:** Modify activity.js to display averages instead of sums, then add frustration state widget
- **Config UI last:** Extend config editor with frustration settings section
- Threshold coloring applied consistently across cards, chart, and widget using shared threshold constants from config

## Files to Modify

### Modified Files
- `src/claude_headspace/models/headspace_snapshot.py` — add `frustration_rolling_3hr: Mapped[float | None]`
- `src/claude_headspace/services/headspace_monitor.py` — add `_calc_rolling_3hr()`, include in `recalculate()`, read `session_rolling_window_minutes` from config
- `src/claude_headspace/routes/headspace.py` — include `frustration_rolling_3hr` in `/api/headspace/current` response
- `src/claude_headspace/routes/activity.py` — compute and include `frustration_avg` in metrics API; pass threshold config and session window config to template
- `src/claude_headspace/routes/config.py` — handle headspace.session_rolling_window_minutes in config editor
- `templates/activity.html` — add frustration state widget HTML, inject session_rolling_window config
- `templates/config.html` — add frustration settings section (thresholds + session window duration)
- `static/js/activity.js` — display average instead of sum in cards; chart with fixed 0-10 Y-axis and gaps; frustration state widget with SSE updates and tooltips
- `static/css/src/input.css` — frustration state widget styles, threshold color utility classes
- `config.yaml` — add `session_rolling_window_minutes: 180` under headspace section

### New Files
- Alembic migration for `frustration_rolling_3hr` column

### Updated Test Files
- `tests/services/test_headspace_monitor.py` — test _calc_rolling_3hr, recalculate inclusion, config reading
- `tests/routes/test_activity.py` — test frustration_avg in API response
- `tests/routes/test_headspace.py` — test frustration_rolling_3hr in /api/headspace/current

## Acceptance Criteria
1. Activity page metric cards show average frustration (0-10, 1 decimal) instead of sum, with threshold coloring
2. Chart frustration line plots per-bucket average on fixed 0-10 Y-axis with gaps for no-data buckets
3. Frustration state widget shows three rolling-window indicators (Immediate, Short-term, Session) with threshold coloring
4. Widget updates in real-time via existing SSE headspace_update events
5. Widget hidden when headspace monitoring is disabled
6. All thresholds and window durations sourced from config (no hardcoded values)
7. Config UI includes frustration settings section

## Constraints and Gotchas
- **ActivityMetric model is NOT changed** — average is computed at display time from existing `total_frustration` and `frustration_turn_count` fields
- **Activity aggregator is NOT changed** — no new aggregation logic
- **HeadspaceSnapshot already has rolling_10 and rolling_30min** — follow exact same pattern for rolling_3hr
- **Chart gaps:** Chart.js supports `null` data points to create line gaps — use this approach
- **Right Y-axis fixed at 0-10:** Override Chart.js auto-scaling for the frustration axis
- **Threshold coloring on chart line:** Chart.js `segment` plugin or gradient coloring can color line segments by value
- **SSE reuse:** The `headspace_update` event already broadcasts rolling_10 and rolling_30min — just add rolling_3hr to the same payload
- **Config UI already handles headspace section** — extend with session_rolling_window_minutes input
- **Tailwind CSS build required** after adding custom styles — use `npx tailwindcss` (v3, NOT v4)
- **Week/month aggregation in JS** — currently sums hourly buckets; for average display, must sum total_frustration and frustration_turn_count separately then divide

## Git Change History

### Related Files
- Models: `headspace_snapshot.py`, `activity_metric.py` (read-only reference)
- Services: `headspace_monitor.py`, `activity_aggregator.py` (read-only reference)
- Routes: `activity.py`, `headspace.py`, `config.py`
- Templates: `activity.html`, `config.html`
- Static: `activity.js`, `input.css`
- Config: `config.yaml`

### OpenSpec History
- e1-s8-dashboard-ui (archived 2026-01-29) — established dashboard card UI
- e2-s1-config-ui (archived 2026-01-29) — established config editor UI
- e4-s2b-project-controls-ui (archived 2026-02-02) — project controls UI

### Implementation Patterns
- HeadspaceMonitor follows internal method pattern: `_calc_rolling_10()`, `_calc_rolling_30min()` → add `_calc_rolling_3hr()`
- Config reading: `config.get("headspace", {}).get("session_rolling_window_minutes", 180)`
- Route template context: `frustration_thresholds` dict already injected, extend with session_rolling_window
- SSE handling in activity.js: already listens for headspace events (check existing patterns)

## Q&A History
- No clarifications needed — PRD is comprehensive with clear scope boundaries

## Dependencies
- No new Python packages required
- No external API changes
- Database migration: new nullable float column on headspace_snapshots

## Testing Strategy
- **Unit tests for HeadspaceMonitor:** Test `_calc_rolling_3hr()` with various turn distributions, test config reading, test inclusion in recalculate flow
- **Route tests for activity API:** Test `frustration_avg` field in metrics response, test em-dash handling for zero turn count
- **Route tests for headspace API:** Test `frustration_rolling_3hr` in current state response
- **Manual verification:** Check activity page displays averages, chart renders correctly with gaps, widget updates via SSE

## OpenSpec References
- proposal.md: openspec/changes/e5-s5-activity-frustration-display/proposal.md
- tasks.md: openspec/changes/e5-s5-activity-frustration-display/tasks.md
- specs/activity-monitoring/spec.md: openspec/changes/e5-s5-activity-frustration-display/specs/activity-monitoring/spec.md
- specs/headspace-monitoring/spec.md: openspec/changes/e5-s5-activity-frustration-display/specs/headspace-monitoring/spec.md
- specs/config/spec.md: openspec/changes/e5-s5-activity-frustration-display/specs/config/spec.md
