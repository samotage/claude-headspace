---
validation:
  status: invalid
  invalidated_reason: 'PRD amended post-evaluation — criterion 7 and FR6 reworded for build isolation (POST to endpoint, not trigger execution). Requires revalidation.'
---

## Product Requirements Document (PRD) — Handoff Trigger UI

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 13 (E8-S13) — Context threshold monitoring on agent cards and operator-initiated handoff button
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

When an agent's context window fills up, the operator needs a clear visual signal and a deliberate mechanism to trigger a handoff to a fresh successor agent. This PRD defines the handoff trigger UI: context threshold monitoring that flags persona agents as "handoff eligible" and a handoff button that appears on their cards when usage exceeds a configurable threshold.

The trigger is operator-initiated by design (Workshop Decision 5.1). No automatic handoff in v1 — the manual trigger allows compaction to work naturally and doubles as a debugging/tuning mechanism for the handoff prompt. The operator judges whether a clean handoff is needed or whether compaction is handling context pressure adequately. The manual trigger also enables iterative refinement: wind down the threshold to 10%, fire the handoff, inspect the output, tune the prompt — human-in-the-loop iteration on handoff quality before any automation.

This sprint sits between the Handoff data model (E8-S12) and handoff execution (E8-S14) in the build sequence. It leverages the existing context monitoring infrastructure (E6-S4) which already tracks `context_percent_used` on each agent and includes context data in card state JSON. The handoff trigger adds a decision layer: combining persona identity (does this agent have a persona?) with context pressure (has the threshold been exceeded?) to surface an actionable handoff control.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace already monitors `context_percent_used` on each agent via the context poller (E6-S4). The `card_state` service includes context usage in dashboard card JSON with `warning_threshold` (default 65%) and `high_threshold` (default 75%) values from the `context_monitor` config section. The context bar on agent cards reflects these tiers visually.

Epic 8 introduces personas — named identities with skills and experience that persist across agent sessions. When a persona agent's context fills up, the handoff system (E8-S14) orchestrates a seamless transition to a successor agent carrying the same persona. This sprint provides the trigger mechanism — the operator-facing bridge between context pressure detection and the handoff execution engine.

**Dependencies:**
- E8-S12 (Handoff database model — must exist before handoff can be triggered)
- E8-S10 (Card persona identity — handoff button appears only on persona cards)
- E6-S4 (Context monitoring — `context_percent_used` field on Agent model)

### 1.2 Target User

The operator (Sam) — monitors multiple agent sessions via the dashboard and decides when to initiate handoffs based on context pressure and agent effectiveness.

### 1.3 Success Moment

The operator sees an agent's context bar change as usage approaches the handoff threshold. A "Handoff" button appears on the card. The operator clicks it to initiate the handoff flow. For testing, they wind the threshold down to 10% and fire the handoff within minutes of starting an agent, inspecting the output to tune the handoff prompt.

---

## 2. Scope

### 2.1 In Scope

- Configurable handoff threshold in application configuration (default 80%, configurable down to 10% for testing)
- Handoff eligibility computation during card state building (persona + context threshold exceeded)
- Handoff eligibility fields in card state JSON
- "Handoff" button on agent cards — conditionally visible when handoff-eligible
- Context bar visual indicator when handoff threshold is exceeded (distinct from existing warning and high thresholds)
- Handoff button click sends POST request to `/api/agents/<id>/handoff` (endpoint defined by E8-S14)
- Button loading state during handoff request
- SSE-driven updates for handoff eligibility as context usage changes

### 2.2 Out of Scope

- Automatic handoff triggering (deferred — post v1 tuning, per Workshop Decision 5.1)
- Handoff execution logic (E8-S14)
- Handoff database record creation (E8-S14)
- Successor agent creation (E8-S14)
- Handoff history or audit trail UI
- Anonymous agent handoff (anonymous agents do not handoff)
- Persona registration, assignment, or injection (E8-S1 through E8-S9)
- Changes to existing context monitoring behaviour (warning/high thresholds unchanged)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Handoff button appears on persona agent cards when `context_percent_used` meets or exceeds the configured handoff threshold
2. Handoff button does NOT appear on anonymous agent cards regardless of context usage
3. Handoff button does NOT appear when context usage is below the threshold
4. Handoff button does NOT appear when context usage data is unavailable
5. Handoff threshold is configurable and can be set as low as 10% for testing and debugging
6. Context bar visual indicator changes when handoff threshold is exceeded, visually distinct from the existing warning (65%) and high (75%) threshold indicators
7. Button click sends a POST request to `/api/agents/<id>/handoff` with the handoff reason
8. Button provides visual feedback during the handoff request (loading state)
9. Button visibility and context bar indicator update via SSE as context usage changes, without requiring a page reload

### 3.2 Non-Functional Success Criteria

1. No additional API calls or latency introduced for agents without personas — eligibility is a lightweight boolean computation during existing card state building
2. No additional database queries beyond the existing eager-loaded agent relationships
3. SSE payload size increase is negligible (two additional fields: boolean + integer)

---

## 4. Functional Requirements (FRs)

**FR1: Handoff Threshold Configuration**
The application configuration includes a handoff threshold setting — a percentage of context used that determines when an agent becomes eligible for handoff. Default value: 80%. The threshold can be configured to values as low as 10% for testing and debugging purposes.

