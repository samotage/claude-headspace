---
validation:
  status: pending
---

## Product Requirements Document (PRD) — Channel Delivery Engine

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 6 — ChannelDeliveryService: fan-out, response capture, delivery queue
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The channel data model (S3) and ChannelService (S4) give Headspace a way to record messages in channels. This sprint builds the engine that actually delivers those messages to channel members and captures agent responses back into the channel — the fan-out loop that makes group chat work.

The ChannelDeliveryService is a post-commit side effect service. When `ChannelService.send_message()` persists a Message, the delivery engine iterates active (non-muted) members excluding the sender and delivers per member type: tmux `send_text()` for internal online agents, SSE `channel_message` events for operators and remote agents, and deferred storage for offline personas. Agent responses are captured via the existing hook receiver pipeline — when an agent's stop hook fires and the resulting Turn is classified as COMPLETION or END_OF_COMMAND, the delivery engine checks whether the agent is a member of an active channel and, if so, posts the response as a new channel Message that fans out to all other members.

Delivery respects agent state safety. Only agents in AWAITING_INPUT or IDLE states receive messages immediately via tmux. Agents in PROCESSING, COMMANDED, or COMPLETE states have messages queued in an in-memory delivery queue (dict of agent_id to deque of Message IDs). When the CommandLifecycleManager transitions an agent to a safe state, the queue drains FIFO. Feedback loops are prevented by three mechanisms: completion-only relay (no PROGRESS/tool-use noise), source tracking (`source_turn_id` on Messages), and IntentDetector gating.

All design decisions are resolved in the Inter-Agent Communication Workshop, Section 3 (Decisions 3.1-3.4) and Section 0 (Decisions 0.1-0.3). See `docs/workshop/interagent-communication/sections/section-3-message-delivery.md` and `docs/workshop/interagent-communication/sections/section-0-infrastructure-audit.md`.

---

## 1. Context & Purpose

### 1.1 Context

With the channel data model (S3) and ChannelService (S4) in place, Headspace can create channels, manage membership, and persist messages. But messages sit in the database — nothing delivers them to recipients. The tmux bridge exists for operator-to-agent delivery (one sender, one recipient), but has no concept of fan-out to multiple members. The hook receiver captures agent responses for monitoring, but has no concept of relaying those responses to a channel.

The delivery engine closes both gaps. It is the runtime component that transforms channels from a data model into a working group communication system.

The infrastructure audit (Workshop Section 0) confirmed that the existing tmux bridge supports concurrent fan-out: per-pane `RLock` (not a global lock) means delivery to N agents is N parallel tmux operations. The `send_text()` method handles messages over 4KB via `load-buffer` + `paste-buffer`. The `CommanderAvailability` service already monitors pane health per agent. All the delivery primitives exist — this sprint wires them together with fan-out logic, state safety, and response capture.

### 1.2 Target User

The operator (Sam), who creates channels and expects messages to flow between members without manual intervention. Agents, who receive channel messages via tmux and respond naturally — unaware they are in a channel.

### 1.3 Success Moment

The operator sends a message to `#architecture-review` from the dashboard. Three agents (Robbo, Paula, Con) are in the channel. Robbo and Con are in AWAITING_INPUT — they receive the message immediately via tmux, each formatted with the channel envelope. Paula is mid-PROCESSING — her message queues. When Paula's stop hook fires and she transitions to AWAITING_INPUT, the queued message delivers automatically. Con finishes composing a response — the stop hook fires, the hook receiver classifies it as COMPLETION, the delivery engine posts it as a channel Message, and Robbo and the operator see Con's response. The whole loop runs without the operator touching anything after the initial send.

---

## 2. Scope

### 2.1 In Scope

- `ChannelDeliveryService` registered as `app.extensions["channel_delivery_service"]`
- Fan-out: iterate active (non-muted) ChannelMembership records excluding the sender, deliver per member type
- Delivery per member type: tmux (internal agent, online), notification (operator), deferred (offline). SSE broadcasting is handled by ChannelService (S4) — delivery engine does not broadcast independently
- Envelope format for tmux delivery: `[#channel-slug] PersonaName (agent:ID):\n{content}`
- COMMAND COMPLETE marker stripping from channel message content before relay
- Agent response capture: hook receiver integration — when a stop hook produces a COMPLETION or END_OF_COMMAND Turn for a channel member, post the response as a channel Message
- Completion-only relay: only composed final responses (COMPLETION/END_OF_COMMAND), not PROGRESS, QUESTION, or tool-use output
- In-memory delivery queue: dict of `agent_id` to `deque` of Message IDs
- State safety: deliver only in AWAITING_INPUT or IDLE states; queue for PROCESSING, COMMANDED, COMPLETE
- Queue drain on state transition: when an agent transitions to AWAITING_INPUT or IDLE, deliver the oldest queued message (FIFO)
- Per-pane locks via existing tmux bridge — no new global lock
- CommanderAvailability integration: check pane health before tmux delivery
- Feedback loop prevention via completion-only relay + source tracking + IntentDetector gating
- Best-effort delivery: no retry, no delivery tracking table
- Post-commit side effect pattern (same as existing SSE broadcasts and notification triggers)

