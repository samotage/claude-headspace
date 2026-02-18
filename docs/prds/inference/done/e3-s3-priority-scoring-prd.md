---
validation:
  status: valid
  validated_at: '2026-01-30T13:38:34+11:00'
---

## Product Requirements Document (PRD) — Cross-Project Priority Scoring Service

**Project:** Claude Headspace v3.1
**Scope:** Epic 3, Sprint 3 — AI-driven cross-project priority scoring aligned to current objective
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace tracks multiple Claude Code agents working across multiple projects simultaneously. Without intelligent prioritisation, the user must manually assess which agent needs attention — a cognitive overhead that grows with agent count. This PRD defines a priority scoring service that uses LLM inference to score all active agents 0-100 based on how well their current work aligns with the user's stated objective, along with secondary factors like agent state, task duration, project context, and recent activity.

The scoring service evaluates all agents in a single batch inference call for cross-agent comparison and efficiency. Scores are persisted on the Agent model alongside a human-readable reason explaining the ranking. The dashboard's recommended next panel and agent card priority badges are driven by these scores, replacing the current placeholder values.

When no objective is set, scoring falls back to project waypoint priorities. When neither objective nor waypoint is available, agents receive a default score. Scoring is triggered by command state changes and objective updates, with rate-limiting to prevent redundant evaluations during rapid state transitions.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions. Epic 1 established the event-driven architecture, state machine, and dashboard. Epic 3 adds an intelligence layer. Sprint 1 (E3-S1) provides the inference service infrastructure via OpenRouter. Sprint 2 (E3-S2) adds turn and command summarisation, providing command summaries that enrich the scoring context.

The system already has:
- An Objective model (singleton with `current_text`, `constraints`, and history tracking)
- An Agent model with project association, command lifecycle, and state derivation
- A dashboard with agent cards displaying a hardcoded priority value of 50
- A `sort_agents_by_priority()` function that sorts by state + timestamp (placeholder logic)
- A `get_recommended_next()` function ready to consume real priority scores
- Agent card templates wired to display `[{{ agent.priority }}]`

This sprint replaces the placeholder priority logic with LLM-driven scoring that reasons about objective alignment and cross-project context.

### 1.2 Target User

The primary user is the Claude Headspace operator — a developer managing multiple concurrent Claude Code agents across projects. They glance at the dashboard to decide which agent needs their attention next. Priority scoring makes that decision for them.

### 1.3 Success Moment

The user sets an objective ("Ship the authentication feature by Friday"). Multiple agents are active across three projects. The dashboard's recommended next panel highlights the agent whose current command most directly contributes to that objective, with a clear reason: "Working on auth middleware — directly aligned with shipping authentication." The user clicks through to that agent's iTerm2 terminal and provides input, confident they're spending attention on the highest-value work.

---

## 2. Scope

### 2.1 In Scope

- Priority scoring service that evaluates all active agents and assigns a score (0-100)
- Cross-project batch scoring — all agents evaluated in a single inference call for comparative ranking
- Multi-factor scoring considering: objective alignment, agent state, task duration, project context, and recent activity
- Scoring context fallback chain: objective (primary) → project waypoint (fallback) → default score of 50
- Human-readable priority reason stored per agent explaining the score
- Database migration adding priority fields to the Agent model
- Scoring triggers on command state change and objective change
- Rate-limited scoring to prevent redundant evaluations during rapid state changes
- Re-score all agents when the objective changes
- Dashboard integration: priority badges on agent cards displaying the score
- Recommended next panel driven by priority scores
- Priority reason accessible on agent cards
- API endpoint: POST `/api/priority/score` — trigger batch priority scoring
- API endpoint: GET `/api/priority/rankings` — get current priority rankings
- Prompt template for LLM-based priority evaluation with structured JSON response

### 2.2 Out of Scope

