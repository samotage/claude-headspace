---
validation:
  status: valid
  validated_at: '2026-02-19T15:05:56+11:00'
---

## PRD — Agent-Driven Integration Testing: Sprint 1 — Prove the Loop

**Project:** Claude Headspace
**Epic:** E7 — Agent-Driven Integration Testing
**Sprint:** 1 of 3
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace has ~2,500 tests across unit, route, integration, and E2E tiers — but they all use mocked or simulated hooks. No test currently exercises the real production loop. Bugs that pass mock-based tests continue to ship and break the system.

This sprint proves the fundamental mechanism: one test that drives a real Claude Code session through the voice chat UI via Playwright, with real hooks firing, real SSE updating the browser, and structural assertions verifying the rendered result.

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

Every layer is real. Nothing is mocked.

**This is the hardest sprint.** If this works, everything else is incremental.

---

## 1. Context

### 1.1 Problem

The E2E tests use a `HookSimulator` that fires HTTP requests to simulate Claude Code lifecycle hooks — but this skips the actual Claude Code session, tmux bridge, real hook delivery, and real LLM processing. Critical bugs in the interaction between these components pass all existing tests and only surface when a human uses the system.

### 1.2 Target User

Developers and AI agents working on Claude Headspace who need confidence that changes don't break the real end-to-end flow.

### 1.3 Success Moment

A developer runs `pytest tests/agent_driven/test_simple_command.py`, a real Claude Code session launches, processes a command sent through the voice chat UI, and the test passes — proving the full production loop works.

### 1.4 Series Context

This is Sprint 1 of 3 in the Agent-Driven Integration Testing epic:

- **Sprint 1 (this PRD):** Prove the loop — one test, full voice chat → Claude Code → hooks → SSE → browser roundtrip
- **Sprint 2 (`e7-s2`):** Scenario expansion — question/answer, multi-turn, cross-layer verification (DOM vs API vs DB)
- **Sprint 3 (`e7-s3`):** Pattern extraction — shared helpers, permission flow, bug-driven scenarios, format evaluation

Each sprint has a hard gate. Sprint 2 cannot begin until Sprint 1 passes.

---

## 2. Scope

### 2.1 In Scope

- Launch a real Claude Code CLI session in a tmux pane with hooks pointing to the test server
- Ready gate — wait for session-start hook to arrive before running the test
- Navigate Playwright to voice chat, select the agent, send a command
- Wait for agent response bubble to render in the voice chat DOM
- Verify command state transitions in the database
- Conditional teardown — cleanup on success, preserve evidence on failure
- Cost-controlled execution (Haiku model, short deterministic prompts)

### 2.2 Out of Scope

- Multiple scenarios (Sprint 2)
- Cross-layer verification — DOM vs API vs DB consistency (Sprint 2)
- Shared helpers or abstractions (Sprint 3)
- Declarative scenario format (Sprint 3 evaluation)
- Conversation fixture workshop / guided authoring CLI (cut from epic)
- CI/CD integration
- Testing LLM response quality or intelligence
- Parallel test execution

---

## 3. Functional Requirements

**FR1 — Session Launch:** A pytest fixture can launch a `claude` CLI session in a dedicated tmux pane, configured with hooks pointing to the test server URL and using the Haiku model.

**FR2 — Ready Gate:** The fixture waits for the `session-start` hook to arrive at the test server (verified by polling DB for a new Agent record) before yielding. The Claude Code session is confirmed healthy and ready to receive prompts.

**FR3 — Session Isolation:** Each test scenario runs in its own tmux session with a unique name to prevent cross-contamination.

**FR4 — Conditional Teardown:** On test success, the tmux session is killed and the test database is cleaned. On test failure, the tmux session, database state, and any screenshots are preserved for investigation.

**FR5 — Voice Chat Integration:** The test navigates Playwright to the voice chat UI on the test server, selects the agent card, and sends a command using the existing `VoiceAssertions.send_chat_message()` method.

**FR6 — Structural Response Assertion:** After sending a command, the test waits for an agent response bubble to appear in the voice chat DOM (structural: any element with `data-turn-id` and agent actor class). Timeout is configurable and generous (default 60s).

**FR7 — State Transition Assertion:** The test verifies that the command state transitioned through the expected path (IDLE → COMMANDED → PROCESSING → COMPLETE) by querying the database.

**FR8 — Server Target:** The test system targets the real running server. The server URL is read from `config.yaml` (`server.application_url`).

---

## 4. Non-Functional Requirements

**NFR1:** Timeouts must be generous — 60s default per interaction, configurable per test.

**NFR2:** Must use Haiku model with a short, deterministic prompt (e.g., `"Create a file called /tmp/headspace_test_<uuid>.txt with the content hello"`).

**NFR3:** Must use the `claude_headspace_test` database — never production or development databases.

