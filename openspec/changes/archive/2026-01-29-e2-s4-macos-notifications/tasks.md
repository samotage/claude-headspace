# Commands: e2-s4-macos-notifications

## Phase 1: Setup

- [x] Review existing hook_receiver.py patterns
- [x] Review config_manager.py for adding config sections
- [x] Review settings modal patterns from E2-S1
- [x] Plan notification service architecture

## Phase 2: Implementation

### Notification Service (FR1, FR2, NFR1, NFR4)
- [x] Create src/claude_headspace/services/notification_service.py
- [x] Implement NotificationService class
- [x] Implement send_notification() method using subprocess
- [x] Format notification title, subtitle, message
- [x] Support click-to-open URL with highlight parameter
- [x] Implement sound on/off support
- [x] Add timeout handling (500ms target)

### Rate Limiting (FR7)
- [x] Implement per-agent rate limiting
- [x] Track last notification timestamp per agent
- [x] Respect configurable cooldown period
- [x] Skip notifications during cooldown

### Availability Detection (FR8, FR9, NFR3)
- [x] Implement terminal-notifier detection (shutil.which)
- [x] Expose availability status via API
- [x] Log warning on first failure (not error)
- [x] Graceful fallback when unavailable

### Configuration (FR3, FR4, FR5)
- [x] Add notifications section to config.yaml defaults
- [x] Add enabled: true/false global toggle
- [x] Add sound: true/false toggle
- [x] Add events.command_complete: true/false
- [x] Add events.awaiting_input: true/false
- [x] Add rate_limit_seconds: 5 default
- [x] Update config_manager.py to load notifications config

### Preferences API (FR10)
- [x] Create src/claude_headspace/routes/notifications.py
- [x] Implement GET /api/notifications/preferences
- [x] Return current preferences and availability status
- [x] Implement PUT /api/notifications/preferences
- [x] Validate and update preferences
- [x] Register notifications_bp in app.py

### Hook Integration (FR1, FR2)
- [x] Integrate with hook_receiver.py process_stop event
- [x] Trigger notification on command_complete
- [x] Trigger notification on awaiting_input state
- [x] Pass agent context (name, project) to notification

### Preferences UI (FR11)
- [x] Add notifications section to config schema (config_editor.py)
- [x] Global enable/disable toggle in config page
- [x] Sound toggle in config page
- [x] Rate limit setting in config page
- [ ] Show availability status indicator (deferred - requires API call)
- [ ] Show setup instructions when unavailable (deferred - in API response)

### Agent Highlight (FR6)
- [x] Add ?highlight=<agent_id> URL parameter support
- [x] Scroll to agent card when highlight param present
- [x] Add visual highlight animation/glow
- [x] Auto-remove highlight after 2-3 seconds

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
- [ ] Manual test: command_complete notification
- [ ] Manual test: awaiting_input notification
- [ ] Manual test: click-to-navigate works
- [ ] Manual test: rate limiting works
