# Tasks: e2-s4-macos-notifications

## Phase 1: Setup

- [x] Review existing hook_receiver.py patterns
- [x] Review config_manager.py for adding config sections
- [x] Review settings modal patterns from E2-S1
- [x] Plan notification service architecture

## Phase 2: Implementation

### Notification Service (FR1, FR2, NFR1, NFR4)
- [ ] Create src/claude_headspace/services/notification_service.py
- [ ] Implement NotificationService class
- [ ] Implement send_notification() method using subprocess
- [ ] Format notification title, subtitle, message
- [ ] Support click-to-open URL with highlight parameter
- [ ] Implement sound on/off support
- [ ] Add timeout handling (500ms target)

### Rate Limiting (FR7)
- [ ] Implement per-agent rate limiting
- [ ] Track last notification timestamp per agent
- [ ] Respect configurable cooldown period
- [ ] Skip notifications during cooldown

### Availability Detection (FR8, FR9, NFR3)
- [ ] Implement terminal-notifier detection (shutil.which)
- [ ] Expose availability status via API
- [ ] Log warning on first failure (not error)
- [ ] Graceful fallback when unavailable

### Configuration (FR3, FR4, FR5)
- [ ] Add notifications section to config.yaml defaults
- [ ] Add enabled: true/false global toggle
- [ ] Add sound: true/false toggle
- [ ] Add events.task_complete: true/false
- [ ] Add events.awaiting_input: true/false
- [ ] Add rate_limit_seconds: 5 default
- [ ] Update config_manager.py to load notifications config

### Preferences API (FR10)
- [ ] Create src/claude_headspace/routes/notifications.py
- [ ] Implement GET /api/notifications/preferences
- [ ] Return current preferences and availability status
- [ ] Implement PUT /api/notifications/preferences
- [ ] Validate and update preferences
- [ ] Register notifications_bp in app.py

### Hook Integration (FR1, FR2)
- [ ] Integrate with hook_receiver.py process_stop event
- [ ] Trigger notification on task_complete
- [ ] Trigger notification on awaiting_input state
- [ ] Pass agent context (name, project) to notification

### Preferences UI (FR11)
- [ ] Add notifications section to _settings_modal.html
- [ ] Add global enable/disable toggle
- [ ] Add per-event-type toggles
- [ ] Add sound toggle
- [ ] Show availability status indicator
- [ ] Show setup instructions when unavailable
- [ ] Wire toggles to API endpoints

### Agent Highlight (FR6)
- [ ] Add ?highlight=<agent_id> URL parameter support
- [ ] Scroll to agent card when highlight param present
- [ ] Add visual highlight animation/glow
- [ ] Auto-remove highlight after 2-3 seconds

## Phase 3: Testing

- [ ] Test NotificationService sends notification
- [ ] Test notification includes correct content
- [ ] Test rate limiting blocks rapid notifications
- [ ] Test rate limiting allows after cooldown
- [ ] Test terminal-notifier detection
- [ ] Test graceful degradation when unavailable
- [ ] Test GET /api/notifications/preferences returns data
- [ ] Test PUT /api/notifications/preferences updates config
- [ ] Test preferences persist across restart
- [ ] Test hook integration triggers notifications

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Notifications appear within 500ms
- [ ] No console errors
- [ ] Manual test: task_complete notification
- [ ] Manual test: awaiting_input notification
- [ ] Manual test: click-to-navigate works
- [ ] Manual test: rate limiting works