**NFR4:** Test execution is sequential.

**NFR5:** On failure, all artefacts preserved: tmux pane stays open, DB state not cleaned, screenshots saved.

**NFR6:** No new pip dependencies. Use subprocess for tmux (consistent with existing `tmux_bridge.py`).

---

## 5. Deliverables

- `tests/agent_driven/conftest.py` — `claude_session` fixture (launch, ready gate, teardown)
- `tests/agent_driven/test_simple_command.py` — one test: send command via voice chat → verify agent response bubble + state transitions
- Proof of execution: test output showing pass against real Claude Code session

---

## 6. Sprint Gate

**This sprint is NOT complete until:**

- [ ] The test has been executed against a real Claude Code session (not mocked)
- [ ] Playwright drove the voice chat UI to send the command (not tmux directly)
- [ ] An agent response bubble appeared in the voice chat DOM
- [ ] The test passed with screenshots captured
- [ ] The tmux session was cleaned up on success

**Do NOT proceed to Sprint 2 until all gates pass.**

---

## 7. Agent Implementation Constraints

These constraints exist to prevent over-engineering, premature abstraction, and hallucination:

1. **Code budget: 500 lines maximum** across conftest + test file. If you write more, you're over-engineering.
2. **No new classes.** The session fixture is a function. Assertions use existing helpers + inline checks.
3. **No fixture format, no runner, no scenario abstraction.** The test is a pytest function with string literals for prompts and inline assertions.
4. **Use `subprocess` for tmux operations** (consistent with existing `tmux_bridge.py`). Do not add `libtmux` as a dependency.
5. **Do not restructure existing E2E fixtures.** Create a new `tests/agent_driven/` directory. Reuse `e2e_test_db` and `e2e_server` from the existing E2E conftest if possible; duplicate only what's necessary.
6. **Structural assertions only.** Never assert on LLM response content. Assert: turn exists, turn has correct actor, state reached expected value, bubble has `data-turn-id`.
7. **Must execute against a real Claude Code session.** "Should work" is not acceptable. Run the test. Capture the output.

---

## 8. Technical Context

*Implementation-relevant details. They inform the build phase but are not requirements.*

### Production Flow (Voice Chat → Claude Code → Voice Chat)

1. **Frontend → Backend:** `POST /api/voice/command` with `{ text, agent_id }`
2. **Backend → tmux:** `tmux_bridge.send_text(pane_id, text)` delivers to Claude Code PTY
3. **Claude Code → Backend:** Hooks fire to `/hook/*` endpoints (session-start, user-prompt-submit, post-tool-use, notification, stop, session-end)
4. **Backend → Frontend:** `broadcaster.broadcast("turn_created", ...)` → SSE → `voice-sse-handler.js`
5. **Frontend rendering:** Optimistic bubble promotion, agent bubble creation, state pill updates

### Key Race Condition: respond_inflight

When voice chat sends a command, `voice_bridge.py` sets `respond_inflight` flag BEFORE the tmux send. When Claude Code's `user-prompt-submit` hook fires later, `hook_receiver.py` checks this flag to avoid creating a duplicate USER turn. Tests must account for this timing.

### Existing Infrastructure

| Component | Location | Reuse |
|-----------|----------|-------|
| Test database fixture | `tests/e2e/conftest.py` (`e2e_test_db`) | Reuse directly or duplicate pattern |
| Flask test server | `tests/e2e/conftest.py` (`e2e_server`) | Reuse directly |
| Voice chat assertions | `tests/e2e/helpers/voice_assertions.py` | Reuse `VoiceAssertions` class |
| Dashboard assertions | `tests/e2e/helpers/dashboard_assertions.py` | Reuse if dashboard checks needed |
| Hook payload reference | `tests/e2e/helpers/hook_simulator.py` | Reference only — real tests use actual hooks |
| Tmux operations | `src/claude_headspace/services/tmux_bridge.py` | Reference patterns; test fixtures use subprocess directly |

### Session Launch Considerations

- `claude` CLI must be invoked with `--model haiku` for cost control
- Hooks must point to the test server URL (random port from `e2e_server`), NOT the production server
- The `--hooks-endpoint` flag or equivalent environment variable controls where hooks fire
- Each test needs its own tmux session name (e.g., `headspace-test-<uuid>`)
- Ready gate: poll DB for Agent record with matching session UUID, timeout 30s
- Working directory should be a temp directory to avoid polluting real projects

### Cost Control

- Prompt: `"Create a file called /tmp/headspace_test_<uuid>.txt with the content hello"`
- Haiku model
- Single interaction — verify the shape, not the depth

### Server & Network

- Target server: `https://smac.griffin-blenny.ts.net:5055` (TLS via Tailscale)
- Playwright needs `--ignore-https-errors` for Tailscale TLS certs
- Flask debug reloader is running — no separate test instance needed
