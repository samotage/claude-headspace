# Proposal Summary: channel-delivery-restart-resilience

## Architecture Decisions

1. **Init-time reconstruction only** — State is rebuilt once during `ChannelDeliveryService.__init__`, not lazily or on every call. This avoids runtime overhead and naturally serialises with request handling.

2. **Database-only, no external deps** — Reconstruction queries the existing `Message`, `ChannelMembership`, and `Agent` tables. No Redis, no new tables, no migrations. This is Phase 1; Phase 2 (Redis-backed ephemeral state) is a separate PRD.

3. **Stale cutoff threshold** — A 1-hour configurable cutoff prevents false positives from old channel conversations. Read from `channels.reconstruction_cutoff_minutes` in config, defaulting to 60.

4. **Error isolation** — Reconstruction failures are caught and logged at WARNING level. The service remains fully functional without reconstruction — it just behaves as it does today (empty state on restart).

5. **Idempotent by design** — `_channel_prompted` and `_queue` are cleared before repopulation, making reconstruction safe to call multiple times.

## Implementation Approach

Add three private methods to `ChannelDeliveryService`:

1. **`_reconstruct_channel_prompted(cutoff)`** — Single SQL query using subqueries to compare per-agent last-received vs last-sent timestamps within active memberships. Agents where `last_received > last_sent` (or `last_sent IS NULL`) within the cutoff window get added to `_channel_prompted`.

2. **`_reconstruct_queue(cutoff)`** — Query for channel messages sent after each agent's last response where the agent's current command is in an unsafe state. Uses SQLAlchemy ORM queries with joins on `ChannelMembership`, `Agent`, `Command`, and `Message`.

3. **`_reconstruct_state()`** — Orchestrator that clears existing state, calls both reconstruction methods, measures timing, and logs results. Called from `__init__` wrapped in try/except.

The query approach uses lateral/correlated subqueries to avoid N+1 patterns — bounded query count regardless of channel/member count.

## Files to Modify

### Service (primary)
- `src/claude_headspace/services/channel_delivery.py` — Add `_reconstruct_state()`, `_reconstruct_channel_prompted()`, `_reconstruct_queue()` methods; call from `__init__`

### Tests
- `tests/services/test_channel_delivery.py` — Add 8 new test cases covering reconstruction scenarios (prompted, already responded, stale cutoff, queue, ended agents, inactive memberships, idempotency, error isolation)

### No changes required
- `src/claude_headspace/models/message.py` — read-only queries
- `src/claude_headspace/models/channel_membership.py` — read-only queries
- `src/claude_headspace/models/agent.py` — read-only queries
- `src/claude_headspace/models/command.py` — read-only (CommandState enum referenced)

## Acceptance Criteria

1. After a server restart during an active channel conversation, agent responses pending before the restart are relayed correctly when the agent's stop hook fires
2. No false positives: agents NOT prompted by channel messages before restart do not leak DM responses into channels
3. Queued messages for agents in unsafe states are re-queued on restart
4. Reconstruction runs exactly once on service init
5. Reconstruction completes in under 100ms for typical channel sizes
6. All existing tests continue to pass
7. 8 new test cases pass covering reconstruction scenarios

## Constraints and Gotchas

- **App context required** — `__init__` receives `app`, so app context is available. Reconstruction queries must run within this context.
- **Thread safety** — Reconstruction runs in `__init__` before any requests are handled, so no concurrent access concerns. The `_queue_lock` should still be used when populating `_queue` for consistency.
- **Agent.get_current_command()** — This method queries the DB for the agent's most recent command. During queue reconstruction, we need to check each agent's command state, which is an additional query per agent unless batched. Consider pre-fetching current commands in the queue reconstruction query.
- **werkzeug reloader** — The reloader creates a new process and re-imports the app, which calls `__init__` on all services. Reconstruction will run on every reload — must be fast.
- **Recent delivery refactoring** — Commits `8d9a823e` and `a811c81c` removed the command state gate from delivery. Queue reconstruction (FR2) still needs to check command states to identify agents that *should* have been queued but weren't delivered, which is a different semantic from the delivery gate removal.

## Git Change History

### Related files (recent commits)
- `channel_delivery.py` — 3 commits in last 2 days: removed command state gate, switched to lightweight tmux delivery, fixed conversational relay
- Channel subsystem overall — 20 commits in last 2 days covering creation redesign, member pills, voice bridge integration
- No active OpenSpec changes (directory was empty at prepare time)

### OpenSpec history
- `e9-s8-voice-bridge-channels` (archived 2026-03-03) — Channel integration for voice bridge; affected specs: channel-context-tracking, channel-intent-detection, channel-name-matching, voice-formatter-channels, voice-pwa-channels

### Patterns detected
- Service modules in `src/claude_headspace/services/`
- Tests in `tests/services/`
- No templates or static files affected

## Q&A History

No clarifications needed — PRD was clear with no gaps or conflicts identified during proposal review.

## Dependencies

- No new Python packages
- No new APIs or external services
- No database migrations
- No configuration changes required (optional `channels.reconstruction_cutoff_minutes` follows existing config pattern)

## Testing Strategy

- **Unit tests** (8 new cases in `tests/services/test_channel_delivery.py`):
  - Reconstruction of `_channel_prompted` — basic case (agent prompted, not responded)
  - Reconstruction skips agents that already responded
  - Reconstruction respects stale message cutoff
  - Reconstruction of `_queue` — agents in unsafe command states
  - Reconstruction skips ended agents
  - Reconstruction skips inactive memberships
  - Idempotent reconstruction (call twice, no duplicates)
  - Error isolation (DB error during reconstruction, service still works)
- **Regression**: All existing `test_channel_delivery.py` tests must continue to pass
- **Manual verification**: Restart server during active channel conversation, verify agent relay works

## OpenSpec References

- Proposal: `openspec/changes/channel-delivery-restart-resilience/proposal.md`
- Tasks: `openspec/changes/channel-delivery-restart-resilience/tasks.md`
- Spec: `openspec/changes/channel-delivery-restart-resilience/specs/channel-delivery/spec.md`
