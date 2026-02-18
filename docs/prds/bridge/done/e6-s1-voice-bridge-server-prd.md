---
validation:
  status: valid
  validated_at: '2026-02-09T19:32:12+11:00'
---

## Product Requirements Document (PRD) — Voice Bridge Server

**Project:** Claude Headspace
**Scope:** Server-side API, data model, and formatting layer for voice-driven interaction with Claude Code agents
**Author:** Sam (PRD Workshop)
**Status:** Draft

---

## Executive Summary

Claude Headspace currently enables monitoring and interaction with Claude Code agents exclusively through the desktop dashboard. When agents ask questions or need input, the user must be at their Mac to respond. This creates idle time when agents block on questions while the user is away from their desk.

The Voice Bridge Server provides the backend infrastructure for hands-free voice interaction with Claude Code agents from mobile devices. It extends the existing tmux bridge and respond architecture with voice-friendly API endpoints, concise LLM-powered output formatting, enhanced question data capture in the Turn model, and token-based authentication for LAN access.

This PRD covers the server-side foundation only. A companion PRD (e6-s2) covers the PWA mobile client that consumes these APIs. The server-side can be fully tested with HTTP tools (curl, httpie) before any client exists.

---

## 1. Context & Purpose

### 1.1 Context

The tmux bridge (e5-s4), input bridge (e5-s1), and full command & output capture (e5-s9) provide a mature foundation for programmatic interaction with Claude Code sessions. The dashboard respond route already supports text, select, and other input modes via tmux send-keys. The intelligence layer (InferenceService, SummarisationService) already generates LLM-powered summaries.

What's missing is:
- A voice-optimised API layer that returns concise, structured responses designed for listening rather than reading
- Richer question data capture that preserves the full question context (question text, options, type) and links answers back to the questions they resolve
- Network-accessible authentication so mobile devices on the same LAN can securely interact with the server
- Non-structured question passthrough — when an agent asks a question without AskUserQuestion options, the full question text must be available for the user to respond sensibly

### 1.2 Target User

The project owner (single-user system) interacting with Claude Code agents from iPhone or iPad while away from their Mac — on the couch, on a bike, cooking, etc.

### 1.3 Success Moment

The user asks "what needs my attention?" from their phone, hears a concise spoken summary of which agents are waiting, asks for the question details, hears the full question read aloud, speaks their answer, and the agent resumes — all without touching the Mac.

---

## 2. Scope

### 2.1 In Scope

- Enhanced Turn model with structured question detail capture and answer-to-question linking
- Voice-friendly API endpoints for: submitting commands, listing agent status, retrieving recent output, and fetching question details
- LLM-powered voice output formatting with configurable verbosity (concise/normal/detailed)
- Question passthrough for non-structured questions (full question text returned when no AskUserQuestion options exist)
- Token-based authentication middleware for LAN access
- Configurable network binding (localhost-only vs LAN-accessible)
- Voice bridge configuration section in config.yaml
- Access logging for voice bridge API calls
- Graceful error responses formatted for voice consumption

### 2.2 Out of Scope

- Mobile client / PWA (covered in e6-s2)
- Speech-to-text or text-to-speech processing (client-side concern)
- WebSocket support (SSE is sufficient for server-to-client push)
- Remote access beyond LAN
- Multi-user authentication
- Changes to the existing dashboard respond flow or UI
- Wake-word detection or voice activity detection (client-side)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A voice command submitted via the API is delivered to the correct agent and the agent resumes processing
2. Question turns store the full question context (text, options, type) retrievable via API
3. Answer turns are linked to the question turn they resolve
4. Non-structured agent questions (no AskUserQuestion options) return the full question text via API
5. Voice output summaries follow the concise format: status line + key results + next action
6. All voice API endpoints are accessible from another device on the same LAN with a valid token
7. Invalid or missing tokens are rejected with appropriate error responses
8. Requests targeting agents that aren't awaiting input return helpful voice-friendly errors

### 3.2 Non-Functional Success Criteria

1. API response latency (excluding LLM calls) is under 500ms
2. Voice output formatting (with LLM) completes within 2 seconds
3. Token validation adds no more than 5ms per request
4. Voice bridge configuration is hot-reloadable without server restart

---

## 4. Functional Requirements (FRs)

### Turn Model Enhancement

**FR1:** Question turns (intent=QUESTION) store structured question detail including: the question text, the list of options (with labels and descriptions when available), and the question source type (ask_user_question, permission_request, or free_text).

**FR2:** Answer turns (intent=ANSWER) store a reference to the question turn they resolve, creating a question-answer pair within the task.

**FR3:** Question detail and answer linkage are exposed in turn-related API responses, enabling clients to display the full question context alongside the answer.

### Voice Command API

