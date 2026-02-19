## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [x] 2.1 Create `tests/agent_driven/` directory
- [x] 2.2 Create `tests/agent_driven/conftest.py` with fixtures:
  - `claude_session` fixture (function-scoped): launch `claude` CLI in dedicated tmux pane with `--model haiku` and hooks pointing to test server URL, wait for session-start hook (poll DB for Agent record, 30s timeout), yield agent info, conditional teardown (kill tmux on success, preserve on failure)
  - Session isolation: unique tmux session name per test (`headspace-test-<uuid>`)
  - Working directory: project root (session correlator rejects /tmp)
  - Reuse `e2e_test_db` and `e2e_server` fixtures from `tests/e2e/conftest.py`
- [x] 2.3 Create `tests/agent_driven/test_simple_command.py`:
  - Navigate Playwright to voice chat UI on test server
  - Select agent card for the launched Claude Code session
  - Send deterministic command via `VoiceAssertions.send_chat_message()`: `"Create a file called /tmp/headspace_test_<uuid>.txt with the content hello"`
  - Wait for agent response bubble in DOM (`[data-turn-id]` with agent actor class, 60s timeout)
  - Verify command state transitions in DB: IDLE → COMMANDED → PROCESSING → COMPLETE
  - Structural assertions only — never assert on LLM response content

## 3. Testing (Phase 3)

- [x] 3.1 Execute `pytest tests/agent_driven/test_simple_command.py` against real Claude Code session
- [x] 3.2 Verify test passes with real hooks firing (not simulated)
- [x] 3.3 Verify Playwright drove voice chat UI (not tmux directly)
- [x] 3.4 Verify agent response bubble appeared in DOM
- [x] 3.5 Verify tmux session cleaned up on success
- [x] 3.6 Capture screenshots as proof of execution

## 4. Final Verification

- [x] 4.1 All tests passing against real Claude Code session
- [x] 4.2 Code budget: under 500 lines total across conftest + test file (222 lines)
- [x] 4.3 No new pip dependencies added
- [x] 4.4 No new classes created — fixtures are functions, assertions are inline
