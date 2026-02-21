## Why

After Sprint 10, agent cards on the dashboard display persona name and role. However, the agent info panel, project page agent summaries, and activity page agent references still show UUID-based identifiers. This inconsistency undermines the persona concept — the operator recognises "Con — developer" on the card but encounters "4b6f8a" when they drill into details or summaries. Sprint 11 closes this gap across all remaining views.

## What Changes

- Agent info API response (`/api/agents/<id>/info`) includes persona identity fields (name, role, status, slug) when agent has a persona
- Agent info panel JavaScript (`agent-info.js`) renders a PERSONA section above IDENTITY when persona data is present; header shows persona name instead of UUID hero
- Agent info modal template (`_agent_info_modal.html`) updated to support persona name in header
- Project page agent list (`project_show.js`) renders persona name + role instead of UUID hero when agent has persona data
- Project page API response (`/api/projects/<id>`) includes persona fields in agent objects
- Activity page agent rows (`activity.js`) render persona name + role instead of UUID hero when agent has persona data
- Activity page API response (`/api/metrics/projects`) includes persona fields in agent data
- Full backward compatibility: agents without personas retain UUID-based identity across all views

## Impact

- Affected specs: agent-info-persona-display (new capability)
- Affected code:
  - MODIFIED: `src/claude_headspace/services/agent_lifecycle.py` — add persona fields to agent info response
  - MODIFIED: `src/claude_headspace/routes/agents.py` — include persona in agent info API
  - MODIFIED: `src/claude_headspace/routes/projects.py` — include persona fields in project agent data
  - MODIFIED: `src/claude_headspace/routes/activity.py` — include persona fields in activity agent data
  - MODIFIED: `static/js/agent-info.js` — render persona section and persona hero in info panel
  - MODIFIED: `templates/partials/_agent_info_modal.html` — support persona name in header
  - MODIFIED: `static/js/project_show.js` — render persona identity in agent list rows
  - MODIFIED: `static/js/activity.js` — render persona identity in agent metric rows
- Affected tests:
  - MODIFIED: `tests/services/test_agent_lifecycle.py` — test persona fields in agent info
  - MODIFIED: `tests/routes/test_agents.py` — test persona in API response

## Definition of Done

- [ ] Agent info panel shows persona name, role, status, slug when agent has persona
- [ ] Agent info panel persona section appears above existing technical details
- [ ] Agent info panel preserves all existing technical details unchanged
- [ ] Agent info panel for anonymous agent shows no persona section
- [ ] Agent info panel header shows persona name instead of UUID when persona present
- [ ] Project page agent summaries display persona name + role when agent has persona
- [ ] Project page agent summaries display UUID fallback for anonymous agents
- [ ] Activity page agent references display persona name + role when agent has persona
- [ ] Activity page agent references display UUID fallback for anonymous agents
- [ ] No additional API round trips introduced
