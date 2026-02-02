# Proposal: e1-s13-hook-receiver

## Summary

Add hook receiver endpoints to receive lifecycle events directly from Claude Code via hooks, providing instant (<100ms) state updates with 100% confidence instead of relying solely on 2-second polling with inferred states.

## Motivation

Currently, Claude Headspace monitors sessions via polling with 0-2 second latency and 30-90% confidence. Hook events provide direct, instant, certain signals from Claude Code itself, transforming the dashboard from "delayed inference" to "real-time truth."

## Impact

### Files to Create
- `src/claude_headspace/routes/hooks.py` - Hook event reception endpoints
- `src/claude_headspace/services/hook_receiver.py` - Hook event processing service
- `src/claude_headspace/services/session_correlator.py` - Session-to-agent correlation
- `bin/install-hooks.sh` - Hook installation script
- `bin/notify-headspace.sh` - Hook notification script template
- `docs/claude-code-hooks-settings.json` - Settings template
- `tests/routes/test_hooks.py` - Hook endpoint tests
- `tests/services/test_hook_receiver.py` - Hook receiver tests
- `tests/services/test_session_correlator.py` - Correlator tests

### Files to Modify
- `src/claude_headspace/app.py` - Register hooks blueprint
- `src/claude_headspace/config.py` - Add hook configuration options
- `templates/logging.html` - Add hook status display

### Database Changes
None - uses existing Agent model.

## Definition of Done

- [ ] POST /hook/session-start creates/activates agent in idle state
- [ ] POST /hook/user-prompt-submit transitions agent to processing
- [ ] POST /hook/stop transitions agent to idle
- [ ] POST /hook/session-end marks agent inactive
- [ ] GET /hook/status returns last event times and mode
- [ ] Session correlation matches Claude session IDs to agents
- [ ] Hybrid mode: hooks active = 60s polling, hooks silent 300s = 2s polling
- [ ] Hook notification script sends events via HTTP
- [ ] Hook notification script fails silently (always exit 0)
- [ ] Installation script creates notify-headspace.sh with absolute paths
- [ ] Installation script updates ~/.claude/settings.json
- [ ] Logging tab shows hook receiver status
- [ ] Agent cards show "last active" time
- [ ] Hook endpoints respond within 50ms
- [ ] All tests passing

## Risks

- **Users don't install hooks:** Graceful degradation to polling; clear docs
- **Hook events arrive out of order:** State machine validates transitions
- **Multiple sessions in same directory:** Last-matched wins; documented limitation
- **Installation script fails:** Clear error messages; manual fallback documented

## Alternatives Considered

1. **WebSocket from Claude Code:** Rejected - Claude Code doesn't expose WebSocket API
2. **Polling only:** Current approach - insufficient latency and confidence
3. **Hooks only:** Rejected - need fallback when hooks not installed
