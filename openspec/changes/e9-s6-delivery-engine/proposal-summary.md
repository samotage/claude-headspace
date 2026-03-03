# Proposal Summary: e9-s6-delivery-engine

## Architecture Decisions
- `ChannelDeliveryService` is a post-commit side effect service — invoked after `ChannelService.send_message()` commits, not as middleware or a database trigger
- In-memory delivery queue (`dict[int, deque[int]]`) with `threading.Lock` — no database queue table, no delivery tracking. Messages already persist in channel history; the queue only tracks pending tmux deliveries
- State safety: only AWAITING_INPUT and IDLE states are safe for tmux delivery. PROCESSING, COMMANDED, and COMPLETE queue messages. Queue drains one message per state transition (natural pacing)
- Completion-only relay: only COMPLETION and END_OF_COMMAND turns are relayed to channels. PROGRESS, QUESTION, and tool-use output never fan out — prevents intermediate noise and rapid ping-pong
- Best-effort delivery: no retry logic, no delivery tracking table. Failed deliveries are logged and the message persists in channel history for context briefing on next agent spin-up
- Envelope format `[#channel-slug] PersonaName (agent:ID):\n{content}` — signals channel context to receiving agents without requiring them to parse structure
- COMMAND COMPLETE footer is stripped from relayed content (metadata, not conversational) but retained on the individual Turn record
- Feedback loop prevention via three independent layers: completion-only relay, source tracking (`source_turn_id`), and IntentDetector gating
- No new database tables or columns — uses existing Message and ChannelMembership models from S3
- Per-channel notification rate limiting (30s window) on NotificationService — prevents notification spam during active channel conversations

## Implementation Approach
- Create 1 new file: `channel_delivery.py` (ChannelDeliveryService)
- Modify 4 existing files: `hook_receiver.py` (relay + drain), `command_lifecycle.py` (drain), `notification_service.py` (channel notifications), `app.py` (registration)
- All integration points are wrapped in try/except — channel delivery is non-fatal and never blocks existing flows
- Fan-out uses existing tmux bridge `send_text()` with per-pane `RLock` — no new locking or concurrency primitives
- CommanderAvailability pre-check before tmux delivery — uses existing cached pane health, no subprocess calls
- `relay_agent_response()` calls `ChannelService.send_message()` which triggers `deliver_message()` recursively for fan-out to other members

## Files to Modify

### New Files
- `src/claude_headspace/services/channel_delivery.py` — `ChannelDeliveryService` class: `deliver_message()`, `relay_agent_response()`, `drain_queue()`, `_enqueue()`, `_dequeue()`, `_format_envelope()`, `_strip_command_complete()`, `_is_safe_state()`, `_deliver_to_agent()`

### Modified Files
- `src/claude_headspace/services/hook_receiver.py` — Add channel relay check in `process_stop()` after two-commit pattern (line ~1390+), and queue drain after `complete_command()` commit
- `src/claude_headspace/services/command_lifecycle.py` — Add queue drain call in `update_command_state()` on transition to AWAITING_INPUT
- `src/claude_headspace/services/notification_service.py` — Add `_channel_rate_limit_tracker` dict, `_is_channel_rate_limited()` method, and `send_channel_notification()` method
- `src/claude_headspace/app.py` — Register `ChannelDeliveryService` as `app.extensions["channel_delivery_service"]`

### Test Files (New)
- `tests/services/test_channel_delivery.py` — Unit tests for ChannelDeliveryService (~15 test functions)

## Acceptance Criteria
1. When `ChannelService.send_message()` commits, all active non-muted members (excluding sender) receive delivery
2. Internal online agents receive messages via tmux with envelope format `[#slug] Name (agent:ID):\n{content}`
3. Operator receives macOS notification via `send_channel_notification()`
4. Offline agents have messages deferred (persist in channel history)
5. Remote/external members receive no direct delivery (SSE handled by ChannelService)
6. Agents in PROCESSING/COMMANDED/COMPLETE have messages queued
7. Queue drains FIFO when agent transitions to AWAITING_INPUT or IDLE
8. Agent COMPLETION/END_OF_COMMAND turns are relayed as new channel Messages
9. PROGRESS/QUESTION turns are NOT relayed
10. COMMAND COMPLETE footer is stripped from relayed content
11. Per-member delivery failures do not block other members
12. Unavailable tmux panes cause queuing, not failure
13. Per-channel notification rate limiting (30s) prevents notification spam
14. All integration points are non-fatal (try/except wrapped)

