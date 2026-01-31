---
validation:
  status: valid
  validated_at: '2026-01-30T13:12:21+11:00'
---

## Product Requirements Document (PRD) — Turn & Task Summarisation

**Project:** Claude Headspace v3.1
**Scope:** Epic 3, Sprint 2 — Real-time turn summarisation and task completion summaries for dashboard display
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace's dashboard currently displays raw turn text and task state for each agent. With multiple agents running across projects, users must read full conversation content to understand what each agent is doing. This PRD defines turn and task summarisation services that generate concise AI summaries in real-time, transforming the dashboard from a status monitor into an intelligence hub where users can grasp agent activity at a glance.

Turn summarisation triggers automatically when a new turn arrives, producing a 1-2 sentence summary displayed inline on the agent card. Task summarisation triggers on task completion, producing a 2-3 sentence outcome summary. Both services use the inference infrastructure established in E3-S1, process asynchronously to avoid blocking dashboard updates, and cache results by content identity to eliminate redundant API calls.

Success is measured by: summaries appearing on agent cards within 2 seconds of turn arrival, cached results returned instantly for identical content, SSE updates uninterrupted during inference, and graceful degradation when the inference service is unavailable.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace tracks Claude Code sessions across multiple projects via a Kanban-style dashboard. Epic 1 established the event-driven architecture with Task/Turn state machine, SSE real-time updates, and agent card UI. Epic 3 adds an intelligence layer, with Sprint 1 (E3-S1) providing the foundational inference service (OpenRouter API client, InferenceCall logging, rate limiting, caching).

This sprint is the first consumer of that inference infrastructure. It adds domain-specific summarisation services that generate concise AI summaries at two levels:

- **Turn level:** Summarise each agent exchange as it happens for live dashboard display
- **Task level:** Summarise completed task outcomes for history and context

The system already has:
- Flask application with blueprints and service injection (`app.extensions`)
- PostgreSQL database with SQLAlchemy models and Alembic migrations (current head: `5c4d4f13bcfb`)
- Turn model with `actor`, `intent`, `text` fields
- Task model with 5-state lifecycle and `started_at`/`completed_at` timestamps
- TaskLifecycleManager service managing turn processing and state transitions
- Broadcaster service for SSE real-time dashboard updates
- Agent card template (`_agent_card.html`) with existing layout for summary display
- E3-S1 inference service with model selection, caching by input hash, and InferenceCall logging

**Prerequisite:** E3-S1 (OpenRouter Integration & Inference Service) must be complete before this sprint begins.

### 1.2 Target User

The primary user is the Claude Headspace dashboard operator — a developer managing multiple concurrent Claude Code agents across projects. They need to quickly scan agent activity without reading raw conversation text.

### 1.3 Success Moment

A developer glances at the dashboard and sees concise summaries on each agent card: "Refactoring the authentication middleware to use JWT tokens" instead of a wall of raw text. When a task completes, they see "Implemented JWT authentication with refresh tokens. Added middleware, tests, and migration. All 12 tests passing." — immediately understanding what was accomplished without opening the terminal.

---

## 2. Scope

### 2.1 In Scope

- Turn summarisation service that generates 1-2 sentence summaries for each turn as it arrives
- Task summarisation service that generates 2-3 sentence outcome summaries on task completion
- Content-based summary caching that avoids re-summarising identical content
- Dashboard integration: turn summaries displayed inline on agent cards
- Dashboard integration: task summaries displayed on task completion
- Placeholder UX ("Summarising...") while inference is in-flight
- Asynchronous processing that does not block SSE updates or dashboard responsiveness
- Summary and summary timestamp fields added to Turn and Task database models
- Database migration for new summary fields
- API endpoint: POST `/api/summarise/turn/<id>` for manual or programmatic turn summarisation
- API endpoint: POST `/api/summarise/task/<id>` for manual or programmatic task summarisation
- Prompt templates for turn and task summarisation (as design guidance)
- Integration with TaskLifecycleManager for automatic summarisation triggers
- SSE events for pushing summary updates to the dashboard
- Graceful degradation when inference service is unavailable

