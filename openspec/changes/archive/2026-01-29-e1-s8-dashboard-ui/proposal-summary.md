# Proposal Summary: e1-s8-dashboard-ui

## Architecture Decisions
- Jinja2 templates with partials for component reuse
- HTMX for collapse/expand interactivity (no page reload)
- Tailwind CSS for responsive layout and terminal aesthetic
- Flask blueprint pattern for route organization
- Eager loading (selectinload) to prevent N+1 queries

## Implementation Approach
- Create dashboard blueprint with single route at `/`
- Use template partials for header, project groups, agent cards
- Query database with eager loading for projects → agents → commands
- Calculate status counts in route before template rendering
- Apply responsive grid classes for mobile/tablet/desktop

## Files to Modify
**Routes:**
- `src/claude_headspace/routes/dashboard.py` - New dashboard blueprint
- `src/claude_headspace/routes/__init__.py` - Register blueprint

**Templates:**
- `templates/dashboard.html` - Main dashboard template
- `templates/partials/_header.html` - Header bar partial
- `templates/partials/_project_group.html` - Project group partial
- `templates/partials/_agent_card.html` - Agent card partial

**Tests:**
- `tests/routes/test_dashboard.py` - Dashboard route tests

## Acceptance Criteria
- Dashboard route returns 200 with rendered template
- All projects displayed as collapsible groups
- All agents displayed within their project groups
- Header status counts accurate (INPUT NEEDED, WORKING, IDLE)
- Traffic lights reflect project state (red/yellow/green)
- Agent cards display all required fields
- State bars colour-coded (5 distinct colours)
- Responsive at 320px, 768px, 1024px viewports
- Database queries ≤ 5 (no N+1)
- Semantic HTML with ARIA labels

## Constraints and Gotchas
- Agent state is derived from current command, not stored directly
- Traffic light logic requires checking all agents in project
- last_seen_at timeout is 5 minutes for ACTIVE/IDLE status badge
- Priority score is hardcoded to 50 in Epic 1 (LLM scoring in Epic 3)
- Headspace button is placeholder only (wired in Part 2)
- SSE real-time updates are Part 2, not this sprint

## Git Change History

### Related Files
**Models (already exist):**
- src/claude_headspace/models.py - Project, Agent, Command, Turn, CommandState

**Routes:**
- src/claude_headspace/routes/__init__.py - Blueprint registration
- src/claude_headspace/routes/health.py - Existing route pattern

**Templates:**
- templates/base.html - Base template to extend
- templates/errors/*.html - Error template pattern

### OpenSpec History
- e1-s7-sse-system: SSE real-time transport (just completed)
- e1-s6-state-machine: State transitions
- e1-s5-event-system: Event persistence
- e1-s4-file-watcher: File monitoring
- e1-s3-domain-models: Project, Agent, Command, Turn models
- e1-s2-database-setup: PostgreSQL configuration
- e1-s1-flask-bootstrap: Flask app factory

### Implementation Patterns
**Detected from prior sprints:**
1. Create blueprint with routes
2. Add tests in tests/routes/
3. Register blueprint in routes/__init__.py
4. Use existing model relationships

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required**
- **Models:** Project, Agent, Command, Turn from Sprint 3
- **Templates:** base.html from Sprint 1
- **SSE:** Sprint 7 complete, but not integrated until Part 2

## Testing Strategy
- Test route returns 200
- Test template contains expected HTML structure
- Test all projects displayed
- Test all agents displayed within projects
- Test status count calculation accuracy
- Test traffic light colour logic
- Test state bar rendering for each state
- Test responsive breakpoints render correctly
- Test database query count ≤ 5

## OpenSpec References
- proposal.md: openspec/changes/e1-s8-dashboard-ui/proposal.md
- tasks.md: openspec/changes/e1-s8-dashboard-ui/tasks.md
- spec.md: openspec/changes/e1-s8-dashboard-ui/specs/dashboard/spec.md
