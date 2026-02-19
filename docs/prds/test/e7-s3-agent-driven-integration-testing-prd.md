---
validation:
  status: valid
  validated_at: '2026-02-19T15:07:07+11:00'
---

## PRD — Agent-Driven Integration Testing: Sprint 3 — Pattern Extraction + Library Expansion

**Project:** Claude Headspace
**Epic:** E7 — Agent-Driven Integration Testing
**Sprint:** 3 of 3
**Author:** Sam (workshopped with Claude)
**Status:** Draft
**Prerequisite:** Sprint 2 gate passed (`e7-s2`)

---

## Executive Summary

Sprint 1 proved the mechanism. Sprint 2 expanded to three scenarios with cross-layer verification. Sprint 3 extracts proven patterns into reusable helpers, adds scenarios driven by real bugs and permission flows, and evaluates whether a declarative scenario format would reduce duplication.

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

### 1.1 Sprint 1 + 2 Delivered

Sprint 1 established the core mechanism: `claude_session` fixture, ready gate, conditional teardown, one passing test.

Sprint 2 added:
- Question/answer flow test (AWAITING_INPUT, option selection)
- Multi-turn conversation test (sequential commands)
- Cross-layer verification (DOM vs API vs DB consistency)
- Timestamp ordering verification
- All three scenarios passing reliably

### 1.2 What Sprint 3 Adds

- **Shared helpers** extracted from proven patterns (not speculative abstractions)
- **Permission approval flow** — a new interaction shape
- **Bug-driven scenarios** — tests targeting real bugs that survived mock-based testing
- **Structured test output** — clear reporting of scenario progress
- **Format evaluation** — decide whether declarative YAML scenarios add value

### 1.3 Series Context

- **Sprint 1 (`e7-s1`):** Prove the loop — DONE
- **Sprint 2 (`e7-s2`):** Scenario expansion + cross-layer verification — DONE
- **Sprint 3 (this PRD):** Pattern extraction, permission flow, bug-driven scenarios, format evaluation

---

## 2. Scope

### 2.1 In Scope

- Extract shared helpers from Sprint 1+2 boilerplate into `tests/agent_driven/helpers/`
- Permission approval flow scenario
- At least one bug-driven scenario targeting a known bug that passed mock-based tests
- Structured test output (scenario name, step progress, pass/fail, elapsed time)
- Evaluation of whether a declarative scenario format (YAML) adds value — implement if yes, document decision if no
- pytest discovery — all agent-driven tests runnable via `pytest tests/agent_driven/`

### 2.2 Out of Scope

