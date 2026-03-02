# Section 0: Existing Infrastructure Audit

**Status:** Resolved (4 decisions)
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Depends on:** None
**Canonical data model:** [`../../erds/headspace-org-erd-full.md`](../../erds/headspace-org-erd-full.md) — resolved outcomes are stored there, not in embedded ERDs below.

**Purpose:** Ground the workshop in what already exists. Understand the current communication paths, what can be reused, and what gaps need filling.

---

### 0.1 Current Communication Paths
- [x] **Decision: What communication paths exist today, and what's their scope/limitation?**

**Depends on:** None

**Context:** Before designing channels, we need to map what's already built. The existing system has several communication paths, none of which are channel-aware.

**Resolution:**

Seven communication paths exist today. Audit findings:

| # | Path | Direction | Mechanism | Latency | Reusable for Channels? |
|---|------|-----------|-----------|---------|----------------------|
| 1 | **Dashboard Respond** | Operator → Agent | `tmux send_text()` via `/api/respond/<agent_id>` | ~120-500ms (text + Enter + verify) | **Yes — this IS the delivery primitive** |
| 2 | **Voice Bridge** | Operator → Agent | `tmux send_text()` or `interrupt_and_send_text()` via `/api/voice/command` | Same + audio processing | **Yes — routes through same tmux primitive** |
| 3 | **Skill Injection** | Headspace → Agent | `tmux send_text()` one-shot at startup | Same | **Pattern reusable — idempotency guard pattern (`prompt_injected_at`) is a reference** |
| 4 | **Hook Events** | Agent → Headspace | 8 hook endpoints, HTTP POST from Claude Code | Near-instant (same machine) | **Yes — how we know what agents are doing** |
| 5 | **SSE Broadcast** | Headspace → Dashboard | Event queue per client, filter-based routing | Near-instant | **Yes — operator delivery path** |
| 6 | **Remote Agent API** | External → Headspace | REST + session tokens + CORS | HTTP latency | **Partially — needs extension for channel semantics** |
| 7 | **File Watcher** | Agent → Headspace (indirect) | Watchdog + polling on `.jsonl` files | 1-5s polling interval | **Backup only — too slow for real-time chat** |

**Tmux bridge concurrent fan-out capacity:**

- **Per-pane `RLock`:** The tmux bridge uses `_send_locks` dict with independent locks per pane. Concurrent fan-out to different panes is safe — different locks, no contention. Two messages to the *same* pane serialize correctly.
- **No global lock:** No global send lock across all panes. Fan-out to N agents = N independent lock acquisitions in parallel. A 3-person channel fan-out takes ~120-500ms (parallel), not 360-1500ms (serial).
- **Large text:** Messages over 4KB route through `load-buffer` + `paste-buffer` (temp file) instead of `send-keys -l`. Handles formatted channel messages.
- **Interrupt capability:** `interrupt_and_send_text()` sends Escape + 500ms settle + text. Currently used by voice bridge. Available for high-priority channel messages but destructive to in-progress work.

**Gaps identified:**
- No agent-to-agent path exists. Everything routes through the operator or is passively observed.
- No mechanism for agents to explicitly *send* to another entity. Agents produce output captured by hooks; they can't address a recipient.
- Hook receiver has no concept of "this output is addressed to a channel."

---

### 0.2 Agent Response Capture
- [x] **Decision: How are agent responses currently captured, and can this feed into channels?**

**Depends on:** 0.1

**Context:** For channel fan-out to work, Headspace needs to capture what an agent says and relay it to other channel members.

**Resolution:**

**Current capture mechanisms:**

1. **`stop` hook → transcript extraction (primary):** When Claude Code fires the stop hook, `_extract_transcript_content()` reads the last assistant response from the `.jsonl` transcript file. This is the agent's composed, finished response.
2. **PROGRESS turns via `post_tool_use` (intermediate):** During processing, the hook receiver reads new transcript entries incrementally and creates PROGRESS turns. These are partial/intermediate output — the agent's internal thinking, file reads, tool use results.
3. **Deferred re-check (fallback):** If the transcript isn't flushed when `stop` fires, a background thread retries after a short delay.

**Timing:** Capture is **turn-completion-based, not streaming.** The full response is available after the stop hook fires — when the agent is done talking. PROGRESS turns provide intermediate visibility but are inherently partial.

**Critical design decision — completion-only relay:**

Only the agent's **finished, composed response** (captured when the stop hook fires and the transcript is extracted) is relayed to channel members. The relay trigger is the stop hook event, not the Turn intent classification — the resulting Turn may have intent COMPLETION, END_OF_COMMAND, or other values as determined by the IntentDetector. PROGRESS turns, intermediate tool use output, and internal thinking stay on the agent's individual card/voice chat for operator monitoring but **never fan out to the channel.**

