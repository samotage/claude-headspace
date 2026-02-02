# Proposal: e1-s9-objective-tab

## Summary

Add Objective Tab UI and API for setting, viewing, and tracking user objectives that guide agent prioritisation. Implements the user interface layer on top of existing Objective/ObjectiveHistory models from Sprint 3.

## Motivation

Claude Headspace's core value is cross-project prioritisation aligned to user objectives. This sprint provides the interface for users to:
- Set their current focus/objective
- Add optional constraints
- View objective history with timestamps
- Enable future AI-driven prioritisation (Epic 3)

## Impact

### Files to Create
- `src/claude_headspace/routes/objective.py` - Objective API blueprint
- `templates/objective.html` - Objective tab template
- `static/js/objective.js` - Auto-save and UI logic
- `tests/routes/test_objective.py` - API and route tests

### Files to Modify
- `src/claude_headspace/app.py` - Register objective blueprint
- `templates/partials/_header.html` - Wire objective tab link

### Database Changes
None - uses existing Objective and ObjectiveHistory models from Sprint 3.

## Definition of Done

- [ ] Objective tab template with dark terminal aesthetic
- [ ] Objective form with text field (required) and constraints (optional)
- [ ] Auto-save with 2-3 second debounce
- [ ] Save state indicators (saving, saved, error)
- [ ] Objective history display with pagination
- [ ] GET /api/objective endpoint
- [ ] POST /api/objective endpoint with history tracking
- [ ] GET /api/objective/history endpoint with pagination
- [ ] Empty state handling
- [ ] Error state handling
- [ ] All tests passing

## Risks

- **Model availability**: Objective/ObjectiveHistory models from Sprint 3 must exist. Verified - they do.
- **Navigation integration**: Header links must be wired. Minor impact if Sprint 8 navigation differs.

## Alternatives Considered

1. **Real-time SSE for multi-tab sync**: Out of scope per PRD - adds complexity without immediate need.
2. **Rich text editing**: Out of scope - plain text sufficient for MVP.
