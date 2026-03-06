---
validation:
  status: valid
  validated_at: '2026-03-06T13:17:46+11:00'
---

## Product Requirements Document (PRD) — Voice App: Promote Agent Chat to Group Channel

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 12 — Add promote-to-group-channel action to the voice app's agent chat kebab menu
**Author:** Mel
**Status:** Draft
**Depends on:** E9-S10 (Promote to Group Channel — dashboard + backend orchestration)

---

## Executive Summary

S10 delivered the promote-to-group capability on the dashboard: the operator clicks "Create Group Channel" on an agent card's kebab menu, picks a persona, and the system spins up a new agent, creates a group channel, and seeds context. But the voice app — the operator's primary interaction surface — was explicitly out of scope for S10.

This sprint brings the same capability to the voice app. The operator is in an agent chat on the voice page, opens the kebab menu, selects "Create Group Channel", picks a persona from the existing voice persona picker, and the backend orchestration from S10 handles the rest. The voice chat panel switches to the new group channel once it's ready.

The backend is already built (S10). This is a voice app UI integration sprint.

---

## 1. Context & Purpose

### 1.1 Context

The voice app (`/voice`) is the operator's primary conversational interface. It has its own JS architecture — separate from the dashboard — with its own kebab menu system (`voice-chat-controller.js`, `voice-sidebar.js`), chat panels, and sidebar navigation.

S10 built the promote-to-group orchestration backend (`POST /api/agents/<id>/promote-to-group`) and the dashboard UI trigger. The voice app was deferred. This sprint closes that gap.

The voice app already has the building blocks:
- Agent chat header kebab menu (`voice-chat-controller.js`: `buildAgentChatActions()`, `handleAgentChatAction()`)
- Agent card sidebar kebab menu (`voice-sidebar.js`: `_buildVoiceActions()`, `_handleVoiceAction()`)
- Persona picker for agent creation (`voice-sidebar.js`: `showPersonaPicker()`)
- Channel chat panel (`voice-channel-chat.js`) for displaying the resulting group conversation
- Portal kebab menu system (`portal-kebab-menu.js`) with icon registry

### 1.2 Target User

The operator (Sam), using the voice app as the primary interaction surface, mid-conversation with an agent.

### 1.3 Success Moment

Sam is on the voice page chatting with Robbo about a data model question. Robbo raises something that needs Con's perspective. Sam taps the kebab menu in the agent chat header, selects "Create Group Channel", picks Con from the persona picker, and confirms. A loading indicator appears. Seconds later, the voice chat panel switches to the new group channel. Con's agent has been briefed with the last 20 messages from Sam's conversation with Robbo. Sam, Robbo, and Con are now in a three-way voice-app conversation. Sam's original 1:1 chat with Robbo is still accessible in the sidebar.

---

## 2. Scope

### 2.1 In Scope

- "Create Group Channel" action in the voice app's agent chat header kebab menu
- Reuse of the voice app's existing persona picker pattern (`showPersonaPicker()`)
- Call to S10's backend endpoint (`POST /api/agents/<id>/promote-to-group`)
- Voice chat panel auto-switches to the new group channel on completion
- Sidebar updates to reflect the new channel
- Loading state and error handling in the voice app's existing patterns
- Portal kebab menu icon addition for the new action

### 2.2 Out of Scope

- Backend orchestration changes (S10 provides this — no backend work in this sprint)
- Dashboard UI changes (already done in S10)
- Agent sidebar card kebab menu (the promote action lives in the chat header kebab only — the sidebar card is too small for this workflow)
- Persona picker redesign (reuse existing `showPersonaPicker()` as-is)
- New channel type selection (S10 defaults to `workshop`)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. The agent chat header kebab menu includes "Create Group Channel" for active agents with a persona
2. Clicking the action opens the existing voice persona picker with the originating agent's persona filtered out
3. Selecting a persona and confirming calls `POST /api/agents/<id>/promote-to-group` with the selected persona slug
4. A loading indicator is visible during the orchestration flow
5. On success, the voice chat panel switches to the new group channel
6. The new channel appears in the sidebar under its project
7. The original 1:1 agent chat remains accessible in the sidebar
8. Errors display as voice-app toast notifications

### 3.2 Non-Functional Success Criteria

1. No new JS dependencies — vanilla JS, existing IIFE patterns
2. Reuses existing voice app UI components (persona picker, portal kebab, toast notifications)
3. No backend changes required — consumes S10's API as-is

---

## 4. Functional Requirements (FRs)

### Kebab Menu Action

**FR1: Create Group Channel menu item**
The agent chat header kebab menu (`buildAgentChatActions()` in `voice-chat-controller.js`) includes a "Create Group Channel" action. The action appears after "Handoff" and before the divider. It is only shown for active agents that have a persona assigned (same guard as the existing Handoff action: `_agentHasPersona()`).

**FR2: Portal kebab icon**
A new icon is registered in `PortalKebabMenu.ICONS` for the `promote` action. Use the existing `addMember` SVG path as a starting point — the icon should convey "add to group."

### Persona Picker

