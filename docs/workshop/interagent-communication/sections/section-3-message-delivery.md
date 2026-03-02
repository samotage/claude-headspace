# Section 3: Message Delivery & Fan-Out

**Status:** Pending (4 decisions)
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Depends on:** [Section 1](section-1-channel-data-model.md), [Section 2](section-2-channel-operations.md), [Section 0](section-0-infrastructure-audit.md)
**Canonical data model:** [`../erds/headspace-org-erd-full.md`](../erds/headspace-org-erd-full.md)

**Purpose:** Design how messages get from sender to all channel members. This is the delivery engine — the part that makes group chat actually work.

---

### 3.1 Fan-Out Architecture
- [ ] **Decision: How does Headspace deliver a message to all members of a channel?**

**Depends on:** [Section 1](section-1-channel-data-model.md) (data model), [0.1](section-0-infrastructure-audit.md#01-current-communication-paths) (infrastructure audit)

**Context:** When a message is posted to a channel, Headspace must deliver it to every other member. Each member may have a different delivery mechanism (tmux, SSE, API). This is the fan-out problem.

**Questions to resolve:**
- Synchronous or asynchronous fan-out? (Send to all members in parallel? Queue-based?)
- What happens if delivery to one member fails? (Retry? Mark as undelivered? Don't block others?)
- Is delivery best-effort or guaranteed?
- Does the sender get confirmation of delivery to each member?
- How does fan-out scale? (2 members is trivial; 10 agents in an org channel might stress tmux)

**Resolution:** _(Pending)_

---

### 3.2 Agent Response Capture & Relay
- [ ] **Decision: How does an agent's response get captured and posted back to the channel?**

**Depends on:** 3.1, [0.2](section-0-infrastructure-audit.md#02-agent-response-capture) (response capture audit)

**Context:** This is the return path. When Agent B responds in a group channel, that response needs to:
1. Be captured by Headspace (via hooks or transcript monitoring)
2. Be posted as a new message in the channel
3. Be delivered to all other channel members (including the operator via dashboard and other agents via tmux)

This closes the loop — messages flow in both directions through the channel.

**Questions to resolve:**
- Which hook events constitute a "response" that should be relayed?
- How do we attribute a hook event to a specific channel? (Agent might be in multiple channels)
- Does the agent explicitly reply to a channel (`flask msg send --channel ...`) or does Headspace infer the reply from context?
- How do we avoid feedback loops? (Agent B's response is relayed to Agent C, who responds, which is relayed back to Agent B...)
- What's the latency requirement? (Real-time relay vs batched?)

**Resolution:** _(Pending)_

---

### 3.3 Delivery Timing & Agent State
- [ ] **Decision: When is it safe to deliver a message to an agent, and how do we handle timing?**

**Depends on:** 3.1, [0.3](section-0-infrastructure-audit.md#03-delivery-mechanism-constraints) (delivery constraints)

**Context:** Agents have state (IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE). Injecting a message via tmux at the wrong time could corrupt the agent's context or interleave with its output.

**Questions to resolve:**
- Which agent states are safe for message delivery?
- Do we queue messages for agents in unsafe states and deliver when they become receptive?
- Do INTERRUPT-type messages bypass state checks and deliver immediately?
- How does the agent's tmux pane state (cursor position, prompt availability) affect delivery?
- What's the delivery format? (Clearly delimited so the agent knows it's a channel message, not operator input)

**Resolution:** _(Pending)_

---

### 3.4 Operator Delivery
- [ ] **Decision: How does the operator receive and participate in channel messages?**

**Depends on:** 3.1

**Context:** The operator (Sam) is a channel participant but not an Agent in the DB. Delivery is via the dashboard (SSE). The operator sends messages via the dashboard UI or voice bridge.

**Questions to resolve:**
- Dashboard display: channel message feed? Chat-style UI? Integrated into existing agent cards?
- SSE events: new event types for channel messages? Filtered by channel?
- Sending: dashboard input box per channel? Voice bridge integration?
- Does the operator need to "switch channels" or see all channels simultaneously?
- Notification: how does the operator know a new message arrived in a channel they're not currently viewing?

**Resolution:** _(Pending)_
