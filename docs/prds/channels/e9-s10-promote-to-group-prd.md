---
validation:
  status: valid
  validated_at: '2026-03-06T08:16:50+11:00'
---

## Product Requirements Document (PRD) — Promote to Group Channel

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 10 — Spawn-and-merge: promote a 1:1 agent chat to a group channel via the agent card kebab menu
**Author:** Melanie (workshopped with Sam and Robbo)
**Status:** Draft

---

## Executive Summary

The operator is mid-conversation with an agent and realises another perspective would help. Today, adding another agent to the conversation requires leaving the chat, manually creating a channel, adding members, and briefing the new agent on context. This sprint enables a contextual, in-the-moment action: the operator clicks "Create Group Channel" in the agent card's kebab menu, picks a persona, and the system handles the rest — spinning up a new agent, creating a group channel, and seeding the new agent with context from the original conversation.

This is a spawn-and-merge pattern, not a conversion. The original 1:1 agent chat stays intact (it's the foundational tmux/Claude Code connection). A new group channel is created alongside it, seeded with the last 20 messages from the original conversation. Both the original agent and the new agent become members of the group channel. The operator continues the multi-agent conversation in the group channel while the original 1:1 remains available.

This sprint adds a new kebab menu action, a persona picker dialog, and orchestration logic that ties together existing capabilities: agent creation (agent_lifecycle), channel creation (ChannelService), and context briefing (existing channel briefing pattern from S4).

---

## 1. Context & Purpose

### 1.1 Context

The channel admin page (S9) covers planned, deliberate channel creation — "I need a workspace for X." This sprint covers the reactive, conversational use case — "This chat needs another brain." These are fundamentally different intents with different UX triggers.

The operator's 1:1 agent chats are the primary interaction surface. When a conversation reveals the need for additional expertise, the operator shouldn't have to break flow to do admin work. The promote-to-group action keeps them in context, right where the need emerges.

The existing codebase has all the building blocks:
- Agent card kebab menu (`_agent_card.html`, `agent-lifecycle.js`) with extensible action system
- ChannelService (`channel_service.py`) for channel creation, membership management, and context briefing
- Agent lifecycle service (`agent_lifecycle.py`) for spinning up new agents
- Channel chat panel (`_channel_chat_panel.html`, `channel-chat.js`) for the resulting group conversation

What's missing is the glue: a UI trigger, a persona picker, and orchestration logic to chain these capabilities together.

### 1.2 Target User

The operator (Sam), who is actively conversing with an agent and wants to bring in additional expertise without leaving the current interaction context.

### 1.3 Success Moment

Sam is chatting with Robbo about a data model decision. Robbo raises a point about persona constraints that Sam thinks Con should weigh in on. Sam clicks the kebab menu on Robbo's agent card, selects "Create Group Channel", picks "Con" from the persona picker, and hits confirm. Within seconds, a new group channel appears in the channel cards section. Con's agent spins up, receives a briefing with the last 20 messages from Sam's conversation with Robbo, and posts an initial response in the group channel. Sam, Robbo, and Con are now in a three-way conversation. Sam's original 1:1 chat with Robbo is still there, untouched.

---

## 2. Scope

### 2.1 In Scope

- New "Create Group Channel" action in the agent card kebab menu
- Persona picker dialog: search/select from available personas (project context already known)
- Orchestration flow: create group channel → add original agent as member → spin up new agent for selected persona → add new agent as member → seed context from original conversation
- Context seeding: last 20 messages from the original agent's conversation are provided as a briefing to the new agent
- `spawned_from_agent_id` reference on the new Channel model linking back to the originating agent
- Group channel appears in channel cards on the dashboard and is accessible via the chat panel
- Original 1:1 agent chat remains intact and functional
- System messages in the group channel indicating its origin ("Channel created from conversation with [agent name]")

### 2.2 Out of Scope

- Channel admin page (S9 — separate PRD, covers planned creation)
- Voice chat channel creation (separate PRD)
- Converting or destroying the original 1:1 chat (by design — the original stays intact)
- Adding multiple personas at once (v1 adds one; operator can add more via channel member management after creation)
- Selecting which messages to seed (v1 always seeds last 20 — no selection UI)
- Channel type selection (v1 defaults to `workshop` — operator can change via channel admin if needed)
- Automatic agent shutdown for the new agent if the channel completes (follow existing channel lifecycle patterns)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. The agent card kebab menu includes a "Create Group Channel" action for active agents
2. Clicking the action opens a persona picker dialog showing available personas
3. Selecting a persona and confirming triggers the full orchestration flow
4. A new group channel is created with the operator, original agent, and new agent as members
5. The new agent is spun up for the selected persona and joins the group channel
6. The new agent receives a context briefing containing the last 20 messages from the original agent's conversation
7. The group channel appears in the dashboard channel cards section
8. The original 1:1 agent chat remains functional and unmodified
9. The group channel contains a system message indicating its origin
10. The operator can immediately send messages in the new group channel via the chat panel

### 3.2 Non-Functional Success Criteria

1. The full orchestration flow (channel creation + agent spin-up + briefing) completes within 30 seconds
2. The persona picker loads available personas within 1 second
3. All new UI elements follow the existing dark theme and Tailwind CSS conventions
4. No new npm dependencies — vanilla JS only

---

## 4. Functional Requirements (FRs)

### Kebab Menu Action

**FR1: Create Group Channel menu item**
The agent card kebab menu includes a "Create Group Channel" action. The action is visible only for active agents (not dismissed, ended, or idle agents with no tmux connection). The menu item appears after existing actions (Focus, Respond, Handoff, Dismiss) and before the divider.

**FR2: Menu item disabled states**
The "Create Group Channel" action is disabled (greyed out with tooltip) when:
- The agent has no persona assigned (no identity to base the channel on)

### Persona Picker Dialog

**FR3: Persona picker dialog**
Clicking "Create Group Channel" opens a modal dialog with:
- Title: "Add Agent to Group Channel"
- Subtitle: "Select a persona to join the conversation with [original agent's persona name]"
- Searchable list of available personas showing: persona name, role, active/inactive status
- Only active personas are selectable
- Confirm button (disabled until a persona is selected)
- Cancel button

**FR4: Persona filtering**
The persona list excludes:
- The original agent's persona (already in the conversation)
- The operator's persona (automatically added as channel creator)
- Personas that are currently assigned to agents already in a channel with the original agent (prevent duplicates)

**FR5: Confirm and trigger**
Clicking confirm closes the dialog and triggers the orchestration flow. A loading indicator appears on the agent card or in a toast notification ("Creating group channel with [persona name]..."). The UI remains responsive during orchestration.

### Orchestration Flow

**FR6: Channel creation**
The system creates a new channel with:
- Name: auto-generated from the conversation context (e.g., "[original persona name] + [new persona name] group")
- Type: `workshop` (default)
- Status: `active` (skip pending since members are immediately added)
- `spawned_from_agent_id`: reference to the original agent's ID
- Creator/chair: the operator's persona

**FR7: Original agent membership**
The original agent's persona is added to the new channel as a member. The agent's existing tmux connection is used for channel delivery (existing S6 delivery engine pattern).

**FR8: New agent spin-up**
A new agent is always created for the selected persona, associated with the same project as the original agent. The agent spin-up follows the existing agent lifecycle pattern. Even if the persona already has a running agent in the same project, a fresh instance is spun up — the existing agent may be mid-task on unrelated work and should not be pulled into the group channel.

**FR9: New agent membership**
The new agent's persona is added to the channel as a member.

**FR10: Context seeding**
The last 20 turns from the original agent's full conversation history (across all commands, not just the current one) are formatted as a context briefing and delivered privately to the new agent via tmux injection. The briefing is not posted as a visible message in the group channel — it is a private briefing to the new agent only, giving them context without cluttering the channel. The briefing format follows the existing channel context briefing pattern from S4 (the `_send_context_briefing` method).

**FR11: System origin message**
A system message is posted in the group channel: "Channel created from conversation with [original agent persona name]. Context: last 20 messages shared."

**FR12: Operator auto-join**
The operator's persona is automatically added as a member and chair of the new channel. The operator does not need to manually join.

### Data Model

**FR13: Channel spawned_from reference**
The Channel model gains an optional `spawned_from_agent_id` column (FK to Agent, nullable, ON DELETE SET NULL). This provides traceability from the group channel back to the originating 1:1 conversation without coupling the channel's lifecycle to the agent's.

### UI Updates

**FR14: Channel card appearance**
When the orchestration flow completes, a new channel card appears in the dashboard's channel cards section (via existing `channel_update` SSE event). The card is immediately clickable to open the chat panel.

**FR15: Error handling**
If any step of the orchestration fails (agent spin-up fails, channel creation fails, persona not found), the operator sees a clear error message via toast notification. Partial state is cleaned up — if the channel was created but agent spin-up failed, the channel is removed. The original 1:1 chat is never affected by errors in the orchestration flow.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Vanilla JS only**
All JavaScript follows the existing IIFE pattern. No framework dependencies. No new npm packages.

**NFR2: Tailwind CSS styling**
All styling uses Tailwind utility classes and existing custom properties. New custom CSS goes in `static/css/src/input.css`.

**NFR3: Transactional orchestration**
The orchestration flow (channel creation + membership + agent spin-up + briefing) should be atomic where possible. If agent spin-up fails after channel creation, the channel should be cleaned up rather than left in an orphaned state.

**NFR4: Existing pattern adherence**
The persona picker dialog follows the same modal pattern as existing dashboard dialogs. The kebab menu action follows the existing `agent-lifecycle.js` action registration pattern. Agent spin-up uses the existing `agent_lifecycle` service.

---

## 6. UI Overview

### Kebab Menu Addition

```
┌─────────────────────┐
│ Focus               │
│ Respond             │
│ Handoff             │
│ Create Group Channel│  ← new action
│ ─────────────────── │
│ Dismiss             │
└─────────────────────┘
```

### Persona Picker Dialog

```
┌─────────────────────────────────────────┐
│  Add Agent to Group Channel          [X]│
│  Select a persona to join the           │
│  conversation with Robbo                │
│                                         │
│  [🔍 Search personas...]               │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ ○ Con          Builder          │    │
│  │ ○ Paula        Recruiter        │    │
│  │ ○ Gavin        Tester           │    │
│  │ ● Wado         Designer    ←sel │    │
│  └─────────────────────────────────┘    │
│                                         │
│              [Cancel]  [Confirm]        │
└─────────────────────────────────────────┘
```

### Flow Sequence

```
1. Operator clicks kebab on agent card
2. Selects "Create Group Channel"
3. Persona picker dialog opens
4. Operator selects a persona, clicks Confirm
5. Loading indicator: "Creating group channel with Wado..."
6. System: creates channel, adds members, spins up agent, seeds context
7. New channel card appears on dashboard
8. Toast: "Group channel created with Robbo and Wado"
9. Operator clicks channel card → chat panel opens with seeded context
```

---

## 7. Dependencies

| Dependency | Sprint | Status | What It Provides |
|------------|--------|--------|------------------|
| Channel data model | E9-S3 | Done | Channel, ChannelMembership, Message tables |
| ChannelService | E9-S4 | Done | Channel creation, membership, context briefing |
| API endpoints | E9-S5 | Done | REST API for channels |
| Delivery engine | E9-S6 | Done | Fan-out to channel members |
| Dashboard UI | E9-S7 | Done | Channel cards, chat panel, agent card kebab menu |
| Agent lifecycle | Existing | Done | Agent creation/spin-up |

### New Backend Requirements

This sprint requires new backend work beyond pure frontend:

- `spawned_from_agent_id` column on Channel model (Alembic migration)
- API endpoint for the promote-to-group orchestration flow (e.g., `POST /api/agents/<agent_id>/promote-to-group` with `{persona_slug: "..."}`)
- Orchestration logic that chains: channel creation → membership → agent spin-up → context seeding
- Conversation history retrieval: endpoint or service method to fetch the last N turns from an agent's conversation

### Potential API Gaps

- `GET /api/personas?active=true` — persona list for the picker (verify if exists)
- Agent conversation history — need to verify how to fetch the last 20 turns for a given agent

---

## 8. Open Decisions

| Decision | Options | Status |
|----------|---------|--------|
| Channel name generation | Auto-generated from personas vs operator-provided | Auto-generated for v1. Operator can rename via channel admin (S9) if needed. |
| FR8: Reuse existing agent | If persona already has a running agent, reuse it vs always spin up new | **Resolved**: Always spin up a fresh agent. Existing agent may be mid-task on unrelated work. |
| Column naming | `spawned_from_agent_id` vs `originated_from_agent_id` | Using `spawned_from_agent_id` for v1. Consistent with "spawn-and-merge" terminology. |

---

## Document History

| Version | Date       | Author  | Changes |
|---------|------------|---------|---------|
| 1.0     | 2026-03-06 | Melanie | Initial PRD from workshop with Sam and Robbo |
| 1.1     | 2026-03-06 | Melanie | Robbo review fixes: FR10 context seeding changed to private tmux briefing from full conversation history, removed invented 3-channel limit from FR2, updated open decisions with FR8 reuse logic and column naming |
