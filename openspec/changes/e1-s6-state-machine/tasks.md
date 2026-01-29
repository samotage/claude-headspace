# Tasks: e1-s6-state-machine

## Phase 1: Setup

- [ ] Verify existing TaskState and TurnIntent enums in models
- [ ] Review Event model for state_transition payload schema

## Phase 2: Implementation

### Intent Detector (FR5)
- [ ] Create intent_detector module
- [ ] Define QUESTION_PATTERNS regex list
- [ ] Define COMPLETION_PATTERNS regex list
- [ ] Implement detect_agent_intent() with pattern matching
- [ ] Implement detect_user_intent() based on current state
- [ ] Handle missing/empty text (default to progress)

### State Machine (FR3, FR4)
- [ ] Create state_machine module
- [ ] Define VALID_TRANSITIONS mapping
- [ ] Implement validate_transition() method
- [ ] Implement transition() method
- [ ] Return TransitionResult with valid/invalid + reason
- [ ] Log invalid transitions at WARNING level
- [ ] Ensure stateless/reentrant design

### Task Lifecycle Manager (FR6, FR7)
- [ ] Create task_lifecycle module
- [ ] Implement create_task() for new user commands
- [ ] Implement update_task_state() for transitions
- [ ] Implement complete_task() with completed_at timestamp
- [ ] Implement get_current_task() for agent
- [ ] Implement derive_agent_state() computed property

### State Transition Event Logging (FR8)
- [ ] Integrate with EventWriter from Sprint 5
- [ ] Write state_transition events on valid transitions
- [ ] Include agent_id, task_id, from_state, to_state, trigger, confidence

### Turn Event Processing (FR9)
- [ ] Create process_turn_event() function
- [ ] Correlate session_uuid to Agent
- [ ] Detect intent using IntentDetector
- [ ] Apply transition via StateMachine
- [ ] Handle unknown sessions gracefully

### Error Handling (FR10, FR11)
- [ ] Handle unknown session (log warning, skip)
- [ ] Handle invalid transition (log warning, don't update)
- [ ] Handle missing text (default to progress)
- [ ] Handle database errors (propagate, no partial state)
- [ ] Handle user command while awaiting_input (new task)

## Phase 3: Testing

- [ ] Test all valid state transitions (happy path)
- [ ] Test invalid transition rejections
- [ ] Test intent detection for question patterns
- [ ] Test intent detection for completion patterns
- [ ] Test intent detection fallback to progress
- [ ] Test user intent (command vs answer based on state)
- [ ] Test task creation on user command
- [ ] Test task completion with timestamp
- [ ] Test agent state derivation
- [ ] Test state_transition event payload
- [ ] Test unknown session handling
- [ ] Test rapid turns (sequential processing)
- [ ] Test user command while awaiting_input

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No linting errors
- [ ] Intent detection >90% accuracy on test cases
- [ ] Transition latency < 50ms verified
