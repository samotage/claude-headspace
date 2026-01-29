# Proposal: e1-s12-applescript-integration

## Summary

Add AppleScript-based iTerm2 focus integration to enable click-to-focus functionality from the dashboard. When users click an agent card, the system executes AppleScript to activate iTerm2 and focus the specific terminal pane for that session.

## Motivation

Claude Headspace monitors multiple concurrent Claude Code sessions. Sprint 11's launcher script captures iTerm2 pane IDs during session registration. Sprint 12 completes the chain by enabling users to instantly navigate from dashboard to terminal with one click - eliminating the need to manually hunt through iTerm windows, tabs, and panes.

## Impact

### Files to Create
- `src/claude_headspace/services/iterm_focus.py` - AppleScript execution service
- `src/claude_headspace/routes/focus.py` - API endpoint blueprint
- `tests/services/test_iterm_focus.py` - Service unit tests
- `tests/routes/test_focus.py` - API integration tests

### Files to Modify
- `src/claude_headspace/app.py` - Register focus blueprint

### Database Changes
None - uses existing Agent model with `iterm_pane_id` field.

## Definition of Done

- [ ] `POST /api/focus/<agent_id>` endpoint triggers iTerm2 focus
- [ ] AppleScript execution activates iTerm2 and focuses correct pane
- [ ] Focus works across macOS Spaces/Desktops
- [ ] Minimized windows are restored before focusing
- [ ] Permission errors return actionable guidance
- [ ] Missing/stale pane IDs return fallback path
- [ ] iTerm2 not running handled gracefully
- [ ] Unknown agent returns 404
- [ ] Focus attempts logged to event system
- [ ] 2-second timeout prevents blocking
- [ ] All tests passing

## Risks

- **macOS Automation Permissions:** Users must grant permission in System Settings. Detect and provide clear guidance.
- **AppleScript Performance:** Can hang if iTerm2 is unresponsive. Use subprocess timeout.
- **Stale Pane IDs:** Session may have closed. Handle gracefully with fallback path.

## Alternatives Considered

1. **Direct iTerm2 Python API:** Rejected - iTerm2's Python API requires running inside iTerm, not suitable for external Flask app
2. **JXA (JavaScript for Automation):** Considered - AppleScript is more widely documented for iTerm2
3. **Shell scripts calling osascript:** Current approach - subprocess with AppleScript provides timeout control
