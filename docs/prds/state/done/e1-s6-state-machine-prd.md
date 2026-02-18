---
validation:
  status: valid
  validated_at: '2026-01-29T10:07:56+11:00'
---

## Product Requirements Document (PRD) — Command/Turn State Machine

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 6 — Command state machine transitions correctly
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

The Command/Turn State Machine is the core behavioral logic of Claude Headspace. It implements the 5-state model that differentiates this system from simple process monitoring—enabling granular visibility into whether an agent is idle, processing, or awaiting user input.

This sprint delivers the state transition logic that reacts to events from the Event System (Sprint 5), validates transitions, detects turn intents via regex patterns, and manages the Command lifecycle. The state machine consumes `turn_detected` events and produces `state_transition` events, completing the event-driven pipeline that feeds the SSE system (Sprint 7) and dashboard UI (Sprint 8).

Without a reliable state machine, the dashboard cannot accurately reflect agent status, prioritisation is meaningless, and the core value proposition of Claude Headspace collapses. This sprint is the bridge between raw events and meaningful state.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace tracks Claude Code agents performing Commands with Turn-level granularity. Each Command progresses through a 5-state lifecycle:

```
idle → commanded → processing → awaiting_input/complete → idle
```

The state machine:
1. Receives `turn_detected` events from Sprint 5 Event System
2. Detects turn intent (command, answer, question, completion, progress)
3. Validates and applies state transitions
4. Writes `state_transition` events for audit trail
5. Derives Agent state from current Command state

This positions Sprint 6 as the behavioral core—Sprint 5 provides events, Sprint 6 interprets them, Sprint 7 broadcasts the results.

### 1.2 Target User

Developers monitoring multiple Claude Code sessions who need accurate, real-time visibility into what each agent is doing and whether it requires attention.

### 1.3 Success Moment

A developer watches the dashboard as they interact with Claude Code. When they issue a command, the agent immediately shows "commanded" → "processing". When Claude asks a question, it shows "awaiting input" with high visual priority. When Claude completes, it returns to "idle". The states are always accurate, never stuck, never wrong.

---

## 2. Scope

### 2.1 In Scope

- **Command state transition logic** — Enforce valid transitions between 5 states (idle, commanded, processing, awaiting_input, complete)
- **Turn intent detection (regex-based)** — Parse turn content to determine intent (command, answer, question, completion, progress)
- **State transition validator** — Reject invalid transitions with error logging
- **Command lifecycle management** — Create tasks on user command, complete tasks on agent completion
- **Agent state derivation** — Agent.state reflects current_command.state (or idle if no active command)
- **State transition event logging** — Write `state_transition` events to Event table via Event Writer
- **Confidence tracking** — Record confidence level for each transition (1.0 for regex matches)
- **Unit tests** — Cover all valid transitions, invalid transitions, and edge cases

### 2.2 Out of Scope

- LLM-based intent detection (deferred to Epic 3)
- Hook receiver endpoints (Sprint 13)
- File watcher / jsonl parsing (Sprint 4)
- Event writer service implementation (Sprint 5)
- SSE broadcasting of state changes (Sprint 7)
- Dashboard UI (Sprint 8)
- Priority scoring (Epic 3)
- Command summarisation (Epic 3)
- Timeout-based automatic state transitions (future enhancement)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User issues command → Command created in `commanded` state
2. Agent starts responding → Command transitions to `processing`
3. Agent asks question → Command transitions to `awaiting_input`
4. User answers question → Command transitions back to `processing`
5. Agent signals completion → Command transitions to `complete`
6. Command completes → Agent returns to `idle` state (no active command)
7. Invalid transitions are rejected with error log (e.g., `idle` → `processing` without `commanded`)
8. Intent detection achieves >90% accuracy on representative test cases
9. `state_transition` events written to Event table with from_state, to_state, trigger, confidence
10. Unit tests cover all valid state transitions (happy path)
11. Unit tests cover invalid transition rejection (error cases)
12. Unit tests cover edge cases (rapid turns, agent crash scenarios)

### 3.2 Non-Functional Success Criteria

1. State transition latency < 50ms from event receipt to state update
2. Intent detection regex matching completes in < 10ms per turn
3. State machine is stateless/reentrant (no global mutable state)
4. All state transitions are atomic (no partial updates)

---

## 4. Functional Requirements (FRs)

### FR1: Command State Enum

The system shall enforce exactly 5 command states:

| State | Description |
|-------|-------------|
| `idle` | No active work; ready for next command |
| `commanded` | User has issued a command; agent has not yet responded |
| `processing` | Agent is actively working on the task |
| `awaiting_input` | Agent has asked a question; waiting for user response |
| `complete` | Agent has signaled command completion |

