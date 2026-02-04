## Why

Claude Headspace monitors AI agents but not the human operator's wellbeing. Frustration builds silently during long coding sessions, degrading effectiveness. By piggybacking on the existing turn summarisation LLM call, we can extract a frustration score at near-zero additional cost and present a traffic light indicator with gentle alerts.

## What Changes

- **Turn model:** Add nullable `frustration_score` integer column (0-10) for user turns
- **Enhanced turn summarisation:** Extend prompt to return JSON with summary + frustration_score; graceful fallback on parse failure
- **HeadspaceSnapshot model:** New table for persisting rolling averages, traffic light state, flow state, and alert tracking
- **HeadspaceMonitor service:** Orchestrates rolling calculation (10-turn and 30-min averages), threshold detection (5 trigger types), alert cooldown/suppression, flow state detection, snapshot creation, and SSE broadcasting
- **Traffic light indicator:** Added to dashboard stats bar with progressive prominence (green/yellow/red)
- **Alert banner:** Dismissable banner with gentle body-focused messages and "I'm fine" 1-hour suppression
- **Flow state messages:** Periodic positive reinforcement during sustained productive periods
- **API endpoints:** GET `/api/headspace/current` and GET `/api/headspace/history`
- **SSE events:** `headspace_update`, `headspace_alert`, `headspace_flow`
- **Configuration:** New `headspace` section in config.yaml with enable/disable, thresholds, cooldown, flow detection params, and customisable messages
- **Database migration:** Add Turn.frustration_score column and create headspace_snapshots table

## Impact

- Affected specs: turn-summarisation, dashboard-ui, sse-events
- Affected code:
  - `src/claude_headspace/models/turn.py` — add frustration_score column
  - `src/claude_headspace/models/headspace_snapshot.py` — new model
  - `src/claude_headspace/models/__init__.py` — register HeadspaceSnapshot
  - `src/claude_headspace/services/summarisation_service.py` — enhance turn prompt for JSON output, parse frustration score
  - `src/claude_headspace/services/prompt_registry.py` — add frustration-aware turn prompt
  - `src/claude_headspace/services/headspace_monitor.py` — new service (rolling calc, thresholds, alerts, flow, snapshots)
  - `src/claude_headspace/routes/headspace.py` — new blueprint (API + SSE integration)
  - `src/claude_headspace/app.py` — register blueprint + initialise HeadspaceMonitor
  - `templates/partials/_header.html` — traffic light indicator in stats bar
  - `static/js/headspace.js` — client-side SSE listener for traffic light, alerts, flow messages
  - `static/css/main.css` — traffic light and alert banner styles
  - `config.yaml` — add headspace configuration section
  - `migrations/versions/k3l4m5n6o7p8_add_headspace_monitoring.py` — migration

## Definition of Done

1. User turns have frustration_score (0-10) extracted and stored within same LLM call latency
2. Traffic light indicator visible in dashboard stats bar, reflecting current frustration state
3. Traffic light is subtle when green, visible when yellow, prominent when red
4. Alert banner appears on threshold breach with randomly selected gentle message
5. Alerts dismissable; "I'm fine" suppresses for 1 hour
6. Alert cooldown (10 min default) prevents rapid re-triggering
7. Flow state detected when turn rate > 6/hr and frustration < 3 for 15+ min
8. Positive reinforcement messages appear every 15 min during flow
9. HeadspaceSnapshot persisted after each recalculation with 7-day retention
10. GET `/api/headspace/current` returns full headspace state
11. GET `/api/headspace/history` returns time-series with filtering
12. Headspace monitoring configurable/disableable via config.yaml
13. Graceful degradation: malformed LLM response preserves normal turn summary with null frustration_score
14. All updates delivered via SSE (no page refresh required)
