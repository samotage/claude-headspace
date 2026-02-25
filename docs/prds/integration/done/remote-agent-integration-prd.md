---
validation:
  status: valid
  validated_at: '2026-02-25T16:29:15+11:00'
---

## Product Requirements Document (PRD) — Remote Agent Integration API

**Project:** Claude Headspace
**Scope:** External integration API for remote agent creation, embedded chat, and lifecycle management
**Author:** Sam (workshopped with Robbo)
**Status:** Draft

---

## Executive Summary

Claude Headspace needs an external integration API that allows other applications to create purpose-built agents, receive an embeddable chat URL, and manage agent lifecycle — all through a clean, self-contained API namespace that is completely independent of the existing voice bridge.

The first consumer is May Belle (AI-Assisted Job Applications), which needs to spin up a persona-driven agent, inject a job-specific prompt, and embed the resulting chat interface in an iframe within its own application. The user (an NDIS support worker on iPhone Safari) interacts with the agent entirely through this embedded chat pane — they never see or know about Headspace.

This PRD covers: a blocking agent creation endpoint that returns only when the agent is fully ready; a scoped embed view that renders a single-agent chat with no Headspace chrome; agent liveness checking for idempotent reuse; session token authentication for API calls and iframe access; CORS configuration for cross-origin iframe embedding; and standardised error responses.

The existing voice bridge endpoints (`/api/voice/*`) are not modified. This is a new, parallel API surface under `/api/remote_agents/`.

---

## 1. Context & Purpose

### 1.1 Context

Headspace already has a comprehensive agent lifecycle system: tmux-based agent spawning, persona registration with skill injection, a real-time voice bridge chat interface with SSE updates, and question/option rendering. All of this was built for the Headspace dashboard and its companion voice bridge PWA.

External applications now need the same capabilities — create an agent, give it a job, let a user chat with it — but through a clean API contract. The existing voice bridge endpoints are tightly coupled to the PWA's interaction model (fire-and-forget creation, voice-formatted responses, session-list navigation). Modifying them for external consumers would break the existing application.

A separate `remote_agents` API namespace provides the right abstraction: blocking semantics, self-contained responses, session tokens, and an embed view designed for iframe integration.

### 1.2 Target User

The primary consumers are:

1. **External applications** (first: May Belle) — call the API to create agents, check liveness, manage lifecycle
2. **End users of those applications** — interact with agents through the embedded chat pane (never aware of Headspace)
3. **Operators** — debug integration issues using the agent identifiers returned by the API, cross-referenced against Headspace's dashboard

### 1.3 Success Moment

An external application makes a single POST request to Headspace, receives a ready-to-use embed URL and session token within 15 seconds, drops the URL into an iframe, and the end user is immediately talking to a persona-driven agent — with no awareness that Headspace exists behind the scenes.

---

## 2. Scope

### 2.1 In Scope

- New `remote_agents` API namespace (`/api/remote_agents/`) — completely independent of existing voice bridge endpoints
- Blocking agent creation endpoint — accepts project slug, persona slug, and initial prompt; returns only when the agent is fully ready (registered, skill-injected, prompt delivered)
- Create response payload with all identifiers the calling application needs: `agent_id`, `embed_url`, `session_token`, `project_slug`, `persona_slug`, `tmux_session_name`, `status`
- Session token authentication — opaque token returned by create, required for subsequent API calls (liveness, shutdown) and embedded in the embed URL for iframe access
- Agent liveness check endpoint — calling application checks whether a previously created agent is still alive for idempotent reuse (page refresh, re-navigation)
- Agent shutdown endpoint — calling application requests graceful agent termination when done
- Scoped embed view — stripped-down chat interface for iframe embedding: single agent only, no Headspace chrome (no header, no session switcher, no navigation, no dashboard links)
- Embed view core features: text input, message thread, question/option rendering
- Embed view feature flags: file upload, context usage display, and voice microphone can be enabled/disabled per-agent via flags on the create request or embed URL parameters
- SSE real-time updates scoped to the embedded agent — same infrastructure as the voice bridge, filtered to the single agent
- CORS configuration — configurable allowed origins in `config.yaml` for cross-origin iframe embedding over TLS
- Standardised error response envelope across all `remote_agents` endpoints with HTTP status codes, error codes, and retry guidance
- Configuration entries in `config.yaml` for: allowed CORS origins, embed feature flag defaults, agent creation timeout

### 2.2 Out of Scope

