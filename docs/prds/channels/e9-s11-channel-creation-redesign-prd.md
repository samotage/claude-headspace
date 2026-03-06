---
validation:
  status: valid
  validated_at: '2026-03-06T11:43:18+11:00'
---

## Product Requirements Document (PRD) — Channel Creation Redesign + Member Pills

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 11 — Redesign channel group chat creation in both the voice chat application and the dashboard to always spin up new agents from personas; add per-member pills to channel chat headers in both surfaces
**Author:** Mel (workshopped with Sam and Robbo)
**Status:** Draft

---

## Executive Summary

This sprint redesigns channel group chat creation across **both the voice chat application and the dashboard**. The backend changes are shared; the frontend must be implemented in each surface independently.

**Three changes, two surfaces:**

**1. Channel creation.** V0 required agents to already be running before a channel could be created. This was a delivery shortcut. The designed intent is that channel creation is self-contained: the operator picks a project and selects personas (multi-checkbox), and the system spins up new agents automatically. This replaces the V0 form in both the voice app channel creation bottom sheet and the dashboard channel admin page.

**2. Add member.** The voice app channel kebab menu has an "Add member" action that currently shows a stub message ("Member picker not yet available in voice app. Use the dashboard to add members."). The dashboard also needs this flow. Both surfaces get a real picker: project picker + persona single-select, which spins up a new agent and adds them to the channel.

**3. Member pills.** The channel chat header in both surfaces currently shows a plain member count with no per-member identity. Both get per-member pills — one per member, clickable to focus that agent's iTerm/tmux session.

---

## 1. Context & Purpose

### 1.1 Context

**Two surfaces, shared backend:**
- **Voice chat application:** `static/voice/voice.html`, `voice-sidebar.js`, `voice-channel-chat.js`, `voice-api.js`, `voice.css` — standalone static app, custom CSS, vanilla JS IIFE pattern
- **Dashboard:** Jinja templates (`templates/`), dashboard JS (`static/js/`), Tailwind CSS

**V0 channel creation — voice app:** The voice sidebar "+" button opens `#channel-picker` bottom sheet. Current form: channel name (text), channel type (select), optional existing agent IDs. Submits via `VoiceAPI.createChannel(name, channelType, memberAgentIds)`. This is the shortcut being removed.

**V0 channel creation — dashboard:** The channel admin page (S9) has a channel creation form (name, type, description, optional personas from a list of existing agents). Same shortcut being removed.

**V0 add member — voice app:** `voice-channel-chat.js` `add-member` case dispatches stub message: "Member picker not yet available in voice app. Use the dashboard to add members."

**V0 add member — dashboard:** Post-creation member addition exists but is not cross-project aware (S5 FR7 defined `POST /api/channels/<slug>/members` without `project_id`).

**V0 member count:** Both surfaces show a plain member count (voice: `#channel-chat-member-count`; dashboard: channel chat panel header). No per-member identity in either.

### 1.2 Target User

The operator (Sam), using either the voice chat application or the dashboard, who needs to create channels with fresh agents from personas.

### 1.3 Success Moment

Sam is in the voice app. He taps "+" next to "Channels." The creation bottom sheet opens with project picker and persona multi-checkbox — not the old name/type/agents form. He picks the project, checks three personas, taps "Create Channel." The channel opens, "Channel initiating..." appears. Pills appear in the header as agents connect. When all three are ready, the go-signal message appears and the chat input unlocks. He taps a pill to jump to that agent's iTerm session.

The same experience is available when Sam creates a channel from the dashboard — same flow, same readiness model, different UI surface.

---

## 2. Scope

### 2.1 In Scope

