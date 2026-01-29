# Tasks: e1-s6-state-machine

## Phase 1: Setup

- [x] Verify existing TaskState and TurnIntent enums in models
- [x] Review Event model for state_transition payload schema

## Phase 2: Implementation

### Intent Detector (FR5)
- [x] Create intent_detector module
- [x] Define QUESTION_PATTERNS regex list
- [x] Define COMPLETION_PATTERNS regex list
- [x] Implement detect_agent_intent() with pattern matching
- [x] Implement detect_user_intent() based on current state
- [x] Handle missing/empty text (default to progress)

### State Machine (FR3, FR4)
- [x] Create state_machine module
- [x] Define VALID_TRANSITIONS mapping
- [x] Implement validate_transition() method
- [x] Implement transition() method
- [x] Return TransitionResult with valid/invalid + reason
- [x] Log invalid transitions at WARNING level
- [x] Ensure stateless/reentrant design

### Task Lifecycle Manager (FR6, FR7)
- [x] Create task_lifecycle module
- [x] Implement create_task() for new user commands
- [x] Implement update_task_state() for transitions
- [x] Implement complete_task() with completed_at timestamp
- [x] Implement get_current_task() for agent
- [x] Implement derive_agent_state() computed property

### State Transition Event Logging (FR8)
- [x] Integrate with EventWriter from Sprint 5
- [x] Write state_transition events on valid transitions
- [x] Include agent_id, task_id, from_state, to_state, trigger, confidence

### Turn Event Processing (FR9)
- [x] Create process_turn_event() function
- [x] Correlate session_uuid to Agent
- [x] Detect intent using IntentDetector
- [x] Apply transition via StateMachine
- [x] Handle unknown sessions gracefully

### Error Handling (FR10, FR11)
- [x] Handle unknown session (log warning, skip)
- [x] Handle invalid transition (log warning, don't update)
- [x] Handle missing text (default to progress)
- [x] Handle database errors (propagate, no partial state)
- [x] Handle user command while awaiting_input (new task)

## Phase 3: Testing

- [x] Test all valid state transitions (happy path)
- [x] Test invalid transition rejections
- [x] Test intent detection for question patterns
- [x] Test intent detection for completion patterns
- [x] Test intent detection fallback to progress
- [x] Test user intent (command vs answer based on state)
- [x] Test task creation on user command
- [x] Test task completion with timestamp
- [x] Test agent state derivation
- [x] Test state_transition event payload
- [x] Test unknown session handling
- [x] Test rapid turns (sequential processing)
- [x] Test user command while awaiting_input

## Phase 4: Final Verification

- [x] All tests passing
- [x] No linting errors
- [x] Intent detection >90% accuracy on test cases
- [x] Transition latency < 50ms verified
