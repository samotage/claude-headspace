## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [x] 2.1 Extend `create_agent()` in `agent_lifecycle.py` — add optional `persona_slug` and `previous_agent_id` parameters, validate persona slug against Persona table (active status), pass persona slug to CLI command args, pass `previous_agent_id` via environment variable
- [x] 2.2 Extend `claude-headspace start` in `cli/launcher.py` — add `--persona <slug>` flag to argparse, validate persona slug against database before session launch, set `CLAUDE_HEADSPACE_PERSONA_SLUG` and `CLAUDE_HEADSPACE_PREVIOUS_AGENT_ID` environment variables for hook script inheritance
- [x] 2.3 Extend `notify-headspace.sh` — read `CLAUDE_HEADSPACE_PERSONA_SLUG` and `CLAUDE_HEADSPACE_PREVIOUS_AGENT_ID` from environment, include as `persona_slug` and `previous_agent_id` in JSON payload when present (omit when absent)
- [x] 2.4 Extend `/hook/session-start` in `routes/hooks.py` — extract `persona_slug` and `previous_agent_id` from incoming payload, pass both to `process_session_start()`
- [x] 2.5 Extend `process_session_start()` in `hook_receiver.py` — accept `persona_slug` and `previous_agent_id` parameters, store them on the agent or pass through for S8 consumption

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for `create_agent()` persona validation (`tests/services/test_agent_lifecycle.py`) — valid slug passes, invalid slug returns failure, missing slug preserves existing behaviour, previous_agent_id passed through
- [x] 3.2 Unit tests for CLI persona flag (`tests/cli/test_launcher.py`) — argparse recognizes --persona, validation logic tested
- [x] 3.3 Unit tests for hook payload extension (`tests/routes/test_hooks.py`) — persona_slug extracted from session-start payload, previous_agent_id extracted, both absent when not provided
- [x] 3.4 Unit tests for `process_session_start()` persona passthrough (`tests/services/test_hook_receiver.py`) — persona_slug and previous_agent_id accepted and stored/passed through
- [x] 3.5 Regression: existing agent creation tests still pass with no persona specified

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
