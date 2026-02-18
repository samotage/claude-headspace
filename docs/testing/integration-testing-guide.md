# Integration Testing Guide

## Prerequisites

- **PostgreSQL** running locally (the test database must be Postgres)
- The database user must have **CREATE DATABASE** privileges
- Python dependencies installed: `pip install -e ".[dev]"`

## Running Integration Tests

```bash
# Run only integration tests
pytest tests/integration/

# Run all tests (unit + integration)
pytest

# Run with verbose output
pytest tests/integration/ -v

# Run a specific test file
pytest tests/integration/test_persistence_flow.py
```

## Configuration

The test database URL is resolved in this order:

1. `TEST_DATABASE_URL` environment variable (if set)
2. Auto-constructed from `config.yaml` database settings with `_test` suffix

Example with env var:

```bash
TEST_DATABASE_URL=postgresql://user@localhost:5432/claude_headspace_test pytest tests/integration/
```

## Database Lifecycle

The test infrastructure manages the database automatically:

1. **Session start**: Creates `claude_headspace_test` database (drops it first if it exists from a previous interrupted run)
2. **Schema creation**: Uses `db.metadata.create_all()` to create all tables
3. **Per-test isolation**: Each test function gets a database session wrapped in a transaction that is rolled back after the test
4. **Session end**: Drops the test database

No manual setup or cleanup is required.

## Writing a New Integration Test

### Step 1: Create a test file in `tests/integration/`

```python
"""Description of what this test file covers."""

import pytest
from sqlalchemy import select

from claude_headspace.models import Project, Agent
from .factories import ProjectFactory, AgentFactory


@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    """Inject the test db_session into all factories you use."""
    ProjectFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session


class TestMyFeature:
    def test_something(self, db_session):
        # Create test data using factories
        project = ProjectFactory(name="my-project")
        db_session.flush()

        # Query the database
        result = db_session.execute(
            select(Project).where(Project.id == project.id)
        ).scalar_one()

        # Assert
        assert result.name == "my-project"
```

### Step 2: Use the `db_session` fixture

The `db_session` fixture provides a SQLAlchemy session connected to the test database. Each test's changes are automatically rolled back.

### Step 3: Use factories to create test data

Factories auto-create parent entities via `SubFactory`:

```python
# Creates a Turn + its Command + its Agent + its Project
turn = TurnFactory(text="Hello")
db_session.flush()

# Or create a specific chain
project = ProjectFactory(name="specific-project")
agent = AgentFactory(project=project)
command = CommandFactory(agent=agent)
db_session.flush()
```

### Step 4: Flush and query

Call `db_session.flush()` after creating entities to ensure they're written to the database, then use SQLAlchemy `select()` to query:

```python
from sqlalchemy import select

result = db_session.execute(
    select(Agent).where(Agent.project_id == project.id)
).scalars().all()
```

## Factory Reference

| Factory | Model | Auto-creates |
|---------|-------|-------------|
| `ProjectFactory` | Project | — |
| `AgentFactory` | Agent | Project |
| `CommandFactory` | Command | Agent, Project |
| `TurnFactory` | Turn | Command, Agent, Project |
| `EventFactory` | Event | — (references are optional) |
| `ObjectiveFactory` | Objective | — |
| `ObjectiveHistoryFactory` | ObjectiveHistory | Objective |

### Overriding factory defaults

```python
# Override specific fields
project = ProjectFactory(name="custom", path="/custom/path")

# Override parent entity
my_project = ProjectFactory()
agent = AgentFactory(project=my_project)

# Override enum values
command = CommandFactory(state=CommandState.PROCESSING)
turn = TurnFactory(actor=TurnActor.AGENT, intent=TurnIntent.COMPLETION)
```

## Fixture Reference

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_database_url` | session | The test database connection URL |
| `test_db_engine` | session | SQLAlchemy engine connected to test DB (manages create/drop) |
| `TestSessionFactory` | session | `sessionmaker` bound to test engine |
| `db_session` | function | Per-test session with automatic rollback |
