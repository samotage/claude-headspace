# Tasks: e1-s13-hook-receiver

## Phase 1: Setup

- [ ] Review existing Agent model and state management
- [ ] Review existing routes/app.py for blueprint registration pattern
- [ ] Review Claude Code hooks documentation
- [ ] Plan service architecture

## Phase 2: Implementation

### Hook Event Reception (FR1-FR3)
- [ ] Create src/claude_headspace/routes/hooks.py blueprint
- [ ] Implement POST /hook/session-start endpoint
- [ ] Implement POST /hook/session-end endpoint
- [ ] Implement POST /hook/stop endpoint
- [ ] Implement POST /hook/notification endpoint
- [ ] Implement POST /hook/user-prompt-submit endpoint
- [ ] Implement GET /hook/status endpoint
- [ ] Validate incoming hook event payloads
- [ ] Register hooks_bp in app.py

### Session Correlation (FR4-FR6)
- [ ] Create src/claude_headspace/services/session_correlator.py
- [ ] Implement correlation by Claude session ID (cache lookup)
- [ ] Implement correlation by working directory
- [ ] Handle new session creation when no match found
- [ ] Handle multiple sessions in same directory

### State Management (FR7-FR9)
- [ ] Create src/claude_headspace/services/hook_receiver.py
- [ ] Implement session-start → Agent created/activated, idle state
- [ ] Implement user-prompt-submit → Agent transitions to processing
- [ ] Implement stop → Agent transitions to idle
- [ ] Implement session-end → Agent marked inactive
- [ ] Record hook-originated updates with high confidence indicator
- [ ] Emit events for downstream consumers (SSE, event log)

### Hybrid Mode (FR10-FR13)
- [ ] Use hooks as primary event source when available
- [ ] Configure infrequent polling (60s) when hooks active
- [ ] Detect when hooks become silent (300s timeout)
- [ ] Increase polling frequency when hooks silent
- [ ] Return to infrequent polling when hooks resume

### Hook Script & Installation (FR14-FR18)
- [ ] Create bin/notify-headspace.sh notification script
- [ ] Script sends hook events via HTTP to application
- [ ] Script fails silently (always exit 0)
- [ ] Script uses environment variables ($CLAUDE_SESSION_ID, $CLAUDE_WORKING_DIRECTORY)
- [ ] Create bin/install-hooks.sh installation script
- [ ] Installation creates notify-headspace.sh in ~/.claude/hooks/
- [ ] Installation updates ~/.claude/settings.json with hook config
- [ ] Installation validates paths are absolute (not ~ or $HOME)
- [ ] Installation sets appropriate file permissions
- [ ] Create docs/claude-code-hooks-settings.json template

### User Interface (FR19-FR21)
- [ ] Add hook receiver status section to Logging tab
- [ ] Display hooks enabled/disabled state
- [ ] Display last hook event timestamp
- [ ] Display current mode (hooks active vs polling fallback)
- [ ] Add "last active" time to agent cards
- [ ] Update "last active" in real-time via SSE

### Configuration (FR22-FR23)
- [ ] Add hooks configuration section to config.py
- [ ] Support enabling/disabling hook reception
- [ ] Support polling_interval_with_hooks setting
- [ ] Support fallback_timeout setting
- [ ] Support environment variable overrides

## Phase 3: Testing

- [ ] Test POST /hook/session-start creates agent
- [ ] Test POST /hook/user-prompt-submit transitions to processing
- [ ] Test POST /hook/stop transitions to idle
- [ ] Test POST /hook/session-end marks inactive
- [ ] Test GET /hook/status returns correct data
- [ ] Test session correlation by Claude session ID
- [ ] Test session correlation by working directory
- [ ] Test new agent creation for unknown sessions
- [ ] Test hybrid mode polling interval changes
- [ ] Test hook notification script sends events
- [ ] Test hook notification script fails silently
- [ ] Test installation script creates files correctly
- [ ] Test installation script uses absolute paths

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Hook endpoints respond within 50ms
- [ ] Manual test: install hooks on clean system
- [ ] Manual test: end-to-end hook flow
- [ ] No console errors
