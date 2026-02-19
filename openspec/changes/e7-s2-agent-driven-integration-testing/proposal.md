## Why

Sprint 1 proved the fundamental agent-driven testing mechanism with a single simple command round-trip. Sprint 2 expands coverage to two additional interaction shapes (question/answer flow and multi-turn conversation) and adds cross-layer verification that ensures the browser DOM, API transcript, and database are all consistent after each scenario.

## What Changes

- Add question/answer flow test exercising AWAITING_INPUT state, option rendering via AskUserQuestion tool, user selection, and completion
- Add multi-turn conversation test exercising sequential command/response cycles with context retention
- Add cross-layer verification logic comparing DOM elements, API transcript (`/api/voice/agents/<id>/transcript`), and database records (Turn, Command models) for consistency
- Add timestamp ordering verification ensuring monotonic ordering across API and DB layers
- Add screenshot capture for all new scenarios

## Impact

- Affected specs: testing (agent-driven integration tests)
- Affected code:
  - `tests/agent_driven/test_question_answer.py` (new)
  - `tests/agent_driven/test_multi_turn.py` (new)
  - `tests/agent_driven/conftest.py` (no changes expected, existing fixtures sufficient)
  - `tests/e2e/helpers/voice_assertions.py` (no changes expected, existing API sufficient)
- Existing test infrastructure:
  - `claude_session` fixture (from Sprint 1) - used unchanged
  - `e2e_test_db`, `e2e_app`, `e2e_server` fixtures - used unchanged
  - `VoiceAssertions` helper - used unchanged
- API endpoints consumed (read-only, no changes):
  - `/api/voice/agents/<id>/transcript` (cross-layer verification)
  - `/api/voice/command` (sending commands via voice chat)
- Related OpenSpec history:
  - `integration-testing-framework` (archived 2026-01-30)
  - `e7-s1-agent-driven-integration-testing` (archived 2026-02-19)
