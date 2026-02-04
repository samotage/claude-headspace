## Why

The Input Bridge (e5-s1) established the dashboard's respond pipeline but its transport mechanism — commander socket injection via `claudec` — fails because Claude Code's Ink TUI rejects programmatic stdin as non-keyboard input. A proof of concept confirmed that `tmux send-keys` reliably triggers Ink's `onSubmit` handler, making it the only verified programmatic input method.

## What Changes

- **New service:** `tmux_bridge.py` wrapping tmux CLI commands (`send-keys`, `list-panes`, `capture-pane`) as subprocess calls
- **Replace `commander_service.py`:** Socket-based send/health logic replaced with tmux subprocess calls; `SendResult`/`HealthResult` namedtuple shapes preserved with new `TmuxBridgeErrorType` enum
- **Replace `commander_availability.py`:** Socket-probing replaced with tmux pane existence checks; class retains `app.extensions["commander_availability"]` key for backward compatibility
- **Agent model migration:** Add nullable `tmux_pane_id` field (coexists with `iterm_pane_id`)
- **Hook script update:** `bin/notify-headspace.sh` extracts `$TMUX_PANE` and includes it in every hook payload
- **Hook routes update:** All 8 hook routes in `routes/hooks.py` extract `tmux_pane` from payload and pass through to hook receiver
- **Hook receiver update:** `process_session_start()` gains `tmux_pane_id` parameter; late discovery for other hooks
- **Respond route update:** `routes/respond.py` targets agents by `tmux_pane_id` instead of deriving socket path from `claude_session_id`; reads `config["tmux_bridge"]` instead of `config["commander"]`
- **Config update:** Replace `commander:` section with `tmux_bridge:` section (health_check_interval, subprocess_timeout, text_enter_delay_ms, sequential_send_delay_ms)
- **Extension registration:** New `app.extensions["tmux_bridge"]` service; `commander_availability` key preserved
- **Tests:** New tests for tmux_bridge service; update existing commander/respond/hooks tests

## Impact

- Affected specs: input-bridge (transport layer replacement)
- Affected code:
  - **New:** `src/claude_headspace/services/tmux_bridge.py`
  - **Replace:** `src/claude_headspace/services/commander_service.py` (delete)
  - **Modify:** `src/claude_headspace/services/commander_availability.py` (socket probes -> tmux pane checks)
  - **Modify:** `src/claude_headspace/routes/respond.py` (tmux_pane_id targeting, TmuxBridgeErrorType)
  - **Modify:** `src/claude_headspace/routes/hooks.py` (extract tmux_pane from all hook payloads)
  - **Modify:** `src/claude_headspace/services/hook_receiver.py` (tmux_pane_id parameter on process_session_start)
  - **Modify:** `src/claude_headspace/models/agent.py` (add tmux_pane_id field)
  - **Modify:** `src/claude_headspace/app.py` (register tmux_bridge extension, update commander_availability init)
  - **Modify:** `bin/notify-headspace.sh` (extract $TMUX_PANE)
  - **Modify:** `config.yaml` (replace commander: with tmux_bridge:)
  - **Migration:** New Alembic migration for tmux_pane_id column
  - **Tests (new):** `tests/services/test_tmux_bridge.py`
  - **Tests (update):** `tests/services/test_commander_availability.py`, `tests/routes/test_respond.py`, `tests/routes/test_hooks.py`
  - **Tests (delete):** `tests/services/test_commander_service.py`
- Related OpenSpec history: e5-s1-input-bridge (archived 2026-02-02) — established the respond pipeline this change rewires