- Redesign channel creation in the voice app (`#channel-picker` bottom sheet) — project picker + persona multi-checkbox; new agents spun up
- Redesign channel creation in the dashboard (channel admin page) — same flow, popup/modal pattern
- Wire voice app `add-member` stub to a real picker (project + persona single-select)
- Add/extend dashboard post-creation member addition with project picker for cross-project support
- Cross-project member addition: post-creation only; project picker present in add-member flow
- Channel readiness model: `pending` until all agents connected; chat input locked in both surfaces
- Progressive status UX: initiation system message, per-agent pills appear as agents connect, live count, go-signal message on full readiness
- Spin-up failure: system message with failure detail, channel stays `pending`
- Per-member pills in both voice app and dashboard channel chat headers, replacing plain count text
- Pill click-through to focus API in both surfaces
- Reuse the same bottom sheet / popup component for both creation and add-member within each surface

### 2.2 Out of Scope

- Reusing existing running agents at channel creation time (explicitly removed — V0 shortcut)
- Cross-project member addition at creation time (post-creation only)
- Removing members from a channel
- Agent reconnection if a channel-member agent crashes mid-session
- Specific wording of system messages (implementer decision within the tones confirmed by Sam)
- Specific error message content for spin-up failures (to be determined when failures are encountered)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Channel creation in both voice app and dashboard opens a picker with project selector and persona multi-checkbox — not the V0 name/type/agents form
2. Each selected persona results in one new agent being spun up — no reuse of existing agents
3. Channel status is `pending` and chat input is disabled (in both surfaces) until all agents are connected
4. A system message "Channel initiating..." (or similar) is injected immediately on creation
5. As each agent connects, their pill appears progressively in the channel chat header in both surfaces
6. Header member count reflects live state: e.g., "1 of 3 online" updating to "3 of 3 online"
7. When all agents are connected, a go-signal system message is injected and chat input becomes enabled
8. If a spin-up fails, a system message with failure detail is injected; the channel remains `pending`
9. "Add member" in both surfaces opens a picker (project + persona single-select) — not a stub or project-unaware form
10. The selected project in the add-member picker may differ from the channel's original project
11. Channel chat header in both surfaces shows one pill per member instead of a plain count
12. Each pill is clickable and calls the focus API for that agent
13. Pills in pending state (agent not yet connected) are visually distinct from connected pills

### 3.2 Non-Functional Success Criteria

1. Vanilla JS only in both surfaces — no framework dependencies
2. Voice app styles in `static/voice/voice.css`; dashboard styles via Tailwind utility classes with custom CSS in `static/css/src/input.css` if needed
3. No new database migrations (existing `ChannelMembership.agent_id` nullable field supports pending state)
4. Creation and add-member flows within each surface share a single component (parameterised by mode, not duplicated)

---

## 4. Functional Requirements (FRs)

### Channel Creation (Both Surfaces)

**FR1: Channel creation — project picker**
Channel creation opens a picker. Step 1 is a project picker (single-select, required). In the voice app this is a bottom sheet; in the dashboard this is a popup/modal.

**FR2: Channel creation — channel type**
Step 2 is a channel type selector (single-select, required). Available types: workshop, delegation, review, standup, broadcast. The type field is retained from V0 — its full significance will be defined in the organisational workshop context.

**FR3: Channel creation — persona multi-checkbox**
Step 3 shows active personas for the selected project as a multi-checkbox list. At least one must be selected. CTA: "Create Channel."

**FR4: Channel name**
Channel name is auto-generated from the selected persona names (e.g., "Robbo + Con + Wado"). The existing channel name text input is removed from both creation forms.

**FR5: Agent spin-up at creation**
On submit, the system creates the Channel record in `pending` status, then spins up one new agent per selected persona. No existing running agents are attached. Even if a persona has a running agent, a fresh instance is created.

**FR6: Pending state and chat input lock**
While the channel is `pending`, the chat input is disabled in both surfaces. The channel is visible but messaging is blocked.

**FR7: Initiation system message**
A system message is injected immediately on creation: "Channel initiating..." (exact wording is implementer decision).

**FR8: Progressive pill appearance**
As each agent connects, their member pill appears in the channel chat header. Pills appear one by one — not all at once.

