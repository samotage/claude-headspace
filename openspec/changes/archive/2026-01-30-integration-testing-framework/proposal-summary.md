# Proposal Summary: integration-testing-framework

## Architecture Decisions
- Use `Base.metadata.create_all()` for schema creation rather than running Alembic migrations in tests — simpler, faster, and guarantees model-metadata parity
- Session-scoped database creation/teardown (once per test run), function-scoped session cleanup (per test) for balance of speed and isolation
- Per-test isolation via transaction rollback — each test runs in a savepoint that is rolled back, avoiding full table truncation
- Factory Boy with `SQLAlchemyModelFactory` base class, session injected via `conftest.py` fixture
- Test database name derived from production config with `_test` suffix (`claude_headspace_test`)

## Implementation Approach
- Create `tests/integration/` as a self-contained test package with its own `conftest.py` managing the full database lifecycle
- Factories defined in a single `factories.py` module — 7 factories matching the 7 models (Project, Agent, Task, Turn, Event, Objective, ObjectiveHistory)
- Factories use `SubFactory` for parent relationships to auto-create dependency chains
- Proof-of-concept tests cover: factory validation (all 7 produce persistable instances), end-to-end persistence flow (Project → Agent → Task → Turn → Event), and constraint verification
- Database URL configurable via `TEST_DATABASE_URL` env var, with fallback to config.yaml values + `_test` suffix on database name

## Files to Modify
- `pyproject.toml` — add `factory-boy` to dev dependencies

## Files to Create
- `tests/integration/__init__.py` — package marker
- `tests/integration/conftest.py` — database lifecycle fixtures (create DB, create tables, session management, teardown)
- `tests/integration/factories.py` — Factory Boy factory definitions for all 7 models
- `tests/integration/test_factories.py` — validate each factory produces persistable instances
- `tests/integration/test_persistence_flow.py` — end-to-end entity chain test
- `tests/integration/test_model_constraints.py` — database constraint verification tests
- `docs/testing/integration-testing-guide.md` — pattern documentation

## Acceptance Criteria
- `pytest tests/integration/` runs all integration tests against real Postgres
- Test database created automatically at session start, destroyed at session end
- Each test starts with clean database state (no data leaks)
- Factory Boy factories for all 7 models produce valid, persistable instances
- At least one test verifies full entity chain: Project → Agent → Task → Turn → Event
- Integration tests coexist with existing unit tests (`pytest` runs everything)
- Pattern documentation enables writing new integration tests by example

## Constraints and Gotchas
- **Postgres required** — tests will skip/fail without a running Postgres instance; SQLite not acceptable
- **Database user needs CREATE DATABASE privilege** — the test fixture creates/drops databases
- **Enum types are PostgreSQL-specific** — TaskState, TurnActor, TurnIntent use `create_constraint=True` with PG enum types
- **Event model uses JSONB** — PostgreSQL-specific column type for `payload` field
- **Timezone-aware datetimes** — all DateTime columns use `timezone=True`, factories must generate timezone-aware timestamps
- **Unique constraints** — Project.path (unique), Agent.session_uuid (unique index) must be unique per factory instance
- **Cascade deletes** — Agent → Task → Turn cascades; Objective → ObjectiveHistory cascades; Event FKs use SET NULL
- **Flask-SQLAlchemy context** — `db.session` requires Flask app context; integration test fixtures need to handle app context properly
- **Existing test isolation** — integration tests must not interfere with mock-based unit tests (separate conftest.py, separate database)

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/project.py`, `agent.py`, `task.py`, `turn.py`, `event.py`, `objective.py`
- Database: `src/claude_headspace/database.py` (SQLAlchemy init, engine config, health checks)
- Config: `src/claude_headspace/config.py` (database env var mappings, config loading)
- Migrations: `migrations/versions/` (4 migration files defining schema evolution)
- Tests: `tests/conftest.py` (existing root fixtures), `tests/test_models.py`, `tests/test_database.py`

### OpenSpec History
- No previous OpenSpec changes to the testing subsystem

### Implementation Patterns
- Flask app factory pattern via `create_app(config_path)`
- Service injection via `app.extensions["service_name"]`
- Database access via `db` global from `database.py` (Flask-SQLAlchemy)
- Existing test fixtures: `app` (Flask app), `client` (test client), `temp_config` (YAML config)
- Existing model tests use `app_with_db` and `db_session` fixtures in `test_models.py`

## Q&A History
- No clarification needed — PRD was sufficiently clear and no gaps or conflicts detected

## Dependencies
- **factory-boy** — required dev dependency (not currently installed)
- **psycopg2-binary** — already installed (PostgreSQL driver)
- **Flask-SQLAlchemy** — already installed (>=3.1)
- No external services or APIs required
- No database migrations needed (test DB uses `create_all()` from model metadata)

## Testing Strategy
- **Factory validation tests** — each of 7 factories creates an instance, persists it, retrieves it, asserts field values
- **End-to-end persistence test** — full chain: Project → Agent → Task → Turn → Event creation, persistence, retrieval, assertion
- **Constraint tests** — unique constraints, NOT NULL enforcement, enum validation, cascade delete behavior
- **Isolation tests** — verify no data leaks between test functions
- **Coexistence test** — run full `pytest` suite to verify no interference with existing unit tests

## OpenSpec References
- proposal.md: openspec/changes/integration-testing-framework/proposal.md
- tasks.md: openspec/changes/integration-testing-framework/tasks.md
- spec.md: openspec/changes/integration-testing-framework/specs/testing/spec.md
