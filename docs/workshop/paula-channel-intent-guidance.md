# Channel Intent Engineering — AR Director Guidance

**Author:** Paula (AR Director)
**Date:** 2 March 2026
**For:** Robbo — incorporation into Inter-Agent Communication Workshop
**Context:** Review of workshop document + live channel participation. Three areas of guidance for workshop integration.

---

## 1. Channel Behavioral Primer — Two-Layer Architecture

The current prototype primer (the `[CHANNEL CONTEXT]` block used in the persona-alignment-workshop channel) is solid groundwork. It sets effective ground rules for group participation. However, it treats all channels and all participants identically. This limits alignment as channel types diversify.

### Recommendation: Base Primer + Channel Intent

**Base primer (universal, platform asset):**

Injected into every channel participant. Contains the behavioral ground rules that apply regardless of channel type, role, or purpose. The current prototype is close to this — concise, constraint-based, effective.

Maintained by the AR Director as a persona-adjacent platform asset (alongside `platform-guardrails.md`). Lives at a stable path (e.g., `data/templates/channel-base-primer.md`). Changes follow the same review process as guardrails — Paula proposes, Sam/Robbo approve.

The base primer covers:
- Conciseness and self-evaluation before responding
- Substance over noise — respond to what was said, reference by name
- No monologuing — make your point, let others respond
- Research before responding if needed, but present conclusions not journeys
- Operator sets direction; other members are peers

**Channel intent (per-channel or per-channel-type):**

Injected alongside the base primer. Tells participants what this specific channel is optimising for. Set when the channel is created — either explicitly by the creator or implicitly from a channel-type template.

Examples by channel type:

| Channel Type | Intent | What Good Participation Looks Like |
|---|---|---|
| **Workshop** | Resolved decisions with documented rationale | Challenge assumptions, propose alternatives, converge on decisions. Output is decisions, not discussion. |
| **Delegation** | Task completion to spec | Chair defines the task; members execute and report. Conversation is scoped to the task. Tangents are flagged, not followed. |
| **Review** | Finding problems before they ship | Adversarial by design. Silence is not agreement — if you haven't found an issue, say why it's sound. |
| **Standup** | Status visibility and blocker surfacing | Brief updates: what's done, what's next, what's blocked. No problem-solving in the channel — spin off a delegation channel for that. |
| **Broadcast** | Information dissemination | One-way from chair. Members acknowledge receipt. Questions go to a follow-up channel, not inline. |

The channel intent block is short — 2-3 sentences maximum. It answers: "What is this channel for, and what does good participation look like here?" It does NOT prescribe procedure. It encodes purpose.

### Workshop Integration Point

This guidance affects:
- **Section 1.1 (Channel Model):** The channel table should carry a `channel_type` field that maps to an intent template, plus an optional `intent_override` (text or JSONB) for custom channels.
- **Section 3.1 (Fan-Out Architecture):** The primer + intent are injected as part of message delivery envelope, not stored per-message. They're context, not content.
- **Section 4.1 (Workshop Channel Setup):** Channel creation should set the intent, either from a type template or explicitly.

---

## 2. Persona-Based Channel Membership

### Principle

The persona is the stable identity in a channel. The agent is the transient instance.

When a channel has "Con" as a member, it means the persona Con — not agent #1053 specifically. If agent #1053 hands off to agent #1054, the new agent inherits Con's channel membership. From the channel's perspective, Con went home and came back the next day. The conversation continues.

### Implications for the Data Model

- **Membership table:** Should reference `persona_id`, not just `agent_id`. The `agent_id` field tracks the current active instance for delivery routing, but the membership itself is persona-scoped.
- **Handoff flow:** When `HandoffExecutor` creates a successor agent, it updates the `agent_id` on all active channel memberships for that persona. The channel membership record persists; only the delivery target changes.
- **Message attribution:** Messages in the channel history show the persona name ("Con", "Paula") with the agent instance ID as metadata. The conversation reads as a continuous dialogue with Con, not a fragmented history across agent instances.
- **Edge case — no active agent:** If a persona's agent has ended and no successor exists, the membership remains but delivery is suspended. The persona is "offline" in the channel. When a new agent for that persona starts and is detected, delivery resumes.

