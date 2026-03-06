# PRD: Channel Creation Redesign + Member Pills
**Epic:** E9 — Channels
**Sprint:** S11
**Status:** Draft
**Author:** Robbo
**Workshop:** #workshop-create-channel-chat-17 (2026-03-06)

---

## Problem Statement

Channel group chat creation (V0) required agents to already be running before a channel could be created. This was an acknowledged shortcut. The designed intent is that channel creation spins up new agents from personas — the same way a single agent is created, extended to multi-persona selection.

Additionally, the channel chat panel header shows a plain member count ("3 members") with no per-member identity or iTerm/tmux navigation — a gap that has been requested before and is overdue.

---

## Goals

1. **Redesign channel creation** so that selecting personas during channel setup always spins up new agents. No reuse of existing running agents.
2. **Unify the creation popup** so the same component handles channel creation and post-creation member addition (context-aware, not two separate flows).
3. **Add member pills to the channel chat header** — one pill per member, clickable via the existing focus API.
4. **Enable cross-project channel membership** — post-creation, add a persona from a different project.

---

## Out of Scope

- Reusing existing running agents (explicitly removed — V0 shortcut)
- Cross-project membership at creation time (post-creation only, by design)
- Multi-chair model
- Message editing or deletion
- Channel type changes post-creation

---

## Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Channel creation always spins up new agents from personas | Designed intent. V0 shortcut (attach existing agents) is removed. |
| D2 | Cross-project member addition is post-creation only | Simplicity. Creation stays single-project scoped. |
| D3 | Channel becomes active only when all agents are connected | Clean readiness model. No partial-active state. |
| D4 | Same popup component for create and post-creation add | Reuse over duplication. Context-aware: create = multi-select; add = single-select. |
| D5 | Member pill click uses existing focus API (`/api/focus/<agent_id>`) | Reuse existing behaviour, no new infrastructure needed. |
| D6 | Chat input locked until all agents connected; pills appear progressively | Readiness is binary (all or nothing) but UX shows incremental progress via pills and count. |
| D7 | System message injected on initiation and on full readiness | Channel chat is the status surface — no separate loading screen. |
| D8 | Agent spin-up failure: channel stays pending, system message with failure detail injected | Fail loudly. No silent partial channels. |

---

## User Stories

### US1 — Create a channel with new agents

**As** an operator,
**I want** to create a channel group chat by selecting a project and one or more personas,
**so that** new agents are spun up for each selected persona and the channel opens ready for interaction.

**Acceptance Criteria:**
- [ ] "New Channel" action opens a popup (project picker → persona multi-checkbox)
- [ ] Each selected persona results in one new agent being created
- [ ] Channel status remains `pending` until all agents are connected
- [ ] Chat input is disabled while channel is `pending`
- [ ] System message injected immediately on creation: *"Channel initiating…"*
- [ ] As each agent connects, their pill appears in the header progressively
- [ ] Member count in header reflects live state: *"1 of 3 members online"* → *"2 of 3 members online"*
- [ ] When all agents are connected, channel transitions to `active` and a go-signal system message is injected (e.g., *"All members connected — let's go."*)
- [ ] Chat input becomes enabled on `active` transition
- [ ] If any agent fails to spin up, a system message is injected with the failure detail; channel remains `pending` and does not proceed
- [ ] Operator (chair) is added as a member automatically

### US2 — Add a persona to an existing channel (same or cross-project)

**As** an operator,
**I want** to add a new persona to an existing channel after it was created,
**so that** I can expand the group or bring in a persona from a different project.

**Acceptance Criteria:**
- [ ] An "Add member" button is visible in the channel chat panel
- [ ] Clicking it opens the same popup as channel creation (single-select mode, project picker included)
- [ ] The selected project may differ from the channel's original project
- [ ] A new agent is spun up for the selected persona
- [ ] New member appears in the channel once the agent is connected
- [ ] New member pill appears in the header

### US3 — Member pills in channel chat header

**As** an operator,
**I want** to see per-member pills in the channel chat panel header,
**so that** I can identify who is in the channel and navigate directly to their iTerm/tmux session.

**Acceptance Criteria:**
- [ ] Channel chat panel header shows one pill per active member (not a plain count)
- [ ] Each pill displays the persona name
- [ ] Clicking a pill calls the focus API for that member's agent
- [ ] Pills update in real-time when members are added or agents connect
- [ ] If an agent is not yet connected (pending), the pill is shown in a distinct visual state (e.g., muted/greyed)

---

## Functional Specification

### Popup Component (Shared)

One reusable popup, two modes:

**Create mode** (triggered from "New Channel"):
- Step 1: Project picker (single select, required)
- Step 2: Persona multi-checkbox (filtered to personas with active persona records for the selected project)
- Step 3: Optional channel name override (auto-generated from persona names if not provided)
- CTA: "Create Channel"

