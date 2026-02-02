## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Commander Service (Backend)

- [x] 2.1 Create `commander_service.py` — Unix socket client for claude-commander
  - Socket path derivation from `claude_session_id` (`/tmp/claudec-<SESSION_ID>.sock`)
  - `send_text(session_id, text)` — send JSON `{"action": "send", "text": "..."}` over socket, return success/error
  - `check_health(session_id)` — send `{"action": "status"}`, return availability result
  - `get_socket_path(session_id)` — derive and validate socket path exists
  - Error handling: connection refused, socket not found, timeout, process died
  - NamedTuple result types following `iterm_focus.py` pattern

- [x] 2.2 Create `commander_availability.py` — availability tracking and periodic health checks
  - In-memory cache of commander availability per agent
  - Periodic health check loop (configurable interval)
  - SSE broadcast on availability change
  - Thread-safe with locking (following `HookReceiverState` pattern)

- [x] 2.3 Register commander service in `app.py`
  - Import and initialize `CommanderService`
  - Register in `app.extensions["commander_service"]`
  - Start availability checker (non-testing only)
  - Register cleanup in atexit handler

### Response API (Backend)

- [x] 2.4 Create `routes/respond.py` — response submission endpoint
  - `POST /api/respond/<int:agent_id>` — accepts `{"text": "..."}` JSON body
  - Validates: agent exists, agent in AWAITING_INPUT state, has `claude_session_id`, commander socket reachable
  - Sends text via commander service
  - Creates Turn record (actor: USER, intent: ANSWER) with response text
  - Triggers state transition (AWAITING_INPUT → PROCESSING) via `TaskLifecycleManager.process_turn()`
  - Broadcasts state change via SSE
  - Returns JSON response with status
  - `GET /api/respond/<int:agent_id>/availability` — check commander availability for agent

- [x] 2.5 Register respond blueprint in `app.py`

### Dashboard UI (Frontend)

- [x] 2.6 Create `static/js/respond-api.js` — client-side response handler
  - `RespondAPI.sendResponse(agentId, text)` — POST to respond endpoint
  - Quick-action button click handler — sends option number
  - Free-text input submit handler — sends typed text
  - Toast notifications for success/error feedback (following `focus-api.js` pattern)
  - Visual confirmation animation on success
  - IIFE pattern with global export

- [x] 2.7 Extend dashboard template — add input widget to agent cards
  - Conditionally render input widget when agent is in AWAITING_INPUT state AND commander available
  - Parse numbered options from question text using regex (e.g., `1. Yes / 2. No`)
  - Render quick-action buttons for each parsed option
  - Render free-text input field with send button
  - Hide input widget when no commander socket available (show focus button only)
  - Wire up SSE listener for commander availability changes to show/hide widget dynamically

- [x] 2.8 Add CSS styles for input widget
  - Quick-action button styles (horizontal row, consistent with existing button patterns)
  - Free-text input field styles
  - Send button styles
  - Success highlight animation
  - Error state styles
  - Responsive layout within agent card

### Configuration

- [x] 2.9 Add commander configuration to `config.yaml`
  - `commander.health_check_interval` — seconds between health checks (default: 30)
  - `commander.socket_timeout` — socket connection timeout in seconds (default: 2)
  - `commander.socket_path_prefix` — socket path prefix (default: `/tmp/claudec-`)

## 3. Testing (Phase 3)

### Unit Tests

- [x] 3.1 Test `commander_service.py`
  - Socket path derivation from session ID
  - Send text success/failure scenarios (mock socket)
  - Health check success/failure scenarios (mock socket)
  - Error handling: connection refused, timeout, socket not found, dead process
  - Result types and error classification

- [x] 3.2 Test `commander_availability.py`
  - Availability cache updates
  - Thread safety
  - SSE broadcast on availability change

- [x] 3.3 Test `routes/respond.py`
  - Happy path: send response, verify Turn created, state transitioned
  - Agent not found → 404
  - Agent not in AWAITING_INPUT → 409
  - No claude_session_id → 400
  - Commander socket unavailable → 503
  - Commander send failure → 502
  - Availability check endpoint

### Integration Tests

- [x] 3.4 Test end-to-end response flow
  - Create agent in AWAITING_INPUT state via factories
  - Submit response via API (with mock commander socket)
  - Verify Turn record created with correct actor/intent
  - Verify task state transition to PROCESSING
  - Verify SSE broadcast fired

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete — dashboard input widget appears and functions
