# Tasks: e8-s13-handoff-trigger-ui

## Phase 1: Preparation

- [x] 1.1 Read existing card_state.py, _agent_card.html, dashboard-sse.js, config.py, input.css to understand current implementation
- [x] 1.2 Read proposal.md and spec.md for full requirements

## Phase 2: Implementation

- [x] 2.1 Add handoff_threshold to config defaults in config.py (default 80, min 10)
- [x] 2.2 Extend build_card_state() in card_state.py to compute handoff eligibility and add handoff_eligible + handoff_threshold to context block
- [x] 2.3 Add handoff button to _agent_card.html template (conditional on handoff eligibility, positioned in card footer area)
- [x] 2.4 Add handoff tier CSS to context bar in _agent_card.html (third tier above warning/high)
- [x] 2.5 Add handoff CSS classes to input.css (context bar handoff tier colour, button styles, loading state)
- [x] 2.6 Rebuild Tailwind CSS output
- [x] 2.7 Extend handleCardRefresh() in dashboard-sse.js to update handoff button visibility and context bar handoff indicator
- [x] 2.8 Add handoff button click handler in agent-lifecycle.js: POST to /api/agents/<id>/handoff with loading/disabled state

## Phase 3: Testing

- [x] 3.1 Add unit tests for handoff eligibility computation in card_state.py (persona+context+threshold combinations)
- [x] 3.2 Add unit tests for card state JSON handoff fields (present when eligible, absent when not)
- [x] 3.3 Run existing card_state tests to verify no regressions
- [x] 3.4 Run existing dashboard route tests to verify no regressions

## Phase 4: Verification

- [x] 4.1 Verify handoff threshold config loads correctly
- [x] 4.2 Mark all tasks complete
- [x] 4.3 Final review of changes against Definition of Done
