# Tasks: e1-s13-hook-receiver

## Phase 1: Setup

- [x] Review existing Agent model and state management
- [x] Review existing routes/app.py for blueprint registration pattern
- [x] Review Claude Code hooks documentation
- [x] Plan service architecture

## Phase 2: Implementation

### Hook Event Reception (FR1-FR3)
- [x] Create src/claude_headspace/routes/hooks.py blueprint
- [x] Implement POST /hook/session-start endpoint
- [x] Implement POST /hook/session-end endpoint
- [x] Implement POST /hook/stop endpoint
- [x] Implement POST /hook/notification endpoint
- [x] Implement POST /hook/user-prompt-submit endpoint
- [x] Implement GET /hook/status endpoint
- [x] Validate incoming hook event payloads
- [x] Register hooks_bp in app.py

### Session Correlation (FR4-FR6)
- [x] Create src/claude_headspace/services/session_correlator.py
- [x] Implement correlation by Claude session ID (cache lookup)
- [x] Implement correlation by working directory
- [x] Handle new session creation when no match found
- [x] Handle multiple sessions in same directory

### State Management (FR7-FR9)
- [x] Create src/claude_headspace/services/hook_receiver.py
- [x] Implement session-start → Agent created/activated, idle state
- [x] Implement user-prompt-submit → Agent transitions to processing
- [x] Implement stop → Agent transitions to idle
- [x] Implement session-end → Agent marked inactive
- [x] Record hook-originated updates with high confidence indicator
- [x] Emit events for downstream consumers (SSE, event log)

### Hybrid Mode (FR10-FR13)
- [x] Use hooks as primary event source when available
- [x] Configure infrequent polling (60s) when hooks active
- [x] Detect when hooks become silent (300s timeout)
- [x] Increase polling frequency when hooks silent
- [x] Return to infrequent polling when hooks resume

### Hook Script & Installation (FR14-FR18)
- [x] Create bin/notify-headspace.sh notification script
- [x] Script sends hook events via HTTP to application
- [x] Script fails silently (always exit 0)
- [x] Script uses environment variables ($CLAUDE_SESSION_ID, $CLAUDE_WORKING_DIRECTORY)
- [x] Create bin/install-hooks.sh installation script
- [x] Installation creates notify-headspace.sh in ~/.claude/hooks/
- [x] Installation updates ~/.claude/settings.json with hook config
- [x] Installation validates paths are absolute (not ~ or $HOME)
- [x] Installation sets appropriate file permissions
- [x] Create docs/claude-code-hooks-settings.json template

### User Interface (FR19-FR21)
- [ ] Add hook receiver status section to Logging tab
- [ ] Display hooks enabled/disabled state
- [ ] Display last hook event timestamp
- [ ] Display current mode (hooks active vs polling fallback)
- [ ] Add "last active" time to agent cards
- [ ] Update "last active" in real-time via SSE

Note: UI tasks deferred - depends on Sprint 8 (Dashboard UI) which is not yet complete.

### Configuration (FR22-FR23)
- [x] Add hooks configuration section to config.py
- [x] Support enabling/disabling hook reception
- [x] Support polling_interval_with_hooks setting
- [x] Support fallback_timeout setting
- [x] Support environment variable overrides

## Phase 3: Testing

- [x] Test POST /hook/session-start creates agent
- [x] Test POST /hook/user-prompt-submit transitions to processing
- [x] Test POST /hook/stop transitions to idle
- [x] Test POST /hook/session-end marks inactive
- [x] Test GET /hook/status returns correct data
- [x] Test session correlation by Claude session ID
- [x] Test session correlation by working directory
- [x] Test new agent creation for unknown sessions
- [x] Test hybrid mode polling interval changes
- [x] Test hook notification script sends events
- [x] Test hook notification script fails silently
- [x] Test installation script creates files correctly
- [x] Test installation script uses absolute paths

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Hook endpoints respond within 50ms
- [ ] Manual test: install hooks on clean system
- [ ] Manual test: end-to-end hook flow
- [ ] No console errors
