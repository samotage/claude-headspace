# Inter-Agent Communication — Design Workshop (Epic 9)

**Date:** 1 March 2026
**Status:** Pending workshop. Sections 0–5 defined.
**Epic:** 9 — Inter-Agent Communication
**Inputs:**
- Organisation Workshop Sections 0–1 (resolved decisions on org structure, serialization, CLI)
- `docs/workshop/organisation-workshop.md` — Organisation workshop (on hold, Sections 2–9 blocked on this epic)
- `docs/workshop/agent-teams-workshop.md` — Phase 1 design decisions (Epic 8)
- `docs/conceptual/headspace-agent-teams-functional-outline.md` — Agent Teams vision
- `docs/workshop/erds/headspace-org-erd-full.md` — Data model reference
- Existing codebase: tmux bridge, hook receiver, SSE broadcaster, remote agent infrastructure

**Method:** Collaborative workshop between operator (Sam) and architect (Robbo). Same format as the Organisation Workshop — work through sections sequentially, resolve decisions with documented rationale.

**Prerequisite:** This workshop assumes Epic 8 Phase 1 (Personable Agents) is substantially built. Tmux bridge, hook receiver, SSE broadcaster, and remote agent API all exist and work. This workshop designs the channel-based communication layer that sits between agents and underpins the organisation mechanics designed in the Organisation Workshop.

**Relationship to Organisation Workshop:** This epic was extracted from the Organisation Workshop when Section 2 (Inter-Agent Communication) revealed that the communication primitive is channel-based group chat, not point-to-point messaging. The organisation mechanics (Sections 2–9 of the Organisation Workshop) build on top of the channel infrastructure designed here. The Organisation Workshop resumes after this epic delivers working channels.

---

## How to Use This Document

Work through sections in order. Each section contains numbered decisions (0.1, 1.1, etc.) that may depend on earlier decisions. Dependency chains are explicit.

Sections are designed to be completable in a single workshop session. Start each session by reviewing the previous section's resolutions, then work through the current section's decisions.

---

## Workshop Log

| Date | Session | Sections | Key Decisions |
|------|---------|----------|---------------|
| | | | |

---

## The Foundational Insight

During the Organisation Workshop (Section 2), the operator's first real use case clarified the architecture:

> **Use case:** Sam, Robbo, and Paula need to sit down together and workshop persona alignment. Three participants, one conversation. Everyone sees everything. Any response while others are thinking is an interrupt.

This is a **group chat** — a well-solved problem (Slack, Discord, iMessage) with a well-understood data model. The communication primitive is not "Agent A sends a message to Agent B." It is:

**A message is posted to a channel, and all participants in that channel receive it.**

This means:
- **Channel** is the conversation container (N participants)
- **Message** belongs to a channel, from a sender (not sender→receiver)
- **Membership** determines who's in each channel
- **Delivery** fans out per member's connection type (tmux, SSE, API)
- **Point-to-point** is the degenerate case — a channel with two members
- **Interrupts** fall out naturally — a new message in the channel while others are mid-thought

Everything downstream — task delegation, escalation, reporting, org-aware routing — builds on channels. The channel is the nervous system; the organisation is the brain that decides which nerves to fire.

---

## Section 0: Existing Infrastructure Audit

**Purpose:** Ground the workshop in what already exists. Understand the current communication paths, what can be reused, and what gaps need filling.

---

### 0.1 Current Communication Paths
- [ ] **Decision: What communication paths exist today, and what's their scope/limitation?**

**Depends on:** None

**Context:** Before designing channels, we need to map what's already built. The existing system has several communication paths, none of which are channel-aware:

**Known paths to audit:**
- Operator → Agent: tmux bridge (`send_text()`) — types into agent's terminal
- Agent → Operator: hook events surfaced on dashboard (passive observation, not active sending)
- Dashboard → Agent: respond endpoint via tmux bridge (operator types in dashboard, delivered to agent)
- Voice bridge → Agent: voice-first API, routes to tmux bridge
- Remote agent communication: embed chat widget, SSE for status
- Agent → Headspace: hook lifecycle events (session-start, stop, tool-use, etc.)
- Skill injection: tmux-based persona priming at session startup