**FR9: Live member count**
The header displays live readiness state: "1 of 3 online" updating progressively.

**FR10: Go-signal system message**
When all agents are connected and the channel transitions to `active`, a system message is injected (tone: "green light, let's go"). Chat input becomes enabled.

**FR11: Spin-up failure handling**
If any agent fails to spin up, a system message with failure detail is injected. The channel remains `pending`. Failure message content to be determined when failures are encountered in practice.

### Post-Creation Member Addition (Both Surfaces)

**FR12: Add member — voice app stub wired**
The `add-member` case in `voice-channel-chat.js` (currently stub) is wired to open the creation picker in single-select mode. Stub message removed.

**FR13: Add member — dashboard**
The dashboard channel chat panel's add-member action opens the same picker in single-select mode with project picker present.

**FR14: Add member picker — single-select mode**
Project picker present, may select a different project from the channel's original. CTA: "Add to Channel." Persona single-select.

**FR15: New agent spin-up for added member**
A new agent is spun up for the selected persona under the specified project. Cross-project membership tracked at membership level; channel `project_id` FK unchanged.

**FR16: New member pill on connection**
New member's pill appears in the header when their agent connects. Channel remains active during addition.

### Member Pills (Both Surfaces)

**FR17: Per-member pills replace plain count**
Channel chat header in both surfaces displays one pill per member. Each pill shows the persona name.

**FR18: Pill click — focus API**
Clicking a pill calls `/api/focus/<agent_id>`. Pending pills (agent not yet connected) are not clickable.

**FR19: Pending pill state**
Pills with null `agent_id` are rendered in a visually distinct pending state (e.g., muted/greyed).

**FR20: Real-time pill updates**
Pills update in real-time via SSE when members are added or agents connect. No page reload.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Vanilla JS**
Both surfaces use vanilla JS. Voice app follows existing IIFE pattern. Dashboard follows existing dashboard module pattern. No framework dependencies.

**NFR2: CSS — surface-specific**
Voice app: all new styles in `static/voice/voice.css`.
Dashboard: Tailwind utility classes; custom CSS in `static/css/src/input.css` if needed. Never write to `static/css/main.css` directly.

**NFR3: Reusable component within each surface**
Within each surface, the creation and add-member flows share one component parameterised by mode. Not duplicated.

**NFR4: No schema migrations**
`ChannelMembership.agent_id` is already nullable. Confirm `Channel.status = 'pending'` readiness transition is wired before building.

---

## 6. UI Overview

### Voice App — Channel Creation Bottom Sheet (Redesigned)

```
+------------------------------------------+
|  Create Channel                       [X] |
|------------------------------------------|
|  Project                                  |
|  [v Claude Headspace               ]      |
|                                           |
|  Personas                                 |
|  +--------------------------------------+ |
|  | [x] Robbo        Architect           | |
|  | [x] Con          Builder             | |
|  | [ ] Paula        Recruiter           | |
|  | [x] Wado         Designer            | |
|  +--------------------------------------+ |
|                                           |
|         [Create Channel - 3 selected]     |
+------------------------------------------+
```

### Dashboard — Channel Creation Popup (Redesigned)

```
+------------------------------------------+
|  New Channel                          [X] |
|------------------------------------------|
|  Project                                  |
|  [v Select project...              ]      |
|                                           |
|  Personas                                 |
|  +--------------------------------------+ |
|  | [x] Robbo        Architect           | |
|  | [x] Con          Builder             | |
|  | [ ] Paula        Recruiter           | |
|  | [x] Wado         Designer            | |
|  +--------------------------------------+ |
|                                           |
|            [Cancel]  [Create Channel]     |
+------------------------------------------+
```

### Channel Chat Header — Pending State (Both Surfaces)