**FR3: Reuse existing persona picker**
The action triggers the existing `showPersonaPicker()` function from `voice-sidebar.js` (or an extracted version if it's tightly coupled to agent creation). The picker fetches active personas via `VoiceAPI.getActivePersonas()` and displays them in the existing picker UI.

**FR4: Persona filtering**
The persona picker filters out:
- The current agent's persona (already in the conversation)
- Any persona that has no active status

**FR5: Picker callback**
On persona selection and confirm, the picker invokes a callback that triggers the promote-to-group API call rather than the agent creation flow.

### API Integration

**FR6: Promote API call**
On confirm, the voice app calls `POST /api/agents/<agent_id>/promote-to-group` with body `{ "persona_slug": "<selected_slug>" }`. This is S10's existing endpoint — no new backend work.

**FR7: Loading state**
While the API call is in flight, display a loading indicator. Options (follow whichever pattern the voice app already uses for async operations):
- Inline text in the chat header: "Creating group channel with [persona name]..."
- Or a toast notification with spinner

**FR8: Success handling**
On API success (the response includes the new channel ID and details):
- Switch the voice chat panel to the new group channel (use existing `VoiceChannelChat.openChannel()` or equivalent)
- The sidebar refreshes to show the new channel (via existing SSE `channel_update` event handling)
- Show a success toast: "Group channel created with [original persona] and [new persona]"

**FR9: Error handling**
On API failure:
- Show an error toast with the failure reason
- Remain on the current agent chat (no navigation change)
- No partial state to clean up on the frontend (backend handles rollback per S10 FR15)

### Sidebar Updates

**FR10: Channel appears in sidebar**
The new channel appears in the sidebar via the existing SSE `channel_update` event handler. No additional sidebar logic is needed — the existing channel rendering in `voice-sidebar.js` should pick it up automatically.

**FR11: Original chat preserved**
The original 1:1 agent chat remains in the sidebar agent list, clickable, and fully functional. The promote action does not modify, hide, or reparent the original chat.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Vanilla JS only**
All JavaScript follows the existing voice app IIFE pattern. No framework dependencies.

**NFR2: Existing component reuse**
Reuse `showPersonaPicker()`, `PortalKebabMenu`, voice toast notifications, and `VoiceChannelChat` panel switching. Minimise new UI code.

**NFR3: No backend changes**
This sprint adds zero backend code. All orchestration is handled by S10's `POST /api/agents/<id>/promote-to-group` endpoint.

---

## 6. UI Overview

### Agent Chat Header Kebab (Updated)

```
┌─────────────────────┐
│ Fetch context        │
│ Attach to terminal   │
│ Agent info           │
│ Reconcile            │
│ Handoff              │
│ Create Group Channel │  <- new action
│ ─────────────────── │
│ Dismiss agent        │
└─────────────────────┘
```

### Flow Sequence

```
1. Operator is in agent chat on voice page
2. Taps kebab menu in chat header
3. Selects "Create Group Channel"
4. Existing persona picker opens (filtered)
5. Operator selects a persona, taps Confirm
6. Loading indicator: "Creating group channel with [persona]..."
7. Backend (S10): creates channel, adds members, spins up agent, seeds context
8. Voice chat panel switches to new group channel
9. Toast: "Group channel created with Robbo and Con"
10. Original 1:1 chat with Robbo still in sidebar
```

---

## 7. Dependencies

| Dependency | Sprint | Status | What It Provides |
|------------|--------|--------|------------------|
| Promote-to-group backend | E9-S10 | Done | `POST /api/agents/<id>/promote-to-group` endpoint, orchestration logic |
| Voice app kebab menus | E9-S8 | Done | Portal kebab menu system, agent chat header kebab |
| Voice persona picker | Existing | Done | `showPersonaPicker()` in voice-sidebar.js |
| Voice channel chat | E9-S8 | Done | `VoiceChannelChat` panel, `openChannel()` |
| Channel SSE events | E9-S5/S6 | Done | `channel_update` SSE event handling in voice app |

### No New Backend Requirements

This sprint is frontend-only. S10's API endpoint is consumed as-is.

### Potential Gaps to Verify During Build

- Is `showPersonaPicker()` in `voice-sidebar.js` extractable or reusable with a custom callback, or is it hardwired to agent creation? If hardwired, it needs a small refactor to accept a callback parameter.
- Does S10's promote endpoint return the new channel ID in the response? The voice app needs it to switch the chat panel.

---

## 8. Open Decisions

| Decision | Options | Status |
|----------|---------|--------|
| Kebab menu placement | Agent chat header only vs also sidebar card | **Resolved**: Chat header only. Sidebar card is too compact for this workflow — operator is already in the chat when the need arises. |
| Persona picker reuse | Direct reuse vs extract-and-parameterise | **Open**: Verify during build whether `showPersonaPicker()` can accept a callback or needs minor refactoring. |

---

## 9. Standing Note: Voice App Targeting

This PRD exists because S10 was scoped to the dashboard without a corresponding voice app PRD. Going forward, any feature that touches agent interactions should explicitly address both surfaces (dashboard and voice app) in scope, or explicitly defer the other surface with a follow-up PRD reference.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-06 | Mel    | Initial PRD — voice app counterpart to S10 promote-to-group |
