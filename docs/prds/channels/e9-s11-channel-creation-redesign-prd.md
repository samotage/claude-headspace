---
validation:
  status: draft
  validated_at: null
---

## Product Requirements Document (PRD) — Channel Creation Redesign + Member Pills

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 11 — Redesign channel group chat creation to always spin up new agents from personas; add per-member pills to the channel chat header
**Author:** Mel (workshopped with Sam and Robbo)
**Status:** Draft

---

## Executive Summary

Channel group chat creation (V0) required agents to already be running before a channel could be created. This was an acknowledged shortcut. This sprint returns to the designed intent: channel creation always spins up fresh agents from personas, using the same flow the operator already knows from single-agent creation, extended to multi-persona selection.

Alongside this, the channel chat panel header currently shows a plain member count ("3 members") with no per-member identity or navigation. This sprint replaces that with per-member pills that show who is in the channel and allow the operator to click through to each agent's iTerm/tmux session — consistent with the focus behaviour already present in single-agent chats.

---

## 1. Context & Purpose

### 1.1 Context

V0 channel creation was built around pre-existing agents: the operator had to spin up agents independently, then create a channel and attach them. This was a delivery shortcut, not a design intent. It created an awkward two-step flow and left the system dependent on external state (agents being alive and correctly identified at channel creation time).

The designed intent — confirmed in this workshop — is that channel creation is self-contained: the operator picks a project and selects personas, and the system handles spinning up the corresponding agents. This mirrors the existing single-agent creation flow and extends it naturally to multi-persona selection.

The member pills gap has been requested before. The channel header telling the operator there are "3 members" without naming them is a usability hole — the operator can't see who is in the channel without opening something else, and can't navigate to an agent's session directly from the panel header.

### 1.2 Target User

The operator (Sam), who creates and manages group channels and needs both a cleaner creation flow and better situational awareness inside the channel chat panel.

### 1.3 Success Moment

Sam clicks "New Channel" on the channel admin page. A popup appears. He selects the project, checks three personas from a list, and clicks "Create Channel." The channel appears immediately in `pending` state with the message "Channel initiating…" As each agent comes online, their pill appears in the header: "1 of 3 online" → "2 of 3 online" → "3 of 3 online." When all three are connected, the go-signal message appears ("Green light — let's go" or similar) and the chat input unlocks. Sam can click any pill in the header to jump straight to that agent's iTerm session.

---

## 2. Scope

### 2.1 In Scope

- Replace V0 channel creation (attach existing agents) with persona-based spin-up at creation time
- New channel creation popup: project picker + persona multi-checkbox, mirroring the single-agent creation flow
- Post-creation member addition: same popup, context-aware (single-select mode), accessible from inside the channel chat panel; project may differ from the channel's original project
- Channel readiness model: channel blocks in `pending` state until all agents are connected; chat input stays locked until all members are online
- Progressive status UX: system message on initiation, per-member pills appear as agents connect, member count updates in real-time, go-signal system message when all are ready
- Spin-up failure handling: failure surfaces as a system message with failure detail in the channel; channel remains `pending`
- Member pills in the channel chat panel header: one pill per member, clickable via the existing focus API, pending state visually distinct
- Reuse the same popup component for both channel creation and post-creation member addition

### 2.2 Out of Scope

- Reusing existing running agents at channel creation time (explicitly removed — V0 shortcut)
- Cross-project member addition at creation time (post-creation only, by design)
- Removing members from a channel (not requested in this sprint)
- Agent reconnection if a channel-member agent crashes mid-session
- Specific wording of system messages (implementer decision, within the "green light, let's go" tone)
- Specific error message content for spin-up failures (to be determined when failures are encountered in practice)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Creating a channel from the channel admin page opens a popup with project picker and persona multi-checkbox
2. Each selected persona results in one new agent being spun up — no reuse of existing agents
3. Channel status is `pending` and chat input is disabled until all agents are connected
4. A system message "Channel initiating…" (or similar) is injected immediately on creation
5. As each agent connects, their pill appears progressively in the channel chat header
6. Member count in the header reflects live state (e.g., "1 of 3 online")
7. When all agents are connected, a go-signal system message is injected and chat input becomes enabled
8. If a spin-up fails, a system message with failure detail is injected; the channel remains `pending`
9. An "Add member" button is visible in the channel chat panel
10. Clicking "Add member" opens the same popup in single-select mode; the selected project may differ from the channel's original project
11. The channel chat panel header shows one pill per member, with click-through to that agent's iTerm/tmux session via the existing focus API
12. Pills in pending state (agent not yet connected) are visually distinct from connected pills

### 3.2 Non-Functional Success Criteria

1. Vanilla JS only — no new framework dependencies or npm packages
2. All styling uses Tailwind utility classes and existing custom properties; new custom CSS goes in `static/css/src/input.css`
3. No new database migrations required (existing `ChannelMembership.agent_id` nullable field supports pending state)
4. Popup component is a single component, not duplicated for the two modes

---

## 4. Functional Requirements (FRs)

### Channel Creation

