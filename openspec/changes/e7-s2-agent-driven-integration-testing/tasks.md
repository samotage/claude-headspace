## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Question/Answer Flow Test (FR9)

- [ ] 2.1 Create `tests/agent_driven/test_question_answer.py`
  - Navigate to voice chat, select agent card
  - Send prompt that triggers AskUserQuestion with options
  - Assert AWAITING_INPUT state reached in database
  - Assert question bubble rendered in voice chat DOM
  - Assert option buttons visible in the question bubble
  - Select an option via tmux send-keys (Enter)
  - Assert command reaches COMPLETE state
  - Assert response bubble rendered after option selection
  - Capture screenshots at each stage

### Multi-Turn Conversation Test (FR10)

- [ ] 2.2 Create `tests/agent_driven/test_multi_turn.py`
  - Navigate to voice chat, select agent card
  - Send first command, wait for completion
  - Send second command, wait for completion
  - Assert both commands reach COMPLETE state in DB
  - Assert correct number of user and agent turns in DB
  - Assert all bubbles rendered in correct order in DOM
  - Assert command separator visible between command groups
  - Capture screenshots at each stage

### Cross-Layer Verification (FR11, FR12, FR13)

- [ ] 2.3 Implement cross-layer verification logic
  - DOM/API consistency: fetch `/api/voice/agents/<id>/transcript`, compare turn count, turn IDs, and actor sequence against DOM `.chat-bubble[data-turn-id]` elements
  - DOM/DB consistency: query Turn and Command models directly, compare turn_id presence and command states against DOM
  - Timestamp ordering: verify turns are monotonically ordered by timestamp in both API response and DB query
  - Implement as inline verification steps or a shared plain function if identical across tests

- [ ] 2.4 Add cross-layer verification to question/answer test
- [ ] 2.5 Add cross-layer verification to multi-turn test
- [ ] 2.6 Add cross-layer verification to existing simple command test (optional, at least one scenario required)

### Screenshot Capture (FR14)

- [ ] 2.7 Ensure screenshot capture at each scenario stage (before/after key interactions)

## 3. Testing (Phase 3)

- [ ] 3.1 Run question/answer test against real Claude Code session — passes
- [ ] 3.2 Run multi-turn test against real Claude Code session — passes
- [ ] 3.3 Run all three scenarios (simple command + question/answer + multi-turn) together — all pass
- [ ] 3.4 Verify cross-layer verification runs and passes on at least one scenario
- [ ] 3.5 Verify timestamp ordering passes
- [ ] 3.6 Verify screenshots captured for all scenarios
- [ ] 3.7 Reliability check: all three scenarios pass on at least 3 consecutive runs

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Sprint gate criteria met (all checkboxes in PRD Section 6)