- Changes to existing voice bridge endpoints (`/api/voice/*`) — they remain untouched
- The May Belle persona itself — registered separately via `flask persona register` before calling this API
- Project auto-registration — the calling application's project must exist in Headspace before agent creation
- API key infrastructure for application-level authentication (Phase 1 uses session tokens for per-agent auth; application-level auth relies on Tailscale LAN trust)
- Chat session persistence or restoration across agent restarts (if an agent dies, the calling application creates a new one)
- Multi-user support or per-user agent sessions
- Batch agent creation (one agent per request)
- Phase 2 features: auto-draft, auto-submit, batch processing
- Webhook/callback patterns (the create endpoint blocks synchronously)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. An external application can create an agent with a single POST to `/api/remote_agents/create` providing `project_slug`, `persona_slug`, and `initial_prompt`, and receive a complete response with `agent_id`, `embed_url`, `session_token`, and identifying metadata
2. The create endpoint blocks until the agent is fully ready: registered in the database, persona skill injected, initial prompt delivered — or returns a timeout error within the configured timeout period
3. The `embed_url` renders a single-agent chat interface in an iframe with no Headspace chrome visible — no header, no session list, no navigation, no dashboard links
4. The embedded chat view supports real-time updates via SSE scoped to the single agent — agent responses appear without polling or page refresh
5. Text input, message thread display, and question/option rendering work correctly in the embedded view
6. File upload, context usage display, and voice microphone are controllable via feature flags and hidden by default in the embedded view
7. The calling application can check agent liveness via `GET /api/remote_agents/<id>/alive` using the session token, and receive a clear alive/not-alive response for idempotent reuse
8. The calling application can shut down an agent via `POST /api/remote_agents/<id>/shutdown` using the session token
9. The session token authenticates all subsequent API calls (liveness, shutdown) and grants access to the embedded chat view — requests without a valid token are rejected
10. CORS headers allow the embedded chat view to load cross-origin in an iframe from configured allowed origins over TLS
11. All error conditions return a consistent JSON error envelope with HTTP status code, error code, human-readable message, and retry guidance
12. Existing voice bridge functionality (`/api/voice/*`) is completely unaffected

### 3.2 Non-Functional Success Criteria

