## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Helper Extraction (FR15)

- [x] 2.1 Create `tests/agent_driven/helpers/__init__.py`
- [x] 2.2 Create `tests/agent_driven/helpers/cross_layer.py` -- extract `verify_cross_layer_consistency` from Sprint 2 tests into a shared plain function
- [x] 2.3 Create `tests/agent_driven/helpers/output.py` -- structured test output helper (scenario name, step progress, elapsed time)
- [x] 2.4 Refactor `test_question_answer.py` to use shared cross-layer helper
- [x] 2.5 Refactor `test_multi_turn.py` to use shared cross-layer helper
- [x] 2.6 Optionally refactor other test files to use shared helpers where applicable

### Permission Approval Flow (FR16)

- [x] 2.7 Create `tests/agent_driven/test_permission_approval.py`
  - Send prompt that triggers a tool permission request
  - Assert AWAITING_INPUT state reached with permission context
  - Detect permission-related UI element or tmux pane content
  - Approve permission via voice chat or tmux
  - Assert command reaches COMPLETE state
  - Assert result rendered in voice chat
  - Include cross-layer verification
  - Capture screenshots at each stage

### Bug-Driven Scenario (FR17)

- [x] 2.8 Identify a real bug that survived mock-based testing (document commit hash/issue/description)
- [x] 2.9 Create bug-driven test file (e.g., `tests/agent_driven/test_bug_<name>.py`)
  - Document which bug it targets
  - Exercise the specific code path the bug affected
  - Would have caught the bug if it existed at the time

### Structured Test Output (FR19)

- [x] 2.10 Integrate structured output into new tests (scenario name, step progress, elapsed time)
- [x] 2.11 Optionally add structured output to existing Sprint 1+2 tests

### Format Evaluation (FR20)

- [x] 2.12 Evaluate whether declarative YAML scenario format adds value
  - If yes: implement minimal version using yaml.safe_load
  - If no: document decision in tests/agent_driven/ README or inline
  - Either way: every scenario must remain writable as plain pytest

### pytest Discovery (FR18)

- [x] 2.13 Verify all agent-driven tests are discoverable via `pytest tests/agent_driven/`

## 3. Testing (Phase 3)

- [ ] 3.1 Run permission approval test against real Claude Code session -- passes
- [ ] 3.2 Run bug-driven scenario against real Claude Code session -- passes
- [ ] 3.3 Run full suite `pytest tests/agent_driven/` -- all scenarios pass together
- [ ] 3.4 Verify at least 5 total scenarios exist and pass
- [ ] 3.5 Verify shared helpers are used by at least 3 tests
- [ ] 3.6 Verify structured test output shows scenario progress
- [ ] 3.7 Verify format evaluation is documented

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Sprint gate criteria met (all checkboxes in PRD Section 6)