**FR2: Handoff Eligibility Computation**
During card state building, each agent's handoff eligibility is computed. An agent is handoff-eligible when ALL of the following conditions are true:
- Agent has a persona
- Agent has context usage data available
- Agent's context usage percentage meets or exceeds the configured handoff threshold

**FR3: Card State Handoff Fields**
The card state JSON includes handoff eligibility data: whether the agent is handoff-eligible and the configured handoff threshold percentage. These fields are included in both the initial page render data and SSE `card_refresh` event payloads.

**FR4: Handoff Button Display**
The agent card displays a "Handoff" button when the agent is handoff-eligible. The button is not rendered when the agent is not handoff-eligible (no persona, below threshold, or no context data). The button is visually distinct and positioned so the operator can identify it quickly.

**FR5: Context Bar Handoff Indicator**
When an agent's context usage exceeds the handoff threshold, the context bar on the agent card displays a distinct visual indicator that communicates "handoff recommended." This indicator represents a third tier above the existing warning and high indicators — the visual progression is: normal → warning (65%) → high (75%) → handoff-eligible (configured threshold).

**FR6: Handoff Button Action**
When the operator clicks the handoff button, the action sends a POST request to `/api/agents/<id>/handoff` with the agent ID and handoff reason. The actual endpoint handler is defined by E8-S14 — this sprint is responsible for the client-side request, not the server-side handler. The button provides visual feedback during the request (loading/disabled state) to prevent double-clicks and communicate progress.

**FR7: SSE-Driven State Updates**
Handoff eligibility and context bar indicator state update in real-time via SSE. When context usage crosses the threshold (in either direction), the card updates button visibility and context bar indicator without requiring a page reload.

**FR8: Anonymous Agent Exclusion**
Anonymous agents (those without a persona) never display the handoff button or handoff-related context bar indicators, regardless of their context usage level. Existing context monitoring visuals (warning/high tiers) remain unchanged for all agents.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Backward Compatibility**
Anonymous agents display exactly as they do today. No handoff-related UI elements appear on anonymous agent cards. No changes to existing context monitoring behaviour, warning thresholds, or high thresholds.

**NFR2: Testing Support**
The threshold can be configured to a low value (e.g., 10%) so that handoff eligibility can be triggered easily during development and testing without waiting for an agent to use 80% of its context.

**NFR3: Lightweight Computation**
Handoff eligibility is a simple boolean comparison (persona exists + percentage >= threshold). No LLM calls, no additional database queries, no external service calls.

---

## 6. UI Overview

**Context Bar — Three-Tier Progression:**
```
0%────────65%──────75%──────80%──────100%
   normal    warning   high   handoff
                              ▲
                              └─ Handoff button appears here
```
- Below 65%: context bar displays normally (existing behaviour)
- 65-74%: warning indicator (existing behaviour, unchanged)
- 75-79%: high indicator (existing behaviour, unchanged)
- 80%+ (configurable): handoff indicator — visually distinct from warning/high (e.g., colour change, pulsing, or label). Handoff button appears.

**Agent Card — With Handoff Button (persona + threshold exceeded):**
```
┌─────────────────────────────────────────┐
│ Con — developer          <1m ago  up 2h │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← Context bar: handoff indicator
│ Fix authentication bug in login flow    │
│ Investigating root cause of token...    │
│                              [Handoff]  │  ← Button: visible, actionable
└─────────────────────────────────────────┘
```

**Agent Card — Persona, Below Threshold (no button):**
```
┌─────────────────────────────────────────┐
│ Con — developer          <1m ago  up 2h │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░ │  ← Context bar: normal/warning
│ Fix authentication bug in login flow    │
│ Investigating root cause of token...    │
│                                         │  ← No button
└─────────────────────────────────────────┘
```

**Anonymous Agent Card (no button regardless of context):**
```
┌─────────────────────────────────────────┐
│ 4b b2c3d4                <1m ago  up 2h │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← Context bar: existing behaviour only
│ Run the test suite                      │
│ All 42 tests passing                    │
│                                         │  ← No button ever
└─────────────────────────────────────────┘
```

**Button States:**
- **Hidden:** Agent has no persona, or context below threshold, or no context data
- **Visible:** Agent has persona AND context >= threshold — "Handoff" button displayed
- **Loading:** Button clicked, handoff request in progress — disabled with loading indicator
- **Hidden again:** After handoff completes (agent ends, successor takes over)

---

## Design Reference

All technical decisions for this sprint are resolved:

- **Workshop Decision 5.1** (`docs/workshop/agent-teams-workshop.md`): Operator-initiated handoff only, no auto-trigger in v1, manual trigger allows compaction to work naturally, manual trigger doubles as debugging mechanism
- **Epic 8 Roadmap Sprint 13** (`docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md`): Deliverables, dependencies, acceptance criteria
- **Dependencies:** E8-S12 (Handoff model), E8-S10 (card persona identity), E6-S4 (context monitoring)
- **Existing infrastructure:** `context_monitor` config section (warning_threshold, high_threshold), `card_state.build_card_state()` context block, context poller background service

---

## Document History

| Version | Date       | Author | Changes                           |
| ------- | ---------- | ------ | --------------------------------- |
| 1.0     | 2026-02-20 | Sam    | Initial PRD from workshop         |
