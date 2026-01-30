## Why

The current test suite (780+ tests) mocks SQLAlchemy sessions, engines, and repository methods extensively, creating false confidence that persistence logic works. Tests pass even when underlying database operations are broken. A real integration testing framework running against Postgres is needed to verify actual data persistence and retrieval.

## What Changes

- Add `factory-boy` dev dependency for test data generation
- Create `tests/integration/conftest.py` with database lifecycle fixtures (create/teardown test DB, session management, per-test cleanup)
- Create Factory Boy factories for all 7 models: Project, Agent, Task, Turn, Event, Objective, ObjectiveHistory
- Create `tests/integration/` directory with proof-of-concept integration tests
- Add integration testing pattern documentation
- Configure test database connection (`claude_headspace_test`) separate from production

## Impact

- Affected specs: testing infrastructure, developer workflow
- Affected code:
  - `pyproject.toml` — add factory-boy dependency
  - `tests/integration/conftest.py` — new: database lifecycle fixtures
  - `tests/integration/factories.py` — new: Factory Boy factory definitions
  - `tests/integration/test_persistence_flow.py` — new: end-to-end persistence tests
  - `tests/integration/test_factories.py` — new: factory validation tests
  - `docs/testing/integration-testing-guide.md` — new: pattern documentation
- No changes to production code, existing tests, or database configuration
- No breaking changes — additive only
