## 1. Strategy Renumbering

- [x] 1.1 Renumber strategy comments and docstrings in `session_correlator.py` from (1, 2, 2.5, 2.75, 3, 4) to (1, 2, 3, 4, 5, 6)
- [x] 1.2 Update log messages in `session_correlator.py` to use sequential strategy numbers
- [x] 1.3 Update `correlation_method` values in `CorrelationResult` if any reference old numbering
- [x] 1.4 Update tests in `tests/services/test_session_correlator.py` to match new numbering in comments and assertions
- [x] 1.5 Run targeted correlator tests to verify renumbering is correct

## 2. Agent Model — tmux_session Column

- [x] 2.1 Add `tmux_session: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)` to Agent model in `models/agent.py`
- [x] 2.2 Generate Alembic migration: `flask db migrate -m "add tmux_session to agents"`
- [x] 2.3 Review generated migration and apply: `flask db upgrade`

## 3. Data Capture Pipeline — Launcher + Hook Script + Server

- [x] 3.1 Set `CLAUDE_HEADSPACE_TMUX_SESSION` env var in `cli/launcher.py` before `os.execvp`, using the `session_name` variable (line ~452)
- [x] 3.2 Read `CLAUDE_HEADSPACE_TMUX_SESSION` from environment in `bin/notify-headspace.sh` and include as `tmux_session` in JSON payload
- [x] 3.3 Extract `tmux_session` from request JSON in all 8 hook routes in `routes/hooks.py` and pass it through to the lifecycle bridge
- [x] 3.4 Extend `hook_lifecycle_bridge.py` backfill logic to set `agent.tmux_session` from the hook payload (alongside existing `tmux_pane_id` backfill)

## 4. Card State — Expose tmux_session

- [x] 4.1 Add `tmux_session` field to the dict returned by `build_card_state()` in `services/card_state.py`

## 5. Attach — AppleScript Function

- [x] 5.1 Add `attach_tmux_session(session_name)` function to `services/iterm_focus.py` that: checks for existing attached tab via `tmux list-clients`, focuses it if found, otherwise opens new iTerm2 tab with `tmux attach -t <name>`
- [x] 5.2 Add `check_tmux_session_exists(session_name)` helper that runs `tmux has-session -t <name>` and returns bool

## 6. Attach — API Endpoint

- [ ] 6.1 Add `POST /api/agents/<id>/attach` route in `routes/focus.py` that validates agent, checks tmux_session exists, calls `attach_tmux_session()`, returns result
- [ ] 6.2 Add attach event logging following the existing `_log_focus_event` pattern

## 7. Dashboard UI — Attach Button

- [x] 7.1 Add attach button to agent card template (visible when `tmux_session` is non-null)
- [x] 7.2 Add JS click handler that POSTs to `/api/agents/<id>/attach` and shows success/error feedback
- [x] 7.3 Ensure SSE `card_refresh` events correctly show/hide the attach button based on `tmux_session`

## 8. Tests

- [x] 8.1 Add unit tests for `attach_tmux_session()` in `tests/services/test_iterm_focus.py` (mock subprocess)
- [x] 8.2 Add unit tests for `check_tmux_session_exists()` in `tests/services/test_iterm_focus.py`
- [x] 8.3 Add route tests for `POST /api/agents/<id>/attach` in `tests/routes/test_focus.py` (success, no session, session not found, agent not found)
- [x] 8.4 Add test for `tmux_session` in `build_card_state()` output in `tests/services/test_card_state.py`
- [x] 8.5 Add test for `tmux_session` backfill in hook lifecycle bridge tests
- [x] 8.6 Run all targeted tests for modified files