- Inference service infrastructure or OpenRouter client (E3-S1 prerequisite)
- Turn or command summarisation services (E3-S2)
- Git analysis or progress summaries (E3-S4)
- Brain reboot generation (E3-S5)
- User feedback on scores (thumbs up/down)
- Priority score visibility toggle in settings
- Cost budget caps for inference calls
- Score history tracking or trend analysis
- Custom user-defined scoring weights
- Chunking logic for very large agent counts (>20 agents)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. All active agents receive a priority score (0-100) when scoring is triggered
2. Each scored agent has a human-readable priority reason explaining the score
3. The recommended next panel displays the highest-priority agent
4. Priority badges on agent cards show the LLM-generated score, replacing the hardcoded placeholder
5. Changing the objective triggers re-scoring of all agents with updated alignment context
6. Command state changes trigger a rate-limited re-score of all agents
7. When no objective is set, scoring falls back to project waypoint priorities
8. When neither objective nor waypoint is available, agents receive a default score of 50 with a reason indicating no scoring context
9. Scores persist to the database and are preserved across page reloads
10. Scoring completes via a single batch inference call through the E3-S1 inference service

### 3.2 Non-Functional Success Criteria

1. Scoring triggers are rate-limited so that rapid state changes do not cause redundant inference calls
2. Scoring does not block the Flask request/response cycle or SSE event stream
3. When the inference service is unavailable, existing scores are preserved — no scores are cleared or zeroed
4. The scoring API endpoints respond with appropriate error status when scoring cannot complete
5. Batch scoring handles variable agent counts (1 to many) without failure

---

## 4. Functional Requirements (FRs)

### Priority Scoring Service

**FR1:** The system shall provide a priority scoring service that accepts a list of active agents and returns a score (0-100) and reason for each agent.

**FR2:** The scoring service shall evaluate all agents in a single batch inference call, enabling cross-agent comparison and efficient API usage.

**FR3:** The scoring service shall use the objective-level inference tier (as defined by E3-S1) for all priority scoring calls.

### Scoring Context & Fallback

**FR4:** When an objective is set, the scoring prompt shall include the objective text and constraints as the primary scoring context, with objective alignment as the dominant scoring factor.

**FR5:** When no objective is set but a project has a waypoint, the scoring prompt shall use the project's waypoint priorities (next_up, upcoming) as the scoring context.

**FR6:** When neither an objective nor a waypoint is available for a given agent's project, that agent shall receive a default score of 50 with a reason indicating no scoring context is available.

### Scoring Factors

**FR7:** The scoring evaluation shall consider the following factors: objective or waypoint alignment, agent state, task duration, project context, and recent activity. Objective/waypoint alignment shall be the most heavily weighted factor.

**FR8:** The scoring prompt shall provide the LLM with each agent's project name, current state, current command summary (if available from E3-S2), task duration, and project waypoint next-up items.

### Score Storage

**FR9:** The Agent model shall be extended with fields for: priority score (integer 0-100), priority reason (text), and priority score timestamp.

**FR10:** A database migration shall add the priority fields to the Agent model.

**FR11:** Priority scores and reasons shall be persisted to the database when scoring completes.

### Scoring Triggers

**FR12:** A command state change on any agent shall trigger a rate-limited re-score of all active agents.

**FR13:** An objective change shall trigger an immediate re-score of all active agents.

**FR14:** Scoring triggers shall be rate-limited so that multiple rapid state changes are consolidated into a single scoring evaluation rather than triggering redundant calls.

### API Endpoints

**FR15:** POST `/api/priority/score` shall trigger a batch priority scoring of all active agents and return the results (scores and reasons per agent).

**FR16:** GET `/api/priority/rankings` shall return the current priority rankings — all agents ordered by score descending, with their score, reason, and score timestamp.

**FR17:** Both endpoints shall return appropriate error responses when scoring cannot complete (e.g., inference service unavailable, no active agents).

### Dashboard Integration

**FR18:** Agent cards shall display the priority score as a badge, replacing the current hardcoded placeholder value.

**FR19:** The recommended next panel shall display the agent with the highest priority score.

**FR20:** The priority reason shall be accessible on agent cards (e.g., via tooltip, expandable detail, or inline text).

**FR21:** When scores are updated, the dashboard shall reflect the new values via the existing SSE real-time update mechanism.

### Prompt Template

**FR22:** The scoring service shall use a prompt template that provides the LLM with the scoring context (objective or waypoint), the list of agents with their metadata, and instructions to return a JSON array of scored agents.

