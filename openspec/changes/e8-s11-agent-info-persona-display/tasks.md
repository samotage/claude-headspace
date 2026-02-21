## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [ ] 2.1 Modify `agent_lifecycle.py` — add persona fields (name, role, status, slug) to agent info response dict when agent has a persona; null/absent when no persona
- [ ] 2.2 Modify `routes/projects.py` — include persona_name and persona_role in project agent list data when agent has persona
- [ ] 2.3 Modify `routes/activity.py` — include persona_name and persona_role in activity metrics agent data when agent has persona
- [ ] 2.4 Modify `agent-info.js` — render persona name in header (replacing UUID hero) and add PERSONA section above IDENTITY section when persona data is present
- [ ] 2.5 Modify `_agent_info_modal.html` — update header to support persona name display (if template changes needed beyond JS)
- [ ] 2.6 Modify `project_show.js` — render persona name + role instead of UUID hero in agent list rows when persona data is available
- [ ] 2.7 Modify `activity.js` — render persona name + role instead of UUID hero in agent metric rows when persona data is available

## 3. Testing (Phase 3)

- [ ] 3.1 Unit tests for agent info response — verify persona fields included when agent has persona
- [ ] 3.2 Unit tests for agent info response — verify no persona fields when agent has no persona
- [ ] 3.3 Regression: existing agent info, project, and activity tests still pass
- [ ] 3.4 Visual verification — Playwright screenshot of agent info panel with persona section

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
