# Proposal Summary: e1-s12-applescript-integration

## Architecture Decisions
- AppleScript via `osascript` subprocess for iTerm2 control
- Service layer pattern (iterm_focus.py) separated from route layer
- 2-second subprocess timeout to prevent blocking
- Error type enumeration for consistent error handling
- Fallback path in all error responses for manual navigation

## Implementation Approach
- Create focus service that wraps AppleScript execution
- Create Flask blueprint with POST /api/focus/<agent_id> endpoint
- Map AppleScript errors to specific error types
- Log focus events for debugging and audit trail
- Use Agent model's iterm_pane_id and project relationship

## Files to Modify
**Services:**
- `src/claude_headspace/services/iterm_focus.py` - AppleScript execution service (new)

**Routes:**
- `src/claude_headspace/routes/focus.py` - Focus API blueprint (new)
- `src/claude_headspace/app.py` - Register focus_bp

**Tests:**
- `tests/services/test_iterm_focus.py` - Service unit tests (new)
- `tests/routes/test_focus.py` - API integration tests (new)

## Acceptance Criteria
- POST /api/focus/<agent_id> triggers iTerm2 focus
- Correct pane activated (matching iterm_pane_id)
- Works across macOS Spaces/Desktops
- Restores minimized windows
- Permission errors return actionable guidance
- Missing/stale pane IDs handled with fallback path
- Focus latency < 500ms, API timeout < 2 seconds
- All tests passing

## Constraints and Gotchas
- **macOS Automation Permission**: First use requires user to grant permission in System Settings → Privacy & Security → Automation
- **iTerm2 Session ID Format**: pane_id format is `pty-XXXXX` captured from ITERM_SESSION_ID env var
- **AppleScript Timeout**: osascript can hang if iTerm2 is unresponsive - must use subprocess timeout
- **Space Switching**: activate command handles space switching automatically
- **Minimized Windows**: May need explicit window show/raise in AppleScript

## Git Change History

### Related Files
**Models (existing):**
- src/claude_headspace/models/agent.py - Agent model with iterm_pane_id field

**Routes (patterns to follow):**
- src/claude_headspace/routes/health.py - Simple API endpoint pattern
- src/claude_headspace/routes/sessions.py - Agent lookup pattern (from Sprint 11)

**Services (patterns to follow):**
- No existing services - will establish pattern

### OpenSpec History
- e1-s11-launcher-script: Launcher Script (just completed) - Added iterm_pane_id to Agent
- e1-s3-domain-models: Domain Models (Agent, Project)

### Implementation Patterns
1. Create service module with focused responsibility
2. Create Flask blueprint with API routes
3. Register blueprint in app.py
4. Add comprehensive tests for service and routes

## Q&A History
- No clarifications needed - PRD is comprehensive
- Sprint 11 dependency satisfied (Agent.iterm_pane_id exists)

## Dependencies
- **No new pip packages required** - uses stdlib subprocess, osascript is macOS builtin
- **Sprint 11 (Launcher Script):** Agent.iterm_pane_id (complete)
- **Sprint 3 (Domain Models):** Agent, Project models (complete)
- **macOS with iTerm2** - Required for actual focus operations

## Testing Strategy
- Test POST /api/focus returns 200 on success (mocked)
- Test POST /api/focus returns 404 for unknown agent
- Test error responses for various failure modes
- Test fallback_path inclusion in error responses
- Test timeout handling with slow subprocess mock
- Test AppleScript generation correctness
- Manual testing for actual focus behavior

## OpenSpec References
- proposal.md: openspec/changes/e1-s12-applescript-integration/proposal.md
- tasks.md: openspec/changes/e1-s12-applescript-integration/tasks.md
- spec.md: openspec/changes/e1-s12-applescript-integration/specs/focus/spec.md
