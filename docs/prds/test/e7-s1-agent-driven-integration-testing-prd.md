---
validation:
  status: valid
  validated_at: '2026-02-18T15:32:15+11:00'
---

## Product Requirements Document (PRD) — Agent-Driven Integration Testing

**Project:** Claude Headspace
**Scope:** Full-loop integration testing with real Claude Code sessions, Playwright browser automation, and cross-layer verification
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace has extensive unit, route, and E2E tests — but they all use mocked or simulated hooks. No test currently exercises the real production loop: a real Claude Code agent processing real prompts, firing real hooks back to the server, with the browser rendering real SSE updates. Bugs that pass mock-based tests continue to ship and break the system.

This PRD defines an agent-driven integration testing system that replaces simulation with reality. A test orchestrator drives both a real Claude Code session (in a tmux pane) and a Playwright browser (on the voice chat UI), running predefined conversation scenarios and verifying that every layer of the stack works together correctly. Tests assert on structure — not content — because agent responses are non-deterministic.

The system includes a conversation fixture format (markdown with YAML frontmatter) for defining test scenarios, a runner that executes them against the real system, and a workshop process for authoring new fixtures. Success means that bugs which survive mock-based testing are caught before they reach users.

---

## 1. Context & Purpose

### 1.1 Context

The project has ~960 tests across unit, route, integration, and E2E tiers. The E2E tests use a `HookSimulator` that fires HTTP requests to simulate Claude Code lifecycle hooks — but this skips the actual Claude Code session, tmux bridge, real hook delivery, and real LLM processing. Critical bugs in the interaction between these components pass all existing tests and only surface when a human uses the system.

The existing integration testing PRD (`testing/integration-testing-framework-prd.md`) addressed mock-to-real-DB replacement but did not cover the full frontend-to-agent-to-backend loop.

### 1.2 Target User

Developers and AI agents working on Claude Headspace who need confidence that changes don't break the real end-to-end flow.

### 1.3 Success Moment

A developer makes a change, runs the integration test suite, and a conversation scenario that exercises the affected code path either passes (confirming the change works in the real system) or fails with clear evidence of what broke and where.

---

## 2. Scope

### 2.1 In Scope

- Real Claude Code session management — launch, health check, teardown of `claude` CLI sessions in tmux panes with hooks firing to the server
- Conversation scenario framework — a declarative way to define named conversation flows with prompts, expected progressions, and structural assertions
- Conversation fixture format — markdown files with YAML frontmatter, human-readable and LLM-friendly
- Conversation fixture library — predefined scenarios covering key interaction shapes
- Conversation fixture workshop — a guided authoring process (terminal command/prompt) for creating new fixture files
- Cross-layer verification — at each assertion point, verify consistency across browser DOM, API transcript, database state, and tmux pane content
- Playwright browser automation — drive the voice chat UI to send commands and verify rendered output
- Structural assertion model — assert on structure not content (turns exist, states follow valid paths, timestamps ordered, correct number of rounds)
- Sequential test execution
- Cost-controlled execution using cheapest viable model
- Cleanup on success only — failed runs preserve all evidence (tmux panes, DB state, screenshots) for investigation

### 2.2 Out of Scope

- Testing LLM intelligence or response quality
- Load or performance testing
- Testing Claude Code itself (that's Anthropic's responsibility)
- Replacing existing unit, route, or E2E tests (those remain for fast feedback)
- CI/CD integration (requires tmux, network access, API key, running server — future work)
- Parallel test execution

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. All defined conversation scenarios run against a real Claude Code session and pass
2. Bugs that pass mock-based tests but break the real loop are detected by at least one scenario
3. A new conversation scenario can be added by writing a markdown fixture file — no framework code changes required
4. New conversation fixtures can be authored via a guided workshop process
5. Cross-layer consistency is verified at every assertion point (DOM matches API matches DB)
6. Failed test runs preserve all evidence for human investigation

### 3.2 Non-Functional Success Criteria

1. Each individual scenario completes within a bounded timeout (configurable, generous enough for real LLM calls)
2. Test execution uses the cheapest viable model to control costs
3. Conversation fixtures are readable by both humans and LLMs without requiring knowledge of the test framework internals

---

## 4. Functional Requirements (FRs)

### Session Management

**FR1:** The system can launch a Claude Code CLI session in a dedicated tmux pane, configured with hooks pointing to the target server.

**FR2:** The system can verify that a launched Claude Code session is healthy and ready to receive prompts.

**FR3:** The system can send text prompts to a Claude Code session via its tmux pane.

**FR4:** The system can tear down a Claude Code session and its tmux pane on test success. On test failure, the session and pane are preserved for investigation.

**FR5:** Each test scenario runs in its own isolated tmux session to prevent cross-contamination.

### Conversation Fixture Format

**FR6:** Conversation scenarios are defined as markdown files with YAML frontmatter containing scenario metadata (name, description, interaction shape, model, timeout).

