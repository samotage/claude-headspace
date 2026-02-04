## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Core Service

- [ ] 2.1.1 Create `src/claude_headspace/services/tmux_bridge.py` with:
  - `TmuxBridgeErrorType` enum (PANE_NOT_FOUND, TMUX_NOT_INSTALLED, SUBPROCESS_FAILED, NO_PANE_ID, TIMEOUT, SEND_FAILED, UNKNOWN)
  - `SendResult` and `HealthResult` namedtuples (same shape as commander, referencing TmuxBridgeErrorType)
  - `send_text(pane_id, text, config)` — sends literal text via `send-keys -t -l` then Enter as separate call with configurable delay
  - `send_keys(pane_id, *keys, config)` — sends special keys (Enter, Escape, Up, Down, C-c, C-u)
  - `check_health(pane_id, config)` — checks pane exists + Claude Code running via `list-panes`
  - `capture_pane(pane_id, lines, config)` — captures last N lines via `capture-pane`
  - `list_panes(config)` — lists all panes with metadata (pane_id, session, command, cwd)
  - Error handling: catch `FileNotFoundError` (TMUX_NOT_INSTALLED), `CalledProcessError` (map to PANE_NOT_FOUND or SUBPROCESS_FAILED), `TimeoutExpired` (TIMEOUT)

### 2.2 Database Migration

- [ ] 2.2.1 Create Alembic migration to add `tmux_pane_id` nullable string column to `agents` table
- [ ] 2.2.2 Update Agent model (`models/agent.py`) to add `tmux_pane_id` mapped column

### 2.3 Hook Script

- [ ] 2.3.1 Update `bin/notify-headspace.sh` to extract `$TMUX_PANE` env var and include `tmux_pane` field in every hook payload via jq

### 2.4 Hook Routes & Receiver

- [ ] 2.4.1 Update `routes/hooks.py` — all 8 hook route handlers extract `tmux_pane = data.get("tmux_pane")`:
  - `hook_session_start()`: pass `tmux_pane_id=tmux_pane` to `process_session_start()`
  - All other hooks: if `tmux_pane` present and `agent.tmux_pane_id` not set, store it (late discovery) and register with availability tracker
- [ ] 2.4.2 Update `hook_receiver.py` — `process_session_start()` gains `tmux_pane_id: str | None = None` parameter; stores on agent and registers with availability tracker

### 2.5 Availability Tracker

- [ ] 2.5.1 Update `commander_availability.py`:
  - Internal mapping changes from `agent_id -> session_id` to `agent_id -> tmux_pane_id`
  - `register_agent(agent_id, tmux_pane_id)` parameter renamed
  - `check_agent(agent_id, tmux_pane_id=None)` parameter renamed
  - Health check calls `tmux_bridge.check_health()` instead of `commander_service.check_health()`
  - Config reads from `tmux_bridge:` section instead of `commander:`
  - Import `tmux_bridge` instead of `commander_service`

### 2.6 Respond Route

- [ ] 2.6.1 Update `routes/respond.py`:
  - Import `TmuxBridgeErrorType` and tmux_bridge module instead of commander_service
  - `respond_to_agent()`: validate `agent.tmux_pane_id` instead of `agent.claude_session_id`; call tmux_bridge.send_text() with pane_id; map TmuxBridgeErrorType to HTTP status codes
  - `check_availability()`: use `agent.tmux_pane_id` instead of `agent.claude_session_id`; preserve `commander_available` response field name

### 2.7 App Registration & Config

- [ ] 2.7.1 Update `app.py`: register `tmux_bridge` in `app.extensions["tmux_bridge"]`; update commander_availability init to not depend on commander_service
- [ ] 2.7.2 Update `config.yaml`: replace `commander:` with `tmux_bridge:` section (health_check_interval: 30, subprocess_timeout: 5, text_enter_delay_ms: 100, sequential_send_delay_ms: 150)

### 2.8 Cleanup

- [ ] 2.8.1 Delete `src/claude_headspace/services/commander_service.py`

## 3. Testing (Phase 3)

- [ ] 3.1 Create `tests/services/test_tmux_bridge.py` — unit tests for send_text, send_keys, check_health, capture_pane, list_panes, error handling (mock subprocess)
- [ ] 3.2 Update `tests/services/test_commander_availability.py` — update mocks from commander_service to tmux_bridge; verify tmux pane checks
- [ ] 3.3 Update `tests/routes/test_respond.py` — update mocks for tmux_bridge; test tmux_pane_id validation; test TmuxBridgeErrorType mapping
- [ ] 3.4 Update `tests/routes/test_hooks.py` — verify tmux_pane extraction and passthrough for all hook routes
- [ ] 3.5 Delete `tests/services/test_commander_service.py`

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete (send response via dashboard to tmux session)