### 2.2 Out of Scope

- Channel data model and migrations (S3)
- ChannelService CRUD operations (S4 — delivery engine calls `ChannelService.send_message()` for response posting)
- API endpoints for channel messaging (S5)
- Dashboard UI for channel message display (S7)
- Voice bridge channel integration (S8)
- Per-recipient delivery tracking table (v2)
- Priority delivery that bypasses the queue (v2)
- Cooldown for sustained ping-pong between agents (v2)
- Operator delivery display — the SSE events are broadcast in this sprint, rendered in S7
- Channel behavioral primer injection (separate concern from message delivery)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. When a Message is persisted via `ChannelService.send_message()`, the delivery engine fans out to all active (non-muted) members excluding the sender
2. Internal online agents receive messages via tmux `send_text()` with the envelope format `[#channel-slug] PersonaName (agent:ID):\n{content}`
3. Operators and remote agents receive messages via `channel_message` SSE events on the existing `/api/events/stream`
4. Offline personas (no active agent) have messages deferred — they catch up via context briefing on next spin-up (Decision 2.1)
5. Messages are only delivered to agents in AWAITING_INPUT or IDLE states; messages for agents in PROCESSING, COMMANDED, or COMPLETE states are queued
6. When an agent transitions to AWAITING_INPUT or IDLE, the oldest queued message is delivered first (FIFO)
7. When an agent's stop hook produces a COMPLETION or END_OF_COMMAND Turn and the agent is a member of an active channel, the response is posted as a new channel Message
8. PROGRESS turns, QUESTION turns, and tool-use output are NOT relayed to the channel
9. The `COMMAND COMPLETE` marker footer is stripped from channel message content before relay
10. Feedback loops do not occur: an agent receiving a channel message and responding does not cause infinite relay cascades
11. If a tmux pane is unavailable (CommanderAvailability reports false), the message stays queued and is logged
12. Delivery failures for individual members do not block delivery to other members

### 3.2 Non-Functional Success Criteria

1. Fan-out to N agents takes ~120-500ms (parallel per-pane locks, not serial) for typical channel sizes (2-10 members)
2. The in-memory delivery queue survives within a server process lifetime; on restart, queued messages are lost but persist in channel history for context briefing
3. The delivery engine adds no new database tables or columns
4. Service registration follows the existing `app.extensions` pattern

---

## 4. Functional Requirements (FRs)

### Fan-Out

**FR1: Post-commit fan-out trigger**
When `ChannelService.send_message()` commits a Message to the database, the delivery engine shall be invoked as a post-commit side effect to deliver the message to all other active members. The sender receives an immediate response (201 Created from the API layer); delivery to other members is asynchronous.

**FR2: Member iteration**
The delivery engine shall iterate all ChannelMembership records for the message's channel where `status = 'active'`, excluding the membership record matching the sender's persona. For each member, delivery mechanism is determined by persona type and agent status.

**FR3: Delivery per member type**
The delivery engine shall deliver messages according to the member type table:

| Member type | Delivery mechanism | Details |
|---|---|---|
| Agent (internal, online) | tmux `send_text()` | Envelope format. Per-pane lock. State safety check. |
| Agent (internal, offline) | Deferred | No active agent instance. Message persists in channel history. |
| Agent (remote/external) | No delivery action | SSE broadcast already handled by ChannelService (S4). |
| Person (internal — operator) | Notification only | macOS notification via NotificationService. SSE broadcast already handled by ChannelService (S4). |
| Person (external) | No delivery action | SSE broadcast already handled by ChannelService (S4). |

**FR4: Failure isolation**
If delivery fails for one member (tmux error, SSE broadcast exception), the engine shall log the failure and continue delivering to remaining members. No member's delivery failure blocks another's.

### Envelope Format

**FR5: Tmux delivery envelope**
Messages delivered to agents via tmux shall be wrapped in the following envelope format:

```
[#channel-slug] PersonaName (agent:ID):
{message content}
```

Where:
- `#channel-slug` is the channel's slug (from the Channel model)
- `PersonaName` is the sender's persona name
- `agent:ID` is the sender's agent instance ID (or `operator` for person/internal senders with no agent)
- `{message content}` is the message text with any `COMMAND COMPLETE` marker footer stripped

