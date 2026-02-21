## Why

The dashboard agent card currently displays a truncated session UUID as the hero identifier, which is meaningless to the operator. With the persona system established in E8-S1 through E8-S9, agents can now have named persona identities. This sprint makes persona identity visible on the dashboard — the card hero transforms from meaningless identifiers ("4b b2c3d4") to recognisable team members ("Con — developer").

## What Changes

- Card state computation (`card_state.py`) includes persona name and role when agent has a persona
- SSE `card_refresh` payload carries `persona_name` and `persona_role` fields
- Jinja2 agent card template conditionally renders persona name + role instead of UUID hero
- Dashboard SSE JavaScript (`dashboard-sse.js`) renders persona identity on card updates (new cards, Kanban cards, condensed cards, and SSE refreshes)
- Full backward compatibility: agents without personas retain UUID-based hero display

## Impact

- Affected specs: card-persona-identity (new capability)
- Affected code:
  - MODIFIED: `src/claude_headspace/services/card_state.py` — add persona_name and persona_role to card state dict
  - MODIFIED: `templates/partials/_agent_card.html` — conditional hero rendering (persona name + role OR UUID)
  - MODIFIED: `static/js/dashboard-sse.js` — render persona identity in SSE-driven card updates, Kanban cards, and condensed cards
- Affected tests:
  - MODIFIED: `tests/services/test_card_state.py` — test persona data in card state
  - MODIFIED: `tests/routes/test_dashboard.py` — test persona rendering in template (if applicable)

## Definition of Done

- [ ] Agent card with persona displays "Name — role" as hero text
- [ ] Agent card without persona displays UUID hero unchanged
- [ ] SSE card_refresh includes persona_name and persona_role when available
- [ ] Real-time SSE updates render persona identity without page reload
- [ ] Kanban command cards display persona identity when available
- [ ] Condensed completed-command cards display persona identity when available
- [ ] Multiple persona agents render correctly and independently
- [ ] No additional database queries introduced
- [ ] Visual verification via Playwright screenshot confirms correct rendering