**FR23:** The prompt template shall instruct the LLM to return structured JSON: an array of objects each containing agent identifier, score (0-100), and reason (text).

### Edge Cases

**FR24:** When zero active agents exist, scoring shall be a no-op and the rankings endpoint shall return an empty list.

**FR25:** When one active agent exists, scoring shall still run and provide a score and reason for that agent.

**FR26:** When the inference service returns an error or is unavailable, existing persisted scores shall be preserved unchanged.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Scoring shall not block the Flask request/response cycle or SSE event delivery. The POST scoring endpoint may process synchronously, but event-triggered scoring (from state changes) shall not block event processing.

**NFR2:** The rate-limiting mechanism for scoring triggers shall be safe for concurrent access from multiple event sources.

**NFR3:** The prompt template shall handle variable agent counts without exceeding reasonable token limits for the objective-level model.

**NFR4:** The JSON response parsing from the LLM shall handle malformed responses gracefully — logging the error and preserving existing scores rather than crashing.

**NFR5:** Priority score database writes shall use the existing SQLAlchemy session management patterns established in Epic 1.

---

## 6. UI Overview

Priority scoring integrates into two existing dashboard areas:

**Agent Cards:** Each agent card currently displays `[{{ agent.priority }}]` with a hardcoded value. This PRD replaces that with the real LLM-generated score (0-100). The priority reason is accessible via the card (tooltip, expandable section, or similar pattern consistent with existing card layout).

**Recommended Next Panel:** The dashboard already has a recommended next section driven by `get_recommended_next()`. This PRD upgrades it to use the highest priority score rather than state-based sorting. The panel shows the top-priority agent's project, state, score, and reason — giving the user immediate guidance on where to focus attention.

No new pages, modals, or navigation elements are required. All changes are upgrades to existing dashboard components.

---

## 7. Technical Context for Builder

This section provides implementation guidance and is not part of the requirements. The builder may adapt these recommendations.

### Scoring Weight Guidance

The roadmap recommends the following weight distribution for the scoring prompt:

| Factor              | Weight | Description                                      |
| ------------------- | ------ | ------------------------------------------------ |
| Objective alignment | 40%    | How well does agent's work align with objective? |
| Agent state         | 25%    | awaiting_input > processing > idle               |
| Task duration       | 15%    | Longer tasks may need attention                  |
| Project context     | 10%    | Project waypoint priorities                      |
| Recent activity     | 10%    | Recently active vs stale                         |

### State-Based Modifier Guidance

The roadmap suggests state-based modifiers as a scoring signal:
- `awaiting_input` — highest urgency (agent is blocked, needs user)
- `processing` — moderate urgency (agent is working)
- `idle` — lowest urgency (agent is idle)

### Debounce Guidance

A 5-second debounce delay is recommended for state-change-triggered scoring to consolidate rapid transitions.

### Prompt Template Reference

The roadmap provides this prompt structure:

```
You are prioritising agents working across multiple projects.

Current Objective: {objective.text}
Constraints: {objective.constraints}

Agents to score:
{for agent in agents}
- Agent: {agent.session_uuid}
  Project: {agent.project.name}
  State: {agent.state}
  Current Command: {agent.current_command.summary or "None"}
  Task Duration: {task_duration}
  Waypoint Next Up: {agent.project.waypoint.next_up}
{endfor}

Score each agent 0-100 based on priority for user attention.
Return JSON: [{"agent_id": "...", "score": N, "reason": "..."}]
```

When falling back to waypoint-only scoring (no objective), adapt the prompt to use project waypoint as the primary alignment context.

### Integration Points

- Uses E3-S1 inference service for LLM calls (objective-level tier)
- Uses E3-S2 command summaries for context in scoring prompt (if available; degrade gracefully if summaries not yet generated)
- Integrates with Epic 1 Objective model (`current_text`, `constraints`) and Agent model
- Updates dashboard recommended next panel via existing SSE mechanism
- Updates agent card priority badges via existing template variable

### Data Model Additions

The Agent model requires three new fields:
- `priority_score` (integer, nullable) — 0-100
- `priority_reason` (text, nullable) — LLM-generated explanation
- `priority_updated_at` (datetime, nullable) — when the score was last updated
