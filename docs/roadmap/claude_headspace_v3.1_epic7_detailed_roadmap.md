# Epic 7 Detailed Roadmap: Agent-Driven Integration Testing

**Project:** Claude Headspace v3.1  
**Epic:** Epic 7 — Agent-Driven Integration Testing  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-02-20

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 7 implementation. It breaks Epic 7 into 3 sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem. This roadmap is designed to grow as new ideas emerge — additional sprints will be appended as they are scoped and workshopped.

**Epic 7 Goal:** Establish a testing infrastructure that exercises the real production loop — real Claude Code sessions, real hooks, real SSE, real browser rendering — eliminating the gap between mock-based tests and production behavior.

**Epic 7 Value Proposition:**

- **Real Production Loop Testing** — Tests drive actual Claude Code sessions through the voice chat UI via Playwright, with real hooks firing, real SSE updating the browser, and structural assertions verifying the rendered result
- **Cross-Layer Verification** — Ensures the browser DOM, API transcript, and database are all consistent at the end of each scenario
- **Bug-Driven Scenarios** — Tests targeting real bugs that survived mock-based testing, preventing regression
- **Pattern Extraction** — Shared helpers extracted from proven patterns, not speculative abstractions

**The Differentiator:** Claude Headspace has ~2,500 tests across unit, route, integration, and E2E tiers — but they all use mocked or simulated hooks. No test currently exercises the real production loop. Bugs that pass mock-based tests continue to ship and break the system. Epic 7 closes this gap by proving that the full voice chat → Claude Code → hooks → SSE → browser roundtrip works correctly.

**The Loop Under Test:**

```
Playwright (voice chat UI)
    → user types command in chat input
    → POST /api/voice/command
    → voice_bridge.py resolves agent → tmux_bridge.send_text()
    → tmux send-keys delivers text to real Claude Code PTY
    → Claude Code processes (real LLM, real tools)
    → Claude Code fires hooks back to /hook/* endpoints
    → hook_receiver processes → state transition → DB write → broadcaster.broadcast()
    → SSE event delivered to browser
    → voice-sse-handler.js renders response bubble
    → Playwright asserts on rendered DOM
```

Every layer is real. Nothing is mocked.

**Success Criteria:**

- Run `pytest tests/agent_driven/test_simple_command.py` → real Claude Code session launches, processes command, test passes
- Simple command test proves the fundamental mechanism works
- Question/answer test exercises AWAITING_INPUT state and option selection
- Multi-turn test verifies sequential command/response cycles
- Cross-layer verification confirms DOM, API, and DB consistency
- Permission approval flow test exercises permission request handling
- Bug-driven scenarios catch regressions that mock-based tests miss
- All scenarios pass reliably (3+ consecutive runs without flaky failures)

**Architectural Foundation:** Builds on Epic 6's voice bridge (E6-S1, E6-S2), agent chat history (E6-S3), and tmux bridge (E5-S4). Leverages existing E2E infrastructure (Playwright, test database fixtures).

**Dependency:** Epic 6 must be complete before Epic 7 begins (voice bridge server, voice bridge client, and agent chat history must exist).

---

## Epic 7 Story Mapping

| Story ID | Story Name                                              | Subsystem                    | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------------------- | ---------------------------- | ------------- | ------ | -------- |
| E7-S1    | Prove the loop — one test, full roundtrip               | `agent-driven-testing-core`  | test/         | 1      | P1       |
| E7-S2    | Scenario expansion + cross-layer verification           | `agent-driven-testing-expand`| test/         | 2      | P1       |
| E7-S3    | Pattern extraction + library expansion                  | `agent-driven-testing-lib`   | test/         | 3      | P1       |

---

## Sprint Breakdown

### Sprint 1: Prove the Loop (E7-S1)

**Goal:** Prove the fundamental mechanism: one test that drives a real Claude Code session through the voice chat UI via Playwright, with real hooks firing, real SSE updating the browser, and structural assertions verifying the rendered result.

**Duration:** 1-2 weeks  
**Dependencies:** Epic 6 complete (voice bridge server, voice bridge client, agent chat history)

**This is the hardest sprint.** If this works, everything else is incremental.

**Deliverables:**

**Session Launch Fixture:**

- `claude_session` pytest fixture launches a `claude` CLI session in a dedicated tmux pane
- Hooks configured to point to the test server URL
- Uses Haiku model for cost control
- Each test scenario runs in its own tmux session with a unique name

