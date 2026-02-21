## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [x] 2.1 Extend `process_session_start()` in `hook_receiver.py` — replace transient `_pending_persona_slug` storage with Persona lookup by slug, set `agent.persona_id` when found, log warning when not found, log assignment at INFO level
- [x] 2.2 Extend `process_session_start()` in `hook_receiver.py` — replace transient `_pending_previous_agent_id` storage with actual `agent.previous_agent_id` assignment (convert string to int)
- [x] 2.3 Handle DB error during Persona lookup — catch exceptions, log error, create agent without persona (do not block registration)

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for persona assignment (`tests/services/test_hook_receiver.py`) — valid slug sets persona_id, persona relationship navigable
- [x] 3.2 Unit tests for persona not found (`tests/services/test_hook_receiver.py`) — unrecognised slug logs warning, agent created with persona_id=NULL
- [x] 3.3 Unit tests for no persona slug (`tests/services/test_hook_receiver.py`) — existing behaviour unchanged, no extra DB queries
- [x] 3.4 Unit tests for previous_agent_id assignment (`tests/services/test_hook_receiver.py`) — string converted to int, set on agent record
- [x] 3.5 Regression: existing hook_receiver and session_correlator tests still pass

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
