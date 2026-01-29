# Proposal: e1-s6-state-machine

## Summary

Implement the Task/Turn State Machine - the core behavioral logic that interprets events and manages task state transitions. Consumes `turn_detected` events from Sprint 5 and produces `state_transition` events for Sprint 7.

## Motivation

Without a reliable state machine, the dashboard cannot accurately reflect agent status. This sprint is the bridge between raw events (Sprint 5) and meaningful state that the UI (Sprint 8) can display.

## Impact

### Files to Create
- `src/claude_headspace/services/state_machine.py` - StateMachine class with transition logic
- `src/claude_headspace/services/intent_detector.py` - IntentDetector with regex patterns
- `src/claude_headspace/services/task_lifecycle.py` - TaskLifecycleManager for create/complete
- `tests/services/test_state_machine.py` - Transition tests
- `tests/services/test_intent_detector.py` - Intent detection tests
- `tests/services/test_task_lifecycle.py` - Lifecycle tests

### Files to Modify
- `src/claude_headspace/services/__init__.py` - Export new services
- `src/claude_headspace/models/enums.py` - TurnIntent enum already exists

### Database Changes
None - Using existing Task and Turn models from Sprint 3.

## Definition of Done

- [ ] StateMachine class with transition() method
- [ ] State transition validator (valid/invalid + reason)
- [ ] IntentDetector with regex patterns for question/completion/progress
- [ ] TaskLifecycleManager for task creation and completion
- [ ] Agent state derivation (computed property)
- [ ] State transition event logging via EventWriter
- [ ] All valid state transitions covered by tests
- [ ] All invalid transition rejections tested
- [ ] Edge cases tested (rapid turns, user command while awaiting)
- [ ] >90% intent detection accuracy on test cases

## Risks

- **Regex pattern accuracy**: Patterns may miss edge cases. Mitigation: Comprehensive test cases, defaulting to 'progress' for ambiguous agent turns.
- **State derivation performance**: Computed property queries database. Mitigation: Can cache current_task if needed.
- **Rapid turn handling**: Multiple events in quick succession. Mitigation: Process sequentially with validation.

## Alternatives Considered

1. **LLM-based intent detection**: More accurate but slower and more complex. Deferred to Epic 3.
2. **Store agent state separately**: Simpler queries but data duplication. Rejected: Derived property is safer.
3. **Async event processing**: Use queues for events. Rejected: Adds complexity for Epic 1.