**FR6: COMMAND COMPLETE stripping**
The `COMMAND COMPLETE` footer (machine-parseable signal for monitoring software) shall be stripped from message content before channel relay. This marker is metadata, not conversational content. It is retained on the agent's individual Turn record.

### Agent Response Capture

**FR7: Completion relay trigger**
When the hook receiver's `process_stop()` processes a Turn classified as COMPLETION or END_OF_COMMAND for an agent that is a member of an active channel, the delivery engine shall post the agent's response as a new Message in that channel.

**FR8: Message attribution**
The relayed Message shall be created with:
- `persona_id` from the agent's persona
- `agent_id` from the agent
- `source_turn_id` from the Turn that triggered the relay
- `source_command_id` from the agent's current Command
- `message_type = "message"`

**FR9: Completion-only relay**
Only Turns with intent COMPLETION or END_OF_COMMAND shall be relayed to the channel. PROGRESS, QUESTION, and other intents remain on the agent's individual card for operator monitoring but never fan out.

**FR10: One-agent-one-channel attribution**
Channel membership is enforced as one agent per active channel (partial unique index from S3 Decision 1.4). If agent #1053 produces output, the delivery engine looks up their single active ChannelMembership to determine the target channel. No disambiguation is needed.

### Delivery Queue

**FR11: In-memory queue structure**
The delivery engine shall maintain an in-memory queue as a dict of `agent_id` to `collections.deque` of Message IDs. Messages already persist in the channel — the queue tracks which ones have not yet been delivered to a specific agent.

**FR12: State safety check**
Before delivering a message via tmux, the delivery engine shall check the target agent's current command state:

| Agent State | Safe to deliver? | Action |
|---|---|---|
| AWAITING_INPUT | Yes | Deliver immediately |
| IDLE | Yes | Deliver immediately — message becomes a new COMMAND |
| PROCESSING | No | Add Message ID to agent's queue |
| COMMANDED | No | Add Message ID to agent's queue |
| COMPLETE | No | Add Message ID to agent's queue |

**FR13: Queue drain on state transition**
When the CommandLifecycleManager transitions an agent to AWAITING_INPUT or IDLE, the delivery engine shall check for queued messages and deliver the oldest first (FIFO). Only one message is delivered per transition — the agent processes it, eventually transitions to a safe state again, and the next queued message delivers on that transition.

**FR14: Pane health check**
Before tmux delivery, the delivery engine shall consult `CommanderAvailability.is_available(agent_id)`. If the pane is unavailable (agent crashed, tmux session gone), the message stays queued and is logged as undeliverable at warning level.

### Feedback Loop Prevention

