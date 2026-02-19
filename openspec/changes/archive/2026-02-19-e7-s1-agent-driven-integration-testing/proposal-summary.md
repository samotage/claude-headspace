# Proposal Summary: e7-s1-agent-driven-integration-testing

## Architecture Decisions
- Create a new `tests/agent_driven/` directory — separate from existing `tests/e2e/` to keep agent-driven tests distinct
- Reuse `e2e_test_db` and `e2e_server` fixtures from `tests/e2e/conftest.py` via imports — avoid duplicating database/server setup
- Use `subprocess` for all tmux operations (consistent with `src/claude_headspace/services/tmux_bridge.py`) — no `libtmux` dependency
- No new classes — fixtures are functions, assertions are inline
- Target the real running server via `config.yaml` `server.application_url`

## Implementation Approach
- Build a `claude_session` pytest fixture that launches a real `claude` CLI in a tmux pane with hooks pointing to the test server
- Implement a ready gate that polls DB for Agent record created by the session-start hook
- Write one test: send command via voice chat UI (Playwright) → wait for response bubble → verify DB state transitions
- Conditional teardown: kill tmux on success, preserve everything on failure
- Code budget: 500 lines maximum across both files

## Files to Modify
- `tests/agent_driven/__init__.py` (NEW — empty package marker)
- `tests/agent_driven/conftest.py` (NEW — `claude_session` fixture + helpers)
- `tests/agent_driven/test_simple_command.py` (NEW — single test function)

## Acceptance Criteria
- Test executes against a real Claude Code session (not mocked)
- Playwright drives the voice chat UI to send the command (not tmux directly)
- Agent response bubble appears in the voice chat DOM
- Command state transitions verified in DB (COMMANDED → PROCESSING → COMPLETE)
- Tmux session cleaned up on success, preserved on failure
- Test passes with screenshots captured

## Constraints and Gotchas
- **Race condition — respond_inflight:** When voice chat sends a command, `voice_bridge.py` sets `respond_inflight` flag BEFORE tmux send. When Claude Code's `user-prompt-submit` hook fires later, `hook_receiver.py` checks this flag to avoid duplicate USER turns. Tests must account for this timing.
- **Hooks endpoint:** Claude CLI hooks must point to the test server URL (random port from `e2e_server`), NOT the production server. Use `--hooks-endpoint` flag or environment variable.
- **TLS:** Playwright needs `--ignore-https-errors` for Tailscale TLS certs on the real server.
- **Working directory:** Use a temp directory for the Claude session to avoid polluting real projects. However, session correlator rejects `/tmp` paths — use a real-looking project path or the test project directory.
- **Cost control:** Use `--model haiku` and a short deterministic prompt (`"Create a file called /tmp/headspace_test_<uuid>.txt with the content hello"`).
- **Structural assertions only:** Never assert on LLM response content. Assert: turn exists, correct actor, state reached expected value, bubble has `data-turn-id`.
- **Generous timeouts:** 60s default per interaction — real LLM processing is slow.
- **No new dependencies:** Use subprocess for tmux (no libtmux).

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/tmux_bridge.py` (tmux operation patterns)
- Routes: `src/claude_headspace/routes/voice_bridge.py` (POST /api/voice/command)
- Routes: `src/claude_headspace/routes/hooks.py` (hook endpoints)
- Services: `src/claude_headspace/services/hook_receiver.py` (hook processing)
- Services: `src/claude_headspace/services/broadcaster.py` (SSE events)
- Tests: `tests/e2e/conftest.py` (e2e_test_db, e2e_server, voice_page fixtures)
- Tests: `tests/e2e/helpers/voice_assertions.py` (VoiceAssertions class)
- Tests: `tests/e2e/helpers/hook_simulator.py` (hook payload reference)

### OpenSpec History
- `integration-testing-framework` (archived 2026-01-30) — established prior test patterns for this subsystem

### Implementation Patterns
- Test infrastructure follows: conftest fixtures → test files → helpers pattern
- Tmux operations use subprocess (consistent with tmux_bridge.py)
- E2E fixtures use session-scoped database, function-scoped cleanup
- Voice assertions use Playwright `expect()` with domain-specific methods

## Q&A History
- No clarification needed — PRD was precise and internally consistent
- Gap flagged by validator ("missing context_purpose section") was a false positive — section exists under "1. Context" heading

## Dependencies
- No new pip dependencies required
- Requires `claude` CLI installed and available on PATH
- Requires `tmux` installed
- Requires Playwright browsers installed (`npx playwright install`)
- Requires `claude_headspace_test` database

## Testing Strategy
- Execute `pytest tests/agent_driven/test_simple_command.py` against real Claude Code session
- Verify with screenshots showing voice chat UI interaction
- Verify DB state transitions via direct query
- Sprint gate: test must pass with real session, real hooks, real SSE, real DOM

## OpenSpec References
- proposal.md: openspec/changes/e7-s1-agent-driven-integration-testing/proposal.md
- tasks.md: openspec/changes/e7-s1-agent-driven-integration-testing/tasks.md
- spec.md: openspec/changes/e7-s1-agent-driven-integration-testing/specs/testing/spec.md
