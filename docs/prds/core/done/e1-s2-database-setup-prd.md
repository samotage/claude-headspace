---
validation:
  status: valid
  validated_at: '2026-01-29T10:30:00+11:00'
---

# Product Requirements Document (PRD) — Database Setup

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 2 — Postgres database connection and migrations
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the database infrastructure for Claude Headspace v3.1. Sprint 2 establishes Postgres connectivity, ORM abstraction, and a version-controlled migration system that all subsequent sprints depend on for persistent storage.

The deliverable is a fully configured database layer that connects to Postgres, provides an ORM for model definitions, and supports repeatable schema migrations via CLI commands. This foundation enables Sprint 3 (Domain Models) to define the Objective, Project, Agent, Command, Turn, and Event models with confidence that the database infrastructure is solid.

**Key Outcomes:**
- Postgres database connection using configuration from `config.yaml`
- ORM layer providing database abstraction for future models
- Version-controlled, repeatable database migrations via CLI
- Connection pooling for performance
- Health check integration reporting database status
- Graceful error handling for connection failures

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace v3.1 requires persistent storage for session tracking, event logging, and objective management. The event-driven architecture relies on a robust database layer to store events, state transitions, and audit trails. Postgres was chosen over SQLite for its superior concurrency handling (multiple writers: watcher process + Flask server) and performance with large event logs.

Sprint 1 establishes the Flask application foundation. Sprint 2 adds the database layer. Sprint 3 will define the domain models that use this infrastructure.

### 1.2 Target User

Developers building and maintaining Claude Headspace. The database setup must be straightforward (configuration-driven), reliable (connection pooling, error handling), and maintainable (migrations for schema evolution).

### 1.3 Success Moment

A developer configures Postgres credentials in `config.yaml`, runs `flask db upgrade`, and sees the health check endpoint report `"database": "connected"` — confirming the database layer is operational and ready for domain models.

---

## 2. Scope

### 2.1 In Scope

- Postgres database connection using configuration from `config.yaml`
- ORM layer providing database abstraction for models
- Version-controlled, repeatable database migrations
- Migration CLI commands (`flask db init`, `flask db migrate`, `flask db upgrade`, `flask db downgrade`)
- Database initialization verification (connection test on startup)
- Connection pooling with configurable pool size and timeout
- Config.yaml schema extension for database settings
- Environment variable overrides for database configuration
- Support for `DATABASE_URL` connection string (takes precedence)
- Graceful error handling for connection failures (app starts but reports unhealthy)
- Database health check integration (extend `/health` endpoint)

### 2.2 Out of Scope

- Domain models (Objective, Project, Agent, Command, Turn, Event) — Sprint 3
- Seed data or fixtures
- Database backup/restore utilities
- Multi-database support
- Read replicas or sharding
- Database administration UI
- Docker Compose for Postgres (documentation reference only)
- Production deployment configuration (SSL, connection strings)
- Database user/role creation scripts

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC-1:** Application connects to Postgres successfully on startup when credentials are valid
2. **SC-2:** `flask db init` creates the migrations directory structure
3. **SC-3:** `flask db migrate -m "message"` generates migration files when models are defined
4. **SC-4:** `flask db upgrade` applies pending migrations to the database
5. **SC-5:** `flask db downgrade` reverts the most recent migration
6. **SC-6:** Connection pooling uses the configured `pool_size` value
7. **SC-7:** Database configuration loads from `config.yaml` with environment variable overrides
8. **SC-8:** `DATABASE_URL` environment variable takes precedence over individual config fields
9. **SC-9:** `/health` endpoint includes `"database": "connected"` or `"database": "disconnected"` status
10. **SC-10:** Connection errors are logged with actionable messages (host, port, error type)

### 3.2 Non-Functional Success Criteria

1. **SC-11:** Database connection established within 5 seconds on startup
2. **SC-12:** Connection pool recovers from transient failures (auto-reconnect)
3. **SC-13:** No database credentials logged in plaintext (password masked in logs)

---

## 4. Functional Requirements (FRs)

### FR1: Database Configuration Schema

The application reads database configuration from `config.yaml` with the following schema:

```yaml
database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: postgres
  password: ""
  pool_size: 10
  pool_timeout: 30
```

All fields have sensible defaults. The `password` field defaults to empty string for local development.

### FR2: Environment Variable Overrides

Environment variables override configuration file values:

| Config Key | Environment Variable |
|------------|---------------------|
| `database.host` | `DATABASE_HOST` |
| `database.port` | `DATABASE_PORT` |
| `database.name` | `DATABASE_NAME` |
| `database.user` | `DATABASE_USER` |
| `database.password` | `DATABASE_PASSWORD` |
| `database.pool_size` | `DATABASE_POOL_SIZE` |
| `database.pool_timeout` | `DATABASE_POOL_TIMEOUT` |

### FR3: DATABASE_URL Support

If the `DATABASE_URL` environment variable is set, it takes precedence over all individual database configuration fields. The URL format follows the standard:

```
postgresql://user:password@host:port/database
```

### FR4: Database Connection

The application establishes a database connection during initialization. The connection uses the configured credentials and connection pool settings.

### FR5: Connection Pooling

The database connection uses a connection pool with:
- Configurable pool size (default: 10 connections)
- Configurable pool timeout (default: 30 seconds)
- Automatic connection recycling for stale connections

### FR6: Migration Commands

The application provides CLI commands for database migrations:

