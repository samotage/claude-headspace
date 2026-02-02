# Proposal Summary: e2-s4-macos-notifications

## Architecture Decisions
- Use terminal-notifier via subprocess (not native APIs) for simplicity and compatibility
- Event-driven notifications triggered by hook receiver (no polling)
- Config-based preferences in config.yaml for persistence
- Rate limiting per agent to prevent spam
- Click-to-navigate using URL with highlight parameter

## Implementation Approach
- Create NotificationService class encapsulating all notification logic
- Integrate with existing hook_receiver.py process_stop() method
- Add notifications blueprint for preferences API
- Extend settings modal UI for preferences management
- Use shutil.which() for terminal-notifier detection

## Files to Modify

**Services:**
- `src/claude_headspace/services/notification_service.py` - NEW - Core notification logic
- `src/claude_headspace/services/hook_receiver.py` - MODIFY - Add notification triggers

**Routes:**
- `src/claude_headspace/routes/notifications.py` - NEW - Preferences API
- `src/claude_headspace/app.py` - MODIFY - Register notifications blueprint

**Config:**
- `src/claude_headspace/config_manager.py` - MODIFY - Add notifications section

**Templates:**
- `templates/partials/_settings_modal.html` - MODIFY - Add notifications UI

**Static:**
- `static/js/settings.js` - MODIFY - Add notification preference handlers
- `static/js/dashboard.js` - MODIFY - Handle highlight URL parameter

**Tests:**
- `tests/services/test_notification_service.py` - NEW
- `tests/routes/test_notifications.py` - NEW

## Acceptance Criteria
- Notifications for task_complete events
- Notifications for awaiting_input events
- Click-to-navigate with agent highlight
- Global and per-event toggles
- Sound toggle
- Rate limiting (5 second default)
- terminal-notifier detection
- Setup guidance UI
- Preferences API (GET/PUT)
- Persistence across restarts
- < 500ms notification latency
- Graceful degradation

## Constraints and Gotchas
- **terminal-notifier required:** Must be installed via Homebrew, detect and guide if missing
- **Subprocess timeout:** terminal-notifier call needs timeout to not block
- **Rate limiting state:** Track per-agent last notification time in memory (not persisted)
- **Click action URL:** localhost:5050 hardcoded, may need config if port changes
- **Sound option:** Only default or silent, no custom sounds

## Git Change History

### Related Files
This is a new subsystem with no existing files.

**Integration Points:**
- `src/claude_headspace/services/hook_receiver.py` - Event source
- `src/claude_headspace/config_manager.py` - Config loading
- `templates/partials/_settings_modal.html` - UI pattern from E2-S1

### OpenSpec History
- First change to notifications subsystem

### Implementation Patterns
Based on existing patterns:
1. Create service class in services/
2. Create routes blueprint in routes/
3. Register blueprint in app.py
4. Add config section to config_manager
5. Update UI template
6. Add comprehensive tests

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required** - uses subprocess, shutil
- **External:** terminal-notifier (Homebrew package)
- **E1 Complete:** Hook receiver, SSE, dashboard
- **E2-S1 Complete:** Settings modal UI

## Testing Strategy
- Test NotificationService send_notification method
- Test rate limiting blocks and allows correctly
- Test terminal-notifier detection
- Test graceful degradation
- Test GET/PUT preferences API
- Test preferences persistence
- Test hook integration triggers

## OpenSpec References
- proposal.md: openspec/changes/e2-s4-macos-notifications/proposal.md
- tasks.md: openspec/changes/e2-s4-macos-notifications/tasks.md
- spec.md: openspec/changes/e2-s4-macos-notifications/specs/notifications/spec.md
