## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Dependencies & Configuration

- [x] 2.1.1 Add `factory-boy` to dev dependencies in `pyproject.toml`
- [x] 2.1.2 Install updated dependencies

### 2.2 Database Lifecycle Fixtures

- [x] 2.2.1 Create `tests/integration/__init__.py`
- [x] 2.2.2 Create `tests/integration/conftest.py` with:
  - Session-scoped fixture to create `claude_headspace_test` database (drop if exists, then create)
  - Session-scoped fixture to create all tables using model metadata (`Base.metadata.create_all`)
  - Function-scoped fixture for database session with per-test rollback/cleanup
  - Session-scoped fixture to teardown (drop) test database after all tests
  - Test database URL configuration via env var `TEST_DATABASE_URL` or fallback to config-based construction

### 2.3 Factory Boy Factories

- [x] 2.3.1 Create `tests/integration/factories.py` with SQLAlchemyModelFactory definitions:
  - `ProjectFactory` — generates valid Project with unique path, name
  - `AgentFactory` — generates valid Agent with UUID, links to Project (SubFactory)
  - `CommandFactory` — generates valid Task with state=IDLE default, links to Agent (SubFactory)
  - `TurnFactory` — generates valid Turn with actor, intent, text, links to Task (SubFactory)
  - `EventFactory` — generates valid Event with event_type, optional foreign keys
  - `ObjectiveFactory` — generates valid Objective with text and timestamp
  - `ObjectiveHistoryFactory` — generates valid ObjectiveHistory, links to Objective (SubFactory)

### 2.4 Integration Tests

- [x] 2.4.1 Create `tests/integration/test_factories.py` — verify each factory produces a persistable instance
- [x] 2.4.2 Create `tests/integration/test_persistence_flow.py` — end-to-end test:
  - Create Project → Agent → Command → Turn → Event chain
  - Persist all entities
  - Retrieve all entities from fresh query
  - Assert data integrity (field values, relationships, foreign keys)
- [x] 2.4.3 Create `tests/integration/test_model_constraints.py` — verify database constraints:
  - Unique constraint on Project.path
  - Unique index on Agent.session_uuid
  - Cascade delete behavior (Agent deletion cascades to Commands, Turns)
  - NOT NULL enforcement
  - Enum constraint enforcement (CommandState, TurnActor, TurnIntent)

### 2.5 Documentation

- [x] 2.5.1 Create `docs/testing/integration-testing-guide.md` with:
  - Prerequisites (local Postgres instance)
  - How to run integration tests
  - How to write a new integration test (step-by-step with example)
  - Factory usage patterns
  - Fixture reference

## 3. Testing (Phase 3)

- [ ] 3.1 Run `pytest tests/integration/` and verify all tests pass against real Postgres
- [ ] 3.2 Run `pytest` (full suite) and verify integration tests coexist with existing unit tests
- [ ] 3.3 Verify test database is created at session start and destroyed at session end
- [ ] 3.4 Verify no data leaks between tests (run tests multiple times, check isolation)

## 4. Final Verification

- [ ] 4.1 All tests passing (both unit and integration)
- [ ] 4.2 No linter errors
- [ ] 4.3 Factory definitions validated against all model constraints
- [ ] 4.4 Documentation reviewed for completeness
