# Proposal Summary: e5-s8-cli-tmux-bridge

## Architecture Decisions
- Replace claudec detection with tmux pane detection via `$TMUX_PANE` environment variable — no subprocess calls, just `os.environ.get()`
- Follow the existing `iterm_pane_id` pattern in sessions.py for `tmux_pane_id` storage and availability registration
- Front-load availability registration at session creation time (currently deferred to first hook event via backfill)
- Always launch `claude` directly — remove wrapper binary pattern entirely

## Implementation Approach
- **Removal-first:** Delete `detect_claudec()`, `shutil` import, and `claudec_path` parameter before adding new tmux code
- **Pattern-following:** Mirror the `iterm_pane_id` extraction pattern in sessions.py for the new `tmux_pane_id` field
- **Availability registration:** Copy the pattern from `hooks.py` `_backfill_tmux_pane()` into `sessions.py` `create_session()`
- This is a focused refactor with no new models, migrations, or services — just rewiring existing capabilities

## Files to Modify

### Source Files
- `src/claude_headspace/cli/launcher.py` — Remove: `detect_claudec()`, `shutil` import, `claudec_path` param from `launch_claude()`. Add: `get_tmux_pane_id()`. Update: `cmd_start()` flow, `register_session()` signature, `--bridge` help text
- `src/claude_headspace/routes/sessions.py` — Add: `tmux_pane_id` extraction from payload, storage on Agent, `CommanderAvailability` registration

### Test Files
- `tests/cli/test_launcher.py` — Remove: `TestDetectClaudec`, claudec launch tests. Add: `TestGetTmuxPaneId`, tmux bridge tests. Update: bridge flag tests, full success test
- `tests/routes/test_sessions.py` — Add: tests for `tmux_pane_id` in registration, availability registration, backward compatibility

## Acceptance Criteria
1. `claude-headspace start --bridge` inside tmux → outputs `Input Bridge: available (tmux pane %N)`, registers pane ID
2. `claude-headspace start --bridge` outside tmux → outputs `Input Bridge: unavailable (not in tmux session)` to stderr, launches anyway
3. `claude-headspace start` without `--bridge` → no bridge detection output
4. Session registration includes `tmux_pane_id` when available, Agent has pane ID immediately
5. `CommanderAvailability` begins monitoring from session creation
6. Zero references to `claudec`, `claude-commander`, or `detect_claudec` remain

## Constraints and Gotchas
- The `--bridge` flag must be preserved with same name and short form for user alias compatibility (`clhb`)
- `tmux_pane_id` field already exists on Agent model (added in e5-s4 migration) — no migration needed
- The `CommanderAvailability` service is accessed via `current_app.extensions.get("commander_availability")` — may not be available in all contexts (check for None)
- `launch_claude()` currently has `claudec_path` as a keyword arg — tests reference it explicitly, must update all call sites
- The `register_session()` function currently has 4 positional args — adding `tmux_pane_id` as keyword-only keeps backward compatibility

## Git Change History

### Related Files
- CLI: `src/claude_headspace/cli/launcher.py`
- Routes: `src/claude_headspace/routes/sessions.py`
- Services (untouched): `src/claude_headspace/services/tmux_bridge.py`, `src/claude_headspace/services/commander_availability.py`
- Hook lifecycle (untouched): `src/claude_headspace/services/hook_lifecycle_bridge.py`

### OpenSpec History
- e5-s1-input-bridge (archived 2026-02-02) — established respond pipeline and claudec pattern
- e5-s4-tmux-bridge (archived 2026-02-04) — replaced server-side transport with tmux send-keys, added Agent.tmux_pane_id field

### Implementation Patterns
- Follow `iterm_pane_id` extraction pattern: `data.get("tmux_pane_id")` → store on Agent constructor
- Follow availability registration pattern from hooks.py: `commander_availability.register_agent(agent.id, tmux_pane_id)`
- Structure: CLI launcher changes → sessions route changes → tests

## Q&A History
- No clarification needed — PRD is comprehensive with clear file targets, code patterns, and explicit scope

## Dependencies
- No new packages required
- No new database migrations (tmux_pane_id column already exists from e5-s4)
- No new services or configuration changes

## Testing Strategy
- Unit tests for new `get_tmux_pane_id()` function (env var present/absent)
- Updated integration tests for `cmd_start()` with `--bridge` flag (tmux detection instead of claudec)
- Route tests for `POST /api/sessions` with `tmux_pane_id` field
- Negative tests: backward compatibility without `tmux_pane_id`, launch without `--bridge`

## OpenSpec References
- proposal.md: openspec/changes/e5-s8-cli-tmux-bridge/proposal.md
- tasks.md: openspec/changes/e5-s8-cli-tmux-bridge/tasks.md
- spec.md: openspec/changes/e5-s8-cli-tmux-bridge/specs/launcher/spec.md