### 2.2 Out of Scope

- OpenRouter API client and inference service infrastructure (E3-S1, prerequisite)
- Priority scoring (E3-S3)
- Progress summary generation from git history (E3-S4)
- Brain reboot generation (E3-S5)
- Summary feedback or rating mechanisms (deferred to future)
- Batch or bulk re-summarisation of historical turns/tasks
- User editing of generated summaries
- Project-level or objective-level summarisation
- Summary re-generation when turn content is amended

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A new turn arrives and a summary is generated and displayed on the agent card within 2 seconds
2. A task completes and a summary is generated and displayed on the agent card and in task history
3. Identical turn content returns a cached summary without making a duplicate inference call
4. Manual summarisation via POST `/api/summarise/turn/<id>` returns the correct summary for the specified turn
5. Manual summarisation via POST `/api/summarise/task/<id>` returns the correct summary for the specified task
6. Summary fields are persisted to the database and survive page reloads
7. All summarisation inference calls are logged via the E3-S1 InferenceCall system with correct level, purpose, and entity associations

### 3.2 Non-Functional Success Criteria

1. SSE updates continue uninterrupted while summarisation inference is in-flight
2. Dashboard remains responsive during summarisation processing
3. When the inference service is unavailable, the dashboard displays raw turn/task text without errors
4. Turn summarisation uses a fast, cost-efficient model appropriate for high-volume real-time use
5. A "Summarising..." placeholder is visible while inference is pending, replaced by the summary on completion

---

## 4. Functional Requirements (FRs)

### Turn Summarisation

**FR1:** The system shall automatically trigger turn summarisation when a new turn is recorded by the TaskLifecycleManager.

**FR2:** The turn summarisation service shall generate a 1-2 sentence summary focusing on what action was taken or requested in the turn.

**FR3:** The turn summarisation service shall include the turn's text content, actor, and intent as context for the summarisation prompt.

**FR4:** The generated turn summary shall be stored in the Turn model's summary field and the generation timestamp recorded.

**FR5:** After a turn summary is generated, the system shall push an SSE event to update the agent card on the dashboard without requiring a page reload.

### Task Summarisation

**FR6:** The system shall automatically trigger task summarisation when a task transitions to the complete state.

**FR7:** The task summarisation service shall generate a 2-3 sentence summary of the completed task's outcome.

**FR8:** The task summarisation service shall include as context: the task's start and completion timestamps, the number of turns in the task, and the final turn's text content.

**FR9:** The generated task summary shall be stored in the Task model's summary field and the generation timestamp recorded.

**FR10:** After a task summary is generated, the system shall push an SSE event to update the agent card and task history on the dashboard.

### Caching