**FR7:** The body of a conversation fixture defines a sequence of steps, each specifying: the prompt to send, the expected progression (state transitions, turn creation), and structural assertions to verify.

**FR8:** Conversation fixtures support assertion types including: turn existence (for both actors), state transition validation, bubble rendering in browser, DOM/API transcript consistency, timestamp ordering, question/option rendering, and expected number of interaction rounds.

**FR9:** Conversation fixtures are self-contained — all information needed to run the scenario is in the file. No external configuration or code references required.

### Conversation Fixture Library

**FR10:** The system includes predefined conversation fixtures covering at minimum:
- Simple command/response (command → processing → completion)
- Structured question flow (command → AskUserQuestion with options → user picks option → completion)
- Permission request flow (command triggers tool permission → approve → completion)
- Permission deny flow (command triggers permission → deny → agent adapts)
- Multi-turn conversation (3+ sequential command/response exchanges)
- Progress updates during processing (command → agent emits progress → completion)
- Agent session ends unexpectedly (session-end fires while processing)
- Browser/API consistency (full cross-check at end of any flow)

### Scenario Runner

**FR11:** The scenario runner loads a conversation fixture, launches the required infrastructure (tmux session, browser page), and executes each step sequentially.

**FR12:** At each step, the runner sends the specified prompt, waits for the expected progression to occur (with configurable timeout), and then runs all structural assertions for that step.

**FR13:** The runner produces clear, structured output indicating which scenario is running, which step is executing, and pass/fail status with details for each assertion.

**FR14:** The runner integrates with pytest so scenarios can be discovered, selected, and run using standard pytest commands and conventions.

### Cross-Layer Verification

**FR15:** At each assertion point, the system can verify that the browser DOM state is consistent with the API transcript endpoint response.

**FR16:** At each assertion point, the system can verify that the database state (turns, tasks, agents) is consistent with both the browser and API.

**FR17:** At each assertion point, the system can verify that the tmux pane content reflects the expected state of the Claude Code session.

**FR18:** Timestamp ordering is verified: turns in the API transcript and database are monotonically ordered by timestamp.

### Conversation Fixture Workshop

**FR19:** A guided workshop process exists for authoring new conversation fixtures. It can be invoked from the terminal.

**FR20:** The workshop walks the author through defining: scenario name and description, interaction shape, prompt sequence, expected progression at each step, and structural assertions.

**FR21:** The workshop outputs a properly formatted markdown conversation fixture file that is ready to run without modification.

**FR22:** The workshop validates the generated fixture against the expected format before saving.

### Server Target

**FR23:** The test system targets the real running server. The server URL is read from `config.yaml` (`server.application_url`).

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Individual scenario timeouts must be configurable, with defaults generous enough to accommodate real LLM response times (5–60 seconds per interaction).

**NFR2:** Tests must use the cheapest viable model (e.g., Haiku) via simple, short prompts to control costs.

**NFR3:** Tests must use the `claude_headspace_test` database — never production or development databases.

**NFR4:** Test execution is sequential — one scenario at a time — to avoid race conditions and simplify debugging.

**NFR5:** On test failure, all artefacts are preserved: tmux panes remain open, database state is not cleaned up, screenshots are saved. Cleanup only occurs on success.

**NFR6:** The conversation fixture format must be readable and authorable by both humans and LLMs without specialised tooling.

---

## 6. Technical Context & Considerations

*These are implementation-relevant details preserved from the workshop. They inform the build phase but are not requirements.*

### Existing Infrastructure to Build On

- `tests/e2e/conftest.py` — Database fixtures (`e2e_test_db`), Flask server fixtures, Playwright browser fixtures, `clean_db` truncation
- `tests/e2e/helpers/hook_simulator.py` — `HookSimulator` class (reference for hook payload structures; real tests use actual hooks instead)
- `tests/e2e/helpers/dashboard_assertions.py` — SSE connection assertions, agent card state checks, screenshot capture
- `tests/e2e/helpers/voice_assertions.py` — Voice chat navigation, bubble assertions, transcript verification
- `tests/integration/conftest.py` — Real Postgres test database lifecycle (create/drop), per-test rollback isolation
- `tests/integration/factories.py` — Factory Boy factories for all domain models

### Session Management Considerations

- `libtmux` (Python library) is a candidate for tmux session/pane management — currently not a dependency; existing `tmux_bridge.py` uses subprocess
- tmux `send-keys` is the mechanism for delivering prompts to Claude Code sessions
- Each scenario needs its own tmux session for isolation
- Claude Code hooks must be configured to fire to the target server URL

### Server & Network

- Target server: `https://smac.griffin-blenny.ts.net:5055` (TLS via Tailscale)
- Playwright needs `--ignore-https-errors` for Tailscale TLS certs
- Flask debug reloader is running on the real server — no need for a separate test instance

### Cost Control

- Simple, predictable prompts that force specific interaction shapes (e.g., "create a file called test.txt with the content hello" rather than open-ended requests)
- Haiku model for all test interactions
- Keep conversation turns to the minimum needed to verify the interaction shape