**Ready Gate:**

- Fixture waits for `session-start` hook to arrive at the test server
- Verified by polling DB for a new Agent record
- Claude Code session confirmed healthy and ready to receive prompts
- Timeout: 30 seconds

**Conditional Teardown:**

- On test success: tmux session killed, test database cleaned
- On test failure: tmux session preserved, database state preserved, screenshots saved

**Voice Chat Integration:**

- Test navigates Playwright to voice chat UI on the test server
- Selects the agent card
- Sends a command using existing `VoiceAssertions.send_chat_message()` method

**Structural Response Assertion:**

- Waits for agent response bubble to appear in voice chat DOM
- Structural assertion: any element with `data-turn-id` and agent actor class
- Timeout: 60 seconds (configurable)

**State Transition Assertion:**

- Verifies command state transitioned through expected path
- IDLE → COMMANDED → PROCESSING → COMPLETE
- Queries database directly

**Subsystem Requiring PRD:**

1. `agent-driven-testing-core` — Session fixture, ready gate, conditional teardown, voice chat integration, structural assertions

**PRD Location:** `docs/prds/test/done/e7-s1-agent-driven-integration-testing-prd.md`

**Stories:**

- E7-S1: Prove the loop — one test, full voice chat → Claude Code → hooks → SSE → browser roundtrip

**Technical Decisions Made:**

- Use `subprocess` for tmux operations (consistent with existing `tmux_bridge.py`) — **decided**
- No new pip dependencies — **decided**
- Structural assertions only (never assert on LLM response content) — **decided**
- Target the real running server (URL from `config.yaml`) — **decided**
- Haiku model with short, deterministic prompts for cost control — **decided**
- `claude_headspace_test` database only — **decided**

**Agent Implementation Constraints:**

- Code budget: 500 lines maximum across conftest + test file
- No new classes — session fixture is a function
- No fixture format, no runner, no scenario abstraction
- Use `subprocess` for tmux operations
- Do not restructure existing E2E fixtures
- Structural assertions only
- Must execute against a real Claude Code session

**Test Prompt:**

```
"Create a file called /tmp/headspace_test_<uuid>.txt with the content hello"
```

**Risks:**

- Claude Code session startup time (mitigated: 30s ready gate timeout)
- LLM response variability (mitigated: structural assertions only, not content)
- tmux pane cleanup on failure (mitigated: conditional teardown preserves evidence)

**Acceptance Criteria:**

- [ ] Test executed against a real Claude Code session (not mocked)
- [ ] Playwright drove the voice chat UI to send the command (not tmux directly)
- [ ] Agent response bubble appeared in the voice chat DOM
- [ ] Test passed with screenshots captured
- [ ] tmux session cleaned up on success
- [ ] tmux session preserved on failure for investigation

---

### Sprint 2: Scenario Expansion + Cross-Layer Verification (E7-S2)

**Goal:** Expand to three reliable scenarios covering different interaction shapes and add cross-layer verification that ensures the browser DOM, API transcript, and database are all consistent.

**Duration:** 1-2 weeks  
**Dependencies:** E7-S1 complete (Sprint 1 gate passed)

**Deliverables:**

**Question/Answer Flow Test:**

- Sends prompt that triggers Claude Code to use `AskUserQuestion`
- Asserts AWAITING_INPUT state reached in database
- Asserts question bubble rendered in voice chat DOM
- Asserts option buttons visible in the question bubble
- User clicks an option via Playwright
- Asserts command reaches COMPLETE state
- Asserts response bubble rendered after option selection

**Multi-Turn Conversation Test:**

- Sends command via voice chat, waits for completion
- Sends second command
- Asserts both round-trips complete (both commands reach COMPLETE)
- Asserts correct number of user turns and agent turns in DB
- Asserts all bubbles rendered in correct order
- Asserts command separator visible between command groups

**Cross-Layer Verification:**

- DOM/API Consistency: fetches API transcript endpoint, compares against voice chat DOM
  - Same number of turns
  - Same turn IDs present
  - Same actor sequence (USER, AGENT, USER, AGENT, ...)
- DOM/DB Consistency: queries database directly, compares against voice chat DOM
  - Turn records match bubbles by `turn_id`
  - Command records reflect final state (COMPLETE)
  - Agent record exists with correct project association
