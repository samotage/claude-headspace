---
validation:
  status: valid
  validated_at: '2026-03-07T16:57:54+11:00'
---

## Product Requirements Document (PRD) — Channel Delivery Restart Resilience

**Project:** Claude Headspace
**Scope:** Reconstruct channel delivery state from database on server restart
**Author:** Shorty (with Mark)
**Status:** Draft

---

## Executive Summary

Server restarts — particularly werkzeug debug reloads during active development — wipe the in-memory state that `ChannelDeliveryService` uses to track which agents have been prompted by channel messages and which messages are queued for delivery. This causes agent responses to be silently dropped because the relay gate (`_channel_prompted`) rejects them as "likely a direct/DM conversation."

This PRD specifies the requirements for reconstructing channel delivery state from existing database records on service initialisation. The fix uses data already persisted in the `Message` table — no new dependencies, tables, or infrastructure.

This is Phase 1 of a two-phase approach to server restart resilience. Phase 2 (Redis-backed ephemeral state across all services) is addressed in a separate PRD.

---

## 1. Context & Purpose

### 1.1 Context

`ChannelDeliveryService` maintains two in-memory data structures critical to channel message flow:

1. **`_channel_prompted: set[int]`** — Tracks agent IDs that received a channel message via tmux and haven't yet responded. The `relay_agent_response()` method checks this set before relaying an agent's completion back to the channel. If the agent is not in this set, the response is silently dropped.

2. **`_queue: dict[int, deque[int]]`** — Holds Message IDs for agents that were in unsafe command states (PROCESSING, COMMANDED) when a channel message arrived. These messages are delivered when the agent transitions to a safe state.

Both structures are initialised empty on every server start. During development, werkzeug's debug reloader triggers frequently (on any Python file save), wiping this state mid-conversation. Observed failure: three agents had their channel responses silently dropped after a single reload at 16:04:58, with log entries incorrectly attributing the drops to "likely a direct/DM conversation."

### 1.2 Target User

Operators and developers using channel-based multi-agent workshops during active development of Claude Headspace.

### 1.3 Success Moment

A server restart occurs mid-conversation in a channel workshop. Agents that were prompted before the restart complete their responses, and those responses appear in the channel as expected — no silent drops, no manual intervention.

---

## 2. Scope

### 2.1 In Scope

- Reconstruction of `_channel_prompted` state from `Message` table records on `ChannelDeliveryService.__init__`
- Reconstruction of `_queue` state from `Message` table records on init
- Logging of reconstruction results for operational visibility
- Tests covering restart reconstruction scenarios

### 2.2 Out of Scope

- Redis or any external backing store (Phase 2)
- Reconstruction of other services' in-memory state (Broadcaster replay buffer, InferenceCache, SessionRegistry, etc.)
- Changes to the `Message` model or database schema
- Changes to the delivery or relay logic itself
- New configuration options (reconstruction is always-on, no toggle)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. After a server restart during an active channel conversation, agent responses that were pending before the restart are relayed to the channel when the agent's stop hook fires
2. No false positives: agents that were NOT prompted by a channel message before the restart do not have their DM/direct responses leak into channels
3. Queued messages (for agents in unsafe states at restart time) are re-queued and delivered when the agent transitions to a safe state
4. Reconstruction runs exactly once on service init — not on every relay or delivery call

### 3.2 Non-Functional Success Criteria

1. Reconstruction query completes in under 100ms for typical channel sizes (≤10 active members, ≤1000 messages per channel)
2. No additional database load during normal operation (reconstruction is init-only)

---

## 4. Functional Requirements (FRs)

**FR1: Reconstruct `_channel_prompted` on init**

On `ChannelDeliveryService.__init__`, the service must query the database to identify agents that were prompted by a channel message but have not yet responded. An agent is considered "prompted but unresponded" when:

- The agent has an active `ChannelMembership` (status = "active")
- The agent is alive (Agent.ended_at is NULL)
- The most recent `Message` in the agent's channel that was NOT sent by this agent is more recent than the most recent `Message` sent BY this agent in the same channel
- OR the agent has never sent a message in the channel but messages from others exist

These agent IDs must be added to `_channel_prompted`.

