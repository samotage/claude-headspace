## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [ ] 2.1 Add `_reconstruct_channel_prompted()` method to `ChannelDeliveryService`
  - Query active `ChannelMembership` records with live agents (ended_at IS NULL)
  - For each (agent_id, channel_id) pair, compare last received vs last sent message timestamps
  - Apply 1-hour stale message cutoff (configurable via `channels.reconstruction_cutoff_minutes` in config)
  - Add qualifying agent IDs to `_channel_prompted` set
  - Use 1-2 SQL queries with subqueries — no N+1 per-agent loops

- [ ] 2.2 Add `_reconstruct_queue()` method to `ChannelDeliveryService`
  - Identify messages sent to channels where agent members were in unsafe command states
  - Check agent's current command state and compare message timestamps against agent's last response
  - Add undelivered Message IDs to `_queue` dict per agent
  - Use efficient SQL with joins — bounded query count regardless of channel count

- [ ] 2.3 Add `_reconstruct_state()` orchestrator method
  - Call `_reconstruct_channel_prompted()` then `_reconstruct_queue()`
  - Measure and log total reconstruction time
  - Log counts: agents added to prompted set, messages re-queued per agent
  - Log explicitly if no state was reconstructed
  - Clear sets/dicts before populating (idempotency)

- [ ] 2.4 Call `_reconstruct_state()` from `__init__`
  - Must run within app context (available in `__init__` since `app` is passed)
  - Wrap in try/except to prevent reconstruction failures from blocking service startup
  - Log any reconstruction errors as WARNING (service remains functional without reconstruction)

## 3. Testing (Phase 3)

- [ ] 3.1 Test reconstruction of `_channel_prompted` — basic case
  - Create channel with two agent members, one message from agent A to channel
  - Restart service (new instance) — agent B should be in `_channel_prompted`

- [ ] 3.2 Test reconstruction skips agents that already responded
  - Agent B's last message is more recent than last message from others
  - Restart service — agent B should NOT be in `_channel_prompted`

- [ ] 3.3 Test reconstruction respects stale message cutoff
  - All messages older than cutoff threshold
  - Restart service — `_channel_prompted` should be empty

- [ ] 3.4 Test reconstruction of `_queue` — agents in unsafe states
  - Agent in PROCESSING state with undelivered channel messages
  - Restart service — messages should be in agent's queue

- [ ] 3.5 Test reconstruction skips ended agents
  - Agent with ended_at set — should not be reconstructed

- [ ] 3.6 Test reconstruction skips inactive memberships
  - Membership with status != "active" — should not be reconstructed

- [ ] 3.7 Test idempotent reconstruction
  - Call `_reconstruct_state()` twice — no duplicates in sets/dicts

- [ ] 3.8 Test reconstruction error isolation
  - DB error during reconstruction — service still initialises

- [ ] 3.9 Existing tests continue to pass
  - All existing `test_channel_delivery.py` tests remain green

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: restart server during active channel conversation, verify relay works
