# Proposal: e1-s8-dashboard-ui

## Summary

Implement the core Dashboard UI - the primary visual interface for Claude Headspace. This provides a Kanban-style layout with project groups, agent cards, and state visualization allowing users to monitor multiple Claude Code agents at a glance.

## Motivation

Without a dashboard, users must manually track agent states across terminal windows—defeating the purpose of the monitoring system. This sprint delivers the user-facing interface that makes the backend infrastructure (Sprints 1-7) visible and actionable.

## Impact

### Files to Create
- `src/claude_headspace/routes/dashboard.py` - Dashboard blueprint and route
- `templates/dashboard.html` - Main dashboard template
- `templates/partials/_header.html` - Header bar partial
- `templates/partials/_project_group.html` - Project group partial
- `templates/partials/_agent_card.html` - Agent card partial
- `tests/routes/test_dashboard.py` - Dashboard route tests

### Files to Modify
- `src/claude_headspace/routes/__init__.py` - Register dashboard blueprint
- `templates/base.html` - May need minor updates for dashboard layout
- `static/css/src/input.css` - Add dashboard-specific Tailwind styles

### Database Changes
None - uses existing Project, Agent, Task, Turn models from Sprint 3.

## Definition of Done

- [ ] Dashboard route at `/` returns 200 with template
- [ ] All projects displayed as collapsible groups
- [ ] All agents displayed within project groups
- [ ] Header with status counts (INPUT NEEDED, WORKING, IDLE)
- [ ] Traffic light indicators per project
- [ ] Agent cards with session ID, status, uptime, state bar, task summary
- [ ] State bars colour-coded (5 states)
- [ ] Responsive layout (mobile/tablet/desktop)
- [ ] Semantic HTML with ARIA labels
- [ ] Database queries optimized (no N+1)
- [ ] All tests passing

## Risks

- **Template complexity**: Many nested components. Mitigated by using Jinja partials.
- **Query performance**: N+1 queries with nested relationships. Mitigated by eager loading.
- **State derivation**: Agent state derived from tasks. Ensured by existing model properties.

## Alternatives Considered

1. **React/Vue SPA**: More complex, requires build pipeline. Rejected for Epic 1 simplicity.
2. **Server-rendered with Turbo**: HTMX already in stack. Rejected to avoid adding another tool.
