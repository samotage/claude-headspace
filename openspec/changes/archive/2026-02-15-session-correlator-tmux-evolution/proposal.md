## Why

The session correlator recently gained tmux_pane_id-based correlation to handle context compression (where Claude Code gets a new session ID mid-conversation). However the strategy numbering is now messy (1, 2, 2.5, 2.75, 3, 4), the tmux session name isn't persisted on the Agent model, and there's no way to attach to an agent's tmux session from the dashboard. Users who start agents via voice bridge (e.g. from their phone while cycling) currently need to manually run `tmux ls` + `tmux attach -t ...` from a terminal to connect — the dashboard should handle this in one click.

## What Changes

- **Strategy renumbering**: Clean up session correlator strategy numbering from historical cruft (1, 2, 2.5, 2.75, 3, 4) to sequential 1–6 across code comments, docstrings, tests, and log messages
- **New `tmux_session` column on Agent model**: Store the tmux session name (e.g. `hs-claude-headspace-14100608`) on Agent records via Alembic migration. Captured either by setting a `CLAUDE_HEADSPACE_TMUX_SESSION` env var in the launcher (which the hook script forwards) or by extracting it via `tmux display-message -p '#S'` in the hook script
- **Dashboard "Attach" action**: New endpoint and iTerm2 AppleScript function to open a terminal tab attached to an agent's tmux session. Extends the existing `iterm_focus.py` AppleScript infrastructure with a `attach_tmux_session(session_name)` function. Reuses existing attached tab if one is already connected
- **Expose `tmux_session` in card state**: Add `tmux_session` to `build_card_state()` so the dashboard JS can display it and power the attach action

## Capabilities

### New Capabilities
- `tmux-attach`: Dashboard action and API endpoint for attaching to an agent's tmux session via iTerm2, including AppleScript execution and session name resolution

### Modified Capabilities
- `domain-models`: Agent model gains `tmux_session` column (String, nullable) with Alembic migration
- `agent-lifecycle`: Session correlator strategies renumbered 1–6; tmux session name captured and persisted during agent creation/backfill
- `hooks`: Hook payload extended to include `tmux_session` from environment variable or tmux query
- `focus`: Focus spec extended with tmux attach behaviour as a new action type alongside existing pane focus
- `dashboard`: Agent card state includes `tmux_session` field; card UI gains attach action button

## Impact

- **Models**: `Agent` model — new nullable `tmux_session` column + Alembic migration
- **Services**: `session_correlator.py` (renumbering + tmux session persistence), `iterm_focus.py` (new attach function), `card_state.py` (new field)
- **Routes**: `hooks.py` (pass tmux_session), new or extended route for attach action
- **CLI**: `launcher.py` (set `CLAUDE_HEADSPACE_TMUX_SESSION` env var)
- **Scripts**: `bin/notify-headspace.sh` (forward tmux session env var in JSON payload)
- **Frontend**: Dashboard JS + card template (attach button, tmux_session display)
- **Database**: One Alembic migration adding `tmux_session` to agents table
- **Tests**: Strategy renumbering in existing correlator tests, new tests for attach endpoint and AppleScript function
