---
validation:
  status: valid
  validated_at: '2026-02-20T15:52:28+11:00'
---

## Product Requirements Document (PRD) — Dashboard Card Persona Identity

**Project:** Claude Headspace
**Scope:** Agent card hero display with persona name and role suffix
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for updating the dashboard agent card to display persona identity instead of UUID-based hero text when an agent has an associated persona. When a persona is present, the card hero shows the persona's name (e.g., "Con") with their role as a suffix (e.g., "Con — developer"), replacing the current cryptic UUID display. Anonymous agents (those without a persona) retain the existing UUID-based hero display unchanged.

This is the first user-facing result of the persona identity system (Epic 8, Sprints 1-9). The data foundation, registration, assignment, and injection pipeline are all prerequisites — this sprint makes persona identity visible on the dashboard. The card hero transforms from meaningless identifiers ("4b6f8a") to recognisable team members ("Con — developer"), making the dashboard immediately legible.

All design decisions for this sprint were resolved in the Agent Teams Design Workshop (Decision 4.2): persona name as hero text, role as suffix, no colour coding, no avatars, full backward compatibility for anonymous agents.

---

## 1. Context & Purpose

### 1.1 Context

The dashboard agent card currently displays a truncated session UUID as the hero identifier — the first 2 characters rendered prominently (`hero_chars`) with the remaining 6 characters as a trail (`hero_trail`). This is functionally meaningless to the operator. With the persona system established in E8-S1 through E8-S8, agents can now have named persona identities. The card should reflect this identity when available.

### 1.2 Target User

The operator (Sam) monitoring agent sessions on the Claude Headspace dashboard. The operator needs to immediately identify which persona is driving each agent — "that's Con working on the backend" vs "that's Robbo reviewing architecture" — without clicking into detail panels.

### 1.3 Success Moment

The operator opens the dashboard and sees "Con — developer" and "Robbo — architect" on their respective agent cards, instantly recognising which team members are active. An anonymous agent card still shows its UUID hero, clearly distinguishable from persona-backed agents.

---

## 2. Scope

### 2.1 In Scope

- Agent card hero displays persona name when agent has an associated persona
- Role displayed as a suffix after the persona name (e.g., "Con — developer")
- UUID-based hero display preserved for agents without a persona (full backward compatibility)
- Card state computation includes persona identity data when available
- SSE `card_refresh` events carry persona identity fields
- Dashboard JavaScript renders persona name and role from SSE data
- Kanban command cards display persona identity when available
- Condensed completed-command cards (JS-built) display persona identity when available

### 2.2 Out of Scope

- Colour coding per persona or role (Workshop Decision 4.2 — not needed at this stage)
- Avatar or icon display (Workshop Decision 4.2 — name as text is sufficient)
- Agent info panel persona details (E8-S11)
- Project page and activity page persona display (E8-S11)
- Persona registration, assignment, or injection (E8-S1 through E8-S9)
- Workshop mode visual differentiation (Workshop Decision 4.3 — deferred)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. An agent card whose agent has an associated persona displays the persona's name as the hero text and the persona's role as a suffix (e.g., "Con — developer")
2. An agent card whose agent has no persona displays the UUID-based hero (`hero_chars` + `hero_trail`) exactly as it does today
3. SSE `card_refresh` events include persona name and role fields when the agent has a persona
4. Real-time SSE updates correctly render persona identity on cards without requiring a page reload
5. Multiple agents with the same persona each display the persona's name and role correctly
6. The dashboard renders correctly with a mix of persona-backed and anonymous agents simultaneously
7. Kanban command cards and condensed completed-command cards display persona identity when available
8. Card layout handles persona name and role suffix without visual overflow or breaking the card structure

### 3.2 Non-Functional Success Criteria

1. No additional database queries beyond the existing eager-loaded agent relationships — persona data accessed via the agent's existing persona relationship
2. SSE payload size increase is negligible (two additional short string fields)

---

## 4. Functional Requirements (FRs)

**FR1: Card State Persona Data**
When building card state for an agent with an associated persona, include the persona's name and the persona's role name in the card state data. When the agent has no persona, these fields are absent or null.

**FR2: SSE Payload Extension**
The `card_refresh` SSE event payload includes persona name and persona role fields when the agent has an associated persona. When the agent has no persona, these fields are absent or null. Existing payload fields are unchanged.

**FR3: Card Hero — Persona Display**
When the agent has a persona, the card hero section displays the persona name as the primary text and the role as a suffix, separated by an em dash (e.g., "Con — developer"). The hero section remains clickable for tmux attach / iTerm focus functionality.

**FR4: Card Hero — UUID Fallback**
When the agent has no persona, the card hero section displays the existing UUID-based hero (`hero_chars` as prominent text, `hero_trail` as trailing text). No change from current behaviour.

**FR5: Real-Time SSE Update**
When a `card_refresh` SSE event arrives with persona identity data, the card hero section updates to display the persona name and role. When the SSE event has no persona data, the card hero displays the UUID. Updates happen in-place without page reload.

**FR6: Kanban Command Card Persona Display**
Kanban command cards (used in the Kanban view) display persona name and role when the agent has a persona, and UUID hero when the agent has no persona.

**FR7: Condensed Completed-Command Card Persona Display**
Condensed completed-command cards (built dynamically in JavaScript when a command transitions to COMPLETE) display persona name and role when persona data is available in the SSE event, and UUID hero when no persona data is present.

**FR8: Multiple Persona Agents**
When multiple active agents share the same persona, each agent's card independently displays the correct persona name and role.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: No Additional Database Queries**
Persona data for card state computation is accessed via the agent's existing relationship chain (agent → persona → role). No separate database queries are introduced for card rendering.

**NFR2: Backward Compatibility**
All existing agent cards (anonymous, no persona) render identically to their current appearance. No visual changes occur for agents without personas.

---

## 6. UI Overview

**Card Hero Section (with persona):**

```
┌─────────────────────────────────────────┐
│ Con — developer          <1m ago  up 2h │  ← Hero: persona name + role suffix
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← State bar (unchanged)
│ Fix authentication bug in login flow    │  ← Instruction (unchanged)
│ Investigating root cause of token...    │  ← Summary (unchanged)
└─────────────────────────────────────────┘
```

**Card Hero Section (without persona — unchanged):**

```
┌─────────────────────────────────────────┐
│ 4b b2c3d4                <1m ago  up 2h │  ← Hero: UUID hero_chars + hero_trail
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← State bar (unchanged)
│ Run the test suite                      │  ← Instruction (unchanged)
│ All 42 tests passing                    │  ← Summary (unchanged)
└─────────────────────────────────────────┘
```

**Key visual details:**
- Persona name uses the same CSS treatment as `hero_chars` (prominent, readable)
- Role suffix is secondary/dimmer text, separated by an em dash
- Click-to-focus/attach behaviour unchanged (entire hero section remains clickable)
- Last-seen and uptime display unchanged (positioned after hero text)

---

## Design Reference

All technical decisions for this sprint are resolved:

- **Workshop Decision 4.2** (`docs/workshop/agent-teams-workshop.md`): Persona name as hero, role as suffix, no colour coding, no avatars, anonymous agents keep UUID
- **Epic 8 Roadmap Sprint 10** (`docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md`): Deliverables, dependencies, acceptance criteria
- **Dependency:** E8-S8 (agents have `persona_id` set via SessionCorrelator)

---

## Document History

| Version | Date       | Author | Changes                           |
| ------- | ---------- | ------ | --------------------------------- |
| 1.0     | 2026-02-20 | Sam    | Initial PRD from workshop         |
