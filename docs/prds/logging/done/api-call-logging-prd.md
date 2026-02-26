---
validation:
  status: valid
  validated_at: '2026-02-26T19:34:18+11:00'
---

## Product Requirements Document (PRD) — API Call Logging

**Project:** Claude Headspace
**Scope:** External API request/response logging tab in the logging subsystem
**Author:** Shorty (PRD Workshop)
**Status:** Draft

---

## Executive Summary

Claude Headspace exposes RESTful APIs for external applications (remote agents, voice bridge, embed chat). When cross-system integrations fail or behave unexpectedly, there is currently no way to inspect what arrived on the wire, what was sent back, or why a call failed. Developers are flying blind.

This PRD adds an "API" tab to the existing logging subsystem (alongside Events and Inference) that captures every external API request and response with full payloads, HTTP metadata, timing, and authentication status. The goal is simple: if we can see it, we can fix it.

Success means a developer can open the API log tab, filter to a failing endpoint, expand a row, and see exactly what the caller sent and what the system returned — end of mystery.

---

## 1. Context & Purpose

### 1.1 Context

The system's external API surface is growing. Remote agents, voice bridge, and embed chat all accept requests from external applications. When these integrations break — malformed payloads, auth failures, unexpected responses — there is no persistent, inspectable record of what happened. Python logger output is ephemeral and unstructured. The existing Event model captures business domain events (hooks, state transitions), not HTTP traffic.

### 1.2 Target User

Developers and system operators debugging cross-system integrations. The primary user is someone staring at a broken integration who needs to answer: "What did the caller actually send, and what did we send back?"

### 1.3 Success Moment

A developer sees a remote agent creation failing from an external app. They open the API log tab, filter to `POST /api/remote_agents/create`, see a 422 response, expand the row, read the request payload and error response, and immediately understand the problem.

---

## 2. Scope

### 2.1 In Scope

- New "API" tab in the logging subsystem alongside Events and Inference
- Persistent capture of all external API requests and responses
- Captured data per call: timestamp, HTTP method, endpoint path, query parameters, request headers (selected/safe), request payload (body), response payload (body), HTTP status code, response latency (ms), source IP, authentication status (authenticated/failed/unauthenticated/bypassed)
- Target endpoints for capture: remote agents (`/api/remote_agents/*`), voice bridge (`/api/voice_bridge/*`), embed (`/embed/*`), and any future external-facing API routes
- Filterable table: by endpoint path, HTTP method, status code category (2xx/4xx/5xx), authentication status
- Text search across request and response payloads
- Click-to-expand rows showing full request payload, full response payload, headers, and metadata
- Pagination with the same pattern as Events and Inference tabs
- Real-time SSE updates when new API calls are logged
- Clear-all functionality with destructive confirmation
- New database model to persist API call log records

### 2.2 Out of Scope

- Internal hook endpoints (`/hook/*`) — these are local Claude Code lifecycle events, not external API traffic
- SSE stream connections (`/api/events/stream`)
- Dashboard page requests (HTML routes)
- Internal API endpoints used only by the dashboard frontend (e.g., `/api/events`, `/api/inference/calls`)
- Alerting, rate-limit enforcement, or anomaly detection based on API logs
- Log retention policies or automatic cleanup/rotation
- Request payload redaction or PII masking (can be added later)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Every external API call (remote agents, voice bridge, embed) is captured with full request and response payloads
2. The API log tab displays captured calls in a paginated, filterable table
3. Developers can filter by endpoint, HTTP method, status code category, and authentication status
4. Developers can search across request and response payload content
5. Expanding a row shows the complete request payload, response payload, and HTTP metadata
6. New API calls appear in real-time via SSE without page refresh
7. The clear-all function removes all API log records with destructive confirmation

### 3.2 Non-Functional Success Criteria

1. Logging does not add more than 50ms of latency to API request processing
2. The logging mechanism does not break or interfere with existing API behaviour — if logging fails, the API call still succeeds
3. Large payloads (up to 1MB) are captured without truncation

