## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [ ] 2.1 Modify `card_state.py` — add `persona_name` and `persona_role` fields to card state dict when agent has a persona (via agent.persona.name and agent.persona.role.name); null/absent when no persona
- [ ] 2.2 Modify `_agent_card.html` — conditional hero rendering: if persona_name present, show "Name — role" instead of UUID hero_chars + hero_trail; preserve click-to-focus behaviour
- [ ] 2.3 Modify `dashboard-sse.js` — update `card_refresh` SSE handler to render persona name + role in hero section when persona_name is present in data; fall back to UUID hero when absent
- [ ] 2.4 Modify `dashboard-sse.js` — update Kanban command card builder to display persona name + role when persona data available
- [ ] 2.5 Modify `dashboard-sse.js` — update condensed completed-command card builder to display persona name + role when persona data available

## 3. Testing (Phase 3)

- [ ] 3.1 Unit tests for `card_state.py` — card state includes persona_name and persona_role when agent has persona
- [ ] 3.2 Unit tests for `card_state.py` — card state has no persona fields when agent has no persona
- [ ] 3.3 Visual verification — Playwright screenshot of dashboard with persona-backed agent card
- [ ] 3.4 Regression: existing card_state and dashboard tests still pass

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