**Rationale:** PROGRESS turns are the agent's internal notes — useful for monitoring what an individual agent is doing, but noise in a group conversation. Relaying them would pollute groupthink and potentially derail the discussion's direction. Agents in a group channel should present composed, self-evaluated responses — not stream of consciousness.

**COMMAND COMPLETE marker handling:** The `COMMAND COMPLETE` footer (machine-parseable signal for monitoring software) is **stripped from channel messages** before relay. It's metadata, not conversational content. Retained in individual agent monitoring.

**Relay flow:**
1. Agent's stop hook fires → transcript extracted → COMPLETION turn created
2. Channel relay service checks: is this agent a member of any active channel?
3. If yes: strip `COMMAND COMPLETE` footer → wrap in channel envelope → fan out to other members
4. PROGRESS/intermediate output → SSE/dashboard/voice chat for individual agent only

**Remote agents:** No hooks (no tmux). Would need API-based response submission — a different capture path. Deferred to channel data model design ([Section 1, Decision 1.5](section-1-channel-data-model.md#15-relationship-to-existing-models)).

---

### 0.3 Delivery Mechanism Constraints
- [x] **Decision: What are the practical constraints on message delivery to agents?**

**Depends on:** 0.1

**Context:** Delivering a message to an agent (via tmux injection) has practical constraints that affect channel design.

**Resolution:**

**Agent state safety for message delivery:**

| Agent State | Safe to Deliver? | Reason |
|-------------|-----------------|--------|
| AWAITING_INPUT | **Yes — ideal** | Agent is waiting for input, prompt is ready |
| IDLE | **Yes** | No active command |
| COMPLETE | **Yes** | Command just finished, before next prompt |
| COMMANDED | **Risky** | Agent is processing user's command, may be mid-output |
| PROCESSING | **No** | Agent actively producing output, injection will interleave |

Channel delivery should target AWAITING_INPUT/IDLE/COMPLETE states. Messages to agents in PROCESSING state should be queued and delivered when the agent reaches a safe state (the stop hook is the natural trigger — the agent just finished, now deliver queued messages).

**Maximum message size:** 4KB via `send-keys -l`, effectively unlimited via `load-buffer` + `paste-buffer`. Not a practical constraint for channel messages.

**The envelope — message attribution and identity:**

Channel messages require a formatting envelope so agents can distinguish channel messages from operator commands and identify who said what. Resolved format:

```
[#channel-name] PersonaName (agent:ID):
<message content>
```

Components:
- **`[#channel-name]`** — identifies this as a channel message and which channel
- **`PersonaName`** — the persona name (who said it, conversationally)
- **`(agent:ID)`** — the specific agent instance ID (traceable back to individual agent card, full history, thinking)

Example:
```
[#persona-alignment-workshop] Paula (agent:1087):
I disagree with the approach to skill file injection. The current
tmux-based priming has a fundamental timing problem...
```

**Traceability:** The agent ID in the envelope links directly to the agent's individual card on the dashboard, where the operator can see all PROGRESS turns, tool use, and internal thinking. The channel view shows composed responses only; the individual card shows everything.

**Channel vs individual view:** These are separate views. The channel shows only composed responses relayed between members. The agent's individual card shows their full history including PROGRESS turns and internal processing. Linked by agent ID and timestamp but not interleaved.

---

### 0.4 Channel Behavioral Primer
- [x] **Decision: How do agents know they're in a group conversation and how to behave?**

**Depends on:** 0.1, 0.3

**Context:** Agents in solo mode are verbose, exploratory, and stream-of-consciousness — which is fine when it's just the operator monitoring. In a group channel, this behaviour is disruptive. Agents need a behavioral frame that shapes them into good group participants.

**Resolution:**

**Two-layer primer architecture** (incorporating AR Director guidance from `docs/workshop/interagent-communication/paula-channel-intent-guidance.md`):

**Layer 1 — Base Primer (universal, platform asset):**

Injected into every channel participant on join. Contains behavioral ground rules that apply regardless of channel type, role, or purpose. Maintained as a platform asset at a stable path (e.g., `data/templates/channel-base-primer.md`) alongside `platform-guardrails.md`. Changes follow the same review process as guardrails.

```markdown
[CHANNEL CONTEXT] You are participating in a group conversation
in channel #<channel-name>.

Members: <list of PersonaName (agent:ID) or OperatorName (operator)>
Chair: <chair name> — sets direction, resolves disagreements

Ground rules:
- You are one voice among several. Be concise and composed.
- Self-evaluate before responding: does this add value to the
  discussion, or am I just thinking out loud?
- Respond to the substance of what others said. Reference their
  points by name.
- If you disagree, say so directly and explain why — but stay
  constructive.
- Do not monologue. Make your point, then let others respond.
- If you need to do research or read files to inform your
  response, do it — but your channel response should be the
  conclusion, not the journey.
```

**Layer 2 — Channel Intent (per-channel-type):**

Injected alongside the base primer on join. Tells participants what this specific channel is optimising for. Set at channel creation — either from a channel-type template or explicitly by the creator. Short: 2-3 sentences maximum. Answers: "What is this channel for, and what does good participation look like here?"

| Channel Type | Intent Example |
|---|---|
| **Workshop** | Resolve decisions with documented rationale. Challenge assumptions, propose alternatives, converge on decisions. Output is decisions, not discussion. |
| **Delegation** | Task completion to spec. Chair defines the task; members execute and report. Conversation is scoped to the task. Tangents are flagged, not followed. |
| **Review** | Finding problems before they ship. Adversarial by design. Silence is not agreement — if you haven't found an issue, say why it's sound. |
| **Standup** | Status visibility and blocker surfacing. Brief updates: what's done, what's next, what's blocked. No problem-solving in the channel — spin off a delegation channel for that. |
| **Broadcast** | Information dissemination. One-way from chair. Members acknowledge receipt. Questions go to a follow-up channel, not inline. |

**Key design decisions:**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Injection timing** | Once on channel join | Repeating per-message wastes tokens and annoys agents. This is context, not content. |
| **Two-layer split** | Base primer (universal) + channel intent (per-type) | Separates "how to behave in any group" from "what this group is optimising for." Different governance: base is platform-level, intent is per-channel. |
| **Asset type** | Platform-level injectable markdown | Consistent with persona skill/experience pattern. Lives at `data/templates/channel-base-primer.md` alongside `platform-guardrails.md`. |
| **Channel types** | Enum on Channel model with intent templates | Feeds into [Section 1.1](section-1-channel-data-model.md#11-channel-model). Each type has a default intent; creators can override with custom intent text. |
| **Chair role** | Every channel has a chair | Someone must set direction. Operator when present; designated agent (e.g., Gavin as PM) for autonomous group chats. Any persona can chair — it's per-channel authority, not a persona trait. |
| **Chair capabilities** | Channel creation (creator = initial chair), membership management, intent setting, channel completion, chair transfer | Chair manages the channel. Creator becomes initial chair (per Paula's guidance). Delivery priority explicitly deferred to v2 — Paula recommended soft priority mechanics (Section 3 of AR Director guidance), but the workshop decided group chat is a pipeline (chronological) for v1. Priority delivery suits a different interaction pattern (all-hands). |
| **Channel purpose** | Set at channel creation via type template or explicit override | Feeds directly into the primer. Gives agents a relevance filter for their responses. |

**Behavioural shift from solo to group mode:**

| Solo Agent | Group Channel |
|------------|---------------|
| Verbose exploration is fine | Composed, evaluated responses only |
| Stream of consciousness acceptable | Make your point, then yield the floor |
| All output goes to the operator | Response goes to *everyone* — calibrate accordingly |
| Internal monologue useful for monitoring | Internal monologue is noise — stays off the channel |
| Can go deep on tangents | Stay aligned with channel purpose/intent |

**Forward context for Section 1 (from AR Director guidance):**

- **Persona-based membership (→ [Section 1.1, 1.4](section-1-channel-data-model.md)):** Membership is persona-scoped, not agent-scoped. The persona is the stable channel identity; the agent ID is the mutable delivery target. On handoff, membership persists — only the delivery target changes. Messages are attributed to the persona with agent ID as metadata. If no active agent exists for a persona, membership stays but delivery is suspended.
- **Operator as member (→ [Section 1.1, 1.4](section-1-channel-data-model.md)):** Resolved in 1.1 — the operator IS modelled as a Persona with PersonaType `person/internal`. First-class channel identity with no Agent instances. Delivery via SSE/dashboard/voice bridge. Sits above the org hierarchy (no PositionAssignment) but participates in channels as a peer. Future-proofed: additional human team members would be additional `person/internal` Personas.
- **Channel type on model (→ [Section 1.1](section-1-channel-data-model.md#11-channel-model)):** The Channel table should carry a `channel_type` field (enum) that maps to an intent template, plus an optional `intent_override` (text) for custom channels.