- Timestamp Ordering: turns monotonically ordered by timestamp (no out-of-order turns)

**Screenshot Capture:**

- Every scenario captures before/after screenshots via Playwright
- Screenshots saved to test-run-specific directory

**Subsystem Requiring PRD:**

2. `agent-driven-testing-expand` — Question/answer flow, multi-turn conversation, cross-layer verification

**PRD Location:** `docs/prds/test/done/e7-s2-agent-driven-integration-testing-prd.md`

**Stories:**

- E7-S2: Scenario expansion + cross-layer verification

**Technical Decisions Made:**

- Extract helpers only if EXACT same code appears in 3+ tests — **decided**
- Cross-layer verification can be a shared function if identical across scenarios — **decided**
- Each test file must be independently readable — **decided**
- Structural assertions only — **decided**

**Agent Implementation Constraints:**

- Extract helpers only if the EXACT same code appears in 3+ tests
- No fixture format — scenarios remain pytest functions
- Cross-layer verification can be a shared function if identical
- Each test file must be independently readable
- Structural assertions only
- Must execute against real Claude Code sessions

**Triggering AskUserQuestion:**

```
"Ask me what format I want the output in using AskUserQuestion with options: JSON, YAML, CSV"
```

**Risks:**

- AskUserQuestion tool invocation reliability (mitigated: explicit prompt instruction)
- Multi-turn state management (mitigated: each command creates its own Command record)
- Cross-layer timing (mitigated: verification runs after scenario completion)

**Acceptance Criteria:**

- [ ] All three scenarios (simple command, question/answer, multi-turn) pass against real Claude Code sessions
- [ ] Cross-layer verification (DOM vs API vs DB) runs and passes on at least one scenario
- [ ] Timestamp ordering verified
- [ ] Screenshots captured for all scenarios
- [ ] Tests reliable — pass on at least 3 consecutive runs without flaky failures

---

### Sprint 3: Pattern Extraction + Library Expansion (E7-S3)

**Goal:** Extract proven patterns into reusable helpers, add scenarios driven by real bugs and permission flows, and evaluate whether a declarative scenario format would reduce duplication.

**Duration:** 1-2 weeks  
**Dependencies:** E7-S2 complete (Sprint 2 gate passed)

**Deliverables:**

**Shared Helpers:**

- Common patterns proven across Sprint 1+2 extracted into `tests/agent_driven/helpers/`
- At minimum:
  - Session readiness waiting (poll DB for agent)
  - Cross-layer verification (DOM vs API vs DB)
  - Screenshot capture with consistent naming

**Permission Approval Flow Test:**