**Questions to resolve:**
- Which of these paths are reusable as channel delivery mechanisms?
- What's the current tmux bridge's capacity for concurrent delivery (fan-out to multiple panes)?
- Are there threading/locking concerns with simultaneous tmux sends to multiple agents?
- What's the hook receiver's capacity to ingest and route messages from multiple agents simultaneously?

**Resolution:** _(Pending)_

---

### 0.2 Agent Response Capture
- [ ] **Decision: How are agent responses currently captured, and can this feed into channels?**

**Depends on:** 0.1

**Context:** For channel fan-out to work, Headspace needs to capture what an agent says and relay it to other channel members. Currently, agent output is captured via hooks (post-tool-use, stop events) and optionally via transcript file watching.

**Questions to resolve:**
- What hook events carry the agent's actual response content?
- Is the content available in real-time (as the agent produces it) or only after completion?
- What's the latency between an agent producing output and Headspace having it available?
- Can hook payloads be used directly as channel messages, or do they need transformation?
- How does this work for remote agents (no hooks, API-based)?

**Resolution:** _(Pending)_

---

### 0.3 Delivery Mechanism Constraints
- [ ] **Decision: What are the practical constraints on message delivery to agents?**

**Depends on:** 0.1

**Context:** Delivering a message to an agent (via tmux injection) has practical constraints that affect channel design: timing, agent state, message format, and the risk of interrupting mid-output.

**Questions to resolve:**
- Can we inject into an agent's terminal while it's actively processing (mid-tool-use)?
- What happens if we inject while the agent is producing output — does the injected text interleave?
- Is there a "safe window" for injection (e.g., when agent is in AWAITING_INPUT state)?
- What's the maximum practical message size for tmux injection?
- How does the agent distinguish a channel message from an operator command?

**Resolution:** _(Pending)_

---

## Section 1: Channel Data Model

**Purpose:** Design the data model for channels, messages, and membership. This is the structural foundation — get the model right and the behaviour follows.

---

### 1.1 Channel Model
- [ ] **Decision: What is a Channel, and what does the table look like?**

**Depends on:** Section 0 (infrastructure audit must confirm feasibility)

**Context:** A channel is a conversation container. It needs to support:
- Group workshops (3+ participants, ongoing)
- Point-to-point delegation (2 participants, task-scoped)
- Org-wide announcements (broadcast)
- Possibly ephemeral channels (created for a task, archived on completion)

**Questions to resolve:**
- Channel fields: name, purpose/description, channel_type (group/direct/broadcast), org scope, created_by, status (active/archived)?
- Does a channel have a lifecycle? (created → active → archived)
- Can channels be org-scoped (only members of a specific org) or are they cross-org?
- Do we need channel topics/subjects (like Slack)?
- How does the channel relate to existing models (Project, Organisation)?

**Resolution:** _(Pending)_

---

### 1.2 Message Model
- [ ] **Decision: What is a Message, and what does the table look like?**

**Depends on:** 1.1

**Context:** A message belongs to a channel, from a sender. It's the atomic unit of communication. Messages may need to support different content types and carry metadata about their purpose.

**Questions to resolve:**
- Message fields: channel_id (FK), sender_agent_id (FK, nullable for operator), content, message_type (see 1.3), timestamp, metadata (JSONB)?
- Does a message reference existing models? (e.g., a task delegation message might reference a Task)
- Do we need message editing or deletion, or are messages immutable (audit trail)?
- How does Message relate to the existing Turn model? (Does a received message become a Turn?)
- Do we need message status per recipient (sent/delivered/read) or is that over-engineering for v1?

**Resolution:** _(Pending)_

---

### 1.3 Message Types
- [ ] **Decision: What types of messages exist, and do they have different semantics?**

**Depends on:** 1.2

**Context:** From the Organisation Workshop, the interaction spectrum includes: command, report, question, interrupt, escalation. These were originally framed as point-to-point message types, but in a channel model they might be:
- Just metadata on a message (a `type` field)
- Different delivery urgency (interrupt bypasses queue, report can wait)
- Routing hints (escalation creates or modifies channel membership)

**Questions to resolve:**
- Is message type an enum on the Message model?
- Do different types trigger different delivery behaviour?
- Which types are essential for v1 vs deferrable?
- Does the operator's message have a type? (It's always a command/question in practice)
- Are system messages a type? (e.g., "Paula has joined the channel")