**FR1: Creation popup — project picker**
The "New Channel" action opens a popup. Step 1 is a project picker (single-select, required). The list shows all projects the operator has access to.

**FR2: Creation popup — persona multi-checkbox**
Step 2 shows active personas available for the selected project, presented as a multi-checkbox list. At least one persona must be selected to proceed. The CTA is "Create Channel."

**FR3: Agent spin-up at creation**
When the operator confirms, the system creates the Channel record in `pending` status, then spins up one new agent per selected persona. No existing running agents are attached. Even if a persona already has a running agent, a fresh instance is created.

**FR4: Pending state and chat input lock**
While the channel is `pending`, the chat input is disabled. The operator sees the channel panel but cannot send messages.

**FR5: Initiation system message**
Immediately on channel creation, a system message is injected into the channel: "Channel initiating…" (exact wording is implementer decision within this tone).

**FR6: Progressive pill appearance**
As each agent registers and connects, their member pill appears in the channel chat panel header. Pills appear one by one as agents come online — they do not all appear at once when the channel goes active.

**FR7: Live member count**
The header member count reflects real-time state during spin-up: e.g., "1 of 3 online" → "2 of 3 online" → "3 of 3 online."

**FR8: Go-signal system message**
When all agents are connected and the channel transitions to `active`, a system message is injected signalling readiness (tone: "green light, let's go" — exact wording is implementer decision). Chat input becomes enabled at this point.

**FR9: Spin-up failure handling**
If any agent fails to spin up, a system message is injected into the channel with the failure detail. The channel remains in `pending` state and does not proceed to `active`. Failure detail content is to be determined when failures are encountered in practice.

### Post-Creation Member Addition

**FR10: Add member trigger**
An "Add member" button or equivalent action is visible in the channel chat panel. It is accessible while the channel is active.

**FR11: Add member popup — single-select mode**
The same popup component is reused in single-select mode. Project picker is present and may be set to a project different from the channel's original project. The CTA is "Add to Channel."

**FR12: New agent spin-up for added member**
A new agent is spun up for the selected persona under the specified project. Cross-project membership is tracked at the membership level via the agent's own project association — the channel's original `project_id` FK is not changed.

**FR13: New member appears on connection**
The new member's pill appears in the header when their agent connects. The channel remains active during this addition — existing members are not blocked.

### Member Pills

**FR14: Per-member pills in header**
The channel chat panel header displays one pill per channel member. Pills replace the current plain member count text. Each pill displays the persona name.

**FR15: Pill click — focus API**
Clicking a pill calls the existing focus API (`/api/focus/<agent_id>`) for that member's agent, bringing their iTerm/tmux session to the foreground. This is the same behaviour as the click-to-focus link in single-agent chats.

**FR16: Pending pill state**
If an agent has not yet connected (agent_id is null on the membership), the pill is shown in a visually distinct pending state (e.g., muted/greyed). A pending pill is not clickable.

**FR17: Real-time pill updates**
Pills update in real-time via SSE when members are added or agents connect. No page reload required.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Vanilla JS only**
All JavaScript follows the existing IIFE pattern. No framework dependencies. No new npm packages.

**NFR2: Tailwind CSS styling**
All styling uses Tailwind utility classes and existing custom properties. New custom CSS goes in `static/css/src/input.css`. Never write to `static/css/main.css` directly.

**NFR3: Reusable popup component**
The popup serves both creation and add-member flows. It is implemented once and parameterised by mode — not duplicated. Mode determines: multi vs. single persona select, CTA label, and submit behaviour.

**NFR4: No schema migrations**
The existing `ChannelMembership` model supports pending state via nullable `agent_id`. No new migrations are required. Confirm that `Channel.status = 'pending'` is already plumbed into the readiness transition before building the readiness check service method.

---

## 6. UI Overview

### Channel Creation Popup

```
┌─────────────────────────────────────────┐
│  New Channel                         [X]│
│                                         │
│  Project                                │
│  [▼ Select project...              ]    │
│                                         │
│  Personas                               │
│  ┌─────────────────────────────────┐    │
│  │ ☑ Robbo        Architect        │    │
│  │ ☑ Con          Builder          │    │
│  │ ☐ Paula        Recruiter        │    │
│  │ ☑ Wado         Designer         │    │
│  └─────────────────────────────────┘    │
│                                         │
│              [Cancel]  [Create Channel] │
└─────────────────────────────────────────┘
```

### Channel Panel — Pending State

```
┌──────────────────────────────────────────────┐
│  Group Channel   [Robbo●] [Con●] [Wado○]     │
│                  2 of 3 online               │
├──────────────────────────────────────────────┤
│                                              │
│  [system] Channel initiating…               │
│  [system] Robbo connected.                  │
│  [system] Con connected.                    │
│                                              │
│                                              │
├──────────────────────────────────────────────┤
│  [Chat input — disabled]                     │
└──────────────────────────────────────────────┘
```

### Channel Panel — Active State

