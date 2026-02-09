## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Turn Model Enhancement

- [ ] 2.1 Add `question_text`, `question_options`, `question_source_type`, `answered_by_turn_id` columns to Turn model
- [ ] 2.2 Create Alembic migration for new Turn columns
- [ ] 2.3 Update hook_receiver to populate `question_text`, `question_options`, `question_source_type` when creating QUESTION turns
- [ ] 2.4 Update hook_receiver to populate `answered_by_turn_id` on ANSWER turns (link to most recent QUESTION turn in same task)
- [ ] 2.5 Update respond route to populate `answered_by_turn_id` when creating ANSWER turns

### Voice Bridge Configuration

- [ ] 2.6 Add `voice_bridge` section to config.yaml (enabled, auth_token, localhost_bypass, bind_address, rate_limit, default_verbosity)
- [ ] 2.7 Add config defaults in config.py for voice_bridge section

### Authentication & Network

- [ ] 2.8 Create `voice_auth.py` service — token validation middleware, localhost bypass, access logging
- [ ] 2.9 Update `run.py` to use voice_bridge.network.bind_address from config
- [ ] 2.10 Register voice_auth service in app.py

### Voice Output Formatting

- [ ] 2.11 Create `voice_formatter.py` service — format responses for voice consumption (status + results + action)
- [ ] 2.12 Add voice formatting prompt templates to PromptRegistry
- [ ] 2.13 Register voice_formatter service in app.py

### Voice Bridge API

- [ ] 2.14 Create `voice_bridge.py` route blueprint with 4 endpoints:
  - `POST /api/voice/command` — submit command to agent
  - `GET /api/voice/sessions` — list active agents
  - `GET /api/voice/agents/<agent_id>/output` — recent output
  - `GET /api/voice/agents/<agent_id>/question` — question details
- [ ] 2.15 Implement voice command endpoint (FR4) — route to agent via tmux_bridge, auto-target if single awaiting agent
- [ ] 2.16 Implement session listing endpoint (FR5) — voice-friendly active agent list
- [ ] 2.17 Implement output retrieval endpoint (FR6) — recent task command/output history
- [ ] 2.18 Implement question detail endpoint (FR7) — full question context with structured vs free-text distinction
- [ ] 2.19 Apply voice_auth middleware to voice blueprint via before_request
- [ ] 2.20 Register voice_bridge blueprint in app.py

## 3. Testing (Phase 3)

- [ ] 3.1 Unit tests for Turn model new columns (question_text, question_options, question_source_type, answered_by_turn_id)
- [ ] 3.2 Unit tests for voice_auth service (token validation, localhost bypass, invalid token rejection)
- [ ] 3.3 Unit tests for voice_formatter service (concise/normal/detailed verbosity, error formatting)
- [ ] 3.4 Route tests for voice command endpoint (text routing, auto-target, wrong state errors)
- [ ] 3.5 Route tests for session listing endpoint (active agents, voice-friendly format)
- [ ] 3.6 Route tests for output retrieval endpoint (recent tasks, concise formatting)
- [ ] 3.7 Route tests for question detail endpoint (structured vs free-text, AWAITING_INPUT guard)
- [ ] 3.8 Route tests for authentication (missing token, invalid token, localhost bypass)
- [ ] 3.9 Test hook_receiver populates new Turn columns correctly
- [ ] 3.10 Test respond route populates answered_by_turn_id correctly

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification with curl/httpie
- [ ] 4.4 Migration runs cleanly on test database
