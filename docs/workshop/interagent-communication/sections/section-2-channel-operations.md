# Section 2: Channel Operations & CLI

**Status:** Fully resolved (3 decisions: 2.1–2.3)
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
- [x] **Decision: What API endpoints serve the dashboard and remote agents?**

**Depends on:** 2.2

**Context:** The CLI calls internal API endpoints. The dashboard and remote agents also need API access. This is the HTTP surface for channels.

**Resolution:**

One API surface, one service layer. The CLI (Decision 2.2), dashboard, voice bridge, and remote agents all call the same `ChannelService`. The API endpoints are thin HTTP wrappers — same pattern as the existing remote agent and voice bridge routes.

#### Blueprint: `channels_api` — `/api/channels`

New Flask blueprint. Follows existing conventions: JSON request/response, standard HTTP status codes, error envelope `{error: {code, message, status}}`.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/channels` | Create a channel. Body: `{name, channel_type, description?, intent_override?, organisation_slug?, project_slug?, members?: [persona_slug, ...]}`. Creator becomes chair. Returns 201 + channel JSON. | Dashboard session / Session token |
| `GET` | `/api/channels` | List channels for calling persona. Query params: `?status=`, `?type=`, `?all=true` (operator only — all visible channels). Returns 200 + array. | Dashboard session / Session token |
| `GET` | `/api/channels/<slug>` | Channel details: name, type, status, description, intent, member count, message count, timestamps. Returns 200. | Dashboard session / Session token |
| `PATCH` | `/api/channels/<slug>` | Update channel. Body: `{description?, intent_override?}`. Chair or operator only. Returns 200. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/complete` | Transition to `complete` state. Chair or operator only. Returns 200. | Dashboard session / Session token |

#### Membership: `/api/channels/<slug>/members`

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/channels/<slug>/members` | List members with status, chair designation, online/offline. Returns 200 + array. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/members` | Add a persona. Body: `{persona_slug}`. If no running agent, Headspace spins one up async (same pattern as remote agent creation). Returns 201. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/leave` | Calling persona leaves. Auto-complete if last active member. Returns 200. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/mute` | Mute — delivery paused. Returns 200. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/unmute` | Unmute — delivery resumes. Returns 200. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/transfer-chair` | Transfer chair. Body: `{persona_slug}`. Chair only. Returns 200. | Dashboard session / Session token |

#### Messages: `/api/channels/<slug>/messages`

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/channels/<slug>/messages` | Message history. Query params: `?limit=50`, `?since=<ISO>`, `?before=<ISO>` (cursor pagination by sent_at). Returns 200 + array. | Dashboard session / Session token |
| `POST` | `/api/channels/<slug>/messages` | Send a message. Body: `{content, message_type?: "delegation"\|"escalation"}`. Default type: `message`. `system` type not API-callable — service-generated only. Optional: `attachment_path`. Returns 201 + message JSON. | Dashboard session / Session token |

#### Authentication

**Two auth mechanisms, same as existing codebase:**

1. **Dashboard session** — Flask session cookie. The operator and dashboard JS use this. No changes needed.
2. **Session token** — `Authorization: Bearer <token>` header. Remote agents and embed widgets use this. Existing `session_token.py` infrastructure, existing `require_session_token` decorator. Token is scoped to the agent; channel access is derived from the agent's persona's channel memberships.

No new auth mechanism. The session token already carries agent identity → persona identity → channel membership. The `ChannelService` checks membership on every operation.

#### SSE Integration

**Two new SSE event types, broadcast on the existing `/api/events/stream` endpoint:**

| Event Type | Trigger | Data | Who receives |
|------------|---------|------|-------------|
| `channel_message` | New message posted to channel | `{channel_slug, message_id, persona_slug, persona_name, content_preview, message_type, sent_at}` | All SSE clients (dashboard filters by channel membership client-side; existing `?types=` filter works for selective subscription) |
| `channel_update` | Channel state change (member join/leave, status transition, chair transfer) | `{channel_slug, update_type, detail}` | All SSE clients |

**No separate SSE stream per channel.** The existing stream with type filtering is sufficient. Dashboard JS subscribes to `channel_message` and `channel_update` types, filters by channel membership client-side. Same pattern as `card_refresh` events today.

**Why not per-channel streams:** The existing broadcaster is connection-limited (100 clients). Per-channel streams would multiply connections by channel count. Type filtering on a single stream scales better and matches the existing architecture.

#### Voice Bridge Channel Routing

**Extend the existing semantic picker** with channel-name matching. The voice bridge already has agent matching via `VoiceFormatter`; channel matching follows the same pattern.

New voice commands routed through the existing `/api/voice/command` endpoint:

| Voice pattern | Routes to |
|---------------|-----------|
| "send to workshop channel: [content]" | `flask msg send <matched-slug> <content>` via ChannelService |
| "what's happening in the workshop?" | `GET /api/channels/<matched-slug>/messages?limit=10` → voice-formatted summary |
| "create a delegation channel for [task]" | `POST /api/channels` with inferred type |
| "add Con to this channel" | `POST /api/channels/<current>/members` |

Semantic matching: fuzzy match on channel name and slug, same algorithm as existing agent picker. "the workshop" matches `workshop-persona-alignment-7`. Ambiguous matches return a clarification prompt ("Which channel? persona-alignment-workshop or api-design-workshop?").

#### Shared API Surface — No Separate Remote Agent Channel API

Dashboard and remote agents use the **same endpoints**. The auth layer determines identity; the service layer checks permissions. No duplication.

Remote agents already have session tokens. Those tokens map to agent → persona → channel membership. The channel API checks membership via `ChannelService`, not via a separate remote-agent-specific path.

#### Rate Limiting

No channel-specific rate limiting in v1. The existing voice bridge rate limiter (sliding window per-token) and OpenRouter inference rate limiter handle the expensive operations. Channel message writes are cheap DB inserts — rate limiting is premature until there's evidence of abuse.

#### Response Format

Standard JSON. No voice-formatted wrapper on the REST API — that's the voice bridge's job. The voice bridge calls `ChannelService` directly and wraps responses in its own `{voice: {status_line, results, next_action}}` envelope.

```json
// POST /api/channels/<slug>/messages — 201
{
  "id": 42,
  "channel_slug": "workshop-persona-alignment-7",
  "persona_slug": "architect-robbo-3",
  "persona_name": "Robbo",
  "agent_id": 1103,
  "content": "The persona_id constraint is resolved.",
  "message_type": "message",
  "metadata": null,
  "attachment_path": null,
  "source_turn_id": 5678,
  "source_command_id": 234,
  "sent_at": "2026-03-03T10:23:45Z"
}
```

#### Architectural Notes

| Principle | Detail |
|-----------|--------|
| **One service, many frontends** | CLI, API, voice bridge, dashboard all call `ChannelService`. No logic in routes. |
| **Slug-based URLs** | Channels identified by slug in URLs, not integer IDs. Slugs are unique, human-readable, and already the CLI identifier. |
| **No channel-scoped SSE streams** | Single stream with type filtering. Scales better with the existing 100-connection limit. |
| **No new auth mechanism** | Dashboard session + existing session tokens cover all access patterns. |
| **Fire-and-forget message writes** | API writes message to DB and returns. Fan-out delivery is async (Section 3). |
| **`system` messages not API-callable** | Same as CLI — `system` type is service-generated only (joins, leaves, state changes). |
