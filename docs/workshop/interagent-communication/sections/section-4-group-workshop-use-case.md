# Section 4: The Group Workshop Use Case (End-to-End)

**Status:** Fully resolved (3 decisions: 4.1–4.3)
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Depends on:** [Section 1](section-1-channel-data-model.md), [Section 2](section-2-channel-operations.md), [Section 3](section-3-message-delivery.md)
**Canonical data model:** [`../../erds/headspace-org-erd-full.md`](../../erds/headspace-org-erd-full.md)

**Purpose:** Validate the design by walking through the primary use case end-to-end. If the model can support Sam + Robbo + Paula workshopping persona alignment, it can support everything else.

---

### 4.1 Workshop Channel Setup
- [x] **Decision: How does the operator set up a group workshop with multiple agents?**

**Depends on:** Sections 1–3

**Context:** The concrete scenario: Sam wants to discuss persona alignment with Robbo and Paula. He needs to create a channel, add both agents, and start a conversation where all three participants see everything.

**Resolution:**

#### Step-by-step: operator creates a workshop channel

**Primary path (voice bridge — Sam's preferred interface):**

1. Sam says: *"Create a workshop channel called persona alignment with Robbo and Paula"*
2. Voice bridge semantic picker matches → `ChannelService.create_channel(name="persona-alignment", channel_type=WORKSHOP, members=["architect-robbo-3", "ar-director-paula-2"])`
3. Channel created in `pending` state. Sam's operator persona becomes chair.
4. For each member persona:
   - If persona has a running agent → add to channel immediately (ChannelMembership created, system message "Robbo joined the channel")
   - If persona has no running agent → spin up a new agent (same creation + readiness polling as remote agents, [Decision 2.1](section-2-channel-operations.md#21-channel-lifecycle)), then add. System message: "Paula joined the channel (agent spinning up...)"
5. New agents receive: persona injection (skill + experience), then context briefing ([Decision 2.1](section-2-channel-operations.md#21-channel-lifecycle) — last 10 messages, or in this case the channel description since no messages yet).
6. Sam says: *"Let's discuss the persona alignment approach for the new organisation structure"*
7. Voice bridge routes to `ChannelService.send_message()`. Message written to DB. Channel transitions from `pending` to `active` (first non-system message, [Decision 2.1](section-2-channel-operations.md#21-channel-lifecycle)).
8. Fan-out ([Decision 3.1](section-3-message-delivery.md#31-fan-out-architecture)) delivers to Robbo and Paula via tmux send-keys in envelope format:

```
[#workshop-persona-alignment-7] Sam:
Let's discuss the persona alignment approach for the new organisation structure
```

**Alternative paths work identically:**
- Dashboard: click "Create Channel" in management tab, fill form, same service calls
- CLI (agent-initiated): `flask channel create persona-alignment --type workshop --members architect-robbo-3,ar-director-paula-2`

#### What agents see

Each agent receives the message via tmux as normal input. The envelope prefix tells them the context. Their IntentDetector classifies the content — Sam's opening statement is COMMAND intent, so a new Command is created on each agent. They respond as they normally would.

---

### 4.2 Multi-Agent Conversation Flow
- [x] **Decision: What does the turn-by-turn flow look like in a group workshop?**

**Depends on:** 4.1

**Context:** The core interaction: Sam says something → both agents receive it. One responds → the others see it. Multiple agents may respond concurrently.

**Resolution:**

#### Turn-by-turn walkthrough

**T=0** — Sam sends message (as above). Fan-out delivers to Robbo and Paula.

**T=1** — Robbo responds. His agent produces a COMPLETION turn. Hook receiver captures it → `ChannelService.post_agent_response()` creates a Message → fan-out delivers to Sam (SSE `channel_message` event → dashboard chat panel) and Paula (tmux):

```
[#workshop-persona-alignment-7] Robbo (agent:1103):
The persona type hierarchy resolves the identity question cleanly.
Here's what I think about the alignment approach...
```

**T=2** — Paula is still thinking (PROCESSING state). Robbo's message is **queued** for Paula ([Decision 3.3](section-3-message-delivery.md#33-delivery-timing--agent-state)). When Paula finishes her current thought and enters AWAITING_INPUT, the queued message is delivered.

**T=3** — Paula responds. Her COMPLETION turn is captured → Message created → fan-out to Sam (SSE) and Robbo (tmux):

```
[#workshop-persona-alignment-7] Paula (agent:1087):
I disagree with the approach to skill file injection. The current
tmux-based priming has a fundamental timing problem...
```

**T=4** — Sam reads both responses on the dashboard, types (or speaks): "Paula raises a good point about timing. Robbo, how would you address that?" → fan-out to both agents.

Cycle continues.

#### Simultaneous responses

Both agents can respond at the same time. Per-pane locks (not global lock, [Decision 0.1](section-0-infrastructure-audit.md#01-current-communication-paths)) mean delivery to Robbo and delivery to Paula don't block each other. Messages are ordered by `sent_at` timestamp — the channel history shows them in chronological order, which may interleave.

#### Ordering

**Best-effort chronological by `sent_at`.** No strict ordering guarantees. If Robbo and Paula respond within the same second, their messages appear in insert order. This is fine — agent conversations are inherently asynchronous. Slack doesn't guarantee strict ordering either.

#### Attribution

Agents know who said what from the envelope prefix: `[#channel-slug] PersonaName (agent:ID):`. They can reference each other's responses naturally: "I agree with Robbo's point about..." — the envelope gives them the attribution, their language model handles the reference.

#### Context window

Each agent accumulates channel messages as Turns on their Commands. Standard context window limits apply. When an agent approaches its context limit, the existing handoff mechanism fires — the agent produces a handoff document, a successor agent spins up, joins the same channel via membership continuity ([Decision 1.1](section-1-channel-data-model.md#11-channel-model) — ChannelMembership.agent_id updated to successor), and receives the last 10 messages as context briefing. The conversation continues without interruption from the channel's perspective.

---

### 4.3 Workshop Completion
- [x] **Decision: How does a group workshop end, and what's the output?**

**Depends on:** 4.2

**Context:** A workshop produces decisions and documentation. When the conversation is done, the channel should be archivable and the conversation history should be accessible.

**Resolution:**

#### Ending: explicit completion by operator

The operator explicitly completes the workshop: *"Complete the persona alignment channel"* (voice) or `flask channel complete workshop-persona-alignment-7` (CLI) or dashboard button. Chair and operator both have this capability ([Decision 2.1](section-2-channel-operations.md#21-channel-lifecycle)).

Channel transitions to `complete` state. `completed_at` timestamp set. System message posted: "Channel completed by Sam." Members can still read history but no new messages can be posted.

Auto-complete (last active member leaves) is also possible but unlikely for workshops — the operator usually wraps up explicitly.

#### History access

Full conversation history available via three paths:

1. **Dashboard** — chat panel shows complete history. Channel card remains visible (in `complete` state) until archived.
2. **CLI** — `flask msg history workshop-persona-alignment-7` (conversational envelope format or `--format yaml`).
3. **API** — `GET /api/channels/workshop-persona-alignment-7/messages` (JSON, paginated).

Messages are immutable ([Decision 1.2](section-1-channel-data-model.md#12-message-model)). The full conversation is an operational record.

#### Decision extraction

Not automated in v1. Workshop decisions are captured by the participants in their own documents (the agent working on a spec writes decisions there, the operator reads the channel history and documents conclusions). The channel history is the source of truth for what was discussed.

Future: an LLM summarisation pass over channel history to extract decisions and action items could be added as an inference service feature — same pattern as existing turn/command summarisation. Not in scope for this epic.

#### Archival

Operator archives completed channels when they're no longer relevant: *"Archive the persona alignment channel"* (voice) or dashboard. Channel transitions to `archived` state, `archived_at` timestamp set. Archived channels are excluded from default list views but remain queryable (`--status archived`).

#### Agent state on archival

Archival does **not** affect agent state. Agents that were members of the channel continue running — they may be in other channels or doing independent work. The ChannelMembership records persist (for audit trail) but the channel is frozen. If an agent was exclusively working within this channel and has nothing else to do, the existing agent reaper handles cleanup after the inactivity timeout.