**Add mode** (triggered from channel "Add member" button):
- Step 1: Project picker (single select, required — may differ from channel's project)
- Step 2: Persona single-checkbox or single-select (one persona per add operation)
- CTA: "Add to Channel"

Both modes use the same project picker and persona picker components. The difference is multi vs. single select and the CTA label.

### Channel Creation Backend

**Existing route:** `POST /api/channels`

**Change:** When `personas` are provided (as slugs), the service must:
1. Create the Channel record with status `pending`
2. For each persona slug: call agent creation (same path as `POST /api/agents`) to spin up a new agent
3. Create a `ChannelMembership` record for each persona (agent_id will be null initially)
4. As each agent connects and registers its session, update the membership's `agent_id`
5. When all memberships have non-null `agent_id`, transition Channel status to `active`
6. Broadcast SSE `channel_ready` event to trigger UI update

**No change to `ChannelMembership` model** — `agent_id` is already nullable and updated on agent connect.

**Channel readiness check:** A service method `check_channel_ready(channel_id)` — called after each agent registers — that counts pending memberships and transitions status when count reaches zero.

### Member Pills

**Template:** `templates/partials/_channel_chat_panel.html`

**Current:** "3 members" text (static)
**New:** One `<span>` pill per active membership, styled consistently with agent name pills elsewhere in the dashboard. Each pill:
- Displays `membership.persona.name`
- Has `data-agent-id="{{ membership.agent_id }}"` attribute
- Has `onclick="FocusAPI.focusAgent({{ membership.agent_id }})"` (or equivalent JS handler)
- Visual state: full opacity if `agent_id` is set; muted if `agent_id` is null (agent not yet connected)

**Real-time updates:** Channel chat panel already receives SSE events. On `card_refresh` or a new `channel_member_added` SSE event, re-render the pill row.

### Post-Creation Member Addition

**Existing route:** `POST /api/channels/<slug>/members`

**Change:** Accept `project_id` in the request body (currently membership is implicitly scoped to channel's project). The service resolves the persona within the specified project context and spins up a new agent.

**Cross-project agent:** Agent is created under the specified project (not the channel's project). `ChannelMembership.agent_id` is set when the agent connects. The channel's `project_id` FK remains pointing to the original project — cross-project membership is tracked at the membership level via the agent's own project association.

---

## Data Model

No schema migrations required. The existing `ChannelMembership` model already supports:
- `agent_id` nullable (pending state while agent spins up)
- `persona_id` non-null (stable identity, set at creation)
- `status` field ('active', 'muted', 'left')

**One addition to consider:** A `Channel.status` transition to `pending` → `active` on full readiness. This likely already exists (the model has `status: 'pending'|'active'|'complete'|'archived'`). Confirm whether `pending` is already used or if it needs wiring to the readiness check.

---

## SSE Events

| Event | Trigger | Payload |
|---|---|---|
| `channel_created` | Channel record created (existing) | channel slug, name, status |
| `channel_ready` | All agents connected, status → active | channel slug |
| `channel_member_added` | New membership created post-creation | channel slug, persona name, agent_id (may be null) |
| `channel_member_connected` | Agent connects and membership agent_id updated | channel slug, agent_id |

---

## UI Changes

| Component | Change |
|---|---|
| Channel admin page (`channels.html`) | Replace current create form with new popup (Create mode) |
| Channel chat panel header | Replace "N members" text with per-member pills |
| Channel chat panel | Add "Add member" button → popup (Add mode) |
| Dashboard channel cards | No change to card rendering; pills are panel-only |

---

## Out-of-Scope Deferred Items

- Removing a member from an existing channel (not requested in this sprint)
- Agent reconnection if a channel-member agent crashes mid-session
- Multi-project channel creation (cross-project only post-creation, by decision D2)

---

## Open Questions

_None. All decisions resolved in workshop session._

---

## Workshop Log

| Time | Decision |
|---|---|
| 11:05 | Mel and Robbo joined channel |
| ~11:20 | Sam confirmed: new agents always (V0 shortcut removed) |
| ~11:25 | Sam confirmed: cross-project post-creation only |
| ~11:30 | Sam confirmed: block until all agents connected |
| ~11:35 | Sam confirmed: same popup, context-aware reuse |
| ~11:40 | Sam confirmed: focus API reuse for pill clicks |
| ~11:50 | Sam confirmed: chat input locked until all connected; pills appear progressively |
| ~11:55 | Sam confirmed: system message on initiation; go-signal message on full readiness; tone is "green light, let's go" |
| ~12:00 | Sam confirmed: spin-up failure → system message with failure detail; channel stays pending |