```
┌──────────────────────────────────────────────┐
│  Group Channel   [Robbo●] [Con●] [Wado●]     │
│                  3 of 3 online               │
├──────────────────────────────────────────────┤
│                                              │
│  [system] Channel initiating…               │
│  [system] Robbo connected.                  │
│  [system] Con connected.                    │
│  [system] Wado connected.                   │
│  [system] Green light — let's go.           │
│                                              │
├──────────────────────────────────────────────┤
│  [Chat input — enabled]              [Send]  │
└──────────────────────────────────────────────┘
```

### Creation Flow Sequence

```
1. Operator clicks "New Channel" on channel admin page
2. Popup opens → operator selects project
3. Operator selects personas (multi-checkbox) → clicks "Create Channel"
4. Channel created in pending state
5. System message: "Channel initiating…"
6. Agents spin up; pills appear as each connects
7. Header count updates: "1 of 3 online" → "2 of 3" → "3 of 3"
8. System message: "Green light — let's go" (or similar)
9. Chat input unlocks → channel is usable
```

---

## 7. Dependencies

| Dependency | Sprint | Status | What It Provides |
|------------|--------|--------|------------------|
| Channel data model | E9-S3 | Done | Channel, ChannelMembership, Message tables |
| ChannelService | E9-S4 | Done | Channel creation, membership management |
| API endpoints | E9-S5 | Done | REST API for channels |
| Delivery engine | E9-S6 | Done | Fan-out to channel members |
| Dashboard UI | E9-S7 | Done | Channel cards, chat panel |
| Channel admin page | E9-S9 | Done | "New Channel" action trigger point |
| Promote to group | E9-S10 | Done | Established always-spin-up pattern for group membership |
| Agent lifecycle | Existing | Done | Agent creation/spin-up |
| Focus API | Existing | Done | `/api/focus/<agent_id>` — pill click-through |

### Prior Sprint Modifications

S11 supersedes and extends the following prior-sprint decisions. Implementors must be aware of these changes:

| Prior Sprint | What Changes | Details |
|---|---|---|
| E9-S9 (Channel Admin Page) | Channel creation UI redesigned | S9 FR8/FR15 defined a simple create form (name, type, description, optional personas). S11 replaces this with a multi-step popup (project picker → persona multi-checkbox). The S9 admin page create form must be replaced with the new popup component. |
| E9-S9 (Channel Admin Page) | Add member UI gains project picker | S9 FR13 defined add-member without project selection. S11 adds a project picker to the add-member popup to support cross-project membership. |
| E9-S5 (API Endpoints) | `POST /api/channels/<slug>/members` extended | S5 FR7 defined this endpoint without `project_id`. S11 requires `project_id` in the request body to support cross-project member addition. |
| E9-S10 (Promote to Group) | Agent spin-up reasoning extended | S10 FR8 established the always-spin-up pattern for promote-to-group. S11 extends this pattern to channel creation. Both decisions are aligned: always spin up a fresh agent regardless of whether the persona has a running instance. |

### Backend Changes Required

- `POST /api/channels`: accept `persona_slugs[]` + `project_id`, spin up agents per persona, create memberships with null `agent_id`, set channel to `pending`
- Readiness check: `check_channel_ready(channel_id)` — called after each agent registers; transitions channel to `active` and broadcasts `channel_ready` SSE when all memberships have non-null `agent_id`
- `POST /api/channels/<slug>/members`: accept `project_id` (cross-project support); existing route likely scoped to channel's project only — this is an extension to S5 FR7

### SSE Events

| Event | Trigger | Payload |
|---|---|---|
| `channel_created` | Channel record created | channel slug, name, status |
| `channel_ready` | All agents connected, status → active | channel slug |
| `channel_member_added` | New membership created | channel slug, persona name, agent_id (may be null) |
| `channel_member_connected` | Agent connects, membership agent_id updated | channel slug, agent_id |

### Potential Gaps to Verify

- Confirm `Channel.status = 'pending'` is already wired to a readiness transition, or determine what plumbing needs to be added
- Verify `POST /api/channels/<slug>/members` currently accepts or can be extended to accept `project_id` for cross-project membership

---

## 8. Open Decisions

| Decision | Options | Status |
|----------|---------|--------|
| Exact wording of initiation system message | e.g., "Channel initiating…" | Open — implementer decision within this tone |
| Exact wording of go-signal system message | e.g., "Green light — let's go." | Open — implementer decision within the "green light, go" tone confirmed by Sam |
| Exact wording of spin-up failure message | Dependent on failure type | Open — to be determined when failures are encountered in practice (Sam: "we'll deal with it then") |
| Location of "Add member" trigger in channel panel | Button in header vs. elsewhere in panel | Open — implementer decision; Sam confirmed it exists in the channel view |
| `Channel.status = pending` readiness wiring | Already exists vs. needs plumbing | Open — verify against existing codebase before building |

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-06 | Mel    | Initial PRD from workshop #workshop-create-channel-chat-17 with Sam and Robbo |
| 1.1     | 2026-03-06 | Robbo  | Added Prior Sprint Modifications table; explicit acknowledgement that S11 supersedes S9 create/add-member UI and extends S5 FR7; cross-reference to S10 spin-up pattern |
