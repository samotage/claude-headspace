# Proposal Summary: e7-s2-agent-driven-integration-testing

## Architecture Decisions
- Follow the existing Sprint 1 test pattern: pytest function with VoiceAssertions helper, explicit prompts, inline assertions
- Cross-layer verification implemented as a plain shared function (not a class or framework) since the DOM/API/DB comparison logic is identical across all scenarios
- No new fixtures or helpers beyond what Sprint 1 established; existing `claude_session`, `e2e_app`, `e2e_server` fixtures are sufficient
- AskUserQuestion selection done via tmux send-keys (Enter to select first option), matching the pattern established in `test_interactive_scenarios.py`

## Implementation Approach
- Create two new test files: `test_question_answer.py` and `test_multi_turn.py`
- Each test file is self-contained and independently readable per constraint C4
- Cross-layer verification logic is a plain function that can be called at the end of any scenario; it fetches the API transcript, queries the DB directly, scrapes DOM turn elements, and asserts consistency
- Structural assertions only (no LLM content assertions) per constraint C5
- Generous 60s timeouts for real LLM processing

## Files to Modify
- `tests/agent_driven/test_question_answer.py` (NEW) -- question/answer flow with AskUserQuestion
- `tests/agent_driven/test_multi_turn.py` (NEW) -- sequential command/response cycles
- No modifications to existing files expected

## Files Referenced (Read-Only)
- `tests/agent_driven/conftest.py` -- claude_session fixture, cleanup_stale_test_sessions
- `tests/agent_driven/test_simple_command.py` -- pattern reference for simple command test
- `tests/agent_driven/test_interactive_scenarios.py` -- pattern reference for AskUserQuestion via tmux
- `tests/agent_driven/test_advanced_scenarios.py` -- pattern reference for multi-turn context retention
- `tests/e2e/helpers/voice_assertions.py` -- VoiceAssertions helper class
- `src/claude_headspace/routes/voice_bridge.py` -- `/api/voice/agents/<id>/transcript` endpoint (lines 830-930)
- `src/claude_headspace/models/command.py` -- Command model and CommandState enum
- `src/claude_headspace/models/turn.py` -- Turn model, TurnActor, TurnIntent enums

## Acceptance Criteria
- Question/answer test passes: AskUserQuestion triggered, AWAITING_INPUT reached, option selected, COMPLETE state reached, bubbles rendered
- Multi-turn test passes: two sequential commands both reach COMPLETE, correct turn counts, bubbles in order, command separator visible
- Cross-layer verification passes on at least one scenario: DOM turn IDs match API transcript turn IDs, match DB Turn records; actor sequences consistent; command states correct
- Timestamp ordering verified: monotonically ascending in both API and DB
- Screenshots captured at each scenario stage
- All three scenarios (Sprint 1 simple command + Sprint 2 question/answer + multi-turn) pass together
- Reliability: pass on 3 consecutive runs without flaky failures

## Constraints and Gotchas
- **AskUserQuestion prompt must be very explicit:** The prompt must instruct Claude to use AskUserQuestion with specific named options; vague prompts may not trigger the tool
- **tmux send-keys timing:** After the question bubble appears, a small delay (1s) before sending Enter via tmux is needed to let the terminal UI settle
- **PROGRESS turns:** The API transcript filters out PROGRESS turns with empty text, and the DOM may contain intermediate "WORKING..." bubbles. Cross-layer verification must account for this filtering
- **Command separator detection:** The DOM renders command separators between command groups; these are not turns and should be excluded from turn count comparisons
- **Existing similar tests:** `test_interactive_scenarios.py` already tests AskUserQuestion and `test_advanced_scenarios.py` already tests multi-turn. The Sprint 2 tests differentiate by adding cross-layer verification
- **is_internal filter:** The transcript API filters `Turn.is_internal == False`; DB verification must apply the same filter for consistency
- **Haiku model:** All tests use `--model haiku` for cost control and faster processing

## Git Change History

### Related Files
- Tests: `tests/agent_driven/conftest.py`, `tests/agent_driven/test_simple_command.py`, `tests/agent_driven/test_interactive_scenarios.py`, `tests/agent_driven/test_advanced_scenarios.py`, `tests/agent_driven/test_tool_use_scenarios.py`, `tests/agent_driven/test_long_paste_input.py`
- Helpers: `tests/e2e/helpers/voice_assertions.py`
- Routes: `src/claude_headspace/routes/voice_bridge.py`
- Models: `src/claude_headspace/models/command.py`, `src/claude_headspace/models/turn.py`, `src/claude_headspace/models/agent.py`
- Services: `src/claude_headspace/services/hook_receiver.py`, `src/claude_headspace/services/command_lifecycle.py`, `src/claude_headspace/services/state_machine.py`, `src/claude_headspace/services/tmux_bridge.py`

### OpenSpec History
- `integration-testing-framework` (archived 2026-01-30) -- initial testing infrastructure
- `e7-s1-agent-driven-integration-testing` (archived 2026-02-19) -- Sprint 1: prove the loop with simple command test

### Implementation Patterns
- Tests follow the structure: setup VoiceAssertions -> navigate to voice chat -> select agent -> send command -> wait for bubble -> assert state -> capture screenshot
- AskUserQuestion flow: send explicit prompt -> wait for question bubble -> send Enter via tmux -> wait for response bubble
- Multi-turn flow: send command 1 -> wait for completion -> record bubble count -> send command 2 -> wait for new bubble beyond previous count
- DB verification: use `e2e_app.app_context()` to query Command and Turn models directly

## Q&A History
- No clarifications were needed. The PRD is well-specified and consistent with the existing codebase.
- The gap detection flagged a missing "Context & Purpose" section, which is a false positive -- the PRD uses "Executive Summary" + "Context" sections that serve the same purpose.

## Dependencies
- No new pip packages required (NFR6)
- No external services beyond what Sprint 1 already uses (Claude Code CLI, tmux, test Flask server)
- No database migrations needed

## Testing Strategy
- Each new test file must pass individually against a real Claude Code session
- All three scenarios (Sprint 1 + Sprint 2) must pass together in a single pytest run
- Cross-layer verification must pass on at least one scenario
- Reliability gate: 3 consecutive passing runs
- Run with: `pytest tests/agent_driven/ -m agent_driven --timeout=300`

## OpenSpec References
- proposal.md: openspec/changes/e7-s2-agent-driven-integration-testing/proposal.md
- tasks.md: openspec/changes/e7-s2-agent-driven-integration-testing/tasks.md
- spec.md: openspec/changes/e7-s2-agent-driven-integration-testing/specs/testing/spec.md
