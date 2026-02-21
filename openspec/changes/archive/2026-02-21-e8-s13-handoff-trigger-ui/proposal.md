# Proposal: e8-s13-handoff-trigger-ui

## Why

When a persona agent's context window fills up, the operator needs a clear visual signal and a deliberate mechanism to trigger handoff to a fresh successor agent. Currently, context monitoring (E6-S4) tracks usage and displays warning/high tiers, but there's no handoff-specific indicator or trigger control. This sprint adds the operator-facing bridge between context pressure detection and the handoff execution engine (E8-S14).

## What Changes

### Configuration
- Add `handoff_threshold` to `context_monitor` config section (default 80%, configurable down to 10% for testing)

### Card State Service
- Extend `build_card_state()` to compute handoff eligibility (persona + context data + threshold exceeded)
- Add `handoff_eligible` (boolean) and `handoff_threshold` (integer) fields to card state JSON context block

### Dashboard Template
- Add conditional "Handoff" button to agent card template (visible only when handoff-eligible)
- Add handoff tier visual indicator to context bar (third tier above warning/high)

### Client-Side JavaScript
- Extend SSE `card_refresh` handler to update handoff button visibility and context bar handoff indicator
- Add click handler for handoff button: POST to `/api/agents/<id>/handoff` with loading state

## Impact

### Modified Files
- `src/claude_headspace/services/card_state.py` — add handoff eligibility computation and fields to context block
- `src/claude_headspace/config.py` — add handoff_threshold default to config defaults
- `templates/partials/_agent_card.html` — add handoff button and context bar handoff tier
- `static/js/dashboard-sse.js` — extend card_refresh handler for handoff fields
- `static/css/src/input.css` — add handoff-specific CSS classes (context bar tier, button styles)

### Unchanged Files
- `src/claude_headspace/models/agent.py` — no model changes (uses existing context_percent_used, persona_id)
- `src/claude_headspace/services/context_poller.py` — no changes to polling logic
- Warning/high threshold behaviour unchanged

### Dependencies
- E8-S12 (Handoff model) — merged, provides data model for handoff records
- E8-S10 (Card persona identity) — merged, provides persona_name/persona_role in card state
- E6-S4 (Context monitoring) — merged, provides context_percent_used field and context poller

### Recent OpenSpec History
- e8-s12-handoff-model — Handoff database model (just completed)
- e8-s10-card-persona-identity — Persona identity fields in card state
- e6-s4-context-monitoring — Context percentage tracking infrastructure

## Definition of Done

1. Handoff threshold is configurable in `context_monitor` config section (default 80%)
2. Threshold can be set as low as 10% for testing
3. `build_card_state()` includes `handoff_eligible` and `handoff_threshold` in context block
4. Handoff button appears on persona agent cards when context >= threshold
5. Handoff button does NOT appear on anonymous agents, below-threshold agents, or agents without context data
6. Context bar shows handoff indicator tier (visually distinct from warning/high)
7. Button click sends POST to `/api/agents/<id>/handoff` with loading state
8. SSE card_refresh updates handoff button visibility and context bar indicator in real-time
9. No additional database queries beyond existing eager-loaded relationships