**Resolution:** _(Pending)_

---

### 1.4 Membership Model
- [ ] **Decision: What is channel membership, and what does the table look like?**

**Depends on:** 1.1

**Context:** Membership determines who receives messages in a channel. Members can be agents (local or remote) or the operator. Membership has a lifecycle (joined, left, possibly muted).

**Questions to resolve:**
- Membership fields: channel_id (FK), agent_id (FK, nullable for operator), role_in_channel (owner/member/observer), joined_at, left_at, delivery_method (tmux/sse/api)?
- How is the operator represented? (Not an Agent in the DB — special case or do we model operator as a participant type?)
- Can membership be persona-based (any agent running as Con) rather than agent-instance-based?
- Does membership survive agent handoff? (If Con's agent #1053 hands off to #1054, does #1054 inherit channel membership?)
- Can a member be muted/paused without leaving?

**Resolution:** _(Pending)_

---

### 1.5 Relationship to Existing Models
- [ ] **Decision: How do channels and messages integrate with existing Headspace models?**

**Depends on:** 1.1, 1.2, 1.4

**Context:** Channels don't exist in isolation — they interact with Agents, Commands, Turns, Projects, and potentially Organisations. The integration points need to be clean.

**Questions to resolve:**
- Does a received channel message create a Turn on the receiving agent's current Command?
- Does a channel message that instructs work create a new Command on the receiving agent?
- Can a channel be scoped to a Project?
- Does the channel model connect to the Organisation model (org-scoped channels)?
- How do Events (audit trail) relate to channel messages? (Are messages their own audit trail, or do they also generate Events?)

**Resolution:** _(Pending)_

---

## Section 2: Channel Operations & CLI

**Purpose:** Design how channels are created, managed, and interacted with. The CLI is the primary agent interface; the API serves the dashboard and remote agents.

---

### 2.1 Channel Lifecycle
- [ ] **Decision: How are channels created, and what's their lifecycle?**

**Depends on:** 1.1

**Context:** Channels need to be created, populated with members, and eventually archived. The question is who creates them and when.

**Questions to resolve:**
- Who can create channels? (Operator, any agent, specific roles like PM?)
- Are channels created explicitly ("create a workshop channel") or implicitly ("delegate this task to Con" → system creates a channel)?
- Channel lifecycle: created → active → archived? Can channels be reactivated?
- Do channels have a TTL or auto-archive policy?
- Are there default/standing channels (e.g., an org-wide channel that always exists)?

**Resolution:** _(Pending)_

---

### 2.2 CLI Interface
- [ ] **Decision: What CLI commands do agents use to interact with channels?**

**Depends on:** 2.1, Section 1 (data model)

**Context:** Following the Section 1 org workshop pattern (`flask org`), channel operations need a CLI entry point. Agents interact with channels via bash tools — the CLI is their primary interface.

**Questions to resolve:**
- Command namespace: `flask msg`? `flask channel`? `flask chat`?
- Core commands: create, join, leave, send, list (channels), history (messages)?
- Message sending: `flask msg send --channel <name> "content"`? Or is the channel implicit (agent's current active channel)?
- Do agents need to explicitly "join" channels, or are they added by the creator/system?
- Query commands: list my channels, unread messages, channel members?
- Output format: what does a received message look like in the agent's terminal?

**Resolution:** _(Pending)_

---

### 2.3 API Endpoints
- [ ] **Decision: What API endpoints serve the dashboard and remote agents?**

**Depends on:** 2.2

**Context:** The CLI calls internal API endpoints. The dashboard and remote agents also need API access. This is the HTTP surface for channels.

**Questions to resolve:**
- REST endpoints: `/api/channels`, `/api/channels/<id>/messages`, `/api/channels/<id>/members`?
- Does the dashboard use the same API as remote agents?
- SSE integration: new SSE event types for channel messages? Separate SSE stream per channel?
- Authentication: how do remote agents authenticate to channel APIs? (Existing session token system?)
- Rate limiting considerations?

**Resolution:** _(Pending)_

---

## Section 3: Message Delivery & Fan-Out

**Purpose:** Design how messages get from sender to all channel members. This is the delivery engine — the part that makes group chat actually work.

---

### 3.1 Fan-Out Architecture
- [ ] **Decision: How does Headspace deliver a message to all members of a channel?**

**Depends on:** Section 1 (data model), 0.1 (infrastructure audit)

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

**Depends on:** 3.1, 0.2 (response capture audit)

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

**Depends on:** 3.1, 0.3 (delivery constraints)

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

---

## Section 4: The Group Workshop Use Case (End-to-End)

**Purpose:** Validate the design by walking through the primary use case end-to-end. If the model can support Sam + Robbo + Paula workshopping persona alignment, it can support everything else.

---

### 4.1 Workshop Channel Setup
- [ ] **Decision: How does the operator set up a group workshop with multiple agents?**

**Depends on:** Sections 1–3

**Context:** The concrete scenario: Sam wants to discuss persona alignment with Robbo and Paula. He needs to create a channel, add both agents, and start a conversation where all three participants see everything.

**Questions to resolve:**
- Step-by-step: what does Sam do to initiate this?
- Are both agents already running, or does channel creation spin them up?
- Does the channel have a name/purpose ("persona-alignment-workshop")?
- How does Sam send his first message to both agents?
- What does each agent see when the channel is created and the first message arrives?

**Resolution:** _(Pending)_

---

### 4.2 Multi-Agent Conversation Flow
- [ ] **Decision: What does the turn-by-turn flow look like in a group workshop?**

**Depends on:** 4.1

**Context:** The core interaction:
1. Sam says something → both Robbo and Paula receive it
2. Robbo responds → Sam and Paula both see the response
3. Paula responds (possibly while Robbo is still thinking) → Sam and Robbo see it
4. Sam responds to both → cycle continues

**Questions to resolve:**
- How are simultaneous responses handled? (Robbo and Paula both respond at once)
- Does the conversation have ordering guarantees, or is it best-effort chronological?
- How does an agent know who said what? (Attribution in the delivered message)
- Can agents reference each other's responses? ("I agree with Robbo's point about...")
- How long can a workshop conversation run? (Context window implications for each agent)

**Resolution:** _(Pending)_

---

### 4.3 Workshop Completion
- [ ] **Decision: How does a group workshop end, and what's the output?**

**Depends on:** 4.2

**Context:** A workshop produces decisions and documentation. When the conversation is done, the channel should be archivable and the conversation history should be accessible.

**Questions to resolve:**
- Does the operator explicitly end the workshop, or does the channel just go quiet?
- Is the full conversation history available for review? (Dashboard, CLI, export?)
- Can workshop outcomes (decisions, action items) be extracted from the conversation?
- Does channel archival affect agent state? (Do agents leave the channel when it's archived?)

**Resolution:** _(Pending)_

---

## Section 5: Migration & Integration Checklist

**Purpose:** Consolidate all model changes, new tables, and integration points required by this epic. Populated as decisions are resolved.

---

### Database Changes

| Migration | Model | Change | Priority |
|---|---|---|---|
| _(populated as decisions resolve)_ | | | |

### New Services

| Service | Purpose | Dependencies |
|---|---|---|
| _(populated as decisions resolve)_ | | |

### Integration Points

| Existing System | Integration | Notes |
|---|---|---|
| Tmux Bridge | Message delivery to local agents | Reuse existing `send_text()` |
| Hook Receiver | Agent response capture for channel relay | New processing path |
| SSE Broadcaster | Operator delivery + dashboard updates | New event types |
| Remote Agent API | Message delivery to remote agents | Extend existing infrastructure |
| Voice Bridge | Operator input via voice | Route to channel instead of single agent |

---

## Relationship to Organisation Workshop

When this epic is complete, the Organisation Workshop (Sections 2–9) can resume. The channel infrastructure designed here becomes the foundation for:

- **Section 2 (Inter-Agent Communication)** → Superseded. Channels replace point-to-point messaging.
- **Section 3 (Task Model & Delegation)** → Tasks are communicated via channels. Delegation is posting to a channel.
- **Section 4 (Agent Interaction Patterns)** → Interaction patterns are channel conversation patterns.
- **Section 5+ (Lifecycle, Monitoring, etc.)** → Build on channel infrastructure.

The Organisation Workshop's resolved decisions (Sections 0–1) remain valid and do not depend on channels. The migration checklist from Section 1 can be implemented independently of this epic.
