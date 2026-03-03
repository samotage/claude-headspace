# Tasks: e9-s5-api-sse-endpoints

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Blueprint Scaffolding
- [x] 2.1.1 Create `src/claude_headspace/routes/channels_api.py` with Blueprint instantiation
- [x] 2.1.2 Implement `_error_response()` helper following `remote_agents.py` error envelope pattern
- [x] 2.1.3 Implement `_get_token_from_request()` helper (reuse pattern from `remote_agents.py`)
- [x] 2.1.4 Implement `_resolve_caller()` helper — dual auth (session cookie + Bearer token) resolving to (persona, agent) tuple

### 2.2 Channel Endpoints
- [x] 2.2.1 Implement `POST /api/channels` — create channel (FR1)
- [x] 2.2.2 Implement `GET /api/channels` — list channels with `?status`, `?type`, `?all` filters (FR2)
- [x] 2.2.3 Implement `GET /api/channels/<slug>` — channel detail (FR3)
- [x] 2.2.4 Implement `PATCH /api/channels/<slug>` — update channel (FR4)
- [x] 2.2.5 Implement `POST /api/channels/<slug>/complete` — complete channel (FR5)
- [x] 2.2.6 Implement `POST /api/channels/<slug>/archive` — archive channel (FR5a)

### 2.3 Membership Endpoints
- [x] 2.3.1 Implement `GET /api/channels/<slug>/members` — list members (FR6)
- [x] 2.3.2 Implement `POST /api/channels/<slug>/members` — add member (FR7)
- [x] 2.3.3 Implement `POST /api/channels/<slug>/leave` — leave channel (FR8)
- [x] 2.3.4 Implement `POST /api/channels/<slug>/mute` — mute channel (FR9)
- [x] 2.3.5 Implement `POST /api/channels/<slug>/unmute` — unmute channel (FR10)
- [x] 2.3.6 Implement `POST /api/channels/<slug>/transfer-chair` — transfer chair (FR11)

### 2.4 Message Endpoints
- [x] 2.4.1 Implement `GET /api/channels/<slug>/messages` — message history with cursor pagination (FR12)
- [x] 2.4.2 Implement `POST /api/channels/<slug>/messages` — send message (FR13)

### 2.5 App Factory Registration
- [x] 2.5.1 Import and register `channels_api_bp` in `app.py`

### 2.6 ChannelService Error Mapping
- [x] 2.6.1 Map ChannelService exceptions to HTTP error codes (FR18): ChannelNotFoundError->404, NotAMemberError->403, NotChairError->403, ChannelClosedError->409, AlreadyMemberError->409, NoCreationCapabilityError->403, AgentChannelConflictError->409

## 3. Testing (Phase 3)

### 3.1 Route Tests
- [x] 3.1.1 Test `POST /api/channels` — success (201), missing fields (400), no capability (403)
- [x] 3.1.2 Test `GET /api/channels` — member-scoped list, operator `?all=true`, non-operator `?all=true` silent fallback
- [x] 3.1.3 Test `GET /api/channels/<slug>` — success (200), not found (404)
- [x] 3.1.4 Test `PATCH /api/channels/<slug>` — success (200), not chair (403)
- [x] 3.1.5 Test `POST /api/channels/<slug>/complete` — success (200), not chair (403)
- [x] 3.1.6 Test `POST /api/channels/<slug>/archive` — success (200), not complete (409)
- [x] 3.1.7 Test `GET /api/channels/<slug>/members` — success (200)
- [x] 3.1.8 Test `POST /api/channels/<slug>/members` — success (201), already member (409)
- [x] 3.1.9 Test `POST /api/channels/<slug>/leave` — success (200)
- [x] 3.1.10 Test `POST /api/channels/<slug>/mute` — success (200)
- [x] 3.1.11 Test `POST /api/channels/<slug>/unmute` — success (200)
- [x] 3.1.12 Test `POST /api/channels/<slug>/transfer-chair` — success (200), not chair (403)
- [x] 3.1.13 Test `GET /api/channels/<slug>/messages` — success with pagination (200)
- [x] 3.1.14 Test `POST /api/channels/<slug>/messages` — success (201), invalid type (400), channel closed (409)

### 3.2 Auth Tests
- [x] 3.2.1 Test Bearer token authentication — valid token resolves to persona/agent
- [x] 3.2.2 Test session cookie authentication — resolves to operator persona
- [x] 3.2.3 Test no auth — returns 401
- [x] 3.2.4 Test invalid token — returns 401

### 3.3 Error Handling Tests
- [x] 3.3.1 Test error envelope format `{error: {code, message, status}}`
- [x] 3.3.2 Test all error codes from Section 6.7 of PRD
- [x] 3.3.3 Test service_unavailable (503) when ChannelService not registered

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Route layer is thin — no business logic in handlers
- [x] 4.4 All 18 functional requirements verified
- [x] 4.5 Existing SSE clients unaffected
