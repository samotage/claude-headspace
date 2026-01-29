# Proposal: e2-s4-macos-notifications

## Summary

Add native macOS system notifications for agent state changes, enabling users to receive alerts when agents complete tasks or require input without monitoring the dashboard.

## Motivation

Users cannot watch the dashboard continuously while working. When agents complete or need input, users may not notice, leading to idle agents and lost productivity. The existing hook receiver provides instant state detection - we need to surface this to users proactively.

## Impact

### Files to Create
- `src/claude_headspace/services/notification_service.py` - Core notification logic
- `src/claude_headspace/routes/notifications.py` - Preferences API endpoints
- `tests/services/test_notification_service.py` - Service tests
- `tests/routes/test_notifications.py` - API tests

### Files to Modify
- `src/claude_headspace/app.py` - Register notifications blueprint
- `src/claude_headspace/services/hook_receiver.py` - Integrate notification triggers
- `src/claude_headspace/config_manager.py` - Add notifications config section
- `templates/partials/_settings_modal.html` - Add notifications UI section
- `static/js/settings.js` - Add notifications preference handlers

### Database Changes
None - uses config.yaml for persistence.

## Definition of Done

- [ ] Notifications appear for task_complete events
- [ ] Notifications appear for awaiting_input events
- [ ] Click-to-navigate opens dashboard with agent highlighted
- [ ] Global enable/disable toggle works
- [ ] Per-event-type toggles work
- [ ] Sound toggle works
- [ ] Rate limiting prevents spam (5 second default)
- [ ] terminal-notifier detection works
- [ ] Setup instructions shown when unavailable
- [ ] GET /api/notifications/preferences returns preferences
- [ ] PUT /api/notifications/preferences updates preferences
- [ ] Preferences persist across restarts
- [ ] Notifications appear within 500ms of event
- [ ] Graceful degradation when terminal-notifier missing
- [ ] All tests passing

## Risks

- **terminal-notifier not installed:** Mitigated by detection + setup guidance UI
- **Notification spam:** Mitigated by rate limiting per agent
- **macOS permissions:** terminal-notifier handles permission prompts

## Alternatives Considered

1. **Native NSUserNotification API:** Rejected - requires PyObjC, more complex
2. **AppleScript notifications:** Rejected - less feature-rich than terminal-notifier
3. **Web notifications:** Rejected - requires browser to be open