1. Agent creation completes within 15 seconds under normal conditions
2. The embedded chat view is responsive and functional in iOS Safari iframes (May Belle's primary user context)
3. The API and embed view work correctly over TLS (Tailscale certificates)

---

## 4. Functional Requirements (FRs)

**FR1: Remote Agent Creation Endpoint**

The system provides a `POST /api/remote_agents/create` endpoint that creates a fully ready agent and returns all information the calling application needs. The endpoint accepts a project slug (e.g. `may-belle`), persona slug, and initial prompt. It blocks until the agent is registered in the database, the persona skill file is injected, and the initial prompt is delivered to the agent. The response includes the agent ID, a scoped embed URL for iframe embedding, an opaque session token for subsequent API calls and iframe authentication, the project slug and persona slug echoed back, the tmux session name (for operator debugging), and a status indicator. If the agent fails to become ready within the configured timeout, the endpoint returns a timeout error.

**FR2: Agent Liveness Check**

The system provides a `GET /api/remote_agents/<id>/alive` endpoint that reports whether a previously created agent is still active. The calling application uses this on page refresh or re-navigation to determine whether to reuse the existing embed URL or create a new agent. The endpoint requires a valid session token. The response indicates alive or not-alive status, and optionally includes the agent's current state.

**FR3: Agent Shutdown**

The system provides a `POST /api/remote_agents/<id>/shutdown` endpoint that requests graceful termination of an agent. The calling application uses this when the user's task is complete or the user navigates away. The endpoint requires a valid session token. Shutdown is non-blocking — Headspace initiates termination and returns immediately; tmux session cleanup happens asynchronously. The endpoint is idempotent — calling shutdown on an already-terminated agent returns success, not an error.

Explicit response shapes (S5 contract amendment):

1. **Success (200):** `{"status": "ok", "agent_id": N, "message": "Agent shutdown initiated"}`
2. **Already-shutdown / idempotent (200):** `{"status": "ok", "agent_id": N, "message": "Agent already terminated"}`
3. **Invalid or missing session token (401):** Standard error envelope: `{"error": {"code": "invalid_session_token", "message": "...", "status": 401, "retryable": false, "retry_after_seconds": null}}`
4. **Agent not found (404):** Standard error envelope: `{"error": {"code": "agent_not_found", "message": "...", "status": 404, "retryable": false, "retry_after_seconds": null}}`

**FR4: Scoped Embed View**

The system provides a scoped embed view at the URL returned by the create endpoint. This view renders a single-agent chat interface designed for iframe embedding. The view includes: text input field, message thread with conversation history, and question/option rendering (structured choices, free-text prompts). The view excludes all Headspace chrome: no header, no session switcher, no agent list, no navigation links, no dashboard access. The embed URL includes the session token for authentication and the agent ID for scoping.

**FR5: Embed Feature Flags**

The scoped embed view supports feature flags that control optional capabilities. File upload, context usage display, and voice microphone are each independently enabled or disabled. These flags can be specified on the create request (persisted for the agent's lifetime) or as URL parameters on the embed URL. All three are disabled by default in the embedded context.

**FR6: Real-Time Updates in Embed View**

The embedded chat view maintains an SSE connection to Headspace for real-time updates, scoped to the single agent. Agent responses, state transitions, question events, and turn updates flow through SSE into the iframe. The embed view uses the same SSE infrastructure as the voice bridge, filtered to the relevant agent. The iframe remains in sync with the Headspace application's view of the agent.

**FR7: Session Token Authentication**

The create endpoint generates an opaque session token that is returned in the create response. This token authenticates all subsequent interactions for that agent: liveness checks, shutdown requests, and access to the embedded chat view. Requests to remote agent endpoints without a valid session token are rejected with an appropriate error response. The token is scoped to the specific agent — it cannot be used to access other agents or Headspace features.

**FR8: CORS Configuration**

The system supports configurable CORS allowed origins for cross-origin iframe embedding. Allowed origins are specified in `config.yaml`. CORS headers are applied to the remote agents API endpoints and the embedded chat view. The configuration supports TLS origins (e.g., `https://hostname.tailnet.ts.net:port`).

**FR9: Standardised Error Responses**

All `remote_agents` endpoints return errors in a consistent nested JSON envelope (S5 FR5 contract): `{"error": {"code": "...", "message": "...", "status": N, "retryable": bool, "retry_after_seconds": N|null}}`. The `retry_after_seconds` field is always present (null when not applicable). Specific error conditions include: project not found (404), persona not found (404), agent creation timeout (408, retryable), invalid or missing session token (401), agent not found (404), server error (500), and service unavailable (503).

**FR10: Configuration**

The system adds configuration entries for the remote agent integration: allowed CORS origins (list of permitted origins for iframe embedding), embed feature flag defaults (file upload, context usage, voice microphone — all off by default), and agent creation timeout (maximum time to wait for agent readiness, default 15 seconds).

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The remote agents API must not affect the performance or behaviour of existing voice bridge endpoints — they share underlying infrastructure (tmux bridge, SSE broadcaster, agent lifecycle) but are completely independent at the route level.

**NFR2:** The embedded chat view must be responsive and functional when rendered in an iframe on iOS Safari, as the first consumer's end users are NDIS support workers using iPhones.

**NFR3:** The API must work correctly over TLS using Tailscale certificates, as both the calling application and Headspace are accessed via Tailscale hostnames.

**NFR4:** The session token must be cryptographically opaque — it must not encode or leak internal Headspace state (agent IDs, database keys, or infrastructure details) in a way that can be decoded by the calling application.

---

## 6. UI Overview

### 6.1 Scoped Embed View

The embedded chat view is a minimal, single-purpose interface:

- **Message thread** — scrollable conversation history showing user messages and agent responses, with clear visual distinction between the two. Renders structured question/option UI when the agent asks questions with choices.
- **Text input** — input field at the bottom for the user to type messages, with a send button. Optimised for mobile (iOS Safari keyboard behaviour).
- **No chrome** — no Headspace branding, no header bar, no session list sidebar, no navigation links, no "powered by" attribution. The embed view is a white-label chat pane.
- **Feature flag UI** — when enabled: file upload button appears near the text input; context usage indicator appears in the header area of the embed view; voice microphone button appears near the text input. When disabled (default): these elements are completely absent from the DOM, not just hidden.
- **Loading state** — the embed view shows a loading indicator while establishing the SSE connection and loading initial conversation state.
- **Error state** — if the SSE connection fails or the agent becomes unavailable, the embed view shows a user-friendly error message (not technical details).

### 6.2 No Other UI Changes

The Headspace dashboard, voice bridge PWA, and all existing UI remain unchanged. Agents created via the remote agents API appear on the Headspace dashboard like any other agent — the operator can observe and debug them from the dashboard. The embed view is an additional rendering of the same agent, not a replacement.