## Constraints and Gotchas
- `deliver_message()` is called AFTER `db.session.commit()` in `ChannelService.send_message()` — the Message must exist in DB before fan-out
- `relay_agent_response()` calls `ChannelService.send_message()` which triggers another `deliver_message()` — this is the recursive fan-out by design, not a bug
- Queue drain delivers ONE message per call — natural pacing via state machine. Agent processes message, transitions, next drain fires
- In-memory queue is lost on server restart — messages persist in channel history for context briefing
- `_is_safe_state()` derives state from `CommandLifecycleManager` — it queries the current command, not the agent model directly
- `CommanderAvailability.is_available()` is a cached read — no subprocess overhead during fan-out
- The channel relay in `process_stop()` must be AFTER both commits (turn commit + state transition commit) — the Turn must exist in DB for `source_turn_id` FK

## Git Change History

### Related Files
- `src/claude_headspace/services/channel_service.py` — ChannelService class (S4, already exists) with `send_message()` method
- `src/claude_headspace/services/tmux_bridge.py` — `send_text()` delivery primitive (already exists, no changes)
- `src/claude_headspace/services/commander_availability.py` — `is_available()` pane health check (already exists, no changes)
- `src/claude_headspace/services/intent_detector.py` — Turn classification (already exists, no changes)
- `src/claude_headspace/models/channel.py` — Channel, ChannelMembership, Message models (S3, already exist)

### OpenSpec History
- `e9-s5-api-sse-endpoints` (archived) — Created channels_api blueprint with REST endpoints
- `e9-s4-channel-service-cli` (archived) — Created ChannelService with `send_message()` and all business logic
- `e9-s3-channel-data-model` (archived) — Created Channel, ChannelMembership, Message models
- `e9-s2-persona-type-system` (archived) — Added PersonaType and channel capabilities
- `e9-s1-handoff-improvements` (archived) — Handoff improvements

### Implementation Patterns
- Service registration: Follow existing `app.extensions["channel_service"]` pattern in app.py
- Post-commit side effect: Same pattern as SSE broadcasts and notification triggers in ChannelService
- Non-fatal integration: Wrap in try/except like existing channel relay patterns
- Service access: `current_app.extensions["channel_delivery_service"]`
- State derivation: Use `CommandLifecycleManager.derive_agent_state()` pattern

## Q&A History
- No clarifications needed — all design decisions resolved in Inter-Agent Communication Workshop Sections 0 and 3

## Dependencies

### Internal Dependencies (Already Implemented)
- ChannelService (S4) — `send_message()` for response relay
- Channel, ChannelMembership, Message models (S3) — data model
- PersonaType system (S2) — member type resolution
- TmuxBridge (E5-S4) — `send_text()` delivery primitive
- CommanderAvailability (E6-S2) — pane health monitoring
- HookReceiver (E3-S1) — `process_stop()` integration point
- CommandLifecycleManager (E2-S3) — state transitions, queue drain trigger
- NotificationService (E4-S3) — macOS notifications
- IntentDetector (E3-S2) — turn classification for completion-only relay

### No External Dependencies
- No new pip packages required
- No new npm packages required

## Testing Strategy

### Unit Tests (test_channel_delivery.py)
- Envelope formatting (agent sender, operator sender)
- COMMAND COMPLETE stripping (with and without footer)
- Queue operations (FIFO, empty queue, cleanup)
- State safety checks (safe and unsafe states)
- Fan-out delivery (active members, skip sender, skip muted)
- Unsafe state queuing
- Failure isolation
- Response relay (attribution, no-op when not in channel)
- Queue drain (oldest message, missing message, gone agent)

### Integration Points
- Hook receiver channel relay triggers on COMPLETION
- Hook receiver channel relay does NOT trigger on PROGRESS/QUESTION
- Queue drain triggers after state transitions
- Notification rate limiting

## OpenSpec References
- proposal.md: openspec/changes/e9-s6-delivery-engine/proposal.md
- tasks.md: openspec/changes/e9-s6-delivery-engine/tasks.md
- specs:
  - openspec/changes/e9-s6-delivery-engine/specs/channel-delivery/spec.md
