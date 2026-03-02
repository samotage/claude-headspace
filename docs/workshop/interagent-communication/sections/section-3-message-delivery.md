# Section 3: Message Delivery & Fan-Out

**Status:** Fully resolved (4 decisions: 3.1–3.4)
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Depends on:** [Section 1](section-1-channel-data-model.md), [Section 2](section-2-channel-operations.md), [Section 0](section-0-infrastructure-audit.md)
**Canonical data model:** [`../../erds/headspace-org-erd-full.md`](../../erds/headspace-org-erd-full.md)

**Purpose:** Design how messages get from sender to all channel members. This is the delivery engine — the part that makes group chat actually work.

---

### 3.1 Fan-Out Architecture
- [x] **Decision: How does Headspace deliver a message to all members of a channel?**

**Depends on:** [Section 1](section-1-channel-data-model.md) (data model), [0.1](section-0-infrastructure-audit.md#01-current-communication-paths) (infrastructure audit)

**Context:** When a message is posted to a channel, Headspace must deliver it to every other member. Each member may have a different delivery mechanism (tmux, SSE, API). This is the fan-out problem.

**Resolution:**

#### Async fan-out, per-member, best-effort

When `ChannelService.send_message()` writes a Message to the DB, it kicks off delivery as a **post-commit side effect** — same pattern as existing SSE broadcasts and notification triggers. The sender gets an immediate response (201 Created). Delivery to other members happens asynchronously.

#### Delivery per member type

Fan-out iterates over active (non-muted) ChannelMembership records excluding the sender. Delivery mechanism is determined by the member's persona type and current agent state:

| Member type | Delivery mechanism | How |
|---|---|---|
| **Agent (internal, online)** | tmux send-keys | Envelope format from [Decision 0.3](section-0-infrastructure-audit.md#03-delivery-mechanism-constraints). Per-pane lock (existing tmux bridge — no global lock, confirmed in [0.1](section-0-infrastructure-audit.md#01-current-communication-paths)). Queued if agent not in safe state (see 3.3). |
| **Agent (internal, offline)** | Deferred | No active agent instance. Message sits in channel history. Delivered as context briefing when agent next spins up (Decision 2.1 — last 10 messages). |
| **Agent (remote/external)** | API callback / SSE | Existing remote agent embed SSE stream. `channel_message` event type from [Decision 2.3](section-2-channel-operations.md#23-api-endpoints). |
| **Person (internal — operator)** | SSE + notification | `channel_message` SSE event (Decision 2.3). macOS notification via existing `NotificationService`. See 3.4. |
| **Person (external)** | Embed SSE / API | Same as remote agent — SSE stream on embed widget. Future concern. |

#### Failure handling

**Best-effort, no retry, no delivery tracking.** If tmux send-keys fails for one member, log it and continue to the next. No `MessageDelivery` tracking table (explicitly deferred in Decision 1.2). Messages persist in the channel — members can catch up via history. This matches the existing tmux bridge's fire-and-forget model.

#### Scale

Per-pane locks (not a global lock) mean concurrent delivery to N agents is N parallel tmux operations. The tmux bridge already handles this for its existing use case. For v1 channel sizes (2–10 members), this is fine. If channels grow large, batching or queue-based delivery is a v2 concern.

#### No delivery confirmation to sender

The sender knows the message was written (201 response). They don't know who's received it yet. Same as Slack — you post a message, you don't get per-reader acknowledgements.

---

### 3.2 Agent Response Capture & Relay
- [x] **Decision: How does an agent's response get captured and posted back to the channel?**

**Depends on:** 3.1, [0.2](section-0-infrastructure-audit.md#02-agent-response-capture) (response capture audit)

**Context:** This is the return path. When Agent B responds in a group channel, that response needs to be captured, posted as a channel message, and delivered to all other members. This closes the loop.

**Resolution:**

#### Capture: completion-only relay via existing hook pipeline

The completion-only relay rule from [Decision 0.2](section-0-infrastructure-audit.md#02-agent-response-capture) applies. Only **composed, final responses** are relayed to the channel — not PROGRESS turns, not partial output, not tool-use noise. The `stop` hook and the IntentDetector's COMPLETION/END_OF_COMMAND classification identify when an agent has finished composing.

When the hook receiver processes a Turn classified as COMPLETION or END_OF_COMMAND for an agent that is a member of an active channel:

1. `ChannelService.post_agent_response(agent_id, turn)` is called
2. A new Message is created: `persona_id` from agent's persona, `agent_id` from agent, `source_turn_id` from the Turn, `source_command_id` from the agent's current Command, `message_type = "message"`
3. Fan-out delivers to all other members (3.1)

#### Attribution: one-agent-one-channel, no ambiguity

[Decision 1.4](section-1-channel-data-model.md#14-membership-model) enforces one agent instance per active channel via partial unique index. If agent #1053 produces output, it's for the one channel they're in. No disambiguation needed. Look up the agent's active ChannelMembership → get the channel → post the message.

#### No explicit reply required

The agent doesn't need to run `flask msg send`. Headspace infers the relay: agent is in a channel → their composed response is a channel message. The agent doesn't know it's in a channel (Decision 2.1 architectural insight). It receives input via tmux, responds normally, and Headspace handles the rest.

Agents **can** use `flask msg send` for explicit messages — e.g., a delegation or escalation that they want to tag with a specific `message_type`. But the default path is implicit relay of composed responses.

#### Feedback loop prevention

Three mechanisms:

1. **Completion-only relay** — agents don't relay partial/thinking output. Only composed final responses. This eliminates rapid-fire ping-pong from intermediate output.
2. **Source tracking** — each delivered Message creates a Turn with `source_message_id` set (Decision 1.2). The hook receiver can check: if the Turn that triggered this response was itself caused by a channel message (i.e., agent's input Turn has `source_message_id` set), the response is a **reply** to that message. Normal relay applies.
3. **IntentDetector as gatekeeper** — not every agent response constitutes a COMPLETION. PROGRESS turns, QUESTION turns to the operator, and tool-use output are not relayed. The existing IntentDetector classification governs what gets posted to the channel.

**If sustained ping-pong occurs** (Agent B and C rapidly trading completions), the existing CommandLifecycleManager state machine governs pacing. An agent receiving input while PROCESSING doesn't immediately produce output — it queues. This provides natural backpressure. If it proves insufficient, a simple cooldown (e.g., max 1 relay per agent per 5 seconds) is a v2 concern.

#### Latency

Real-time. The hook receiver fires on each hook event. Channel message creation and fan-out are post-commit side effects — same latency as existing SSE broadcasts (sub-second).

---

### 3.3 Delivery Timing & Agent State
- [x] **Decision: When is it safe to deliver a message to an agent, and how do we handle timing?**

**Depends on:** 3.1, [0.3](section-0-infrastructure-audit.md#03-delivery-mechanism-constraints) (delivery constraints)

**Context:** Agents have state (IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE). Injecting a message via tmux at the wrong time could corrupt the agent's context or interleave with its output.

**Resolution:**

#### Safe state: AWAITING_INPUT only

The only safe state for tmux delivery is **AWAITING_INPUT** — the agent is showing a prompt and waiting for input. This is the same constraint the existing tmux bridge already enforces for operator responses.

| Agent State | Safe to deliver? | Behaviour |
|---|---|---|
| `AWAITING_INPUT` | **Yes** | Deliver immediately via tmux send-keys |
| `IDLE` | **Yes** | Agent at prompt, no active command. Deliver — message becomes a new COMMAND. |
| `PROCESSING` | No | Agent is mid-thought. Queue for delivery when state transitions to AWAITING_INPUT or IDLE. |
| `COMMANDED` | No | Agent just received input, hasn't started processing. Queue. |
| `COMPLETE` | No | Command finished but agent hasn't returned to prompt. Queue. |

#### Queue and deliver on state transition

The `CommandLifecycleManager` already fires state transition events. When an agent transitions to AWAITING_INPUT or IDLE, check the delivery queue for that agent. If messages are pending, deliver the **oldest first** (FIFO). Multiple queued messages are delivered sequentially with the existing per-pane lock ensuring ordering.

The queue is in-memory (a dict of agent_id → deque of Message IDs). Messages already persist in the channel — the queue just tracks which ones haven't been delivered to this member yet. If the server restarts, the queue is lost, but the messages are in the DB. Agents catch up via context briefing on spin-up (Decision 2.1).

#### No interrupt bypass in v1

All messages respect state checks. No priority delivery that bypasses the queue. If the operator needs to interrupt an agent urgently, the existing tmux bridge direct-response path works outside of channels. Channel messages follow the orderly queue.

#### Delivery format: envelope from Decision 0.3

```
[#persona-alignment-workshop] Paula (agent:1087):
I disagree with the approach to skill file injection. The current
tmux-based priming has a fundamental timing problem...
```

The envelope prefix (`[#channel-slug] PersonaName (agent:ID):`) is the signal to the agent that this is a channel message. The IntentDetector processes the content as normal — the envelope is context, not a command structure.

#### CommanderAvailability integration

The existing `CommanderAvailability` service already monitors tmux pane availability per agent in a background thread. The delivery queue checks this before attempting tmux send-keys — if the pane isn't available (agent crashed, tmux session gone), the message stays queued and is logged as undeliverable.

---

### 3.4 Operator Delivery
- [x] **Decision: How does the operator receive and participate in channel messages?**

**Depends on:** 3.1

**Context:** The operator (Sam) is a channel participant but not an Agent in the DB. Delivery is via the dashboard (SSE). The operator sends messages via the dashboard UI or voice bridge.

**Resolution:**

#### Receiving: SSE events on existing stream

The operator's dashboard subscribes to `channel_message` and `channel_update` SSE events ([Decision 2.3](section-2-channel-operations.md#23-api-endpoints)). These events arrive on the existing `/api/events/stream` — no separate connection needed.

#### Dashboard display: channel cards + chat panel

Per the UI/UX context from Decision 1.1:

- **Channel cards** sit at the **top of the dashboard, above all project sections**. Each active channel the operator has joined gets a card showing: channel name, member list, last message summary/detail line. Cards update in real-time via `channel_message` SSE events.
- **Click a channel card** → opens a **chat panel** (slide-out or dedicated view) showing the full message feed, chat-style. The operator sends messages via an input box at the bottom of this panel.
- **Channel management tab** — separate tab in the dashboard for create/view/archive operations. Links to the `/api/channels` endpoints.

The chat panel is the operator's primary channel interaction surface on the dashboard. Implementation detail for the frontend — the backend (SSE events + REST API from 2.3) is already specified.

#### Sending: three paths

1. **Dashboard chat panel** — input box at the bottom of the channel chat view. Posts to `POST /api/channels/<slug>/messages` with dashboard session auth. The standard path when looking at the dashboard.
2. **Voice bridge** — semantic picker routes voice commands to channel operations ([Decision 2.3](section-2-channel-operations.md#23-api-endpoints)). "Send to the workshop: I think we should go with option B" → `ChannelService.send_message()`. The primary path when hands-free.
3. **Voice Chat PWA** — the `/voice` page is the primary participation interface (from Decision 1.1 UI/UX context). Channel messages appear in the voice chat sidebar alongside agent status. Send via voice input.

#### No channel switching needed

The operator sees all their active channels simultaneously as dashboard cards. They can have a chat panel open for one channel while seeing last-message summaries on all others. Same as Slack's sidebar — you see all channels, you're "in" one at a time.

#### Notifications

Existing `NotificationService` (macOS `terminal-notifier`) fires for channel messages directed at the operator or in channels they've joined. Per-channel rate limiting to avoid notification spam when a conversation is active — one notification per channel per 30-second window (configurable). If the operator is actively viewing the channel's chat panel, suppress notifications for that channel (dashboard reports "active" via a heartbeat or focus flag).

#### Operator identity in messages

Operator messages are posted with `persona_id` set to the operator's person/internal Persona, `agent_id = NULL` (no Agent instance), `source_turn_id = NULL`, `source_command_id = NULL`. The message origin is clear from the persona type.
