# Proposal Summary: e1-s13-hook-receiver

## Architecture Decisions
- Hook events received via HTTP endpoints in Flask blueprint
- Session correlation service matches Claude session IDs to agents
- Hybrid mode: hooks as primary source, polling as fallback
- Hook script fails silently to never block Claude Code
- Installation script uses absolute paths for Claude Code compatibility

## Implementation Approach
- Create routes/hooks.py blueprint with 5 event endpoints + 1 status endpoint
- Create services/hook_receiver.py for event processing and state transitions
- Create services/session_correlator.py for session-to-agent matching
- Create bin/install-hooks.sh and bin/notify-headspace.sh scripts
- Add hook status section to Logging tab
- Add "last active" time to agent cards

## Files to Modify
**Routes:**
- `src/claude_headspace/routes/hooks.py` - Hook event endpoints (new)
- `src/claude_headspace/app.py` - Register hooks_bp

**Services:**
- `src/claude_headspace/services/hook_receiver.py` - Event processing (new)
- `src/claude_headspace/services/session_correlator.py` - Session correlation (new)

**Scripts:**
- `bin/install-hooks.sh` - Installation script (new)
- `bin/notify-headspace.sh` - Notification script template (new)
- `docs/claude-code-hooks-settings.json` - Settings template (new)

**Config:**
- `src/claude_headspace/config.py` - Hook configuration options

**Templates:**
- `templates/logging.html` - Hook status display

**Tests:**
- `tests/routes/test_hooks.py` (new)
- `tests/services/test_hook_receiver.py` (new)
- `tests/services/test_session_correlator.py` (new)

## Acceptance Criteria
- Hook endpoints receive events and update agent state within 100ms
- Session correlation matches Claude session IDs to agents
- Hybrid mode: 60s polling with hooks, 2s polling without
- Hook script always exits 0 (never blocks Claude Code)
- Installation script creates files with absolute paths
- Logging tab shows hook receiver status
- Agent cards show "last active" time
- All tests passing

## Constraints and Gotchas
- **Claude Code session IDs** differ from iTerm pane IDs - correlation by working directory as fallback
- **Multiple sessions in same directory** - last-matched wins (documented limitation)
- **Hook script timeout** - 1 second connect, 2 second total max
- **Absolute paths** - Claude Code doesn't expand ~ or $HOME in hook commands
- **Silent failures** - Hook script must always exit 0 to not break Claude Code
- **Concurrent events** - Handle multiple hook events from different sessions

## Git Change History

### Related Files
This is a new subsystem (events/hooks) - no existing files to reference.

**Patterns to follow:**
- Routes: src/claude_headspace/routes/focus.py (Sprint 12)
- Services: src/claude_headspace/services/iterm_focus.py (Sprint 12)
- Tests: tests/routes/test_focus.py (Sprint 12)

### OpenSpec History
- e1-s12-applescript-integration: AppleScript focus (just completed)
- e1-s11-launcher-script: Session launcher with pane ID capture

### Implementation Patterns
1. Create service module with focused responsibility
2. Create Flask blueprint with API routes
3. Register blueprint in app.py
4. Add comprehensive tests for service and routes

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required** - uses stdlib and existing Flask
- **Sprint 5 (Event System):** Event writer, event schemas - **Complete**
- **Sprint 6 (State Machine):** Command state transitions - **Available**
- **Sprint 8 (Dashboard UI):** Agent cards, Logging tab - **Available**
- **macOS with bash shell** - Required for hook scripts

## Testing Strategy
- Test each hook endpoint (session-start, user-prompt-submit, stop, notification, session-end)
- Test status endpoint returns correct data
- Test session correlation by Claude session ID
- Test session correlation by working directory
- Test new agent creation for unknown sessions
- Test hybrid mode polling interval changes
- Test hook notification script sends events
- Test hook notification script fails silently (always exit 0)
- Test installation script creates files with absolute paths
- Manual testing for end-to-end hook flow

## OpenSpec References
- proposal.md: openspec/changes/e1-s13-hook-receiver/proposal.md
- tasks.md: openspec/changes/e1-s13-hook-receiver/tasks.md
- spec.md: openspec/changes/e1-s13-hook-receiver/specs/hooks/spec.md
