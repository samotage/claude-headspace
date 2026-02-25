---
validation:
  status: valid
  validated_at: '2026-02-26T09:37:56+11:00'
---

## Product Requirements Document (PRD) — API Documentation Framework

**Project:** Claude Headspace
**Scope:** Machine-readable API documentation for external APIs, starting with the remote agent API
**Author:** Robbo (architect) / Operator workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace exposes external APIs that are consumed by LLM-powered agents (e.g., May Bell). These consumers need machine-readable documentation to discover endpoints, understand authentication, construct valid requests, and handle errors — without human intervention.

This PRD establishes an API documentation framework using the OpenAPI 3.1 specification. The framework provides a stable, discoverable URL where consumers can fetch a complete API spec. The first spec covers the remote agent API; the pattern scales to future external APIs as they are built.

The primary consumers are LLMs and AI agents. The spec must be optimised for machine comprehension: rich descriptions, complete request/response examples, explicit error schemas, and clear authentication instructions. Human discoverability is supported via a help topic that references the spec.

---

## 1. Context & Purpose

### 1.1 Context

The remote agent API (`/api/remote_agents/`) is live and being consumed by external agents. Currently there is zero machine-readable documentation — consumers must be manually briefed on endpoints, authentication, payloads, and error handling. As more external APIs are built, this approach does not scale.

OpenAPI 3.1 is the industry standard for API specification. It is well-supported by LLMs, code generators, and API tooling. Adopting it establishes a repeatable pattern for documenting all future external APIs.

### 1.2 Target User

- **Primary:** LLM agents and AI-powered systems that consume Claude Headspace external APIs programmatically
- **Secondary:** Human developers or operators who need to understand or debug API integrations

### 1.3 Success Moment

An LLM agent is told to integrate with Claude Headspace. It fetches the OpenAPI spec from a known URL, parses it, and successfully creates a remote agent, checks its liveness, and shuts it down — all without any additional human guidance about the API.

---

## 2. Scope

### 2.1 In Scope

- OpenAPI 3.1 specification covering all remote agent API endpoints
- Spec optimised for LLM consumption (rich descriptions, complete examples, explicit error schemas)
- Spec served as a static file at a stable, discoverable URL
- Help topic documenting the API for human discoverability, cross-linked to the spec URL
- Established directory convention and pattern for future external API specs
- Relative/portable server URL approach (spec documents paths; consumer supplies base URL)

### 2.2 Out of Scope

- Swagger UI or any browser-based API explorer
- Internal API documentation (voice bridge, hooks, SSE, dashboard endpoints)
- Auto-generation of specs from code (decorators, introspection, Flask-RESTX)
- API versioning strategy or breaking change policy
- Authentication mechanism changes (session tokens are documented as-is)
- Dark theme or UI styling of any kind
- npm or other package dependencies
- CORS configuration changes (existing config is documented, not modified)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. An OpenAPI 3.1 spec file is served at a stable URL accessible to consumers on the network
2. The spec documents all remote agent API endpoints: create, alive check, shutdown, and embed
3. The spec includes complete request and response schemas with realistic example payloads
4. The spec documents the session token authentication mechanism with instructions for how to obtain and use tokens
5. The spec documents the standardised error envelope with all error codes and retryable semantics
6. The spec documents CORS behaviour
7. A help topic exists that describes the API and provides the spec URL
8. The help topic is cross-linked: help references spec, spec references help
9. An LLM can parse the spec and generate valid API calls without supplementary documentation

### 3.2 Non-Functional Success Criteria

1. The spec validates against the OpenAPI 3.1 specification standard
2. The directory convention is documented so future external API specs follow the same pattern
3. The spec file is version-controlled and maintained alongside the codebase

---

## 4. Functional Requirements (FRs)

### Spec Content

**FR1:** The spec shall be written in OpenAPI 3.1 format (YAML).

**FR2:** The spec shall document all remote agent API endpoints with their HTTP methods, URL paths, and purpose:
- `POST /api/remote_agents/create` — create a new remote agent
- `GET /api/remote_agents/<agent_id>/alive` — check agent liveness
- `POST /api/remote_agents/<agent_id>/shutdown` — initiate graceful shutdown
- `GET /embed/<agent_id>` — retrieve the embed chat view

**FR3:** The spec shall define reusable schema components for all request and response bodies, including:
- Create request payload (project_path, persona fields, feature flags)
- Create success response (agent_id, embed_url, session_token)
- Alive response (alive status, agent state)
- Shutdown response (acknowledgement, message)
- Error envelope (code, message, status, retryable, retry_after_seconds)

**FR4:** Each schema field shall include a `description` that explains its purpose and semantics in plain language suitable for LLM comprehension.

**FR5:** Each endpoint shall include at least one complete `example` for both successful responses and relevant error responses.

**FR6:** The spec shall document the session token authentication mechanism:
- How a token is obtained (returned in the create response)
- How a token is sent (Authorization: Bearer header or token query parameter)
- Token scope (each token is bound to a specific agent_id)
- What happens when a token is invalid or missing (401 response)

**FR7:** The spec shall document all error response codes (400, 401, 404, 408, 500, 503) with their meaning, the error envelope structure, and which errors are retryable.

**FR8:** The spec shall document CORS behaviour (allowed origins are configurable; preflight OPTIONS requests are supported).

**FR9:** The spec shall use relative paths (no hardcoded server URL). A description or comment shall instruct consumers to supply the base URL of their target Claude Headspace instance.

### Serving & Discoverability

**FR10:** The spec file shall be served as a static file accessible via HTTP GET at a stable URL path.

**FR11:** The spec URL path shall follow the established static file directory convention used by the project.

### Help & Cross-Linking

**FR12:** A help topic shall be created that describes the external API, explains how to use the spec, and provides the URL where the spec can be fetched.

**FR13:** The help topic shall be registered in the help system and accessible via the existing help routes.

**FR14:** The spec file shall include a reference (in its `info.description` or equivalent) pointing to the help topic for additional human-readable context.

### Framework Convention

**FR15:** The directory structure and naming convention for API spec files shall be documented (in the help topic or a README) so that future external API specs follow the same pattern.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The spec shall validate against the OpenAPI 3.1 specification without errors.

**NFR2:** Descriptions and examples shall be written with LLM comprehension as the primary concern — explicit, unambiguous, and self-contained. Avoid jargon that requires external context to parse.

---

## 6. UI Overview

This PRD has no user interface component. The spec is served as a static file. The help topic uses the existing help system UI.