**FR15: Three-layer prevention**
Feedback loops are prevented by three independent mechanisms:
1. **Completion-only relay** — agents do not relay PROGRESS, thinking, or tool-use output. Only composed final responses. This eliminates rapid-fire ping-pong from intermediate output.
2. **Source tracking** — each relayed Message carries `source_turn_id`. The Turn that triggered the relay can be traced back to determine if the agent was responding to a channel message (the input Turn's existence as a channel-delivered message is tracked).
3. **IntentDetector as gatekeeper** — not every agent response is a COMPLETION. PROGRESS, QUESTION, and tool-use turns are classified by IntentDetector and excluded from relay.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: No new database tables or columns**
The delivery engine uses the Message model from S3 and the ChannelMembership model from S3. The in-memory queue requires no schema changes. No `MessageDelivery` tracking table (explicitly deferred per Decision 1.2).

**NFR2: Best-effort delivery**
No retry logic. If tmux `send_text()` fails, the message is logged and not retried. Messages persist in the channel — members can catch up via history. This matches the existing tmux bridge's fire-and-forget model.

**NFR3: Concurrency**
Fan-out to N agents is N parallel tmux operations, each acquiring its own per-pane `RLock`. No global lock across panes. Two messages to the same pane serialize correctly via the existing per-pane lock. For v1 channel sizes (2-10 members), this provides adequate throughput.

**NFR4: Server restart resilience**
On server restart, the in-memory queue is lost. Messages persist in the channel's message history. Agents catch up via context briefing on next spin-up (last 10 messages, per Decision 2.1). No queue persistence mechanism.

**NFR5: Service registration**
`ChannelDeliveryService` shall be registered as `app.extensions["channel_delivery_service"]` following the existing service registration pattern in `app.py`.

**NFR6: Thread safety**
The in-memory delivery queue dict must be thread-safe. Use a threading.Lock for queue mutations (add, drain, check). Individual tmux deliveries use the existing per-pane RLock.

---

## 6. Technical Context

### 6.1 Files to Modify

| File | Change |
|------|--------|
| `src/claude_headspace/services/hook_receiver.py` | In `process_stop()`, after Turn creation and intent classification, call `ChannelDeliveryService.relay_agent_response()` for COMPLETION/END_OF_COMMAND turns. Insert after the existing two-commit pattern (turn committed, state transition committed) and before summarisation. |
| `src/claude_headspace/services/command_lifecycle.py` | In `update_command_state()`, after state transition to AWAITING_INPUT or IDLE (including the IDLE derivation when no active command exists), call `ChannelDeliveryService.drain_queue(agent_id)`. Also hook into `complete_answer()` — after an ANSWER transitions state back to PROCESSING, no drain (PROCESSING is unsafe). |
| `src/claude_headspace/app.py` | Register `ChannelDeliveryService` as `app.extensions["channel_delivery_service"]` during app factory setup. |
| `src/claude_headspace/services/notification_service.py` | Add `_channel_rate_limit_tracker` dict, `_is_channel_rate_limited()` method, and `send_channel_notification()` method. Per-channel rate limiting (30s window). |

### 6.2 New Files

| File | Purpose |
|------|---------|
| `src/claude_headspace/services/channel_delivery.py` | `ChannelDeliveryService` — fan-out engine, delivery queue, response capture relay, envelope formatting. |

### 6.3 ChannelDeliveryService Design

```python
import logging
import re
import threading
from collections import deque

from ..models.command import CommandState

logger = logging.getLogger(__name__)

# COMMAND COMPLETE pattern to strip from channel messages
_COMMAND_COMPLETE_PATTERN = re.compile(
    r'\n*---\nCOMMAND COMPLETE\s*[^\n]*\n---\s*$',
    re.DOTALL,
)


class ChannelDeliveryService:
    """Fan-out delivery engine for channel messages.

    Handles:
    - Message fan-out to all active channel members (per member type)
    - In-memory delivery queue for agents in unsafe states
    - Queue drain on agent state transitions
    - Agent response capture and relay to channel
    - Envelope formatting for tmux delivery
    """

    def __init__(self, app=None):
        self._app = app
        self._lock = threading.Lock()
        # agent_id -> deque of Message IDs awaiting delivery
        self._queues: dict[int, deque[int]] = {}

    def deliver_message(self, message, channel, sender_persona_id: int) -> None:
        """Fan out a message to all active members excluding the sender.

        Called as a post-commit side effect after ChannelService.send_message()
        persists the Message.

        Args:
            message: The persisted Message instance
            channel: The Channel the message belongs to
            sender_persona_id: The persona_id of the sender (excluded from delivery)
        """
        # Iterate non-muted memberships, excluding sender
        ...

    def relay_agent_response(self, agent, turn) -> None:
        """Post an agent's composed response as a channel Message.

        Called from hook_receiver.process_stop() when a Turn is classified
        as COMPLETION or END_OF_COMMAND and the agent is a channel member.

        Args:
            agent: The Agent that produced the response
            turn: The Turn containing the composed response text
        """
        # 1. Look up agent's active ChannelMembership
        # 2. Strip COMMAND COMPLETE footer from turn.text
        # 3. Call ChannelService.send_message() to create the Message
        #    (which triggers deliver_message via post-commit)
        ...

    def drain_queue(self, agent_id: int) -> None:
        """Deliver the oldest queued message for an agent.

        Called from CommandLifecycleManager when agent transitions
        to AWAITING_INPUT or IDLE.

        Delivers ONE message per call (FIFO). The agent processes it,
        transitions again, and the next drain delivers the next message.
        """
        ...

    def _enqueue(self, agent_id: int, message_id: int) -> None:
        """Add a message to an agent's delivery queue."""
        with self._lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = deque()
            self._queues[agent_id].append(message_id)

    def _dequeue(self, agent_id: int) -> int | None:
        """Remove and return the oldest queued message ID, or None."""
        with self._lock:
            q = self._queues.get(agent_id)
            if q:
                msg_id = q.popleft()
                if not q:
                    del self._queues[agent_id]
                return msg_id
            return None

    def _format_envelope(
        self,
        channel_slug: str,
        sender_name: str,
        sender_agent_id: int | None,
        content: str,
    ) -> str:
        """Format a message with the channel envelope for tmux delivery."""
        agent_tag = f"agent:{sender_agent_id}" if sender_agent_id else "operator"
        stripped = _COMMAND_COMPLETE_PATTERN.sub('', content).rstrip()
        return f"[#{channel_slug}] {sender_name} ({agent_tag}):\n{stripped}"

    def _is_safe_state(self, agent) -> bool:
        """Check if agent is in a state safe for tmux delivery."""
        from .command_lifecycle import CommandLifecycleManager
        lifecycle = CommandLifecycleManager(session=db.session)
        state = lifecycle.derive_agent_state(agent)
        return state in (CommandState.AWAITING_INPUT, CommandState.IDLE)
```

### 6.4 Fan-Out Flow (deliver_message)

The full fan-out sequence for a single `deliver_message()` call:

```
ChannelService.send_message()
  -> db.session.commit()
  -> ChannelDeliveryService.deliver_message(message, channel, sender_persona_id)
     |
     +-- Query ChannelMembership WHERE channel_id=X AND status='active'
     |     AND persona_id != sender_persona_id
     |
     +-- For each membership:
     |     |
     |     +-- Resolve member type (persona.persona_type + active agent lookup)
     |     |
     |     +-- AGENT (internal, online):
     |     |     +-- CommanderAvailability.is_available(agent_id)?
     |     |     |   No  -> _enqueue(agent_id, message.id), log warning
     |     |     |   Yes -> _is_safe_state(agent)?
     |     |     |          No  -> _enqueue(agent_id, message.id)
     |     |     |          Yes -> tmux_bridge.send_text(pane_id, envelope)
     |     |     |                 On failure -> log warning, continue
     |     |
     |     +-- AGENT (internal, offline):
     |     |     +-- No active agent. Message persists in channel history.
     |     |         Context briefing on next spin-up (Decision 2.1).
     |     |
     |     +-- AGENT (remote/external):
     |     |     +-- # SSE already broadcast by ChannelService
     |     |
     |     +-- PERSON (internal — operator):
     |     |     +-- notification_service.notify_channel_message(...)
     |     |     +-- # SSE already broadcast by ChannelService
     |     |
     |     +-- PERSON (external):
     |           +-- # SSE already broadcast by ChannelService
     |
     +-- Return (best-effort, no delivery confirmation)
```

### 6.5 Agent Response Capture Flow

The response capture pipeline hooks into the existing `process_stop()` flow in `hook_receiver.py`. The insertion point is after the Turn is created and committed, after intent classification, and after the command state transition — but before summarisation.

```
hook_receiver.process_stop()
  -> Extract transcript -> detect intent
  -> Create Turn (COMPLETION or END_OF_COMMAND)
  -> db.session.commit()  [turn committed]
  -> complete_command() or state transition
  -> db.session.commit()  [state committed]
  ->
  -> ** NEW: Channel relay check **
  -> ChannelDeliveryService.relay_agent_response(agent, turn)
  ->   |
  ->   +-- ChannelMembership.query.filter_by(
  ->   |     persona_id=agent.persona_id,
  ->   |     channel__status='active'
  ->   |   ).first()
  ->   |
  ->   +-- If no active membership -> return (agent not in a channel)
  ->   |
  ->   +-- Strip COMMAND COMPLETE footer from turn.text
  ->   |
  ->   +-- ChannelService.send_message(
  ->   |     channel_id=membership.channel_id,
  ->   |     persona_id=agent.persona_id,
  ->   |     agent_id=agent.id,
  ->   |     text=stripped_text,
  ->   |     source_turn_id=turn.id,
  ->   |     source_command_id=turn.command_id,
  ->   |     message_type="message",
  ->   |   )
  ->   |   -> This triggers deliver_message() for fan-out to other members
  ->
  -> _trigger_priority_scoring()
  -> _execute_pending_summarisations(pending)
  -> broadcast_card_refresh(agent, "stop")
```

**Key constraint:** The relay call must be AFTER the turn and command state are committed (the two-commit pattern in `process_stop`). The relayed Message references the Turn via `source_turn_id` — the Turn must exist in the DB first.

### 6.6 Queue Drain Integration

The queue drain hooks into `CommandLifecycleManager` state transitions. When an agent transitions to a safe state (AWAITING_INPUT or IDLE), the delivery engine checks for queued messages.

**Integration points in `command_lifecycle.py`:**

1. **`update_command_state()` — transition to AWAITING_INPUT:** After the state is set and the notification is sent, call `channel_delivery_service.drain_queue(command.agent_id)`. This handles the stop hook's QUESTION detection path.

2. **Derived IDLE state:** When `get_current_command()` returns None (no active command), the agent is effectively IDLE. The drain should trigger when a command completes (`complete_command()`) and the agent returns to IDLE. The `complete_command()` method itself sets the state to COMPLETE (not safe), but after the command is committed, the next state derivation will return IDLE. The drain should be called from the caller's post-commit path — specifically in `process_stop()` after the `complete_command()` commit, when the agent's derived state is now IDLE.

**Drain semantics:**
- Deliver ONE message per drain call
- After delivery, the agent processes the message, which creates a new COMMANDED state (not safe)
- The agent eventually transitions back to a safe state, triggering another drain
- This provides natural pacing — one message at a time, processing between each

```python
def drain_queue(self, agent_id: int) -> None:
    msg_id = self._dequeue(agent_id)
    if msg_id is None:
        return

    # Fetch Message from DB
    from ..models.message import Message
    message = Message.query.get(msg_id)
    if not message:
        logger.warning(f"drain_queue: message {msg_id} not found (deleted?)")
        return

    # Fetch agent and verify still in safe state
    from ..models.agent import Agent
    agent = Agent.query.get(agent_id)
    if not agent or agent.ended_at is not None:
        logger.info(f"drain_queue: agent {agent_id} gone, clearing queue")
        with self._lock:
            self._queues.pop(agent_id, None)
        return

    # Deliver via tmux
    self._deliver_to_agent(agent, message)
```

### 6.7 State Safety Decision Table (from Workshop Section 3.3)

| Agent State | Safe to deliver? | Rationale |
|---|---|---|
| AWAITING_INPUT | **Yes** | Agent is waiting for input, prompt is ready. The existing tmux bridge already targets this state for operator responses. |
| IDLE | **Yes** | Agent at prompt, no active command. The delivered message becomes a new COMMAND. |
| PROCESSING | No | Agent is mid-thought, actively producing output. Injection will interleave with output. |
| COMMANDED | No | Agent just received input, hasn't started processing. Injection would corrupt input context. |
| COMPLETE | No | Command finished but agent hasn't returned to prompt. Brief window before IDLE. |

The Workshop Section 0.3 originally listed COMPLETE as safe, but Section 3.3 refined this: COMPLETE is a transient state between the command finishing and the agent returning to the prompt. Delivering during this brief window risks interleaving. Queue for COMPLETE; drain on IDLE.

### 6.8 Envelope Format (from Workshop Decisions 0.3 and 3.3)

The envelope format for tmux delivery:

```
[#persona-alignment-workshop] Paula (agent:1087):
I disagree with the approach to skill file injection. The current
tmux-based priming has a fundamental timing problem...
```

Components:
- **`[#channel-slug]`** — identifies this as a channel message and which channel. The `#` prefix signals channel context vs. operator command.
- **`PersonaName`** — the persona name (conversational identity)
- **`(agent:ID)`** — the specific agent instance ID. Links to the individual agent card for full PROGRESS/thinking history. For operator messages: `(operator)` instead of `(agent:ID)`.
- Content follows on the next line.

The envelope prefix is the signal to the agent that this is a channel message. The IntentDetector processes the content as normal — the envelope is context, not a command structure the agent needs to parse.

### 6.9 COMMAND COMPLETE Stripping

The `COMMAND COMPLETE` footer is a machine-parseable marker for monitoring software (defined in the operator's global CLAUDE.md). It appears at the end of agent responses:

```
---
COMMAND COMPLETE -- Summary of what was done.
---
```

This is metadata, not conversational content. Before relaying an agent's response to the channel:
1. Regex-strip the footer pattern from the text
2. The stripped text is used for the channel Message content and the tmux envelope
3. The original (unstripped) text remains on the agent's individual Turn record

### 6.10 Feedback Loop Prevention (from Workshop Decision 3.2)

Three independent mechanisms prevent feedback loops:

**1. Completion-only relay:** Only composed, final responses (COMPLETION/END_OF_COMMAND) are relayed. PROGRESS turns — the agent's intermediate thinking, file reads, tool use — never fan out. This eliminates rapid-fire exchange from intermediate output. An agent receiving a channel message will process it through its normal pipeline (read files, think, compose), and only the final composed response is relayed.

**2. Source tracking:** Each Message carries `source_turn_id` and `source_command_id`. When an agent responds to a channel message, the hook receiver can trace: the agent's input Turn was caused by a channel message delivery. The resulting response Turn is a reply. Normal relay applies — this is not a loop, it is a conversation. A loop would require the same content circulating, which completion-only relay prevents (the agent composes a new, different response each time).

**3. IntentDetector as gatekeeper:** Not every stop hook produces a COMPLETION. The IntentDetector may classify the response as QUESTION (asking the operator something), PROGRESS (intermediate), or other intents. Only COMPLETION and END_OF_COMMAND pass through to channel relay. An agent that receives a channel message and asks the operator a clarifying question does NOT relay that question to the channel.

**Natural backpressure from state machine:** If two agents in a channel rapidly trade completions, the CommandLifecycleManager state machine governs pacing. An agent receiving input while PROCESSING does not immediately produce output — it queues (FR12). This prevents instantaneous ping-pong. If sustained rapid exchange proves problematic in production, a cooldown (max 1 relay per agent per N seconds) is a v2 concern.

### 6.11 Tmux Bridge Integration (from Workshop Section 0.1)

The delivery engine uses the existing `tmux_bridge.send_text()` function. Key properties confirmed in the infrastructure audit:

- **Per-pane `RLock`:** `_send_locks` dict with independent locks per pane. Fan-out to different panes is concurrent. Two messages to the same pane serialize correctly.
- **No global lock:** No `_send_locks_meta_lock` contention for fan-out — it only locks briefly to create/retrieve per-pane locks.
- **Large text handling:** Messages over 4KB route through `load-buffer` + `paste-buffer` (temp file). Channel messages with long envelopes are handled.
- **`send_text()` signature:** `send_text(pane_id, text, ...)` returns a `SendResult` with `.success` and `.error_message` properties.
- **No modification needed:** The tmux bridge is used as-is. The delivery engine is a caller, not a modifier.

### 6.12 CommanderAvailability Integration

Before attempting tmux delivery, the delivery engine calls `CommanderAvailability.is_available(agent_id)` to check cached pane health. This is a read-only check against the in-memory cache — no subprocess call.

If the pane is unavailable:
- The message stays in the agent's delivery queue
- A warning is logged: `"delivery skipped: agent {id} pane unavailable"`
- The queue will drain when the pane becomes available AND the agent is in a safe state

The `CommanderAvailability` background thread runs health checks every 30 seconds. When a pane comes back (or the agent reconnects via `_attempt_reconnection()`), the availability cache updates. The delivery queue does not poll — it relies on the next state transition or explicit drain call.

### 6.13 SSE Event Schema Reference

The `channel_message` SSE event uses the canonical schema defined in S5 Section 6.5. The delivery engine does not broadcast this event directly (see Edit 1c / Finding #1) — ChannelService (S4) handles SSE broadcasting. This section is retained for reference only:

See **e9-s5-api-sse-endpoints-prd.md Section 6.5** for the authoritative `channel_message` and `channel_update` event data schemas.

### 6.14 Notification for Operator Channel Messages

When a message is delivered to an operator (person/internal PersonaType), the delivery engine calls `NotificationService.send_channel_notification()`. This method is added to NotificationService by this sprint.

**NotificationService extension (new method):**
```python
def send_channel_notification(
    self, channel_slug: str, channel_name: str,
    persona_name: str, content_preview: str,
    dashboard_url: str | None = None,
) -> bool:
```
Per-channel rate limiting: one notification per channel per 30-second window (configurable via `config.yaml` `notifications.channel_rate_limit_seconds`). Uses a `_channel_rate_limit_tracker` dict keyed by channel slug, same locking pattern as existing `_rate_limit_tracker`.

### 6.15 Hook Receiver Integration Point

The precise insertion point in `process_stop()` for the channel relay check. The current flow in `hook_receiver.py`:

```python
# After two-commit pattern (turn + state committed):
_trigger_priority_scoring()
pending = lifecycle.get_pending_summarisations()

# State transition for QUESTION intent...

# Broadcast turn for voice chat...

broadcast_card_refresh(agent, "stop")
_execute_pending_summarisations(pending)
# ... completion notification, return
```

The channel relay check inserts AFTER the state transition commits and BEFORE `_trigger_priority_scoring()`:

```python
# After two-commit pattern:

# ** Channel relay — post composed response to agent's channel **
if intent_result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND):
    try:
        from flask import current_app
        delivery_svc = current_app.extensions.get("channel_delivery_service")
        if delivery_svc:
            # Find the Turn that was just committed
            broadcast_turn = None
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent in (
                    TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND,
                ):
                    broadcast_turn = t
                    break
            if broadcast_turn:
                delivery_svc.relay_agent_response(agent, broadcast_turn)
    except Exception as e:
        logger.warning(f"Channel relay failed (non-fatal): {e}")

_trigger_priority_scoring()
# ... rest of existing flow
```

The relay is wrapped in try/except — channel relay failure is non-fatal. The agent's individual card, summarisation, and all existing flows continue regardless.

### 6.16 Queue Drain in process_stop

After `complete_command()` commits and the agent's derived state becomes IDLE, drain the queue:

```python
# In process_stop, after complete_command commit:
try:
    from flask import current_app
    delivery_svc = current_app.extensions.get("channel_delivery_service")
    if delivery_svc:
        delivery_svc.drain_queue(agent.id)
except Exception as e:
    logger.warning(f"Channel queue drain failed (non-fatal): {e}")
```

Similarly, in `update_command_state()`, when transitioning to AWAITING_INPUT:

```python
# After setting command.state = AWAITING_INPUT and notification:
try:
    from flask import current_app
    delivery_svc = current_app.extensions.get("channel_delivery_service")
    if delivery_svc:
        delivery_svc.drain_queue(command.agent_id)
except Exception as e:
    logger.warning(f"Channel queue drain failed (non-fatal): {e}")
```

### 6.17 Design Decisions (All Resolved — Workshop Sections 0 and 3)

| Decision | Resolution | Source |
|----------|-----------|--------|
| Fan-out architecture | Async, per-member, best-effort, post-commit side effect | 3.1 |
| Delivery per member type | tmux (internal online), SSE (operator/remote), deferred (offline) | 3.1 |
| Failure handling | Best-effort, no retry, no delivery tracking table | 3.1 |
| Response capture trigger | Completion-only relay via stop hook + IntentDetector | 3.2, 0.2 |
| Attribution model | One-agent-one-channel, no disambiguation needed | 3.2, 1.4 |
| Feedback loop prevention | Completion-only + source tracking + IntentDetector gating | 3.2 |
| Safe states for delivery | AWAITING_INPUT and IDLE only | 3.3 |
| Unsafe states | PROCESSING, COMMANDED, COMPLETE — queue for these | 3.3 |
| Queue drain trigger | State transition to safe state | 3.3 |
| Queue structure | In-memory dict of agent_id to deque of Message IDs | 3.3 |
| Envelope format | `[#slug] Name (agent:ID):\n{content}` | 0.3 |
| Per-pane locks | Existing tmux bridge, no global lock | 0.1 |
| COMMAND COMPLETE stripping | Strip footer before relay, retain on individual Turn | 0.2 |
| Operator delivery | SSE + notification with per-channel rate limiting | 3.4 |
| No interrupt bypass | All messages respect state checks, no priority queue | 3.3 |

### 6.18 Existing Services Used (DO NOT recreate)

- **`src/claude_headspace/services/tmux_bridge.py`** — `send_text(pane_id, text)` for tmux delivery. Per-pane `RLock` for concurrency. Used as-is.
- **`src/claude_headspace/services/hook_receiver.py`** — `process_stop()` is the insertion point for response capture relay and queue drain. Modify in place.
- **`src/claude_headspace/services/command_lifecycle.py`** — `update_command_state()` and `complete_command()` are insertion points for queue drain. Modify in place.
- **`src/claude_headspace/services/commander_availability.py`** — `is_available(agent_id)` for pane health check before tmux delivery. Used as-is (read-only cache check).
- **`src/claude_headspace/services/broadcaster.py`** — `broadcast()` method for SSE `channel_message` events. Used as-is.
- **`src/claude_headspace/services/notification_service.py`** — For macOS notifications on operator channel messages. Used as-is (caller adds rate limiting).
- **`src/claude_headspace/services/intent_detector.py`** — `detect_agent_intent()` classifies turns. Used as gatekeeper for completion-only relay. No modification.

### 6.19 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent ping-pong: two agents rapidly trading COMPLETION turns in a channel | Medium | Medium | Natural backpressure from state machine (PROCESSING queue). If insufficient, v2 cooldown (max 1 relay per agent per N seconds). |
| Queue grows unbounded for offline agents | Low | Low | Queue is per-agent, only for agents with active tmux panes in unsafe states. Offline agents have no queue — messages persist in channel history. On server restart, queue is lost (messages still in DB). |
| Tmux delivery fails silently for degraded panes | Medium | Low | CommanderAvailability pre-check catches dead panes. Failures are logged at warning level. Messages persist in channel history for context briefing. |
| Race condition between relay_agent_response and process_stop commit | Low | Low | relay_agent_response is called AFTER both commits in the two-commit pattern. Turn and command state are durable before relay fires. |
| Circular relay: agent responds to channel message, response is relayed, another agent responds, etc. | Medium | Medium | This is expected behavior (a conversation), not a bug. Completion-only relay ensures only composed responses circulate. Natural pacing from PROCESSING state. Sustained cascading is a v2 concern with cooldown mitigation. |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| Channel data model (Channel, ChannelMembership, Message) | E9-S3 | Database models for channels, membership, and messages |
| ChannelService | E9-S4 | `send_message()` method that persists Messages and triggers delivery |
| PersonaType system | E9-S2 | `persona_type` field for member type resolution (agent/internal, person/internal, etc.) |
| Tmux bridge | E5-S4 (done) | `send_text()` delivery primitive with per-pane locking |
| CommanderAvailability | E6-S2 (done) | Pane health monitoring for pre-delivery check |
| Hook receiver | E3-S1 (done) | `process_stop()` pipeline for response capture integration |
| CommandLifecycleManager | E2-S3 (done) | State transitions for queue drain triggers |
| SSE Broadcaster | E1-S7 (done) | `broadcast()` for operator/remote delivery events |
| IntentDetector | E3-S2 (done) | Turn classification for completion-only relay gate |
| NotificationService | E4-S3 (done) | macOS notifications for operator channel messages |

S3 and S4 are the critical path. S2 (PersonaType) provides the member type resolution. All other dependencies are shipped.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Sections 0 and 3) |