**FR4:** A voice command endpoint accepts a text command and an optional target agent identifier. If a target is specified, the command is routed to that agent via the existing respond infrastructure. If no target is specified and exactly one agent is awaiting input, the command is routed to that agent automatically.

**FR5:** A session listing endpoint returns all active agents with: project name, agent state, whether the agent is awaiting input, current command summary, and time since last activity. The response is structured for voice consumption (short text strings, no HTML).

**FR6:** An output retrieval endpoint returns recent agent activity for a specified agent: the last N commands executed and their outputs, formatted as concise text. Leverages the full command & output capture from e5-s9.

**FR7:** A question detail endpoint returns the full question context for an agent in AWAITING_INPUT state: the question text, available options (if any), the question source type, and the agent/project context. When no structured options exist (free-text question), the full question text is returned as-is.

### Voice Output Formatting

**FR8:** Voice API responses use a voice-friendly output format: a status line (1 sentence describing what happened), key results (1-3 bullet points), and next action needed (0-2 bullets, or "none"). This format is applied to session listings, output retrieval, and command confirmations.

**FR9:** A verbosity parameter controls output detail level: "concise" (default — minimal, designed for listening), "normal" (moderate detail), and "detailed" (full information, only when explicitly requested).

**FR10:** Error responses are formatted for voice consumption: error type as a short phrase, one suggestion for resolution. No stack traces, status codes, or technical details in the voice response body.

### Question Passthrough

**FR11:** When an agent enters AWAITING_INPUT due to a non-structured question (detected via intent_detector patterns rather than AskUserQuestion tool_input), the full question text from the agent's last turn is preserved and retrievable via the question detail endpoint.

**FR12:** When the voice client retrieves question details, the response clearly distinguishes between structured questions (with selectable options) and free-text questions (requiring a typed/spoken answer), so the client can present the appropriate input mode.

### Authentication & Network

**FR13:** A token-based authentication middleware protects all voice bridge API endpoints. Requests without a valid token receive a 401 response. Localhost requests may optionally bypass authentication (configurable).

**FR14:** The server network binding is configurable: localhost-only (default, current behaviour) or LAN-accessible (binds to 0.0.0.0 or a specific interface). The voice bridge configuration controls this setting.

**FR15:** All voice bridge API requests are logged with: timestamp, source IP, endpoint, target agent, authentication status, and response latency.

### Error Handling

**FR16:** When no agents are currently awaiting input, the voice command endpoint returns a voice-friendly message indicating this, along with a summary of what active agents are doing.

**FR17:** When a targeted agent is not in AWAITING_INPUT state, the response includes the agent's current state and a suggestion (e.g., "Agent is still processing. Try again in a moment.").

**FR18:** When the tmux bridge is unavailable for an agent, the response indicates the connectivity issue in voice-friendly terms.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Voice bridge endpoints respond within 500ms for non-LLM operations (session listing, command routing, question detail retrieval).

**NFR2:** LLM-powered voice formatting completes within 2 seconds, using the existing InferenceService caching to avoid redundant calls.

**NFR3:** The authentication token is configurable in config.yaml and can be rotated without server restart.

**NFR4:** Voice bridge API endpoints are registered as a separate Flask blueprint, cleanly separated from existing dashboard routes.

**NFR5:** Rate limiting is applied to voice bridge endpoints (configurable, default: 60 requests/minute per token).

---

## 6. UI Overview

This PRD has no user-facing UI. All endpoints return JSON structured for voice client consumption. The companion PRD (e6-s2) covers the mobile client UI.

**API response example (session listing, concise verbosity):**

```
Status: You have 3 agents running. One needs your input.
- claude-headspace: awaiting input — asking about test approach
- raglue: processing — running integration tests
- ot-monitor: idle since 5 minutes ago
Action needed: Respond to claude-headspace.
```

**API response example (question detail):**

```
Agent: claude-headspace
Question: "Which testing approach should we use?"
Type: structured
Options:
  1. Unit tests only — faster but less coverage
  2. Integration tests — slower but more thorough
  3. Both — comprehensive but takes longest
```

---

## 7. Tech Context (for implementation reference)

- Voice API endpoints build on the existing respond route (`/api/respond/<agent_id>`) and tmux bridge service
- Turn model changes require an Alembic migration (new columns/foreign key)
- Voice output formatting uses the existing InferenceService and PromptRegistry
- Authentication middleware can use Flask's `before_request` hook scoped to the voice blueprint
- Network binding is controlled by Flask's `app.run(host=...)` parameter, configured via config.yaml
- The e5-s9 full command & output capture provides the data source for the output retrieval endpoint
- Existing question detection (intent_detector.py) and hook_receiver AWAITING_INPUT handling remain unchanged — voice bridge reads the data they produce
