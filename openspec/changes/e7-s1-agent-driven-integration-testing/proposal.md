## Why

Claude Headspace has ~2,500 tests but none exercise the real production loop — Claude Code session → hooks → SSE → browser. Bugs pass mock-based tests and only surface when a human uses the system. This change proves the fundamental mechanism with one end-to-end test that drives a real Claude Code session through the voice chat UI.

## What Changes

- New `tests/agent_driven/` directory for real-session integration tests
- `conftest.py` with `claude_session` fixture: launches real Claude Code in tmux, waits for session-start hook, conditional teardown
- `test_simple_command.py`: one test that sends a command via voice chat UI (Playwright), waits for agent response bubble, verifies state transitions in DB
- Uses existing E2E infrastructure: `e2e_test_db`, `e2e_server` fixtures, `VoiceAssertions` helper

## Impact

- Affected specs: testing
- Affected code:
  - `tests/agent_driven/conftest.py` (NEW)
  - `tests/agent_driven/test_simple_command.py` (NEW)
- No changes to existing source code — this is purely additive test infrastructure
- Reuses existing E2E fixtures from `tests/e2e/conftest.py`
- References patterns from `src/claude_headspace/services/tmux_bridge.py` for subprocess tmux operations
- References `tests/e2e/helpers/voice_assertions.py` for `VoiceAssertions.send_chat_message()`
- Related archived change: `integration-testing-framework` (2026-01-30) — established prior test patterns
- Recent voice chat commits (d5dcbf57, 61fd9be8, b477fdc8) stabilised the voice bridge and tmux bridge — this test validates that work
