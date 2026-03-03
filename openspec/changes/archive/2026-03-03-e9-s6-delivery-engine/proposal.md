# Proposal: e9-s6-delivery-engine

## Why

ChannelService (S4) persists messages in channels but nothing delivers them to recipients. The tmux bridge handles one-to-one operator-to-agent delivery but has no fan-out concept. The hook receiver captures agent responses for monitoring but cannot relay them to a channel. This sprint builds the ChannelDeliveryService — the runtime component that transforms channels from a data model into a working group communication system by implementing message fan-out, state-safe delivery queuing, and agent response capture.

## What Changes

- Create `ChannelDeliveryService` registered as `app.extensions["channel_delivery_service"]` — fan-out engine with in-memory delivery queue, envelope formatting, agent response capture, and state safety checks
- Integrate with `hook_receiver.py` `process_stop()` — relay agent COMPLETION/END_OF_COMMAND turns to the agent's active channel as new Messages
- Integrate with `command_lifecycle.py` — drain delivery queue when agents transition to safe states (AWAITING_INPUT, IDLE)
- Add `send_channel_notification()` to `NotificationService` with per-channel rate limiting (30s window)
- Strip COMMAND COMPLETE footer from relayed message content before channel delivery
- Register service in `app.py` app factory

## Impact

### Affected specs
- `channel-service` — existing spec (S4). Delivery engine calls `send_message()` for response relay. No service changes required.
- `hooks` — existing spec. `process_stop()` gains a channel relay call after the two-commit pattern.
- `state-machine` — existing spec. `command_lifecycle.py` gains queue drain calls on safe-state transitions.
- `notifications` — existing spec. `NotificationService` gains `send_channel_notification()` method.

### Affected code

**New files:**
- `src/claude_headspace/services/channel_delivery.py` — `ChannelDeliveryService` class with fan-out, queue, relay, envelope formatting

**Modified files:**
- `src/claude_headspace/services/hook_receiver.py` — Add channel relay check in `process_stop()` after two-commit pattern
- `src/claude_headspace/services/command_lifecycle.py` — Add queue drain calls on AWAITING_INPUT/IDLE transitions
- `src/claude_headspace/services/notification_service.py` — Add `send_channel_notification()` with per-channel rate limiting
- `src/claude_headspace/app.py` — Register `ChannelDeliveryService`

### Breaking changes
None — this is additive. All new methods, no existing behaviour modified. Existing hook receiver, state machine, and notification flows continue unchanged. Channel relay and queue drain are wrapped in try/except and are non-fatal.