---

## 4. Functional Requirements (FRs)

**FR1:** The system captures every HTTP request to designated external API route prefixes and persists a log record containing: timestamp, HTTP method, endpoint path, query string, request content type, request body, response status code, response content type, response body, response latency in milliseconds, source IP address, and authentication status.

**FR2:** The system provides an "API" tab in the logging subsystem navigation, accessible at `/logging/api`, positioned after the Inference tab.

**FR3:** The API log tab displays captured calls in a paginated table showing: timestamp, HTTP method, endpoint path, status code (colour-coded by category: 2xx green, 4xx amber, 5xx red), latency (ms), source IP, and authentication status.

**FR4:** The API log tab provides filter controls for: endpoint path (dropdown of distinct paths), HTTP method (GET/POST/PUT/DELETE/OPTIONS), status code category (2xx/4xx/5xx/all), and authentication status (authenticated/failed/unauthenticated/bypassed/all).

**FR5:** The API log tab provides a text search field that searches across request body and response body content, with matching snippets shown in results.

**FR6:** Clicking a table row expands it to show the full request payload and full response payload, each syntax-highlighted when the content is JSON, plus request headers (safe subset excluding auth tokens) and call metadata.

**FR7:** The API log tab provides a paginated API endpoint (`GET /api/logging/api-calls`) that supports the filter and search parameters from FR4 and FR5, returning paginated results with total count and page metadata.

**FR8:** The API log tab provides a filters endpoint (`GET /api/logging/api-calls/filters`) that returns the distinct values available for each filter (endpoints, methods, status categories, auth statuses).

**FR9:** The API log tab provides a clear-all endpoint (`DELETE /api/logging/api-calls`) that requires the `X-Confirm-Destructive: true` header and deletes all API call log records.

**FR10:** New API call log records trigger an SSE event that the API log tab listens for, prepending new rows to the table in real-time when the user is on page 1 and the call matches active filters.

**FR11:** The tab navigation partial (`_logging_tabs.html`) is updated to include the API tab with a distinct icon, maintaining the existing tab styling and active-state logic.

**FR12:** Captured request headers exclude sensitive values — `Authorization` header values are replaced with the auth status determination rather than the raw token value.

**FR13:** The logging mechanism is implemented as a non-blocking decorator or middleware that captures data without adding significant latency to the API response. If the logging write fails, the API call still completes normally.

**FR14:** The API call log database model includes foreign key references to project and agent when they can be resolved from the request context, enabling correlation with existing dashboard entities.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** API call logging adds no more than 50ms of overhead to request processing under normal conditions.

**NFR2:** The logging mechanism is fault-tolerant — failures in logging (database errors, serialisation errors) must not cause the API request to fail or return an error to the caller.

**NFR3:** Request and response payloads up to 1MB are captured without truncation. Payloads exceeding 1MB may be truncated with an indicator.

**NFR4:** The API log tab UI follows the same visual patterns, component styles, and interaction behaviours as the existing Events and Inference tabs for consistency.

---

## 6. UI Overview

The API log tab follows the established logging subsystem layout:

- **Tab bar**: Three tabs — Events | Inference | API (new). API tab uses a distinct icon (e.g., arrow exchange or plug icon).
- **Filter bar**: Dropdowns for endpoint path, HTTP method, status category, auth status. Text search field. Clear filters button. Clear all logs button with inline confirmation.
- **Table columns**: Timestamp | Method (badge) | Endpoint | Status (colour-coded badge) | Latency (ms) | Source IP | Auth Status
- **Expanded row**: Two sections side-by-side or stacked — "Request" (headers + body) and "Response" (status + body), each with syntax-highlighted JSON rendering when applicable.
- **States**: Loading, empty (no logs yet), no results (filters matched nothing), error.
- **Pagination**: Previous/Next buttons with page indicator, same as other tabs.
- **Real-time**: New rows prepend with subtle animation on page 1.