**FR11:** Before making an inference call, the summarisation services shall check for an existing cached result matching the same input content identity (using the inference service's content-based caching from E3-S1).

**FR12:** When a cache hit occurs, the cached summary shall be used directly without making a new inference call, and the summary field shall be populated from the cached result.

**FR13:** Cached summaries shall be permanent for the same content — identical input always produces the same cached summary with no expiry.

### Async Processing

**FR14:** Turn and task summarisation shall execute asynchronously, without blocking the turn processing pipeline or SSE event delivery.

**FR15:** While summarisation is in-flight, the dashboard shall display a "Summarising..." placeholder on the relevant agent card.

**FR16:** When the asynchronous summarisation completes, the placeholder shall be replaced by the generated summary via an SSE update.

### API Endpoints

**FR17:** POST `/api/summarise/turn/<id>` shall trigger summarisation for the specified turn and return the generated summary. If the turn already has a summary, the existing summary shall be returned without re-generating.

**FR18:** POST `/api/summarise/task/<id>` shall trigger summarisation for the specified task and return the generated summary. If the task already has a summary, the existing summary shall be returned without re-generating.

**FR19:** Both API endpoints shall return appropriate error responses when the specified turn or task does not exist (404) or when the inference service is unavailable (503).

### Error Handling & Graceful Degradation

**FR20:** When a summarisation inference call fails, the summary field shall remain null, the error shall be logged, and no automatic retry shall be attempted.

**FR21:** When the inference service is unavailable, the dashboard shall display the original raw turn text or task state instead of a summary, without showing error messages to the user.

**FR22:** Failed summarisation calls shall be logged via the E3-S1 InferenceCall system with the error message recorded.

### Integration

**FR23:** All summarisation inference calls shall be made through the E3-S1 inference service, using the appropriate inference level ("turn" for turn summaries, "task" for task summaries) and purpose identifiers.

**FR24:** Summarisation calls shall include the correct entity associations (turn ID, task ID, agent ID, project ID) so that InferenceCall records are linked to the relevant domain objects.

### Data Model

**FR25:** The Turn model shall be extended with: a nullable text field for the summary, and a nullable timestamp field for when the summary was generated.

**FR26:** The Task model shall be extended with: a nullable text field for the summary, and a nullable timestamp field for when the summary was generated.

**FR27:** A database migration shall add the summary fields to the existing Turn and Task tables, chaining from the current migration head.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Summarisation processing shall not block the Flask request thread, SSE event delivery, or the TaskLifecycleManager turn processing pipeline.

**NFR2:** Turn summaries shall be generated and available on the dashboard within 2 seconds of turn arrival under normal inference service conditions.

**NFR3:** The summarisation services shall be thread-safe, supporting concurrent summarisation requests from multiple agents without race conditions.

**NFR4:** The system shall start and remain operational when the inference service is unavailable, with summarisation features degraded (no summaries generated) but all other dashboard functionality unaffected.

**NFR5:** The summary fields in the database shall be indexed appropriately for efficient querying by the dashboard.

**NFR6:** SSE summary update events shall use the existing Broadcaster infrastructure without requiring changes to the SSE transport layer.

---

## 6. UI Overview

### Agent Card — Turn Summary Display

The agent card on the dashboard shall display the most recent turn's summary inline, replacing the current raw text display:

- **Summary present:** Display the 1-2 sentence summary text in the turn area of the card
- **Summary pending:** Display a "Summarising..." indicator (subtle, non-intrusive) while inference is in-flight
- **Summary unavailable:** Display the original raw turn text as fallback (no error shown to user)

### Agent Card — Task Summary Display

When a task completes, the agent card shall display the task summary:

- **Summary present:** Display the 2-3 sentence task outcome summary
- **Summary pending:** Display a "Summarising..." indicator
- **Summary unavailable:** Display the task state (complete) without a summary

### SSE Update Flow

Summary updates flow through the existing SSE system:

1. Turn arrives → agent card updates with turn state (immediate)
2. Summarisation dispatched asynchronously
3. Summary generated → SSE event pushes summary text to agent card (within 2 seconds)
4. Agent card updates in-place without page reload

---

## 7. Prompt Design Guidance

The following prompt templates represent the recommended summarisation approach. They express the **intent** of what should be summarised and the context to include. Exact wording may be refined during implementation.

### Turn Summary Prompt

```
Summarise this turn in 1-2 concise sentences focusing on what action was taken or requested:

Turn: {turn.text}
Actor: {turn.actor}
Intent: {turn.intent}
```

### Task Summary Prompt

```
Summarise the outcome of this completed task in 2-3 sentences:

Task started: {task.started_at}
Task completed: {task.completed_at}
Turns: {turn_count}
Final outcome: {final_turn.text}
```

### Prompt Design Principles

- Summaries should be concise and actionable — a user scanning the dashboard should immediately understand what happened
- Turn summaries focus on the **action** (what was done or requested)
- Task summaries focus on the **outcome** (what was accomplished)
- Summaries should use plain language, avoiding code jargon unless the turn content is technical
- The model used should be fast and cost-efficient, appropriate for high-volume real-time use
