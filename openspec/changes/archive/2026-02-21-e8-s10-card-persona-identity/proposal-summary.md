# Proposal Summary: e8-s10-card-persona-identity

## Architecture Decisions
- Persona data flows through the existing card_state → SSE → dashboard-sse.js pipeline — no new data channels
- Conditional rendering at both template (Jinja2) and JavaScript (SSE) layers — persona hero OR UUID hero, never both
- No additional DB queries: persona data accessed via agent's existing eager-loaded `agent.persona` relationship (agent → persona → role)
- `persona_name` and `persona_role` added as optional fields in card state dict — null/absent when no persona
- Hero section click-to-focus behaviour preserved regardless of persona/UUID display mode

## Implementation Approach
- Add `persona_name` and `persona_role` to card state dict in `card_state.py` (single function change)
- Update `_agent_card.html` Jinja2 template with conditional: `{% if agent.persona_name %}` renders persona hero, else renders UUID hero
- Update `dashboard-sse.js` in three places: SSE card_refresh handler, Kanban card builder, condensed completed-command card builder
- All changes are additive — UUID fallback is the default, persona display is opt-in when data is present

## Files to Modify
- **MODIFIED** `src/claude_headspace/services/card_state.py` — add persona_name and persona_role to card state
- **MODIFIED** `templates/partials/_agent_card.html` — conditional hero rendering
- **MODIFIED** `static/js/dashboard-sse.js` — persona identity in SSE-driven cards (3 locations: card refresh, Kanban, condensed)
- **MODIFIED** `tests/services/test_card_state.py` — test persona data in card state
- **POSSIBLY** `static/css/src/input.css` — minor CSS for persona hero styling (if needed)

## Acceptance Criteria
- Agent card with persona displays "Name — role" as hero text (e.g., "Con — developer")
- Agent card without persona displays UUID hero unchanged (hero_chars + hero_trail)
- SSE card_refresh includes persona_name and persona_role when available
- Real-time SSE updates render persona identity without page reload
- Kanban command cards display persona identity when available
- Condensed completed-command cards display persona identity when available
- Multiple persona agents render correctly and independently
- No additional database queries introduced
- Visual verification via Playwright screenshot

## Constraints and Gotchas
- **Persona relationship must be eager-loaded**: The agent → persona → role chain must already be loaded when card_state is built. Check if `agent.persona` is accessible. If the relationship isn't loaded, use `Persona.query.get(agent.persona_id)` as fallback.
- **Role access**: The persona's role name is accessed via `agent.persona.role.name`. Verify the role relationship is loaded on the Persona model. May need to join through `persona.role_id` → `Role.name`.
- **hero_chars and hero_trail still needed**: Even for persona agents, keep hero_chars/hero_trail in card state for backward compatibility (kebab menu, dismiss dialog, agent info panel reference them).
- **CSS text overflow**: Long persona names + role could overflow the hero area. Consider truncation or responsive sizing. The PRD specifies "no visual overflow or breaking the card structure."
- **Em dash separator**: Use the actual em dash character "—" (not hyphen or en dash) as the separator between name and role.
- **dashboard-sse.js has 3 card builders**: SSE card_refresh handler (line ~947), Kanban command card builder, and condensed completed-command card builder — all need persona support.
- **Tailwind v3**: This project uses Tailwind v3 (not v4). Use `npx tailwindcss` (not `npx @tailwindcss/cli`).
- **Playwright visual verification required**: Per CLAUDE.md guardrails, UI changes MUST be verified with Playwright screenshots.

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/card_state.py`
- Templates: `templates/partials/_agent_card.html`
- Static: `static/js/dashboard-sse.js`, `static/js/agent-lifecycle.js`, `static/js/agent-info.js`
- Tests: `tests/services/test_card_state.py`, `tests/routes/test_dashboard.py`
- CSS: `static/css/src/input.css`, `static/css/main.css`

### OpenSpec History
- `e1-s8-dashboard-ui` (2026-01-29) — original dashboard UI implementation
- `e2-s1-config-ui` (2026-01-29) — config UI
- `e4-s2b-project-controls-ui` (2026-02-02) — project controls UI
- UI commits: dismiss modal fix (2026-02-12), kebab menu (2026-02-12), agent info modal (2026-02-12)

### Implementation Patterns
- card_state.py builds dict → template renders initial HTML → dashboard-sse.js updates via SSE
- Conditional rendering pattern: check data field presence, render persona OR UUID, never both
- SSE data flows: card_state dict is broadcast as-is via broadcaster → SSE → JavaScript

## Q&A History
- No clarifications needed — PRD is comprehensive with clear UI specs and all design decisions resolved

## Dependencies
- No new packages needed
- Consumes E8-S1/S4 Agent.persona relationship (persona_id FK)
- Consumes E8-S1 Persona model (name field) and Role model (name field)
- Relies on existing card_state.py and dashboard-sse.js infrastructure

## Testing Strategy
- **Unit tests** for card_state.py: mock agent with persona → verify persona_name and persona_role in card state; mock agent without persona → verify no persona fields
- **Visual verification**: Playwright screenshot of dashboard to confirm persona hero rendering
- **Regression**: existing card_state and dashboard route tests still pass
- No new test files needed — extend existing test_card_state.py

## OpenSpec References
- proposal.md: openspec/changes/e8-s10-card-persona-identity/proposal.md
- tasks.md: openspec/changes/e8-s10-card-persona-identity/tasks.md
- spec.md: openspec/changes/e8-s10-card-persona-identity/specs/card-persona-identity/spec.md
