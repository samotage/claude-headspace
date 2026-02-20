## Why

Sprint 1+2 proved the agent-driven testing mechanism with three scenarios and cross-layer verification, but each test file contains duplicated boilerplate. Sprint 3 extracts proven patterns into reusable helpers, adds two new interaction shapes (permission approval flow and bug-driven scenarios), introduces structured test output, and evaluates whether a declarative scenario format would reduce duplication.

## What Changes

- Extract shared helper functions from Sprint 1+2 boilerplate into `tests/agent_driven/helpers/`
  - Cross-layer verification (currently duplicated in test_question_answer.py and test_multi_turn.py)
  - Screenshot capture with consistent naming
  - Common setup patterns
- Add permission approval flow test exercising permission-request hook flow
- Add at least one bug-driven scenario targeting a real bug that survived mock-based testing
- Add structured test output (scenario name, step progress, pass/fail, elapsed time)
- Evaluate declarative scenario format (YAML) and document decision
- Ensure all agent-driven tests are discoverable via pytest

## Impact

- Affected specs: testing (agent-driven integration tests)
- Affected code:
  - `tests/agent_driven/helpers/__init__.py` (new)
  - `tests/agent_driven/helpers/cross_layer.py` (new -- extracted from Sprint 2 tests)
  - `tests/agent_driven/helpers/output.py` (new -- structured test output)
  - `tests/agent_driven/test_permission_approval.py` (new)
  - `tests/agent_driven/test_bug_<name>.py` (new -- at least one bug-driven scenario)
  - `tests/agent_driven/test_question_answer.py` (modified -- use shared helpers)
  - `tests/agent_driven/test_multi_turn.py` (modified -- use shared helpers)
  - `tests/agent_driven/test_simple_command.py` (potentially modified -- use shared helpers)
  - `tests/agent_driven/conftest.py` (potentially modified -- add output fixtures)
- Existing test infrastructure used unchanged:
  - `claude_session` fixture
  - `e2e_test_db`, `e2e_app`, `e2e_server` fixtures
  - `VoiceAssertions` helper
- API endpoints consumed (read-only):
  - `/api/voice/agents/<id>/transcript` (cross-layer verification)
  - `/api/voice/command` (sending commands)
- Related OpenSpec history:
  - `integration-testing-framework` (archived 2026-01-30)
  - `e7-s1-agent-driven-integration-testing` (archived 2026-02-19)
  - `e7-s2-agent-driven-integration-testing` (archived 2026-02-19)
