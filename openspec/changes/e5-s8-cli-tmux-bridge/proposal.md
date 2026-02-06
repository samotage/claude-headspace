## Why

The CLI launcher (`claude-headspace start --bridge`) still uses the failed `claudec` (claude-commander) binary to wrap Claude Code sessions. The `claudec` PTY wrapping approach was proven non-functional in e5-s1/e5-s4 — Claude Code's Ink TUI rejects programmatic stdin as non-physical keystrokes. The server-side tmux bridge (e5-s4) is complete and working, but the CLI launcher was excluded from that scope, leaving a broken `--bridge` flag that detects `claudec` instead of tmux panes.

## What Changes

- **Remove** `detect_claudec()` function and all claudec references from CLI launcher
- **Remove** `claudec_path` parameter from `launch_claude()` — always launch `claude` directly
- **Remove** `shutil` import (no longer needed)
- **Add** `get_tmux_pane_id()` function reading `$TMUX_PANE` environment variable
- **Update** `--bridge` flag to call tmux pane detection instead of claudec detection
- **Update** CLI output: `Input Bridge: available (tmux pane %N)` or `Input Bridge: unavailable (not in tmux session)`
- **Update** `register_session()` to accept and send optional `tmux_pane_id` in payload
- **Update** `POST /api/sessions` endpoint to accept `tmux_pane_id`, store on Agent, and register with `CommanderAvailability`
- **Update** `--bridge` help text to reference tmux instead of claudec
- **Update** tests: remove claudec tests, add tmux detection tests, update registration and launch tests

## Impact

- Affected specs: launcher, input-bridge, tmux-bridge
- Affected code:
  - **Modify:** `src/claude_headspace/cli/launcher.py` (remove claudec, add tmux detection, update signatures)
  - **Modify:** `src/claude_headspace/routes/sessions.py` (accept tmux_pane_id, register with availability tracker)
  - **Modify (tests):** `tests/cli/test_launcher.py` (remove claudec tests, add tmux tests)
  - **Modify (tests):** `tests/routes/test_sessions.py` (add tmux_pane_id registration tests)
- Related OpenSpec history:
  - e5-s1-input-bridge (archived 2026-02-02) — established the respond pipeline and claudec pattern being replaced
  - e5-s4-tmux-bridge (archived 2026-02-04) — established server-side tmux bridge, Agent.tmux_pane_id field, and hook backfill pattern this change front-loads