- Sends prompt that triggers a tool permission request
- Asserts AWAITING_INPUT state reached with permission context
- Asserts permission-related UI element rendered
- Permission approved via voice chat (or tmux if voice chat doesn't expose permission controls)
- Asserts command reaches COMPLETE state
- Asserts result rendered in voice chat

**Bug-Driven Scenarios:**

- At least one new scenario based on a real bug that was caught by manual testing but passed all existing automated tests
- Documents which bug it targets (commit hash, issue number, or description)
- Exercises the specific code path that the bug affected
- Would have caught the bug if it had existed at the time

**Structured Test Output:**

- Each test produces clear output indicating:
  - Scenario name
  - Each step executing (e.g., "Sending command...", "Waiting for response bubble...")
  - Pass/fail per assertion
  - Total elapsed time
  - Cost estimate (model + approximate token count) if available

**Scenario Format Evaluation:**

- After implementing helpers and new scenarios, evaluate whether declarative YAML format adds value
- If yes: implement minimal version using `yaml.safe_load`, no custom parser
- If no: document why in test directory README
- Either way: every scenario must remain writable as a plain pytest function

**pytest Discovery:**

- All agent-driven tests discoverable and runnable via standard pytest commands:
  - `pytest tests/agent_driven/` — runs all scenarios
  - `pytest tests/agent_driven/test_simple_command.py` — runs one scenario
  - `pytest tests/agent_driven/ -k question` — selects by keyword

**Subsystem Requiring PRD:**

3. `agent-driven-testing-lib` — Shared helpers, permission flow, bug-driven scenarios, format evaluation

**PRD Location:** `docs/prds/test/done/e7-s3-agent-driven-integration-testing-prd.md`

**Stories:**

- E7-S3: Pattern extraction + library expansion

**Technical Decisions Made:**

- Helpers must be plain functions (no base classes, no inheritance, no metaclasses) — **decided**
- If declarative format implemented, must use standard YAML (`yaml.safe_load`) — **decided**
- Every scenario must also be writable as a plain pytest function — **decided**
- Bug-driven scenarios must reference actual bugs — **decided**

**Agent Implementation Constraints:**

- Helpers must be plain functions
- If declarative format implemented, use standard YAML only
- Every scenario must also be writable as a plain pytest function
- Structural assertions only
- Must execute all scenarios against real Claude Code sessions
- Bug-driven scenarios must reference actual bugs (cite commit, issue, or exact failure)

**Bug-Driven Scenario Candidates:**

- Voice chat ordering bugs (commit `74a8892` on `feature/voice-chat-ordering-remediation`)
- Optimistic bubble promotion failures
- respond_inflight race conditions
- Hook deduplication edge cases

**Risks:**

- Permission flow depends on voice chat UI handling (mitigated: tmux fallback)
- Bug-driven scenarios require identifying actual bugs (mitigated: review recent bug fixes)
- Declarative format may add complexity without benefit (mitigated: evaluation with clear decision criteria)

**Acceptance Criteria:**

- [ ] All scenarios (Sprint 1 + Sprint 2 + Sprint 3) pass together in a single `pytest tests/agent_driven/` run
- [ ] At least 5 total scenarios exist and pass
- [ ] Shared helpers extracted and used by at least 3 tests
- [ ] Scenario format evaluation documented with clear decision
- [ ] A developer unfamiliar with the framework can read any test file and understand what it does
- [ ] Structured test output shows scenario progress during execution

---

## Sprint Dependencies & Sequencing

```
E7-S1 (Prove the Loop)
   │
   └──▶ E7-S2 (Scenario Expansion + Cross-Layer Verification)
           │
           └──▶ E7-S3 (Pattern Extraction + Library Expansion)
```

**Critical Path:** E7-S1 → E7-S2 → E7-S3

**Rationale:**

- E7-S1 proves the fundamental mechanism — cannot expand scenarios without proving the loop works
- E7-S2 expands to multiple scenarios — cannot extract patterns without multiple proven scenarios
- E7-S3 extracts patterns and adds advanced scenarios — requires proven patterns from S1+S2

**Hard Gates:**

- Sprint 2 cannot begin until Sprint 1 gate passes
- Sprint 3 cannot begin until Sprint 2 gate passes

---

## Cross-Epic Dependencies

```
Epic 5 (Voice Bridge & Project Enhancement)
   │
   ├── E5-S4 (tmux Bridge) ─────────────────────────┐
   └── E5-S8 (CLI tmux Alignment) ──────────────────┤
                                                     │
Epic 6 (Voice Bridge & Agent Chat)                   │
   │                                                 │
   ├── E6-S1 (Voice Bridge Server) ─────────────────┤
   ├── E6-S2 (Voice Bridge Client) ─────────────────┤
   └── E6-S3 (Agent Chat History) ──────────────────┤
                                                     │
                                                     ▼
                                              Epic 7 (Agent-Driven Integration Testing)
                                                     │
                                                     ├── E7-S1 (Prove the Loop)
                                                     ├── E7-S2 (Scenario Expansion)
                                                     └── E7-S3 (Pattern Extraction)
```

Epic 5's tmux bridge and Epic 6's voice bridge infrastructure are leveraged by E7 for driving Claude Code sessions and sending commands through the voice chat UI.

---

## Acceptance Test Cases

### Test Case 1: Simple Command Roundtrip

**Setup:** Server running, test database clean, no active agents.

**Success:**

- ✅ Run `pytest tests/agent_driven/test_simple_command.py`
- ✅ Claude Code session launches in tmux pane
- ✅ Ready gate passes (Agent record appears in DB)
- ✅ Playwright navigates to voice chat UI
- ✅ Command sent via voice chat input
- ✅ Agent response bubble appears in DOM
- ✅ Command state transitions verified (IDLE → COMMANDED → PROCESSING → COMPLETE)
- ✅ Test passes, tmux session cleaned up
- ✅ Screenshot captured

### Test Case 2: Question/Answer Flow

**Setup:** Server running, test database clean, no active agents.

**Success:**

- ✅ Run `pytest tests/agent_driven/test_question_answer.py`
- ✅ Prompt triggers AskUserQuestion tool
- ✅ AWAITING_INPUT state reached
- ✅ Question bubble with options rendered
- ✅ Option clicked via Playwright
- ✅ Command reaches COMPLETE state
- ✅ Response bubble rendered
- ✅ Cross-layer verification passes

### Test Case 3: Multi-Turn Conversation

**Setup:** Server running, test database clean, no active agents.

**Success:**

- ✅ Run `pytest tests/agent_driven/test_multi_turn.py`
- ✅ First command sent and completed
- ✅ Second command sent and completed
- ✅ Correct turn count in database
- ✅ All bubbles rendered in correct order
- ✅ Command separator visible
- ✅ Timestamp ordering verified

### Test Case 4: Permission Approval Flow

**Setup:** Server running, test database clean, no active agents.

**Success:**

- ✅ Run `pytest tests/agent_driven/test_permission_approval.py`
- ✅ Prompt triggers permission request
- ✅ AWAITING_INPUT state with permission context
- ✅ Permission approved
- ✅ Command completes
- ✅ Result rendered

### Test Case 5: Full Suite Execution

**Setup:** Server running, test database clean.

**Success:**

- ✅ Run `pytest tests/agent_driven/`
- ✅ All 5+ scenarios execute sequentially
- ✅ All scenarios pass
- ✅ Structured output shows progress for each scenario
- ✅ Total elapsed time reported
- ✅ No flaky failures on 3 consecutive runs

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order:

### Phase 1: Prove the Loop (Week 1-2) — DONE

1. **agent-driven-testing-core** (`docs/prds/test/done/e7-s1-agent-driven-integration-testing-prd.md`) — Session fixture, ready gate, conditional teardown, voice chat integration, structural assertions

**Rationale:** Foundational mechanism that all other scenarios depend on. Must prove the loop works before expanding.

---

### Phase 2: Scenario Expansion (Week 3-4) — DONE

2. **agent-driven-testing-expand** (`docs/prds/test/done/e7-s2-agent-driven-integration-testing-prd.md`) — Question/answer flow, multi-turn conversation, cross-layer verification

**Rationale:** Expands coverage to multiple interaction shapes. Adds cross-layer verification for confidence.

---

### Phase 3: Pattern Extraction (Week 5-6) — DONE

3. **agent-driven-testing-lib** (`docs/prds/test/done/e7-s3-agent-driven-integration-testing-prd.md`) — Shared helpers, permission flow, bug-driven scenarios, format evaluation

**Rationale:** Extracts proven patterns, adds advanced scenarios, evaluates declarative format.

---

## Future Sprints (Planned / Under Consideration)

Epic 7 is designed to grow. The following ideas are candidates for future sprints as they are scoped and workshopped. This section will be updated as new PRDs are created.

### Deferred Scenarios (Candidate)

These scenarios were deferred from the initial epic scope due to complexity or non-determinism:

- **Agent session ends unexpectedly** — requires killing Claude Code mid-interaction; timing-sensitive
- **Progress updates during processing** — cannot guarantee Claude emits progress; non-deterministic
- **Permission deny flow** — requires automating tmux permission dialogs with timing-sensitive key navigation

**Status:** Deferred — may be added as standalone follow-up work after Sprint 3

### CI/CD Integration (Candidate)

Integration of agent-driven tests into CI/CD pipeline with appropriate resource management, cost controls, and failure handling.

**Status:** Idea — requires scoping and PRD workshop

### Parallel Test Execution (Candidate)

Running multiple agent-driven tests in parallel with isolated tmux sessions and database partitions.

**Status:** Idea — requires scoping and PRD workshop

### Performance Profiling Scenarios (Candidate)

Agent-driven tests that exercise performance-sensitive code paths and capture timing metrics.

**Status:** Idea — requires scoping and PRD workshop

### Conversation Fixture Workshop (Cut)

Guided CLI for authoring conversation fixtures was cut from the epic scope permanently. Tests use explicit prompts and inline assertions.

**Status:** Cut — not planned

---

## Document History

| Version | Date       | Author          | Changes                                                |
| ------- | ---------- | --------------- | ------------------------------------------------------ |
| 1.0     | 2026-02-20 | PM Agent (John) | Initial detailed roadmap for Epic 7 (3 sprints)        |

---

**End of Epic 7 Detailed Roadmap**
