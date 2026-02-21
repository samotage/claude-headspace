# Proposal Summary: e8-s11-agent-info-persona-display

## Architecture Decisions
- Persona data flows through existing API endpoints — no new endpoints created
- Three API responses extended: agent info (`/api/agents/<id>/info`), project data (`/api/projects/<id>`), activity metrics (`/api/metrics/projects`)
- Conditional rendering at JavaScript layer — persona display OR UUID display, never both
- Agent info panel gains a new PERSONA section above IDENTITY; header shows persona name instead of UUID
- No additional DB queries: persona data accessed via agent's existing `agent.persona` relationship chain

## Implementation Approach
- Extend `get_agent_info()` in `agent_lifecycle.py` to include persona fields in the identity response
- Extend project route agent serialization to include persona_name and persona_role
- Extend activity metrics agent serialization to include persona_name and persona_role
- Update `agent-info.js` to render persona name in header and add PERSONA section
- Update `project_show.js` to conditionally render persona hero vs UUID hero in agent rows
- Update `activity.js` to conditionally render persona hero vs UUID hero in agent metric rows

## Files to Modify
- **Services:** `src/claude_headspace/services/agent_lifecycle.py` — add persona to agent info response
- **Routes:** `src/claude_headspace/routes/agents.py` — persona in agent info API (if needed beyond service)
- **Routes:** `src/claude_headspace/routes/projects.py` — persona fields in project agent data
- **Routes:** `src/claude_headspace/routes/activity.py` — persona fields in activity agent data
- **Static JS:** `static/js/agent-info.js` — persona section + header rendering
- **Static JS:** `static/js/project_show.js` — persona hero in agent list rows
- **Static JS:** `static/js/activity.js` — persona hero in agent metric rows
- **Template:** `templates/partials/_agent_info_modal.html` — header persona support (if needed)
- **Tests:** `tests/services/test_agent_lifecycle.py` or `tests/routes/test_agents.py`

## Acceptance Criteria
- Agent info panel shows persona name, role, status, slug when agent has persona
- Agent info panel persona section appears above existing IDENTITY section
- Agent info panel header shows persona name instead of UUID hero
- Agent info panel preserves all existing technical details unchanged
- Agent info panel for anonymous agent shows no persona section
- Project page agent summaries display persona name + role for persona agents
- Activity page agent references display persona name + role for persona agents
- Anonymous agents display UUID fallback in all views (unchanged)
- No additional API round trips

## Constraints and Gotchas
- **Agent info JS currently extracts hero from `session_uuid_short`** (lines 54-59 of agent-info.js): first 2 chars as hero, rest as trail. Need to check persona data first, fall back to UUID.
- **Project page uses `session_uuid.substring(0, 8)`** (lines 309-317 of project_show.js): Same pattern — persona name replaces this.
- **Activity page uses same UUID pattern** (lines 632-641 of activity.js): Same conditional swap needed.
- **Agent info response structure**: The `identity` object in agent info needs persona fields added. Check `get_agent_info()` in `agent_lifecycle.py` (line 382+).
- **Persona relationship loading**: Ensure persona and persona.role are loaded when building API responses. Check if joinedload/selectinload is needed.
- **Em dash separator**: Use "—" (em dash) as separator between name and role, consistent with S10.
- **Ended agents**: Persona identity must persist for ended agents — check that persona_id is not cleared on session end.

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/agent_lifecycle.py`
- Routes: `src/claude_headspace/routes/agents.py`, `routes/projects.py`, `routes/activity.py`
- Static: `static/js/agent-info.js`, `static/js/project_show.js`, `static/js/activity.js`
- Templates: `templates/partials/_agent_info_modal.html`
- Tests: `tests/services/test_agent_lifecycle.py`, `tests/routes/test_agents.py`

### OpenSpec History
- `e1-s8-dashboard-ui` (2026-01-29) — original dashboard UI
- `e2-s1-config-ui` (2026-01-29) — config UI
- `e4-s2b-project-controls-ui` (2026-02-02) — project controls UI
- `e8-s10-card-persona-identity` (2026-02-21) — card persona display (S10, just completed)

### Implementation Patterns
- API endpoint returns data → JavaScript renders in DOM
- Conditional rendering: check persona field presence → render persona OR UUID
- Agent info: `get_agent_info()` returns dict → `AgentInfo.open()` fetches + renders
- Project page: `/api/projects/<id>` returns agents array → `_renderAgentsList()` renders
- Activity page: `/api/metrics/projects` returns agent data → `_renderProjectPanels()` renders

## Q&A History
- No clarifications needed — PRD is comprehensive with clear UI specs

## Dependencies
- No new packages
- Depends on E8-S10 (card persona display — establishes the pattern)
- Uses Agent.persona relationship (persona_id FK from E8-S1/S4)
- Uses Persona model (name, slug, status) and Role model (name)

## Testing Strategy
- Unit tests for agent info response: persona fields included/excluded based on persona presence
- Regression: existing agent info, project, and activity tests still pass
- Visual verification: Playwright screenshot of agent info panel with persona section

## OpenSpec References
- proposal.md: openspec/changes/e8-s11-agent-info-persona-display/proposal.md
- tasks.md: openspec/changes/e8-s11-agent-info-persona-display/tasks.md
- spec.md: openspec/changes/e8-s11-agent-info-persona-display/specs/agent-info-persona-display/spec.md
