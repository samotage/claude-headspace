# Proposal Summary: e5-s4-tmux-bridge

## Architecture Decisions
- Replace Unix domain socket transport (`commander_service.py`) with tmux subprocess calls (`tmux_bridge.py`) — the only verified method for programmatic input to Claude Code's Ink TUI
- Preserve all API contracts, SSE event shapes, and dashboard JS — transport change is invisible to the frontend
- Keep `app.extensions["commander_availability"]` key for backward compatibility; add `app.extensions["tmux_bridge"]`
- Pane ID discovery via `$TMUX_PANE` environment variable extracted in hook scripts, with late-discovery fallback across all hook event types

## Implementation Approach
- **New service pattern:** `tmux_bridge.py` wraps `subprocess.run(["tmux", ...])` calls with proper error handling (FileNotFoundError, CalledProcessError, TimeoutExpired mapped to TmuxBridgeErrorType enum)
- **Critical implementation detail:** Text is sent via `send-keys -t <pane_id> -l "<text>"` (literal flag prevents key name interpretation), followed by a separate `send-keys -t <pane_id> Enter` call with 100ms delay between them
- **Replacement, not modification:** `commander_service.py` is deleted entirely; `commander_availability.py` is modified in-place to use tmux health checks instead of socket probes
- **Additive migration:** New nullable `tmux_pane_id` column on agents table, no data backfill needed

## Files to Modify

### New Files
- `src/claude_headspace/services/tmux_bridge.py` — core tmux bridge service
- `migrations/versions/xxxx_add_tmux_pane_id.py` — Alembic migration
- `tests/services/test_tmux_bridge.py` — unit tests for new service

### Modified Files
- `src/claude_headspace/models/agent.py` — add `tmux_pane_id` mapped column
- `src/claude_headspace/services/commander_availability.py` — replace socket probes with tmux pane checks, rename internal mapping from session_id to tmux_pane_id
- `src/claude_headspace/routes/respond.py` — target by tmux_pane_id, import TmuxBridgeErrorType, read tmux_bridge config
- `src/claude_headspace/routes/hooks.py` — all 8 hook handlers extract `tmux_pane` from payload
- `src/claude_headspace/services/hook_receiver.py` — `process_session_start()` gains `tmux_pane_id` parameter
- `src/claude_headspace/app.py` — register tmux_bridge extension, update commander_availability init
- `bin/notify-headspace.sh` — extract `$TMUX_PANE` and include in jq payload
- `config.yaml` — replace `commander:` with `tmux_bridge:` section

### Deleted Files
- `src/claude_headspace/services/commander_service.py`
- `tests/services/test_commander_service.py`

### Updated Test Files
- `tests/services/test_commander_availability.py` — mock tmux_bridge instead of commander_service
- `tests/routes/test_respond.py` — mock tmux_bridge, test tmux_pane_id validation
- `tests/routes/test_hooks.py` — verify tmux_pane extraction

## Acceptance Criteria
1. Dashboard respond button sends text to Claude Code via `tmux send-keys` and the agent resumes processing
2. Dual input works — user typing directly in tmux session and dashboard respond coexist
3. Hook scripts pass `$TMUX_PANE` and pane ID is persisted on Agent as `tmux_pane_id`
4. Availability checks correctly detect tmux pane existence and Claude Code process
5. API contract (`POST /api/respond/<agent_id>`) unchanged — dashboard JS works without modification
6. SSE events for availability changes continue with same event type and payload shape

## Constraints and Gotchas
- **Always use `-l` flag for user text** to prevent tmux from interpreting key names (e.g., "Enter" in user text would be interpreted as the Enter key without `-l`)
- **Send Enter as separate call** without `-l` flag — this is what triggers Ink's onSubmit
- **100ms delay between text send and Enter send** is critical to prevent race conditions (tested value)
- **150ms delay between rapid sequential sends** for reliability
- **Error detection for PANE_NOT_FOUND:** tmux returns non-zero exit code with stderr containing "can't find pane" or similar — parse CalledProcessError stderr to distinguish from other subprocess failures
- **TMUX_NOT_INSTALLED detection:** catch `FileNotFoundError` from `subprocess.run()` when tmux binary not on PATH
- **Subprocess timeout:** Use `subprocess_timeout` config value (default 5s) as `timeout` parameter to `subprocess.run()`
- **Do NOT clear tmux_pane_id on session end** — preserved for audit/debugging
- **Availability endpoint preserves `commander_available` response field name** — dashboard JS depends on this exact key name
- **Health check uses `list-panes -a`** (all panes across all sessions) to find pane by ID — don't use `has-session` which checks session names, not pane IDs

## Git Change History

### Related Files
- Services: `commander_service.py` (delete), `commander_availability.py` (modify)
- Routes: `respond.py` (modify), `hooks.py` (modify)
- Models: `agent.py` (modify)
- Hook receiver: `hook_receiver.py` (modify)
- Scripts: `bin/notify-headspace.sh` (modify)
- Config: `config.yaml` (modify)

### OpenSpec History
- e5-s1-input-bridge (archived 2026-02-02) — established the respond pipeline, commander service, availability tracking, and dashboard respond UI. This change replaces the transport layer while preserving everything else.

### Implementation Patterns
- Service module with functions (not a class) for send/health operations — matches commander_service.py pattern
- NamedTuple result types (SendResult, HealthResult) — same pattern as commander
- Background thread for availability checking — CommanderAvailability class pattern preserved
- Config read from `current_app.config["APP_CONFIG"]["tmux_bridge"]` — same pattern as commander config access

## Q&A History
- No clarifications needed — PRD is comprehensive with verified patterns from proof of concept

## Dependencies
- tmux 3.x must be installed (`brew install tmux`)
- No new Python packages required (uses stdlib subprocess module)
- No external API changes

## Testing Strategy
- **Unit tests for tmux_bridge.py:** Mock `subprocess.run` to test send_text, send_keys, check_health, capture_pane, list_panes; test all error paths (FileNotFoundError, CalledProcessError, TimeoutExpired)
- **Unit tests for commander_availability.py:** Update existing tests to mock tmux_bridge instead of commander_service; verify tmux pane checks
- **Route tests for respond.py:** Mock tmux_bridge module; test tmux_pane_id validation (400 for missing); test error type mapping to HTTP status codes
- **Route tests for hooks.py:** Verify all 8 hook routes extract tmux_pane from payload and pass through
- **Manual verification:** Send response from dashboard to a live Claude Code tmux session

## OpenSpec References
- proposal.md: openspec/changes/e5-s4-tmux-bridge/proposal.md
- tasks.md: openspec/changes/e5-s4-tmux-bridge/tasks.md
- spec.md: openspec/changes/e5-s4-tmux-bridge/specs/tmux-bridge/spec.md