### FR2: Turn Intent Enum

The system shall classify turns into exactly 5 intents:

| Intent | Actor | Description |
|--------|-------|-------------|
| `command` | user | User initiates a new task |
| `answer` | user | User responds to agent's question |
| `question` | agent | Agent asks for clarification |
| `progress` | agent | Agent reports intermediate progress |
| `completion` | agent | Agent signals task is done |

### FR3: State Transition Rules

The system shall enforce valid state transitions based on turn actor and intent:

| Current State | Turn Actor | Turn Intent | New State | Valid |
|---------------|------------|-------------|-----------|-------|
| idle | user | command | commanded | Yes |
| idle | user | answer | - | No (no question pending) |
| idle | agent | * | - | No (agent cannot act when idle) |
| commanded | agent | progress | processing | Yes |
| commanded | agent | question | awaiting_input | Yes |
| commanded | agent | completion | complete | Yes |
| commanded | user | * | - | No (waiting for agent) |
| processing | agent | progress | processing | Yes |
| processing | agent | question | awaiting_input | Yes |
| processing | agent | completion | complete | Yes |
| processing | user | * | - | No (agent is working) |
| awaiting_input | user | answer | processing | Yes |
| awaiting_input | user | command | commanded | Yes (new task) |
| awaiting_input | agent | * | - | No (waiting for user) |
| complete | - | - | (task ends) | Yes |

### FR4: State Transition Validator

The system shall validate transitions before applying:
- Check current state allows the proposed transition
- Check actor/intent combination is valid for current state
- Reject invalid transitions with descriptive error message
- Log rejected transitions at WARNING level
- Return validation result (valid/invalid + reason)

### FR5: Intent Detection Service

The system shall detect turn intent from text content using regex patterns:

**User Intents:**
- `command`: Default for user turns when no active command or task is idle/complete
- `answer`: User turn when current state is `awaiting_input`

**Agent Intents:**
- `question`: Text ends with `?` OR contains phrases like "Would you like", "Should I", "Do you want", "Can you", "Could you"
- `completion`: Text contains phrases like "Done", "Complete", "Finished", "I've completed", "Command complete", "Ready for"
- `progress`: Default for agent turns that don't match question/completion

### FR6: Command Lifecycle Management

The system shall manage Command lifecycle:
- **Command Creation:** When user issues command (intent=command) and no active incomplete command, create new Command with state=commanded
- **Command Continuation:** When turn detected for active command, update command state per transition rules
- **Command Completion:** When state transitions to complete, set Command.completed_at timestamp
- **Command End:** After completion, agent has no active command (state derived as idle)

### FR7: Agent State Derivation

The system shall derive Agent state from current Command:
- If agent has an incomplete command → Agent.state = Command.state
- If agent has no incomplete command → Agent.state = idle
- State is derived (computed property), not stored separately

### FR8: State Transition Event Logging

The system shall write events for every state transition:
- Event type: `state_transition`
- Payload includes: agent_id, command_id, from_state, to_state, trigger, confidence
- Trigger values: `turn` (from turn detection), `manual` (admin override), `timeout` (future)
- Confidence: 1.0 for regex-matched intents

Payload schema (aligned with Sprint 5):
```json
{
  "agent_id": "integer",
  "command_id": "integer",
  "from_state": "string",
  "to_state": "string",
  "trigger": "turn|timeout|manual",
  "confidence": "float (0.0-1.0)"
}
```

### FR9: Turn Event Consumption

The system shall consume `turn_detected` events from the Event table:
- Extract actor, text, session_uuid from event payload
- Correlate session_uuid to Agent
- Detect intent from text
- Apply state transition via validator
- Write resulting `state_transition` event

### FR10: Error Handling

