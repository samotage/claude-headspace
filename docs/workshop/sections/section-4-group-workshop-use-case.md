# Section 4: The Group Workshop Use Case (End-to-End)

**Status:** Pending (3 decisions)
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Depends on:** [Section 1](section-1-channel-data-model.md), [Section 2](section-2-channel-operations.md), [Section 3](section-3-message-delivery.md)
**Canonical data model:** [`../erds/headspace-org-erd-full.md`](../erds/headspace-org-erd-full.md)

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