| Command | Description |
|---------|-------------|
| `flask db init` | Initialize migrations directory (run once) |
| `flask db migrate -m "message"` | Generate migration from model changes |
| `flask db upgrade` | Apply all pending migrations |
| `flask db downgrade` | Revert the most recent migration |
| `flask db current` | Show current migration revision |
| `flask db history` | Show migration history |

### FR7: Health Check Integration

The `/health` endpoint includes database connectivity status:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected"
}
```

When the database is unreachable:

```json
{
  "status": "degraded",
  "version": "0.1.0",
  "database": "disconnected",
  "database_error": "Connection refused"
}
```

The overall status is `"degraded"` (not `"unhealthy"`) when only the database is down, allowing the application to report its state.

### FR8: Connection Error Handling

When the database connection fails:
- The application logs the error with host, port, and error type
- The application continues to start (does not crash)
- The health check reports degraded status
- Subsequent database operations raise appropriate errors
- Passwords are never logged in plaintext

### FR9: Startup Connection Verification

On application startup, the database layer attempts to connect and verifies connectivity. The result is logged:
- Success: `INFO: Database connected to postgresql://user@host:port/database`
- Failure: `ERROR: Database connection failed: [error message]`

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Connection Timeout

Database connection attempts timeout after 5 seconds to prevent startup hangs when Postgres is unavailable.

### NFR2: Connection Recovery

The connection pool automatically recovers from transient connection failures. Stale connections are recycled before use.

### NFR3: Credential Security

Database passwords are never logged. When logging connection strings, the password is masked (e.g., `postgresql://user:***@host:port/db`).

### NFR4: Test Database Support

The configuration supports a separate test database. The test database name is derived from the main database name with `_test` suffix (e.g., `claude_headspace_test`) unless explicitly configured.

---

## 6. Technical Context (Implementation Guidance)

This section provides implementation guidance. These are recommendations, not requirements.

### 6.1 Recommended Stack

- **ORM:** SQLAlchemy 2.0+ (async-ready, type hints)
- **Migrations:** Flask-Migrate (wraps Alembic)
- **Connection:** psycopg2-binary or asyncpg

### 6.2 Flask-SQLAlchemy Integration

Use Flask-SQLAlchemy for Flask integration:

```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = build_database_url(config)
    db.init_app(app)
    return app
```

### 6.3 Flask-Migrate Setup

Initialize Flask-Migrate in the application factory:

```python
from flask_migrate import Migrate

migrate = Migrate()

def create_app():
    # ... app setup ...
    migrate.init_app(app, db)
    return app
```

### 6.4 Connection URL Construction

Build the database URL from config:

```python
def build_database_url(config: dict) -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    db = config["database"]
    return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
```

### 6.5 Connection Pool Configuration

Configure SQLAlchemy engine options:

```python
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": config["database"]["pool_size"],
    "pool_timeout": config["database"]["pool_timeout"],
    "pool_recycle": 3600,  # Recycle connections after 1 hour
    "pool_pre_ping": True,  # Verify connections before use
}
```

### 6.6 Health Check Database Query

Use a simple query to verify connectivity:

```python
def check_database_health() -> tuple[bool, str | None]:
    try:
        db.session.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)
```

### 6.7 File Structure

Extend the Sprint 1 structure:

```
src/claude_headspace/
├── __init__.py
├── app.py              # Application factory (extend)
├── config.py           # Config loader (extend)
├── database.py         # NEW: SQLAlchemy setup
├── routes/
│   └── health.py       # Health check (extend)
└── models/
    └── __init__.py     # NEW: Model base (empty for Sprint 2)

migrations/             # NEW: Flask-Migrate directory
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
```

### 6.8 Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    "flask-sqlalchemy>=3.1",
    "flask-migrate>=4.0",
    "psycopg2-binary>=2.9",
    # ... existing deps ...
]
```

---

## 7. Acceptance Tests

| Test ID | Description | Expected Result |
|---------|-------------|-----------------|
| AT-1 | Configure valid Postgres credentials, run `flask db upgrade` | Migrations apply successfully |
| AT-2 | GET `/health` with valid database | Returns `{"database": "connected"}` |
| AT-3 | GET `/health` with invalid database credentials | Returns `{"database": "disconnected", "status": "degraded"}` |
| AT-4 | Set `DATABASE_URL` env var, start app | Connects using URL (ignores config.yaml fields) |
| AT-5 | Set `DATABASE_HOST=otherhost`, start app | Uses `otherhost` instead of config.yaml value |
| AT-6 | Run `flask db init` in fresh project | Creates `migrations/` directory |
| AT-7 | Start app with Postgres stopped | App starts, logs error, health reports degraded |
| AT-8 | Check logs after connection failure | No password visible in log output |

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Postgres not installed on developer machine | High | Document installation steps; mention Homebrew/Docker options |
| Connection errors not handled gracefully | Medium | Explicit try/catch with logging; app continues running |
| Migration conflicts during parallel development | Low | Document migration merge process; use descriptive migration names |
| Pool exhaustion under load | Low | Configure appropriate pool_size; add monitoring guidance |

---

## 9. Dependencies

- **Requires:** Sprint 1 (Flask Bootstrap) — application factory, config loader
- **Blocks:** Sprint 3 (Domain Models) — needs database layer for model definitions
- **External:** Postgres server running and accessible

---

## 10. Open Questions

None — all questions resolved during workshop.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
