## Why

Claude Headspace v3.1 requires persistent storage for session tracking, event logging, and objective management. The event-driven architecture needs a robust database layer to store events, state transitions, and audit trails. Postgres was chosen for its superior concurrency handling (multiple writers: watcher process + Flask server) and performance with large event logs.

## What Changes

- Add Postgres database connection using configuration from `config.yaml`
- Integrate Flask-SQLAlchemy as the ORM layer for database abstraction
- Add Flask-Migrate for version-controlled, repeatable database migrations
- Implement CLI commands (`flask db init`, `flask db migrate`, `flask db upgrade`, `flask db downgrade`)
- Add database initialization verification (connection test on startup)
- Configure connection pooling with configurable pool size and timeout
- Extend `config.yaml` schema with database settings section
- Support environment variable overrides for all database configuration
- Support `DATABASE_URL` connection string (takes precedence over individual fields)
- Implement graceful error handling for connection failures (app starts but reports degraded)
- Extend `/health` endpoint to include database connectivity status

## Impact

- Affected specs: Database configuration, health check behavior
- Affected code:
  - `src/claude_headspace/app.py` - Extend application factory to initialize SQLAlchemy and Flask-Migrate
  - `src/claude_headspace/config.py` - Add database configuration defaults and environment variable mappings
  - `src/claude_headspace/database.py` - **NEW** SQLAlchemy setup and helper functions
  - `src/claude_headspace/routes/health.py` - Extend to include database connectivity status
  - `src/claude_headspace/models/__init__.py` - **NEW** Model base (empty for Sprint 2)
  - `config.yaml` - Add database section with connection settings
  - `pyproject.toml` - Add flask-sqlalchemy, flask-migrate, psycopg2-binary dependencies
  - `migrations/` - **NEW** Flask-Migrate directory structure
