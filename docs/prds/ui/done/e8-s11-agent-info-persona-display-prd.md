---
validation:
  status: valid
  validated_at: '2026-02-20T15:58:41+11:00'
---

## Product Requirements Document (PRD) — Agent Info Panel + Summary Persona Display

**Project:** Claude Headspace
**Scope:** Persona identity in agent info panel, project page agent summaries, and activity page agent references
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for displaying persona identity across the three remaining views where agents appear: the agent info panel (detail slider), the project page agent summaries, and the activity page agent references. When an agent has an associated persona, these views show the persona's name and role instead of the UUID-based identifier. Technical details (session UUID, claude_session_id, pane IDs, transcript path) are preserved in the agent info panel alongside the new persona section. Anonymous agents retain UUID-based identity across all views.

Sprint 10 established the card persona pattern — persona name as hero text with role suffix on dashboard cards. Sprint 11 extends that same persona identity to every other place agents appear in the application, creating a consistent identity layer. After this sprint, the operator sees "Con — developer" everywhere an agent is referenced, not just on the dashboard card.

All design decisions for this sprint were resolved in the Agent Teams Design Workshop (Decision 4.2): technical details preserved in the info panel, persona identity visible across all views where agents appear, anonymous agents keep UUID display.

---

## 1. Context & Purpose

### 1.1 Context

After Sprint 10, agent cards on the dashboard display persona name and role. However, drilling into the agent info panel, viewing agent summaries on the project page, or checking agent references on the activity page still shows UUID-based identifiers. This inconsistency undermines the persona concept — the operator recognises "Con — developer" on the card but encounters "4b6f8a" when they look at details or summaries. Sprint 11 closes this gap across all remaining views.

### 1.2 Target User

The operator (Sam) who:
- Opens the agent info panel to inspect technical details and command history — needs to see persona identity at the top of the panel
- Views the project page to understand which agents (active and ended) have worked on a project — needs to see persona names in the agent list
- Checks the activity page to review agent performance metrics — needs persona names next to activity data

### 1.3 Success Moment

The operator opens the agent info panel for Con's agent and sees "Con — developer" at the top, with status and slug, followed by the familiar technical details (UUID, session ID, pane IDs). On the project page, the agents accordion lists "Con — developer" and "Robbo — architect" alongside their metrics. On the activity page, agent rows show persona names next to turn counts and frustration scores. An anonymous agent still shows its UUID everywhere — clearly distinguishable.

---

## 2. Scope

### 2.1 In Scope

- Persona identity section in the agent info panel: name, role, status, slug
- Persona section positioned above the existing technical details section when persona is present
- No persona section rendered for anonymous agents (info panel shows technical details only, as today)
- Project page agent summaries display persona name + role for agents with personas
- Project page agent summaries display UUID fallback for anonymous agents
- Activity page agent references display persona name + role for agents with personas
- Activity page agent references display UUID fallback for anonymous agents
- Ended agents with personas retain persona identity in all views (historical visibility)

### 2.2 Out of Scope

- Dashboard card hero changes (E8-S10 — separate PRD, already validated)
- Colour coding per persona or role (Workshop Decision 4.2 — not needed at this stage)
- Avatar or icon display (Workshop Decision 4.2 — name as text is sufficient)
- Handoff trigger UI or handoff-related display (E8-S13)
- Persona registration, assignment, or injection (E8-S1 through E8-S9)
- Workshop mode visual differentiation (Workshop Decision 4.3 — deferred)
- New API endpoints — existing data paths are extended
- Service-layer changes to persona lifecycle or assignment

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Agent info panel shows persona name, role, status, and slug when the agent has an associated persona
2. Agent info panel persona section appears above the existing technical details section (UUID, session IDs, pane IDs, transcript path)
3. Agent info panel preserves all existing technical details unchanged — nothing is removed
4. Agent info panel for an agent without a persona shows no persona section (existing layout unchanged)
5. Project page agent summaries display persona name + role (e.g., "Con — developer") instead of UUID when the agent has a persona
6. Project page agent summaries display UUID-based identity for anonymous agents (unchanged)
7. Activity page agent references display persona name + role instead of UUID when the agent has a persona
8. Activity page agent references display UUID-based identity for anonymous agents (unchanged)
9. Ended agents with personas display their persona identity in all views (persona identity is not lost when an agent ends)
10. Multiple agents with the same persona each display the persona identity correctly across all views
11. The dashboard renders correctly with a mix of persona-backed and anonymous agents across all three views

---

## 4. Functional Requirements (FRs)

**FR1: Agent Info API Persona Data**
The agent info API response includes persona identity fields (name, role, status, slug) when the agent has an associated persona. When the agent has no persona, these fields are absent or null. Existing response fields are unchanged.

