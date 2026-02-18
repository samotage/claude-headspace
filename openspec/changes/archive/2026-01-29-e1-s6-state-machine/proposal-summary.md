# Proposal Summary: e1-s6-state-machine

## Architecture Decisions
- Stateless/reentrant state machine design - no global mutable state
- Regex-based intent detection for Epic 1 (LLM deferred to Epic 3)
- Agent state as derived/computed property from current command state
- Dependency injection for EventWriter integration
- Pure functions for core transition logic (testable without database)

## Implementation Approach
- Create IntentDetector service with regex patterns for question/completion detection
- Create StateMachine service with VALID_TRANSITIONS mapping
- Create CommandLifecycleManager for task creation/completion
- Integrate with EventWriter from Sprint 5 for state_transition events
- Process turn_detected events sequentially to handle rapid turns

## Files to Modify
**Services:**
- `src/claude_headspace/services/__init__.py` - Export new services

**New Files:**
- `src/claude_headspace/services/state_machine.py` - StateMachine class
- `src/claude_headspace/services/intent_detector.py` - IntentDetector with regex
- `src/claude_headspace/services/command_lifecycle.py` - CommandLifecycleManager
- `tests/services/test_state_machine.py` - Transition tests
- `tests/services/test_intent_detector.py` - Intent detection tests
- `tests/services/test_command_lifecycle.py` - Lifecycle tests

## Acceptance Criteria
- Valid transitions between all 5 states (idle, commanded, processing, awaiting_input, complete)
- Invalid transitions rejected with descriptive error
- Intent detection >90% accuracy on test cases
- State transition events written to Event table
- Command creation on user command
- Command completion with timestamp
- Agent state derived from current command

## Constraints and Gotchas
- CommandState enum already exists in models (idle, commanded, processing, awaiting_input, complete)
- TurnIntent enum already exists in models (command, answer, question, progress, completion)
- Use EventWriter from Sprint 5 for writing state_transition events
- Session UUID correlation to Agent - must handle unknown sessions gracefully
- User command while awaiting_input starts NEW task (abandons previous)
- Regex patterns need careful testing - completion phrases vs actual completion

## Git Change History

### Related Files
**Models:**
- src/claude_headspace/models/enums.py (CommandState, TurnIntent, TurnActor)
- src/claude_headspace/models/command.py (Command model)
- src/claude_headspace/models/agent.py (Agent model)

**Services:**
- src/claude_headspace/services/event_writer.py (Sprint 5)
- src/claude_headspace/services/event_schemas.py (Sprint 5)

### OpenSpec History
- e1-s5-event-system: Event writer service (just completed)
- e1-s3-domain-models: Created Command, Agent models with CommandState enum

### Implementation Patterns
**Detected structure from Sprint 5:**
1. Create service class with clear public API
2. Use dataclasses for data structures (TransitionResult)
3. Dependency injection for external services
4. Comprehensive logging at appropriate levels
5. Unit tests for all paths

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required**
- **Command/Turn models:** Already exist from Sprint 3
- **EventWriter:** Sprint 5 provides event writing capability
- **CommandState/TurnIntent enums:** Already defined in models

## Testing Strategy
- Test all valid state transitions (happy path matrix)
- Test all invalid transition rejections
- Test question detection regex patterns
- Test completion detection regex patterns
- Test progress default fallback
- Test user intent (command vs answer)
- Test task creation and completion
- Test agent state derivation
- Test state_transition event payload
- Test edge cases (unknown session, rapid turns)

## OpenSpec References
- proposal.md: openspec/changes/e1-s6-state-machine/proposal.md
- tasks.md: openspec/changes/e1-s6-state-machine/tasks.md
- spec.md: openspec/changes/e1-s6-state-machine/specs/state-machine/spec.md