### Workshop Integration Point

This guidance affects:
- **Section 1.4 (Membership Model):** Membership is persona-based with agent-instance routing. Add `persona_id` (FK) to membership table; `agent_id` becomes the mutable delivery target.
- **Section 1.2 (Message Model):** Messages carry `persona_id` as the sender identity, `agent_id` as the instance metadata.
- **Section 0A.2 (Startup Detection):** When a new agent starts for a persona, check for active channel memberships in addition to handoff documents.

---

## 3. Chair Role — Any Persona, Delivery Priority

### Principle

The chair is the person responsible for the interaction. Any persona can chair. The role is per-channel, not per-persona-type — a developer can chair a technical review, a PM can chair a standup, the operator can chair a workshop, or an agent can chair a session that includes the operator.

### Chair Capabilities

| Capability | Description |
|---|---|
| **Delivery priority** | Chair's messages are delivered first when multiple responses queue simultaneously. Other members' messages queue behind the chair's. |
| **Channel creation** | The creator of a channel is its initial chair. Chair can be transferred. |
| **Membership management** | Chair can add/remove members from the channel. |
| **Channel intent setting** | Chair sets or overrides the channel intent when creating or during the channel lifecycle. |
| **Channel closure** | Chair archives the channel when the interaction is complete. |

### Not a Persona Trait

The chair role is an **in-channel authority**, not a persona capability. It doesn't need to be encoded in persona skill files. Any persona can hold it. What the persona brings to the chair role is their domain expertise and judgment — Gavin chairs with a PM's discipline, Con chairs with a developer's focus, Paula chairs with organisational rigour.

However, **decision boundaries in persona specs should acknowledge channel authority.** If a persona can chair channels, their spec should reflect that they can direct other agents within the scope of a chaired interaction. This is a lightweight addition — not a new section, just a note in the existing Decision Boundaries.

### Delivery Priority Mechanics

When multiple channel members respond near-simultaneously:
1. Check if the chair has a pending response in the delivery queue
2. If yes: deliver the chair's message first to all members
3. Then deliver other members' messages in chronological order
4. If the chair is not in the queue: standard chronological delivery

This is a soft priority, not a hard gate. It ensures the chair's direction-setting messages land before responses that might not have seen the chair's latest input.

### Workshop Integration Point

This guidance affects:
- **Section 1.4 (Membership Model):** Add `is_chair` (boolean) to membership table. Exactly one member per channel has `is_chair = true`.
- **Section 2.1 (Channel Lifecycle):** Chair is set at creation. Transfer mechanism needed (chair can designate a new chair).
- **Section 3.1 (Fan-Out Architecture):** Delivery queue checks chair priority before fan-out ordering.
- **Section 3.3 (Delivery Timing):** Chair priority interacts with delivery timing — chair messages may preempt queued non-chair messages.

---

## Summary for Workshop Incorporation

| # | Guidance | Affects Sections | Key Change |
|---|---|---|---|
| 1 | Two-layer primer: base (universal) + channel intent (per-type) | 1.1, 3.1, 4.1 | Channel carries type + intent; primer is injected context, not stored per-message |
| 2 | Persona-based membership with agent-instance routing | 1.2, 1.4, 0A.2 | Membership references persona; agent ID is mutable delivery target |
| 3 | Chair is per-channel authority, any persona, delivery priority | 1.4, 2.1, 3.1, 3.3 | `is_chair` on membership; delivery queue respects chair priority |

All three recommendations are additive — they extend the existing workshop structure without contradicting any resolved decisions. They can be incorporated as additional context on the affected decision sections, or as resolved sub-decisions within those sections.
