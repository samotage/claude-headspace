# Tasks: e1-s12-applescript-integration

## Phase 1: Setup

- [x] Review existing Agent model and iterm_pane_id field
- [x] Review existing Flask app structure for blueprint registration
- [x] Research iTerm2 AppleScript API documentation
- [x] Plan service architecture

## Phase 2: Implementation

### AppleScript Focus Service (FR6-FR11)
- [x] Create src/claude_headspace/services/iterm_focus.py
- [x] Implement focus_iterm_pane(pane_id) function
  - Execute AppleScript via osascript subprocess
  - Activate iTerm2 application
  - Search for session matching pane_id
  - Activate containing window and tab
  - Select target pane as active session
- [x] Implement subprocess timeout (2 seconds) for NFR2
- [x] Handle AppleScript execution errors
- [x] Detect permission denied errors (FR15)
- [x] Detect iTerm2 not running (FR14)
- [x] Detect pane not found (FR13)

### API Endpoint (FR1-FR5)
- [x] Create src/claude_headspace/routes/focus.py blueprint
- [x] Implement POST /api/focus/<agent_id> endpoint
  - Accept agent_id as path parameter (integer)
  - Lookup Agent from database
  - Return 404 if agent not found (FR5)
  - Return error if no iterm_pane_id (FR12)
  - Call focus service
  - Return success response with agent_id, pane_id (FR3)
  - Return error response with error_type, message, fallback_path (FR4)
- [x] Register focus_bp in app.py

### Error Response Handling (FR12-FR18)
- [x] Implement error type mapping
  - permission_denied: Automation permission not granted
  - pane_not_found: Missing or stale pane ID
  - iterm_not_running: iTerm2 application not running
  - agent_not_found: Agent ID not in database
  - unknown: Other AppleScript failures
- [x] Include fallback_path in all error responses for existing agents (FR17)
- [x] Format actionable error messages (FR15, FR18)

### Event Logging (FR19-FR20)
- [x] Log focus_attempted event on each focus attempt
- [x] Include payload: agent_id, pane_id, outcome, error_type, latency_ms

## Phase 3: Testing

- [x] Test POST /api/focus returns 200 on success
- [x] Test POST /api/focus returns 404 for unknown agent
- [x] Test error response for missing pane_id
- [x] Test error response for permission denied
- [x] Test error response for iTerm2 not running
- [x] Test error response includes fallback_path
- [x] Test timeout handling (mock slow AppleScript)
- [x] Test focus service unit tests with mocked subprocess
- [x] Test AppleScript generation is correct

## Phase 4: Final Verification

- [x] All tests passing
- [ ] Manual test: focus from running session
- [ ] Manual test: focus when iTerm2 not running
- [ ] Manual test: focus with stale pane ID
- [ ] No console errors
- [ ] Focus latency < 500ms (NFR1)
