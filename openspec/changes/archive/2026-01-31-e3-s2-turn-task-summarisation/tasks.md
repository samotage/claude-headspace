## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Data Model

- [x] 2.1 Add `summary` (Text, nullable) and `summary_generated_at` (DateTime, nullable) fields to Turn model
- [x] 2.2 Add `summary` (Text, nullable) and `summary_generated_at` (DateTime, nullable) fields to Command model
- [x] 2.3 Create Alembic migration for summary fields on turns and tasks tables

### 2.2 Summarisation Service

- [x] 2.4 Create `src/claude_headspace/services/summarisation_service.py` with TurnSummarisationService and TaskSummarisationService
- [x] 2.5 Implement turn summarisation: build prompt from turn text/actor/intent, call inference service at "turn" level
- [x] 2.6 Implement command summarisation: build prompt from task timestamps/turn count/final turn, call inference at "command" level
- [x] 2.7 Implement summary persistence: update Turn/Command model summary fields after successful inference
- [x] 2.8 Implement SSE broadcast of summary updates after generation
- [x] 2.9 Implement graceful degradation: handle inference unavailable, failed calls, log errors

### 2.3 API Endpoints

- [x] 2.10 Create `src/claude_headspace/routes/summarisation.py` blueprint with POST `/api/summarise/turn/<id>` and POST `/api/summarise/command/<id>`
- [x] 2.11 Register summarisation blueprint and init service in app.py

### 2.4 Integration

- [x] 2.12 Integrate summarisation trigger into CommandLifecycleManager after turn processing
- [x] 2.13 Integrate summarisation trigger into CommandLifecycleManager on command completion

### 2.5 Dashboard Updates

- [x] 2.14 Update dashboard route to include summary data in agent card rendering
- [x] 2.15 Update agent card template to display summaries and "Summarising..." placeholder

### 2.6 Tests

- [x] 2.16 Create unit tests for TurnSummarisationService
- [x] 2.17 Create unit tests for CommandSummarisationService
- [x] 2.18 Create unit tests for summarisation routes (turn and task endpoints)
- [x] 2.19 Create integration tests for summary field persistence on Turn and Command models
- [x] 2.20 Create unit tests for CommandLifecycleManager summarisation integration

## 3. Testing (Phase 3)

- [ ] 3.1 Run `pytest tests/` and verify all tests pass
- [ ] 3.2 Verify turn summaries generated when new turns arrive
- [ ] 3.3 Verify command summaries generated on command completion
- [ ] 3.4 Verify caching prevents duplicate inference calls
- [ ] 3.5 Verify graceful degradation when inference service unavailable

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Alembic migration applies cleanly
- [ ] 4.4 API endpoints return expected responses
