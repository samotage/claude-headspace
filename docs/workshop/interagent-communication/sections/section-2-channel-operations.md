# Section 2: Channel Operations & CLI

**Status:** Decisions 2.1–2.2 resolved. Decision 2.3 pending.
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Depends on:** [Section 1](section-1-channel-data-model.md)
**Canonical data model:** [`../../erds/headspace-org-erd-full.md`](../../erds/headspace-org-erd-full.md) — resolved outcomes are stored there, not in embedded ERDs below.

**Purpose:** Design how channels are created, managed, and interacted with. The CLI is the primary agent interface; the API serves the dashboard and remote agents.

---

### 2.1 Channel Lifecycle
- [x] **Decision: How are channels created, and what's their lifecycle?**

**Depends on:** [1.1](section-1-channel-data-model.md#11-channel-model)

**Context:** Channels need to be created, populated with members, and eventually archived. The question is who creates them and when.

**Operator use case (2 March 2026):** During a workshop session with Robbo, Sam needed to pull Con into the conversation to brief him on a bug. Today this requires: spinning up a new agent, writing a prompt, sending a document link — "a pain in the fucking ass." The channel should support **mid-conversation member addition** — any participant (or at minimum the chair/operator) can add another persona to the channel, and the new member receives enough context to participate immediately. This is the "pull someone into the meeting" pattern.

**Resolution:**

**1. Creation paths:** CLI (`flask channel create`), dashboard, and voice bridge. Voice bridge is the primary operator interface for this feature.

**2. Who can create:** Capability is a **persona attribute**, implemented as a service-layer check (not a DB column). `agent.can_create_channel?` delegates to `persona.can_create_channel?` which checks persona type and/or role. This is OOP method delegation — the check logic lives on the Persona model, not as a boolean column. Operator always has creation capability inherently (person/internal PersonaType).

**3. Creation mode:** Explicit only for v1. No implicit channel creation from delegation messages.

**4. Lifecycle states:**

| State | Meaning | Transition trigger |
|---|---|---|
| `pending` | Channel created, members being assembled. System messages (joins) permitted, no conversation yet. | Channel created |
| `active` | Conversation in progress. | First non-system message sent |
| `complete` | Business concluded. | Either last active member leaves (auto-complete — muted members do not count as active for this trigger) OR chair/operator explicitly completes |
| `archived` | Deep freeze. Excluded from general lists. | Explicit action, sometime after complete |

No reactivation. Create a new channel if needed.

**5. Mid-conversation member addition:** Any channel participant or operator can add a persona. If the persona has no running agent, Headspace spins one up (same creation + readiness polling pattern as remote agents). New agent receives persona injection, then a context briefing of the last 10 messages injected into spin-up context. System message posted to channel ("Paula joined the channel").

**6. 1:1 to group channel promotion:** Adding a third party to a 1:1 conversation creates a **new channel**. Existing agent sessions continue untouched — their command/turn trees, tmux bridges, and all existing machinery keep running. The channel is an **overlay** that connects existing sessions, not a replacement for them. Agents don't need to know they're "in a channel" in any architectural sense — they receive messages via tmux, they respond, the hook receiver captures the response, and the channel handles fan-out to other members. The 1:1 sessions ARE the agents; the channel is the shared room they're all listening in.

**7. Context briefing:** Last 10 messages from the channel (or from the preceding 1:1 conversation in the promotion case), injected into new agent's spin-up context after persona injection. Delivered as a single synthesised context block, not replayed as individual messages.

**8. Standing/default channels:** None for v1.

**Key architectural insight:** The channel is a Headspace-level construct, not an agent-level one. Nothing changes for existing agent sessions when a channel is created — the IntentDetector classifies inputs, the command/turn tree records them, the tmux bridge delivers them. The channel adds the fan-out layer on top of machinery that already works.

---

### 2.2 CLI Interface
- [x] **Decision: What CLI commands do agents use to interact with channels?**

**Depends on:** 2.1, [Section 1](section-1-channel-data-model.md) (data model)

**Context:** Following the Section 1 org workshop pattern (`flask org`), channel operations need a CLI entry point. Agents interact with channels via bash tools — the CLI is their primary interface.

**Resolution:**

#### Namespace

**Standalone `flask channel` and `flask msg` groups.** Not nested under `flask org`.

Channels are a system-level primitive — cross-org by design. A channel can have members from different orgs or no org at all. Nesting under `flask org` would misrepresent the scope. The Organisation Workshop Section 1.3 resolved `flask org` as the entry point for organisational commands (personas, positions, orgs); channels are communication infrastructure, not org structure.

#### Caller Identity Resolution

The CLI needs to know which agent is calling. Two-strategy cascade:

1. **Primary — tmux pane detection:** `tmux display-message -p '#{pane_id}'` → look up Agent by `tmux_pane_id`. Works for all local agents in tmux sessions. Zero configuration.
2. **Override — `HEADSPACE_AGENT_ID` env var:** Set explicitly when pane detection isn't possible (testing, non-tmux environments, remote agents using CLI). Takes precedence when set.

If neither resolves to a valid active agent, the command fails with: `Error: Cannot identify calling agent. Are you running in a Headspace-managed session?`

The calling agent's persona is derived from the agent record. All capability checks and membership queries use the persona, not the agent directly.

#### Channel Commands — `flask channel`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `create` | `<name> --type <type>` | Create a channel. Required: name and type (workshop/delegation/review/standup/broadcast). Optional: `--description`, `--intent` (custom intent override), `--org <slug>`, `--project <slug>`, `--members <persona-slug>,<persona-slug>,...` (batch add at creation). Creator becomes chair. Channel starts in `pending` state. |
| `list` | _(none)_ | List channels where calling persona is an active member (default). Optional: `--all` (all visible channels), `--status <status>` (filter by lifecycle state), `--type <type>` (filter by channel type). |
| `show` | `<slug>` | Show channel details: name, type, status, description, intent, members (with roles/status), message count, created/completed/archived timestamps. |
| `members` | `<slug>` | List channel members with status (active/left/muted), chair designation, and whether agent is online. |
| `add` | `<slug> --persona <persona-slug>` | Add a persona to the channel. If persona has no running agent, Headspace spins one up asynchronously (same creation + readiness polling as remote agents). System message posted to channel. Returns immediately: "Added Con, agent spinning up..." |
| `leave` | `<slug>` | Leave a channel. Sets membership status to `left`, `left_at` timestamp. If last active member leaves, channel auto-transitions to `complete`. |
| `complete` | `<slug>` | Complete a channel (transition to `complete` state). Chair or operator only. Sets `completed_at` timestamp. Command name matches state name — no translation layer. CLI consumers are agents (software), not humans; state consistency matters more than conversational English. |
| `transfer-chair` | `<slug> --to <persona-slug>` | Transfer chair role to another active member. Current chair only. |
| `mute` | `<slug>` | Mute channel — delivery paused for calling persona. Messages accumulate; catch up via history on unmute. |
| `unmute` | `<slug>` | Unmute channel — delivery resumes from this point forward. |

#### Message Commands — `flask msg`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `send` | `<slug> <content>` | Send a message to a channel. Content is positional (quoted string). Optional: `--type delegation\|escalation` (default: `message`; `system` type not CLI-callable — service-generated only). Optional: `--attachment <path>` (single file, per Decision 1.2). |
| `history` | `<slug>` | Show channel message history. Default format: conversational envelope (see below). Optional: `--format yaml` (machine consumption). Optional: `--limit N` (default: 50). Optional: `--since <ISO-timestamp>`. |

#### Conversational Envelope Format (history default)

```
[#persona-alignment-workshop] Paula (agent:1087) — 2 Mar 2026, 10:23:
I disagree with the approach to skill file injection. The current
tmux-based priming has a fundamental timing problem...

[#persona-alignment-workshop] Robbo (agent:1103) — 2 Mar 2026, 10:24:
Paula raises a valid point. The timing issue is...
```

Default to conversational format because messages are content, not structure — exception to the org CLI's YAML-default rule. `--format yaml` available for machine consumption.

#### One-Agent-One-Channel Enforcement

When an agent tries to join a second channel (via `add` or at creation), the CLI returns an actionable error:

```
Error: Agent #1053 (Con) is already an active member of #delegation-build-auth-12.
Leave that channel first: flask channel leave delegation-build-auth-12
```

This enforces the partial unique index from [Decision 1.4](section-1-channel-data-model.md#14-membership-model) at the CLI layer with a helpful message, not just a database constraint error.

#### Capability Checks

- **Create:** Checks `persona.can_create_channel` (service-layer method on Persona model, per Decision 2.1 — not a DB column). Fails with: `Error: Persona 'con' does not have channel creation capability.`
- **Complete / transfer-chair:** Checks `is_chair` on calling persona's membership. Fails with: `Error: Only the channel chair can complete this channel.`
- **Send / history:** Checks active membership. Fails with: `Error: You are not a member of #channel-slug.`
- **Add:** Checks caller is an active member of the channel. Fails with: `Error: You must be a member of #channel-slug to add others.`

#### Actionable Error Messages

All common failure cases return clear, actionable messages:

| Scenario | Error |
|----------|-------|
| Not a channel member | `Error: You are not a member of #channel-slug.` |
| Channel is complete/archived | `Error: Channel #channel-slug is complete. Create a new channel to continue.` |
| No creation capability | `Error: Persona 'con' does not have channel creation capability.` |
| Already in a channel (one-agent constraint) | `Error: Agent #N (Name) is already active in #other-channel. Leave first: flask channel leave other-channel` |
| Persona already a member | `Error: Persona 'robbo' is already a member of #channel-slug.` |
| Not the chair | `Error: Only the channel chair can [complete/transfer chair for] this channel.` |
| Cannot identify caller | `Error: Cannot identify calling agent. Are you running in a Headspace-managed session?` |

#### Architectural Notes (stated here, detailed in later sections)

| Principle | Detail | Deferred to |
|-----------|--------|-------------|
| **CLI delegates to service layer** | CLI is a thin Click wrapper around `ChannelService` methods. Same service backs the 2.3 API endpoints. | 2.3 |
| **CLI is agent-only** | Person-type personas (operator, external) use dashboard, voice bridge, or API — not CLI. | — |
| **Send is fire-and-forget** | CLI writes Message to DB and returns. Fan-out service handles async delivery to other members. | [Section 3](section-3-message-delivery.md) |
| **Agent spin-up on add is async** | CLI returns immediately with confirmation. Agent creation + readiness polling happens in background. | [Section 3](section-3-message-delivery.md) |
| **Unread tracking** | No per-recipient delivery tracking in v1 data model. Deferred. | v2 |
| **Voice bridge channel routing** | Semantic picker needs new channel-name matching patterns for voice commands like "send a message to the workshop channel." | 2.3 |
| **System messages are service-generated** | `system` message type posted by ChannelService on joins, leaves, state changes. Not exposed via CLI. | [Section 3](section-3-message-delivery.md) |

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
