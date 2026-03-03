# Tasks: e9-s6-delivery-engine

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 ChannelDeliveryService Core
- [x] 2.1.1 Create `src/claude_headspace/services/channel_delivery.py` with class scaffolding, `__init__()`, thread-safe queue structure (`dict[int, deque[int]]`)
- [x] 2.1.2 Implement `_format_envelope()` — channel envelope formatting `[#slug] Name (agent:ID):\n{content}`
- [x] 2.1.3 Implement `_strip_command_complete()` — regex-based COMMAND COMPLETE footer stripping
- [x] 2.1.4 Implement `_is_safe_state()` — agent state safety check (AWAITING_INPUT, IDLE = safe)
- [x] 2.1.5 Implement `_enqueue()` and `_dequeue()` — thread-safe queue add/remove operations
- [x] 2.1.6 Implement `_deliver_to_agent()` — single-agent tmux delivery with CommanderAvailability pre-check and state safety check

### 2.2 Fan-Out Engine
- [x] 2.2.1 Implement `deliver_message()` — iterate active non-muted memberships excluding sender, deliver per member type (FR1-FR4)
- [x] 2.2.2 Handle agent delivery: online (tmux), offline (deferred/log) (FR3)
- [x] 2.2.3 Handle operator delivery: notification via `send_channel_notification()` (FR3)
- [x] 2.2.4 Handle remote/external members: no-op (SSE handled by ChannelService) (FR3)
- [x] 2.2.5 Implement failure isolation: catch per-member exceptions, continue to next (FR4)

### 2.3 Agent Response Capture
- [x] 2.3.1 Implement `relay_agent_response()` — look up agent's active ChannelMembership, strip COMMAND COMPLETE, call `ChannelService.send_message()` (FR7-FR10)
- [x] 2.3.2 Verify completion-only gating: only COMPLETION and END_OF_COMMAND intents trigger relay (FR9)

### 2.4 Delivery Queue
- [x] 2.4.1 Implement `drain_queue()` — dequeue oldest message, verify agent alive and in safe state, deliver via tmux (FR13)
- [x] 2.4.2 Handle edge cases: message deleted, agent gone, pane unavailable (FR14)

### 2.5 Hook Receiver Integration
- [x] 2.5.1 Add channel relay check in `process_stop()` after two-commit pattern, before `_trigger_priority_scoring()` (FR7)
- [x] 2.5.2 Add queue drain call in `process_stop()` after `complete_command()` commit (FR13)
- [x] 2.5.3 Wrap both in try/except for non-fatal failure

### 2.6 CommandLifecycleManager Integration
- [x] 2.6.1 Add queue drain call in `update_command_state()` on transition to AWAITING_INPUT (FR13)
- [x] 2.6.2 Wrap in try/except for non-fatal failure

### 2.7 NotificationService Extension
- [x] 2.7.1 Add `_channel_rate_limit_tracker` dict and `_is_channel_rate_limited()` method
- [x] 2.7.2 Implement `send_channel_notification()` with per-channel rate limiting (30s window)

### 2.8 App Factory Registration
- [x] 2.8.1 Register `ChannelDeliveryService` as `app.extensions["channel_delivery_service"]` in `app.py`

## 3. Testing (Phase 3)

### 3.1 Unit Tests — ChannelDeliveryService
- [x] 3.1.1 Test `_format_envelope()` — correct format with agent sender, operator sender
- [x] 3.1.2 Test `_strip_command_complete()` — strips footer, preserves content without footer
- [x] 3.1.3 Test `_enqueue()` and `_dequeue()` — FIFO ordering, empty queue returns None, cleanup
- [x] 3.1.4 Test `_is_safe_state()` — returns True for AWAITING_INPUT/IDLE, False for PROCESSING/COMMANDED/COMPLETE
- [x] 3.1.5 Test `deliver_message()` — fans out to active members, skips sender, skips muted
- [x] 3.1.6 Test `deliver_message()` — queues for agents in unsafe states
- [x] 3.1.7 Test `deliver_message()` — failure isolation (one member fails, others still delivered)
- [x] 3.1.8 Test `relay_agent_response()` — posts response as channel Message with correct attribution
- [x] 3.1.9 Test `relay_agent_response()` — no-op when agent not in channel
- [x] 3.1.10 Test `drain_queue()` — delivers oldest message, handles missing message, handles gone agent

### 3.2 Integration Tests — Hook Receiver
- [x] 3.2.1 Test channel relay triggers on COMPLETION turn in process_stop
- [x] 3.2.2 Test channel relay does NOT trigger on PROGRESS/QUESTION turn
- [x] 3.2.3 Test queue drain triggers after complete_command

### 3.3 Integration Tests — NotificationService
- [x] 3.3.1 Test `send_channel_notification()` — sends notification
- [x] 3.3.2 Test per-channel rate limiting — second call within 30s is suppressed

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Service properly registered in app.extensions
- [x] 4.4 All 15 functional requirements (FR1-FR15) addressed
- [x] 4.5 All 6 non-functional requirements (NFR1-NFR6) addressed
- [x] 4.6 Existing hook receiver, lifecycle, and notification flows unaffected