The system shall handle edge cases gracefully:
- **Unknown session:** Log warning, skip processing (session discovery is Sprint 4's job)
- **Invalid transition:** Log warning with context, do not update state
- **Missing text:** Treat as progress intent (safest default)
- **Database error:** Propagate to caller, do not leave partial state

### FR11: Edge Case Behaviors

The system shall handle these edge cases:

| Scenario | Behavior |
|----------|----------|
| Agent crash mid-command | Command remains in current state; agent marked inactive by session end (Sprint 4/13) |
| Multiple rapid turns | Process sequentially; each transition validated against updated state |
| User command while awaiting_input | Valid transition; starts new task (abandons previous) |
| Agent speaks when not expected | Invalid transition; logged and rejected |

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Testability

The state machine shall be designed for testability:
- Pure functions where possible (input → output, no side effects)
- Dependency injection for Event Writer
- All transitions testable in isolation
- No reliance on database for core logic tests

### NFR2: Logging

The system shall provide comprehensive logging:
- INFO: State transitions (from → to)
- DEBUG: Intent detection details, regex matches
- WARNING: Invalid transition attempts, unknown sessions
- ERROR: Database failures, unrecoverable errors

### NFR3: Metrics Exposure

The system shall track metrics for monitoring:
- Count of transitions by from_state → to_state
- Count of rejected invalid transitions
- Intent detection breakdown by intent type
- Processing latency histogram

### NFR4: Idempotency

The system shall handle duplicate event processing safely:
- Same turn processed twice should not create duplicate transitions
- Use turn_id or timestamp for deduplication if needed

---

## 6. Technical Context

*Note: This section captures architectural decisions for implementation reference.*

### State Machine Diagram

```
                                ┌─────────────────────────────────┐
                                │                                 │
                                ▼                                 │
┌──────────┐    user command   ┌───────────┐                      │
│          │ ─────────────────▶│           │                      │
│   idle   │                   │ commanded │                      │
│          │◀─┐                │           │                      │
└──────────┘  │                └─────┬─────┘                      │
              │                      │                            │
              │                      │ agent progress/question/   │
              │                      │ completion                 │
              │                      ▼                            │
              │                ┌────────────┐                     │
              │                │            │◀────────────────┐   │
              │                │ processing │                 │   │
              │                │            │─────────┐       │   │
              │                └─────┬──────┘         │       │   │
              │                      │                │       │   │
              │     agent completes  │                │       │   │
              │                      ▼                │       │   │
              │                ┌──────────┐           │       │   │
              │                │          │   agent   │       │   │
              │                │ complete │   asks    │       │   │
              │                │          │  question │       │   │
              │                └────┬─────┘           │       │   │
              │                     │                 ▼       │   │
              │                     │          ┌────────────┐ │   │
              │  command complete      │          │  awaiting  │ │   │
              └─────────────────────┘          │   input    │─┘   │
                                               │            │     │
                                               └──────┬─────┘     │
                                                      │           │
                                                      │ user      │
                                                      │ answers   │
                                                      └───────────┘
```

### Intent Detection Patterns (Regex)

```python
# Agent question patterns
QUESTION_PATTERNS = [
    r'\?$',                           # Ends with question mark
    r'(?i)would you like',            # "Would you like..."
    r'(?i)should I',                  # "Should I..."
    r'(?i)do you want',               # "Do you want..."
    r'(?i)can you (please )?(provide|confirm|clarify)',
    r'(?i)could you',                 # "Could you..."
    r'(?i)what would you prefer',
    r'(?i)which (one|option)',
]

# Agent completion patterns
COMPLETION_PATTERNS = [
    r'(?i)\bdone\b',                  # "Done" as word
    r'(?i)\bcomplete[d]?\b',          # "Complete" or "Completed"
    r'(?i)\bfinished\b',              # "Finished"
    r'(?i)I\'ve (completed|finished|done)',
    r'(?i)task (complete|done)',
    r'(?i)ready for (your )?(next|review)',
    r'(?i)successfully (created|updated|implemented|fixed)',
]
```

### File Structure

```
src/claude_headspace/
├── services/
│   ├── state_machine.py      # StateMachine class - core transition logic
│   ├── intent_detector.py    # IntentDetector class - regex-based detection
│   └── command_lifecycle.py     # CommandLifecycleManager - create/complete tasks

tests/
├── services/
│   ├── test_state_machine.py      # Transition tests
│   ├── test_intent_detector.py    # Intent detection tests
│   └── test_command_lifecycle.py     # Lifecycle tests
```

### Integration with Sprint 5

The state machine integrates with the Event System:

```python
# Consume turn_detected events
def process_turn_event(event: Event) -> None:
    payload = event.payload
    agent = get_agent_by_session(payload["session_uuid"])
    intent = intent_detector.detect(payload["actor"], payload["text"], agent.state)

    result = state_machine.transition(
        agent=agent,
        actor=payload["actor"],
        intent=intent
    )

    if result.valid:
        event_writer.write("state_transition", {
            "agent_id": agent.id,
            "command_id": result.command_id,
            "from_state": result.from_state,
            "to_state": result.to_state,
            "trigger": "turn",
            "confidence": 1.0
        })
```

---

## 7. Dependencies

### Prerequisites

- Sprint 3 (Domain Models) complete — Command, Turn, Event models exist
- Sprint 5 (Event System) complete — Events are being written to database

### Blocking

This sprint blocks:
- Sprint 7 (SSE System) — Needs state transitions to broadcast
- Sprint 8 (Dashboard UI) — Needs accurate agent states to display
- Sprint 13 (Hook Receiver) — Uses state machine for hook-triggered transitions

---

## 8. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
