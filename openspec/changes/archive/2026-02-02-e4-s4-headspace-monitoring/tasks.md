## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Data Layer

- [x] 2.1.1 Add frustration_score column to Turn model
- [x] 2.1.2 Create HeadspaceSnapshot model (integer PK, timestamp, rolling averages, state, turn rate, flow state, flow duration, last alert at, alert count today, created_at)
- [x] 2.1.3 Register HeadspaceSnapshot in models/__init__.py
- [x] 2.1.4 Create database migration (add Turn.frustration_score + create headspace_snapshots table with indexes)

### Frustration Score Extraction

- [x] 2.2.1 Add frustration-aware turn summarisation prompt to prompt_registry.py (JSON output: summary + frustration_score)
- [x] 2.2.2 Modify summarise_turn in summarisation_service.py to use enhanced prompt for USER turns when headspace enabled, parse JSON response, extract frustration_score, fall back to plain text on parse failure
- [x] 2.2.3 After successful frustration extraction, trigger headspace recalculation

### HeadspaceMonitor Service

- [x] 2.3.1 Create headspace_monitor.py service with:
  - Configuration loading from config.yaml headspace section
  - In-memory state: alert cooldown, suppression until, flow state start time, last alert type/time
  - `recalculate(turn)` method: compute rolling averages, determine traffic light state, check thresholds, detect flow state
  - Rolling average calculations: last 10 scored user turns, last 30 minutes scored user turns
  - Traffic light state from higher of two averages
  - Threshold detection: absolute spike, sustained yellow, sustained red, rising trend, time-based
  - Alert triggering with cooldown and suppression logic
  - Flow state detection from turn rate + frustration + duration
  - Snapshot creation and opportunistic pruning
  - SSE broadcasting via broadcaster (headspace_update, headspace_alert, headspace_flow)

### Routes

- [x] 2.4.1 Create headspace.py blueprint with:
  - GET `/api/headspace/current` — latest headspace state
  - GET `/api/headspace/history` — time-series with ?since and ?limit params
- [x] 2.4.2 Register headspace blueprint in app.py
- [x] 2.4.3 Initialise HeadspaceMonitor service in app.py, store in app.extensions

### UI: Traffic Light Indicator

- [x] 2.5.1 Add traffic light indicator to stats bar in _header.html (headspace-indicator element)
- [x] 2.5.2 Add CSS styles for traffic light states (green subtle dot, yellow visible, red prominent) with smooth transitions

### UI: Alert Banner & Flow Messages

- [x] 2.6.1 Add alert banner HTML to base template or header (hidden by default, below stats bar)
- [x] 2.6.2 Create static/js/headspace.js — SSE listener for headspace_update (traffic light), headspace_alert (show banner), headspace_flow (show flow toast)
- [x] 2.6.3 Add dismiss and "I'm fine" button handlers (POST to suppress endpoint or client-side SSE)

### Configuration

- [x] 2.7.1 Add headspace section to config.yaml with all configurable values

## 3. Testing (Phase 3)

- [x] 3.1.1 Unit tests for HeadspaceMonitor: rolling average calculations, threshold detection, alert cooldown/suppression, flow state detection
- [x] 3.1.2 Unit tests for enhanced summarisation: JSON parse success, JSON parse fallback, headspace disabled bypass
- [x] 3.2.1 Route tests for /api/headspace/current and /api/headspace/history endpoints

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