- Conversation fixture workshop / guided authoring CLI (cut from epic permanently)
- Custom DSL or markdown-based fixture format (if a format is warranted, it's plain YAML only)
- Deferred scenarios: unexpected session end, progress updates, permission deny flow
- CI/CD integration
- Parallel test execution

### 2.3 Deferred Scenarios

These remain deferred from the epic scope. They may be added as standalone follow-up work after Sprint 3:

- **Agent session ends unexpectedly** — requires killing Claude Code mid-interaction; timing-sensitive
- **Progress updates during processing** — cannot guarantee Claude emits progress; non-deterministic
- **Permission deny flow** — requires automating tmux permission dialogs with timing-sensitive key navigation

---

## 3. Functional Requirements

### Helper Extraction

**FR15 — Shared Helpers:** Common patterns proven across Sprint 1+2 tests are extracted into shared helper functions in `tests/agent_driven/helpers/`. At minimum:
- Session readiness waiting (poll DB for agent)
- Cross-layer verification (DOM vs API vs DB)
- Screenshot capture with consistent naming

### New Scenarios

**FR16 — Permission Approval Flow:** A test sends a prompt that triggers a tool permission request. The test asserts:
- AWAITING_INPUT state reached with permission context
- Permission-related UI element rendered in voice chat (or detected via tmux pane content)
- Permission approved via voice chat (or tmux if voice chat doesn't expose permission controls)
- Command reaches COMPLETE state
- Result rendered in voice chat

**FR17 — Bug-Driven Scenarios:** At least one new scenario is written based on a real bug that was caught by manual testing but passed all existing automated tests. The test:
- Documents which bug it targets (commit hash, issue number, or description)
- Exercises the specific code path that the bug affected
- Would have caught the bug if it had existed at the time

### Test Infrastructure

**FR18 — Scenario Discovery via pytest:** All agent-driven tests are discoverable and runnable via standard pytest commands:
- `pytest tests/agent_driven/` — runs all scenarios
- `pytest tests/agent_driven/test_simple_command.py` — runs one scenario
- `pytest tests/agent_driven/ -k question` — selects by keyword

**FR19 — Structured Test Output:** Each test produces clear output indicating:
- Scenario name
- Each step executing (e.g., "Sending command...", "Waiting for response bubble...")
- Pass/fail per assertion
- Total elapsed time
- Cost estimate (model + approximate token count) if available from inference logs

### Format Evaluation

**FR20 — Scenario Format Evaluation:** After implementing FR15-FR19, evaluate whether a declarative scenario format would reduce duplication and improve readability:
- **If yes:** Implement a minimal version using plain YAML (`yaml.safe_load`). No custom parser. The YAML is loaded into a dict and the test function iterates over it.
- **If no:** Document why in the test directory README and close the question.
- **Either way:** Every scenario must remain writable as a plain pytest function. The declarative format is a convenience layer, never a requirement.

---

## 4. Non-Functional Requirements

**NFR1:** Timeouts remain generous — 60s default per interaction.

**NFR2:** Haiku model with short, deterministic prompts.

**NFR3:** `claude_headspace_test` database only.

**NFR4:** Sequential execution.

**NFR5:** Evidence preservation on failure.

**NFR6:** No new pip dependencies.

---

## 5. Deliverables

- `tests/agent_driven/helpers/` — extracted shared helper functions
- `tests/agent_driven/test_permission_approval.py` — permission flow test
- At least one bug-driven scenario test (e.g., `tests/agent_driven/test_bug_<name>.py`)
- Written evaluation of declarative scenario format (README in `tests/agent_driven/` or inline)
- Proof of execution: full suite (`pytest tests/agent_driven/`) passing with all 5+ scenarios

---

## 6. Sprint Gate

**This sprint is NOT complete until:**

- [ ] All scenarios (Sprint 1 + Sprint 2 + Sprint 3) pass together in a single `pytest tests/agent_driven/` run
- [ ] At least 5 total scenarios exist and pass
- [ ] Shared helpers are extracted and used by at least 3 tests
- [ ] Scenario format evaluation is documented with a clear decision
- [ ] A developer unfamiliar with the framework can read any test file and understand what it does
- [ ] Structured test output shows scenario progress during execution

---

## 7. Agent Implementation Constraints

1. **Helpers must be plain functions.** No base classes, no inheritance, no metaclasses, no decorators that hide test logic.
2. **If a declarative format is implemented**, it must use standard YAML (parsed by `yaml.safe_load`). No custom parser. No markdown processing. No frontmatter. The YAML is loaded into a Python dict and the test function iterates over it — that's the entire "runner."
3. **Every scenario must also be writable as a plain pytest function.** The declarative format is a convenience layer, not a requirement. If someone wants to write a test without it, they can.
4. **Structural assertions only.** Never assert on LLM response content.
5. **Must execute all scenarios against real Claude Code sessions.** Full suite must pass with proof.
6. **Bug-driven scenarios must reference the actual bug.** No hypothetical bugs. Cite the commit, issue, or describe the exact failure that was missed by mock-based tests.

---

## 8. Technical Context

### Permission Approval in Voice Chat

The permission flow depends on how the voice chat UI handles permission requests:
- Check if voice chat renders permission prompts as interactive elements (buttons/options)
- If voice chat exposes permission controls, use Playwright to click approve
- If voice chat does NOT expose permission controls, fall back to tmux: capture permission dialog from pane, send approval keys
- The `permission_summarizer.py` service and `voice_bridge.py` picker detection logic (lines 305-385) may be relevant

### Bug-Driven Scenario Selection

Review recent bugs that passed all existing tests but broke the real system. Candidates:
- Voice chat ordering bugs (commit `74a8892` on `feature/voice-chat-ordering-remediation`)
- Optimistic bubble promotion failures
- respond_inflight race conditions
- Hook deduplication edge cases
- Any bug where the fix was verified manually but no automated test covers it

### Existing Infrastructure (from Sprint 1+2)

| Component | Location |
|-----------|----------|
| `claude_session` fixture | `tests/agent_driven/conftest.py` |
| Simple command test | `tests/agent_driven/test_simple_command.py` |
| Question/answer test | `tests/agent_driven/test_question_answer.py` |
| Multi-turn test | `tests/agent_driven/test_multi_turn.py` |
| Cross-layer verification | Inline or shared function from Sprint 2 |
| Voice chat assertions | `tests/e2e/helpers/voice_assertions.py` |
| Test database | `tests/e2e/conftest.py` (`e2e_test_db`) |
| Test server | `tests/e2e/conftest.py` (`e2e_server`) |