```
+------------------------------------------------+
| Robbo + Con + Wado  [Robbo~][Con~][Wado~]   :  |
|                     1 of 3 online              |
|------------------------------------------------|
| [system] Channel initiating...                 |
| [system] Robbo connected.                      |
|                                                |
|------------------------------------------------|
| [Chat input -- disabled]                       |
+------------------------------------------------+
```

### Channel Chat Header — Active State (Both Surfaces)

```
+------------------------------------------------+
| Robbo + Con + Wado  [Robbo*][Con*][Wado*]   :  |
|                     3 of 3 online              |
|------------------------------------------------|
| [system] Channel initiating...                 |
| [system] Robbo connected.                      |
| [system] Con connected.                        |
| [system] Wado connected.                       |
| [system] Green light -- let's go.              |
|                                                |
|------------------------------------------------|
| [Type a message...]                    [Send]  |
+------------------------------------------------+
```

### Creation Flow Sequence (Both Surfaces)

```
1. Operator opens channel creation (voice: tap "+"; dashboard: "New Channel" button)
2. Picker opens with project selector + persona multi-checkbox
3. Operator selects project and personas, submits
4. Channel created in pending state; picker closes
5. Channel chat opens; system message: "Channel initiating..."
6. Agents spin up; pills appear in header as each connects
7. Live count: "1 of 3 online" -> "2 of 3" -> "3 of 3"
8. System message: "Green light -- let's go" (or similar)
9. Chat input unlocks -- channel is usable
```

---

## 7. Dependencies

| Dependency | Sprint | Status | What It Provides |
|------------|--------|--------|------------------|
| Channel data model | E9-S3 | Done | Channel, ChannelMembership, Message tables |
| ChannelService | E9-S4 | Done | Channel creation, membership management |
| API endpoints | E9-S5 | Done | REST API for channels |
| Delivery engine | E9-S6 | Done | Fan-out to channel members |
| Dashboard UI | E9-S7 | Done | Dashboard channel cards, chat panel |
| Voice app channel chat | E9-S8 | Done | Voice app channel chat panel, kebab menu, SSE handler |
| Channel admin page | E9-S9 | Done | Dashboard "New Channel" action trigger point |
| Promote to group | E9-S10 | Done | Established always-spin-up pattern |
| Agent lifecycle | Existing | Done | Agent creation/spin-up |
| Focus API | Existing | Done | /api/focus/<agent_id> -- pill click-through |

### Voice App Files Affected

| File | Change |
|---|---|
| `static/voice/voice.html` | Replace `#channel-picker` form body; add member pill container to channel chat header |
| `static/voice/voice-sidebar.js` | `openChannelPicker()` and submit handler redesigned; call new API with `project_id` + `persona_slugs[]` |
| `static/voice/voice-channel-chat.js` | Wire `add-member` case to bottom sheet; replace `#channel-chat-member-count` with per-member pills |
| `static/voice/voice-api.js` | Update `createChannel()` signature; new or extended `addChannelMember()` |
| `static/voice/voice-sse-handler.js` | Handle `channel_member_connected` and `channel_ready` to update pills and unlock input |
| `static/voice/voice.css` | Styles for persona checkbox list, member pills, pending pill state |

### Dashboard Files Affected

| File | Change |
|---|---|
| `templates/` (channel admin page) | Replace channel creation form with popup using project picker + persona multi-checkbox |
| `templates/partials/_channel_chat_panel.html` | Replace member count text with per-member pill row |
| `static/js/` (channel-related modules) | Add/extend member picker popup; wire pill rendering; handle `channel_ready` + `channel_member_connected` SSE events |
| `static/css/src/input.css` | Custom CSS for pills and pending state if Tailwind utilities insufficient |

### Prior Sprint Modifications

S11 supersedes the following:

