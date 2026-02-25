## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 OpenAPI Spec File

- [ ] 2.1.1 Create `static/api/` directory
- [ ] 2.1.2 Create `static/api/remote-agents.yaml` with OpenAPI 3.1 header (`openapi: 3.1.0`, info block with title, version, description referencing help topic)
- [ ] 2.1.3 Add `servers` section with description instructing consumers to supply their own base URL
- [ ] 2.1.4 Document `POST /api/remote_agents/create` — request body schema (project_slug, persona_slug, initial_prompt, feature_flags), 201 success response schema (agent_id, embed_url, session_token, project_slug, persona_slug, tmux_session_name, status), error responses (400, 404, 408, 500, 503)
- [ ] 2.1.5 Document `GET /api/remote_agents/{agent_id}/alive` — path parameter, 200 response schemas (alive=true with agent_id/state/project_slug, alive=false with reason), error responses (401, 503)
- [ ] 2.1.6 Document `POST /api/remote_agents/{agent_id}/shutdown` — path parameter, 200 response schemas (shutdown initiated, already terminated), error responses (401, 404, 503)
- [ ] 2.1.7 Document `GET /embed/{agent_id}` — path parameter, query parameters (token, file_upload, context_usage, voice_mic), 200 response (HTML), error responses (401, 503)
- [ ] 2.1.8 Define reusable schema components in `components/schemas` (CreateRequest, CreateResponse, AliveResponseAlive, AliveResponseNotAlive, ShutdownResponse, ErrorEnvelope)
- [ ] 2.1.9 Define security scheme component (`SessionToken` — Bearer token in Authorization header or `token` query parameter)
- [ ] 2.1.10 Add complete realistic examples to all request/response schemas
- [ ] 2.1.11 Add LLM-optimised descriptions to every field (plain language, unambiguous, self-contained)
- [ ] 2.1.12 Document all error codes (400/missing_fields, 400/invalid_feature_flags, 401/invalid_session_token, 404/project_not_found, 404/persona_not_found, 404/agent_not_found, 408/agent_creation_timeout, 500/server_error, 503/service_unavailable) with retryable semantics
- [ ] 2.1.13 Document CORS behaviour (configurable allowed origins, preflight OPTIONS, headers)
- [ ] 2.1.14 Verify spec uses relative paths only (no hardcoded server URLs)

### 2.2 Help Topic

- [ ] 2.2.1 Create `docs/help/external-api.md` with overview of the external API
- [ ] 2.2.2 Document how to fetch and use the OpenAPI spec (URL path: `/static/api/remote-agents.yaml`)
- [ ] 2.2.3 Document the directory convention for future API specs (`static/api/<api-name>.yaml`)
- [ ] 2.2.4 Cross-link to the spec URL for machine-readable access
- [ ] 2.2.5 Include quick-start instructions for LLM consumers (fetch spec, parse, authenticate, call endpoints)

### 2.3 Help System Registration

- [ ] 2.3.1 Add `{"slug": "external-api", "title": "External API", "order": 17}` to TOPICS list in `src/claude_headspace/routes/help.py`
- [ ] 2.3.2 Add navigation link in `docs/help/index.md`

## 3. Testing (Phase 3)

- [ ] 3.1 Validate `static/api/remote-agents.yaml` against OpenAPI 3.1 standard (programmatic validation)
- [ ] 3.2 Verify spec file is accessible via static file URL (`GET /static/api/remote-agents.yaml`)
- [ ] 3.3 Verify help topic loads via `/api/help/topics/external-api`
- [ ] 3.4 Verify help topic appears in topic list via `/api/help/topics`
- [ ] 3.5 Verify all endpoint paths in the spec match actual route registrations
- [ ] 3.6 Verify all schema fields match actual request/response shapes from route code
- [ ] 3.7 Verify cross-links: spec references help topic, help topic references spec URL

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete (spec served, help topic accessible, cross-links work)
