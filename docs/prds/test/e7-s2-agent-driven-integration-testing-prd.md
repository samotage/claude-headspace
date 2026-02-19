---
validation:
  status: valid
  validated_at: '2026-02-19T15:07:06+11:00'
---

## PRD — Agent-Driven Integration Testing: Sprint 2 — Scenario Expansion + Cross-Layer Verification

**Project:** Claude Headspace
**Epic:** E7 — Agent-Driven Integration Testing
**Sprint:** 2 of 3
**Author:** Sam (workshopped with Claude)
**Status:** Draft
**Prerequisite:** Sprint 1 gate passed (`e7-s1`)

---

## Executive Summary

Sprint 1 proved the fundamental mechanism: one test driving a real Claude Code session through the voice chat UI. Sprint 2 expands to three reliable scenarios covering different interaction shapes and adds cross-layer verification that ensures the browser DOM, API transcript, and database are all consistent.

### The Loop Under Test

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

---

## 1. Context

### 1.1 Sprint 1 Delivered

Sprint 1 established:
- `claude_session` pytest fixture — launches Claude Code in tmux with hooks pointing to test server
- Ready gate — polls DB for Agent record before yielding
- Conditional teardown — cleanup on success, preserve on failure
- One passing test: simple command → agent response bubble → state transitions verified

### 1.2 What Sprint 2 Adds

- **Question/answer flow** — exercises AWAITING_INPUT state, option rendering, user selection
- **Multi-turn conversation** — exercises sequential command/response cycles
- **Cross-layer verification** — proves DOM, API, and DB are consistent at the end of each scenario

### 1.3 Series Context

- **Sprint 1 (`e7-s1`):** Prove the loop — DONE (prerequisite)
- **Sprint 2 (this PRD):** Scenario expansion + cross-layer verification
- **Sprint 3 (`e7-s3`):** Pattern extraction, permission flow, bug-driven scenarios, format evaluation

---

## 2. Scope

### 2.1 In Scope

- Question/answer scenario — trigger AskUserQuestion, verify option rendering, select option, verify completion
- Multi-turn scenario — sequential command/response cycles, verify correct turn count and ordering
- Cross-layer verification — DOM vs API transcript vs database consistency checks
- Timestamp ordering verification
- Screenshot capture for all scenarios

### 2.2 Out of Scope

- Shared helper extraction (Sprint 3 — only extract after patterns are proven across 3+ tests)
- Permission approval flow (Sprint 3)
- Declarative scenario format (Sprint 3 evaluation)
- Deferred scenarios: unexpected session end, progress updates, permission deny

---

## 3. Functional Requirements

### New Scenarios

**FR9 — Question/Answer Flow:** A test sends a prompt via voice chat that triggers Claude Code to use `AskUserQuestion` (structured question with options). The test asserts:
- AWAITING_INPUT state reached in database
- Question bubble rendered in voice chat DOM
- Option buttons visible in the question bubble
- User clicks an option via Playwright
- Command reaches COMPLETE state
- Response bubble rendered after option selection

**FR10 — Multi-Turn Conversation:** A test sends a command via voice chat, waits for completion, then sends a second command. The test asserts:
- Both round-trips complete (both commands reach COMPLETE)
- Correct number of user turns and agent turns exist in DB
- All bubbles rendered in the voice chat DOM in correct order
- Command separator visible between the two command groups

### Cross-Layer Verification

**FR11 — DOM/API Consistency:** At the end of any scenario, a verification step fetches the API transcript endpoint and compares it against the voice chat DOM. Assertions:
- Same number of turns in DOM and API response
- Same turn IDs present in both
- Same actor sequence (USER, AGENT, USER, AGENT, ...)

**FR12 — DOM/DB Consistency:** At the end of any scenario, a verification step queries the database directly and compares against the voice chat DOM. Assertions:
- Turn records in DB match bubbles in DOM by `turn_id`
- Command records reflect final state (COMPLETE)
- Agent record exists with correct project association

**FR13 — Timestamp Ordering:** Turns in both the API transcript and the database are monotonically ordered by timestamp. No out-of-order turns.

**FR14 — Screenshot Capture:** Every scenario captures before/after screenshots via Playwright for visual evidence. Screenshots are saved to a test-run-specific directory.

---

## 4. Non-Functional Requirements

**NFR1:** Timeouts remain generous — 60s default per interaction.

**NFR2:** Haiku model with short, deterministic prompts for all scenarios.

**NFR3:** `claude_headspace_test` database only.

**NFR4:** Sequential execution.

**NFR5:** Evidence preservation on failure (tmux panes, DB, screenshots).

**NFR6:** No new pip dependencies.

---

## 5. Deliverables

- `tests/agent_driven/test_question_answer.py` — question/answer flow test
- `tests/agent_driven/test_multi_turn.py` — multi-turn conversation test
- Cross-layer verification logic (inline in tests, or a single shared function if the check is identical across all three tests)
- Proof of execution: all three scenarios (Sprint 1 + Sprint 2) passing against real Claude Code sessions

---

## 6. Sprint Gate

**This sprint is NOT complete until:**

- [ ] All three scenarios (simple command, question/answer, multi-turn) pass against real Claude Code sessions
- [ ] Cross-layer verification (DOM vs API vs DB) runs and passes on at least one scenario
- [ ] Timestamp ordering is verified
- [ ] Screenshots captured for all scenarios
- [ ] Tests are reliable — pass on at least 3 consecutive runs without flaky failures

**Do NOT proceed to Sprint 3 until all gates pass.**

---

## 7. Agent Implementation Constraints

1. **Extract helpers only if the EXACT same code appears in 3+ tests.** If only two tests share a pattern, inline it.
2. **No fixture format.** Scenarios remain pytest functions with explicit prompts and assertions.
3. **Cross-layer verification can be a shared function** if the check is identical across scenarios — but it must be a plain function, not a class or framework.
4. **Each test file must be independently readable.** A developer should understand what a test does by reading that one file.
5. **Structural assertions only.** Never assert on LLM response content.
6. **Must execute against real Claude Code sessions.** All three scenarios must pass with proof.

---

## 8. Technical Context

### Triggering AskUserQuestion

To trigger a structured question from Claude Code, use an explicit prompt:
```
"Ask me what format I want the output in using AskUserQuestion with options: JSON, YAML, CSV"
```

This forces Claude to use the `AskUserQuestion` tool, which fires a `notification` hook with the question payload. The voice chat renders this as a bubble with option buttons.

### Multi-Turn Considerations

- After the first command completes, the agent returns to IDLE/COMPLETE state
- The second command via voice chat follows the "new command" path in `voice_bridge.py` (lines 406-501)
- Each command creates its own Command record in the database
- The voice chat renders a command separator between groups

### Cross-Layer Verification Endpoints

- **API transcript:** Find the relevant endpoint by checking `src/claude_headspace/routes/` — likely `/api/sessions/<agent_id>/transcript` or similar
- **Database:** Query `Turn` and `Command` models directly via `db.session`
- **DOM:** Use Playwright to query `[data-turn-id]` elements in `#chat-messages`

### Existing Infrastructure (from Sprint 1)

| Component | Location |
|-----------|----------|
| `claude_session` fixture | `tests/agent_driven/conftest.py` |
| Simple command test | `tests/agent_driven/test_simple_command.py` |
| Voice chat assertions | `tests/e2e/helpers/voice_assertions.py` |
| Test database | `tests/e2e/conftest.py` (`e2e_test_db`) |
| Test server | `tests/e2e/conftest.py` (`e2e_server`) |