| Prior | Surface | What Changes | Details |
|---|---|---|---|
| V0 voice app channel creation | Voice app | Creation form replaced | `#channel-picker` took name + type + existing agent IDs. S11 replaces with project picker + persona multi-checkbox. Channel name auto-generated. |
| V0 `VoiceAPI.createChannel` | Voice app | API call signature changed | Currently `(name, channelType, memberAgentIds)`. S11 changes to `(projectId, personaSlugs[])` or equivalent. |
| V0 add-member stub | Voice app | Stub wired to real picker | `voice-channel-chat.js` ~line 439: stub replaced with bottom sheet in add-member mode. |
| E9-S9 channel creation form | Dashboard | Creation form replaced | S9 FR8/FR15 defined a simple create form (name, type, description, optional personas from existing agents). S11 replaces this with the project picker + persona multi-checkbox popup. |
| E9-S9 add-member | Dashboard | Project picker added | S9 FR13 defined add-member without project selection. S11 adds project picker to support cross-project membership. |
| E9-S5 `POST /api/channels/<slug>/members` | Backend | Extended with `project_id` | S5 FR7 defined this endpoint without `project_id`. S11 requires it for cross-project member addition. |
| E9-S10 (Promote to Group) | Both | Pattern aligned | S10 FR8 established always-spin-up. S11 extends to channel creation in both surfaces. |

### Backend Changes Required (Shared)

- `POST /api/channels`: accept `persona_slugs[]` + `project_id`; spin up one new agent per slug; create `ChannelMembership` records with `agent_id = null`; set `Channel.status = 'pending'`
- Readiness check `check_channel_ready(channel_id)`: called after each agent registers; transition to `active` and broadcast `channel_ready` SSE when all memberships have non-null `agent_id`
- `POST /api/channels/<slug>/members`: accept `project_id` for cross-project support

### SSE Events

| Event | Trigger | Payload |
|---|---|---|
| `channel_created` | Channel record created | channel slug, name, status |
| `channel_ready` | All agents connected, status active | channel slug |
| `channel_member_added` | New membership created | channel slug, persona name, agent_id (may be null) |
| `channel_member_connected` | Agent connects, membership agent_id updated | channel slug, agent_id |

### Gaps to Verify Before Building

- Confirm `Channel.status = 'pending'` to `'active'` readiness transition is wired, or determine what needs to be added
- Verify `POST /api/channels/<slug>/members` can accept `project_id` for cross-project membership
- Confirm persona API returns personas (not just running agents) for the project picker in both surfaces

---

## 8. Open Decisions

| Decision | Options | Status |
|----------|---------|--------|
| Channel name auto-generation format | e.g., "Robbo + Con + Wado" vs. role-based | Open -- implementer decision |
| Channel type field | V0 had type select (workshop/delegation/review/broadcast) | Resolved -- keep the type field in the creation form. Full utilisation deferred to organisational workshop context. |
| Exact wording of initiation system message | "Channel initiating..." or similar | Open -- implementer decision within this tone |
| Exact wording of go-signal system message | "Green light -- let's go." or similar | Open -- implementer decision within the tone confirmed by Sam |
| Spin-up failure message content | Dependent on failure type | Open -- to be determined when failures are encountered |
| `Channel.status = pending` readiness wiring | Already exists vs. needs plumbing | Open -- verify against existing codebase |

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-06 | Mel    | Initial PRD from workshop #workshop-create-channel-chat-17 with Sam and Robbo |
| 1.1     | 2026-03-06 | Robbo  | Added Prior Sprint Modifications table; cross-reference to S10 spin-up pattern |
| 1.2     | 2026-03-06 | Mel    | Context correction: PRD initially scoped to voice app only. Corrected NFR2. Added channel type as open decision. |
| 1.3     | 2026-03-06 | Mel    | Scope expanded: functionality applies to both voice app and dashboard. Backend changes shared; frontend implemented independently in each surface. Added dashboard files affected. Restored S9 prior sprint modifications. |
| 1.4     | 2026-03-06 | Robbo  | Sam confirmed: channel type field retained in both creation forms. Added FR2 (channel type selector); renumbered FR3-FR20 accordingly. Resolved channel type open decision. |