**FR2: Agent Info Panel — Persona Section**
When the agent has a persona, the agent info panel renders a persona identity section containing: persona name, role name, persona status, and persona slug. This section appears above the existing technical details section.

**FR3: Agent Info Panel — Technical Details Preserved**
The agent info panel continues to display all existing technical details: session UUID, claude_session_id, iterm_pane_id, tmux_pane_id, tmux_session, bridge status, and transcript_path. These fields are not removed, relocated, or hidden when a persona section is present.

**FR4: Agent Info Panel — Anonymous Fallback**
When the agent has no persona, the agent info panel renders without a persona section. The layout is identical to the current agent info panel.

**FR5: Project Page Agent Summaries — Persona Display**
Agent rows in the project page agents accordion display persona name and role (e.g., "Con — developer") as the primary agent identifier when the agent has a persona. The persona identity replaces the UUID hero in the agent row.

**FR6: Project Page Agent Summaries — UUID Fallback**
Agent rows in the project page agents accordion display the UUID-based hero (`hero_chars` + `hero_trail`) when the agent has no persona. Identical to the current display.

**FR7: Project Page Agent Summaries — Ended Agents**
Ended agents with personas display their persona name and role in the agents accordion, not just their UUID. Persona identity is preserved in historical agent listings.

**FR8: Activity Page Agent References — Persona Display**
Agent rows in the activity page's Projects & Agents section display persona name and role as the primary agent identifier when the agent has a persona. The persona identity replaces the UUID hero in the agent metric row.

**FR9: Activity Page Agent References — UUID Fallback**
Agent rows in the activity page display the UUID-based hero when the agent has no persona. Identical to the current display.

**FR10: Data Availability**
Persona identity data (name, role, status, slug) is available in the data payloads used by the agent info panel, project page agent list, and activity page agent metrics. This may require extending existing API responses or data structures to include persona fields.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: No Additional Round Trips**
Persona data for the agent info panel is included in the existing agent info API response. No separate API call is required to fetch persona details.

**NFR2: Backward Compatibility**
All existing views for anonymous agents (no persona) render identically to their current appearance. No visual changes occur for agents without personas across any of the three views.

---

## 6. UI Overview

**Agent Info Panel (with persona):**

```
┌─────────────────────────────────────────┐
│ Con   Agent Info                    [×] │  ← Hero: persona name
├─────────────────────────────────────────┤
│                                         │
│ PERSONA                                 │
│ Name         Con                        │
│ Role         developer                  │
│ Status       active                     │
│ Slug         developer-con-1            │
│                                         │
│ IDENTITY                                │
│ Agent ID     42                         │
│ Session UUID 4b6f8a2c-...              │
│ Claude ID    ses_abc123                  │
│ tmux Pane    %42                        │
│ tmux Session dev-con                    │
│ Bridge       Connected                  │
│ iTerm Pane   /dev/ttys005              │
│ Transcript   ~/.claude/projects/...     │
│                                         │
│ PROJECT                                 │
│ ...                                     │
│                                         │
│ LIFECYCLE                               │
│ ...                                     │
└─────────────────────────────────────────┘
```

**Agent Info Panel (without persona — unchanged):**

```
┌─────────────────────────────────────────┐
│ 4b b2c3d4   Agent Info             [×] │  ← Hero: UUID
├─────────────────────────────────────────┤
│                                         │
│ IDENTITY                                │
│ Agent ID     42                         │
│ Session UUID 4b6f8a2c-...              │
│ ...                                     │
└─────────────────────────────────────────┘
```

**Project Page Agent Row (with persona):**

```
▶ [PROCESSING] Con — developer    12 turns · 8.2s avg · 🟢 1.2    💬   Last seen 2m ago
```

**Project Page Agent Row (without persona — unchanged):**

```
▶ [PROCESSING] 4b b2c3d4         12 turns · 8.2s avg · 🟢 1.2    💬   Last seen 2m ago
```

**Activity Page Agent Row (with persona):**

```
Con — developer    45 turns · 6.1s avg · Peak 3.2    💬
```

**Activity Page Agent Row (without persona — unchanged):**

```
4b b2c3d4          45 turns · 6.1s avg · Peak 3.2    💬
```

---

## Design Reference

All technical decisions for this sprint are resolved:

- **Workshop Decision 4.2** (`docs/workshop/agent-teams-workshop.md`): Technical details preserved in info panel, persona identity visible across all views where agents appear, anonymous agents keep UUID
- **Epic 8 Roadmap Sprint 11** (`docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md`): Deliverables, dependencies, acceptance criteria
- **Dependency:** E8-S10 (card persona display — establishes the pattern for persona name + role rendering)

---

## Document History

| Version | Date       | Author | Changes                           |
| ------- | ---------- | ------ | --------------------------------- |
| 1.0     | 2026-02-20 | Sam    | Initial PRD from workshop         |