**FR2: Reconstruct `_queue` on init**

On init, the service must identify messages that were sent to a channel but may not have been delivered to all member agents. A message is considered "potentially undelivered" when:

- The message was sent to a channel with active agent members
- The agent member was in an unsafe command state (not AWAITING_INPUT or IDLE) at the time — approximated by checking if the agent's current command is in an unsafe state AND the message was sent after the agent's last response in that channel
- The message was not sent by the agent in question

These Message IDs must be added to the agent's delivery queue in `_queue`.

**FR3: Reconstruction logging**

The service must log the results of reconstruction at INFO level:
- Number of agents added to `_channel_prompted`
- Number of messages re-queued per agent
- Total reconstruction time
- If no state was reconstructed, log that explicitly (avoids confusion about whether reconstruction ran)

**FR4: Reconstruction safety — no false positives**

The reconstruction logic must not add agents to `_channel_prompted` when:
- The agent's most recent message in the channel is more recent than the most recent message from others (agent has already responded)
- The channel is not active (status != "active" or "pending")
- The agent has ended (Agent.ended_at is not NULL)
- The membership is not active (status != "active")

**FR5: Reconstruction safety — stale message cutoff**

Reconstruction must apply a time cutoff to avoid reconstructing state from very old messages. Messages older than a configurable threshold (default: 1 hour) should not trigger `_channel_prompted` reconstruction. This prevents false positives from channels with long gaps between messages.

**FR6: Idempotent reconstruction**

The reconstruction must be safe to run multiple times (e.g., if the service is re-initialised within the same process). Running reconstruction when `_channel_prompted` is already populated must not create duplicates or corrupt state.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Query efficiency**

Reconstruction queries must use appropriate joins and filtering to avoid N+1 query patterns. The reconstruction should execute a bounded number of queries regardless of channel count (preferably 1-2 queries total, not per-channel).

**NFR2: Thread safety**

Reconstruction populates `_channel_prompted` and `_queue` before the service handles any requests. If reconstruction runs during `__init__`, this is naturally serialised. If moved to a lazy-init pattern in future, it must be thread-safe.

**NFR3: No migration required**

The reconstruction must work with the existing database schema. No new columns, tables, or indexes. The existing `Message` table indexes on `channel_id` and `agent_id` are sufficient.

---

## 6. Technical Context

### 6.1 Key Files

| File | Role |
|------|------|
| `src/claude_headspace/services/channel_delivery.py` | Service under modification — `__init__`, `_channel_prompted`, `_queue` |
| `src/claude_headspace/models/message.py` | `Message` model — `channel_id`, `agent_id`, `persona_id`, `sent_at`, `source_turn_id` |
| `src/claude_headspace/models/channel_membership.py` | `ChannelMembership` — `channel_id`, `agent_id`, `persona_id`, `status` |
| `src/claude_headspace/models/agent.py` | `Agent` — `ended_at`, `get_current_command()` |
| `src/claude_headspace/models/command.py` | `Command` — `state`, `CommandState` enum |
| `tests/services/test_channel_delivery.py` | Existing tests (must continue to pass) |

### 6.2 Existing Patterns

- Services receive `app` in `__init__` and have access to `db.session` via the app context
- The `_channel_prompted` set uses `agent.id` (int) as keys
- The `_queue` dict uses `agent.id` (int) → `deque[int]` (Message IDs)
- `clear_agent_queue()` already handles cleanup of both structures for a single agent

### 6.3 Reconstruction Query Shape

The core reconstruction for `_channel_prompted` can be expressed as:

```
For each (agent_id, channel_id) in active memberships with live agents:
  last_received = MAX(sent_at) FROM messages
                  WHERE channel_id = X AND agent_id != A AND sent_at > cutoff
  last_sent     = MAX(sent_at) FROM messages
                  WHERE channel_id = X AND agent_id = A
  IF last_received > last_sent (or last_sent is NULL):
    → add agent_id to _channel_prompted
```

This should be expressible as 1-2 SQL queries with subqueries or lateral joins, not a Python loop with per-agent queries.

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-03-07 | Shorty | Initial draft from workshop #workshop-mark-shorty-21 |
