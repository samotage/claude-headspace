# Proposal Summary: e8-s13-handoff-trigger-ui

## Architecture Decisions
- Operator-initiated handoff only (Workshop Decision 5.1) — no auto-trigger in v1
- Handoff eligibility is a lightweight boolean computation during existing card state building — no new DB queries
- Handoff threshold added to existing `context_monitor` config section (not a new section)
- Client-side POST to handoff endpoint (E8-S14 defines the handler) — this sprint handles trigger UI only
- Three-tier context bar progression reuses existing threshold infrastructure, adding handoff as a fourth tier

## Implementation Approach
- Extend `build_card_state()` to add `handoff_eligible` and `handoff_threshold` to the existing context block
- Add `handoff_threshold` default (80) to config defaults in config.py
- Conditional Jinja2 rendering for handoff button in agent card template
- Extend SSE `handleCardRefresh()` for handoff button visibility and context bar handoff tier
- CSS classes in input.css for handoff-specific styling (context bar tier + button states)
- POST handler sends `{ "reason": "context_limit" }` to `/api/agents/<id>/handoff`

## Files to Modify
- **Services:** `src/claude_headspace/services/card_state.py` — handoff eligibility computation + card state fields
- **Config:** `src/claude_headspace/config.py` — handoff_threshold default
- **Templates:** `templates/partials/_agent_card.html` — handoff button + context bar handoff tier
- **JavaScript:** `static/js/dashboard-sse.js` — SSE card_refresh handler + button click handler
- **CSS:** `static/css/src/input.css` — handoff styling classes

## Acceptance Criteria
1. Handoff threshold configurable in context_monitor config (default 80%, min 10%)
2. build_card_state() includes handoff_eligible + handoff_threshold in context block
3. Handoff button visible on persona agent cards when context >= threshold
4. Button hidden for anonymous agents, below-threshold, or no context data
5. Context bar shows handoff indicator tier (distinct from warning/high)
6. Button click sends POST to /api/agents/<id>/handoff with loading state
7. SSE updates handoff button and context bar in real-time
8. No additional database queries
9. No changes to existing warning/high threshold behaviour

## Constraints and Gotchas
- The POST endpoint `/api/agents/<id>/handoff` does not exist yet (E8-S14) — button will get 404 until E8-S14 is built. This is expected.
- Handoff eligibility uses `agent.persona_id` (not `agent.persona`) to avoid lazy-loading — check if persona relationship is eager-loaded in card state context
- Context bar handoff tier only applies to persona agents — anonymous agents must NOT get handoff styling even if above threshold
- CSS must be rebuilt after adding to input.css (`npx tailwindcss -i static/css/src/input.css -o static/css/main.css`)
- The `_get_context_config()` helper already exists in card_state.py — extend it to read handoff_threshold

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/card_state.py`
- Config: `src/claude_headspace/config.py`
- Templates: `templates/partials/_agent_card.html`
- JavaScript: `static/js/dashboard-sse.js`
- CSS: `static/css/src/input.css`
- Models: `src/claude_headspace/models/agent.py` (read-only — context fields, persona_id)

### OpenSpec History
- e8-s12-handoff-model — Handoff database model (just completed, PR #76)
- e8-s10-card-persona-identity — Persona identity fields in card state
- e6-s4-context-monitoring — Context percentage tracking infrastructure
- e8-s4-agent-model-extensions — persona_id, position_id, previous_agent_id on Agent

### Implementation Patterns
- Card state building: extend `build_card_state()` dict with new fields in context block
- Config defaults: add to DEFAULTS dict in config.py under `context_monitor` section
- Template: conditional Jinja2 blocks for button rendering
- SSE handler: extend `handleCardRefresh()` to read new context fields and update DOM
- CSS: custom classes in input.css, rebuild with tailwindcss CLI

## Q&A History
- No clarifications needed — PRD was comprehensive with clear UI mockups, dependencies, and technical details

## Dependencies
- No new packages required
- No new database migrations
- No external services involved
- Depends on E8-S12 (Handoff model — merged), E8-S10 (card persona identity — merged), E6-S4 (context monitoring — merged)

## Testing Strategy
- Unit tests for handoff eligibility computation (persona + context + threshold combinations)
- Unit tests for card state JSON handoff fields (present/absent based on eligibility)
- Regression tests for existing card_state and dashboard route tests
- No integration tests needed (no database changes)

## OpenSpec References
- proposal.md: openspec/changes/e8-s13-handoff-trigger-ui/proposal.md
- tasks.md: openspec/changes/e8-s13-handoff-trigger-ui/tasks.md
- spec.md: openspec/changes/e8-s13-handoff-trigger-ui/specs/handoff-trigger-ui/spec.md
