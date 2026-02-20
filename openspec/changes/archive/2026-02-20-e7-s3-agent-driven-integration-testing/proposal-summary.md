# Proposal Summary: e7-s3-agent-driven-integration-testing

## Architecture Decisions
- Extract the `verify_cross_layer_consistency` function (currently duplicated in test_question_answer.py and test_multi_turn.py) into `tests/agent_driven/helpers/cross_layer.py` as a shared plain function
- Create a structured output helper in `tests/agent_driven/helpers/output.py` that wraps test steps with scenario name, step progress, and timing
- Helpers must be plain functions only -- no base classes, decorators, or metaclasses (constraint C6)
- Permission approval flow uses the same tmux-based interaction pattern as AskUserQuestion (established in Sprint 2)
- Format evaluation is a deliberate decision point, not a pre-determined outcome

## Implementation Approach
- Phase 1: Extract helpers from existing Sprint 2 tests, then refactor those tests to use the shared helpers
- Phase 2: Implement new scenarios (permission approval, bug-driven) using the shared helpers from Phase 1
- Phase 3: Add structured output, evaluate declarative format, document decision
- Each test file remains self-contained and independently readable
- Bug-driven scenario must reference a real bug -- review commit history for candidates (voice chat ordering bugs, optimistic bubble promotion failures, respond_inflight race conditions)

## Files to Modify
- `tests/agent_driven/helpers/__init__.py` (NEW)
- `tests/agent_driven/helpers/cross_layer.py` (NEW -- extracted from Sprint 2)
- `tests/agent_driven/helpers/output.py` (NEW -- structured test output)
- `tests/agent_driven/test_permission_approval.py` (NEW)
- `tests/agent_driven/test_bug_<name>.py` (NEW -- at least one)
- `tests/agent_driven/test_question_answer.py` (MODIFIED -- use shared helpers)
- `tests/agent_driven/test_multi_turn.py` (MODIFIED -- use shared helpers)
- `tests/agent_driven/test_simple_command.py` (POSSIBLY MODIFIED)
- `tests/agent_driven/conftest.py` (POSSIBLY MODIFIED)

## Acceptance Criteria
- Shared helpers extracted and used by at least 3 test files
- Permission approval test passes: permission triggered, AWAITING_INPUT reached, approved, COMPLETE state, result rendered
- At least one bug-driven scenario passes with documented bug reference
- Structured test output shows scenario name, step progress, elapsed time
- Format evaluation documented with clear decision
- All scenarios (Sprint 1+2+3) pass together in single pytest run
- At least 5 total scenarios exist and pass
- Any developer can read any test file and understand it

## Constraints and Gotchas
- **Permission flow mechanics:** Need to investigate how voice chat handles permission requests. The `permission_summarizer.py` service and `voice_bridge.py` picker detection (lines 305-385) are relevant. If voice chat renders interactive elements, use Playwright; if not, fall back to tmux pane capture and key-based approval
- **Bug selection:** Must reference a real bug. Candidates from commit history: voice chat ordering (74a8892), respond_inflight race conditions (f91c9ec5), hook deduplication edge cases. Need to verify which bugs lack automated test coverage
- **Helper extraction scope:** Only extract patterns that appear identically in 3+ tests. The cross-layer verification function is the primary candidate since it's duplicated in test_question_answer.py and test_multi_turn.py and will be used by new tests
- **Structured output must not break pytest:** Output should use print() or pytest's capsys, not interfere with pytest's own output capture
- **Format evaluation is genuinely open-ended:** The PRD allows either "yes, implement minimal YAML" or "no, document why not." Both are valid outcomes
- **Existing tests already have comprehensive patterns:** test_interactive_scenarios.py and test_advanced_scenarios.py from Sprint 1 also exist and may benefit from helper extraction

## Git Change History

### Related Files
- Tests: `tests/agent_driven/conftest.py`, `tests/agent_driven/test_simple_command.py`, `tests/agent_driven/test_question_answer.py`, `tests/agent_driven/test_multi_turn.py`, `tests/agent_driven/test_interactive_scenarios.py`, `tests/agent_driven/test_advanced_scenarios.py`, `tests/agent_driven/test_tool_use_scenarios.py`, `tests/agent_driven/test_long_paste_input.py`
- Helpers: `tests/e2e/helpers/voice_assertions.py`
- Routes: `src/claude_headspace/routes/voice_bridge.py` (permission handling, picker detection lines 305-385)
- Services: `src/claude_headspace/services/permission_summarizer.py`, `src/claude_headspace/services/hook_receiver.py`
- Models: `src/claude_headspace/models/command.py`, `src/claude_headspace/models/turn.py`

### OpenSpec History
- `integration-testing-framework` (archived 2026-01-30) -- initial testing infrastructure
- `e7-s1-agent-driven-integration-testing` (archived 2026-02-19) -- Sprint 1: prove the loop
- `e7-s2-agent-driven-integration-testing` (archived 2026-02-19) -- Sprint 2: scenario expansion + cross-layer verification

### Implementation Patterns
- Tests follow: setup VoiceAssertions -> navigate to voice chat -> select agent -> send command -> wait for bubble -> assert state -> capture screenshot
- Cross-layer verification: collect DOM turn IDs -> fetch API transcript -> query DB -> compare all three layers -> verify timestamp ordering
- Permission flow (new): send prompt triggering permission -> detect permission UI -> approve -> wait for completion
- Structured output: wrap each test step with timing and progress reporting

## Q&A History
- No clarifications needed. The PRD is well-specified and builds naturally on Sprint 1+2 infrastructure.
- The gap detection flagged a missing "Context & Purpose" section -- false positive (PRD uses "Executive Summary" + "Context").

## Dependencies
- No new pip packages required (NFR6)
- No external services beyond Sprint 1+2 infrastructure
- No database migrations needed

## Testing Strategy
- Each new test file passes individually against real Claude Code session
- All scenarios (Sprint 1+2+3) pass together: `pytest tests/agent_driven/`
- At least 5 total scenarios
- Shared helpers used by at least 3 tests
- Structured output visible during test execution
- Format evaluation documented

## OpenSpec References
- proposal.md: openspec/changes/e7-s3-agent-driven-integration-testing/proposal.md
- tasks.md: openspec/changes/e7-s3-agent-driven-integration-testing/tasks.md
- spec.md: openspec/changes/e7-s3-agent-driven-integration-testing/specs/testing/spec.md
