# database Specification

## Purpose
TBD - created by archiving change e1-s2-database-setup. Update Purpose after archive.
## Requirements
### Requirement: Database Configuration Schema

The application SHALL read database configuration from `config.yaml` with the following schema:

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

All fields SHALL have sensible defaults. The `password` field SHALL default to empty string for local development.

#### Scenario: Valid configuration file

- **WHEN** config.yaml contains valid database section
- **THEN** application uses specified values for connection

#### Scenario: Missing configuration file

- **WHEN** config.yaml does not exist or lacks database section
- **THEN** application uses default values

---

### Requirement: Environment Variable Overrides

Environment variables SHALL override configuration file values with the following mappings:

| Config Key | Environment Variable |
|------------|---------------------|
| `database.host` | `DATABASE_HOST` |
| `database.port` | `DATABASE_PORT` |
| `database.name` | `DATABASE_NAME` |
| `database.user` | `DATABASE_USER` |
| `database.password` | `DATABASE_PASSWORD` |
| `database.pool_size` | `DATABASE_POOL_SIZE` |
| `database.pool_timeout` | `DATABASE_POOL_TIMEOUT` |

#### Scenario: Environment variable set

- **WHEN** DATABASE_HOST=otherhost is set
- **THEN** application connects to "otherhost" instead of config.yaml value

#### Scenario: Environment variable not set

- **WHEN** environment variable is not set
- **THEN** application uses config.yaml value or default

---

### Requirement: DATABASE_URL Support

If the `DATABASE_URL` environment variable is set, it SHALL take precedence over all individual database configuration fields.

#### Scenario: DATABASE_URL set

- **WHEN** DATABASE_URL=postgresql://user:pass@host:5432/db is set
- **THEN** application connects using URL, ignoring individual config fields

#### Scenario: DATABASE_URL not set

- **WHEN** DATABASE_URL is not set
- **THEN** application builds URL from individual configuration fields

---

### Requirement: Database Connection

The application SHALL establish a database connection during initialization using configured credentials and connection pool settings.

#### Scenario: Valid credentials

- **WHEN** Postgres server is running with valid credentials
- **THEN** connection is established within 5 seconds

#### Scenario: Invalid credentials

- **WHEN** credentials are invalid or Postgres unavailable
- **THEN** connection fails gracefully, application continues to start

---

### Requirement: Connection Pooling

The database connection SHALL use a connection pool with:
- Configurable pool size (default: 10 connections)
- Configurable pool timeout (default: 30 seconds)
- Automatic connection recycling for stale connections (pool_recycle: 3600)
- Connection verification before use (pool_pre_ping: True)

#### Scenario: Pool configuration applied

- **WHEN** pool_size: 5 is configured
- **THEN** SQLAlchemy engine uses pool_size=5

#### Scenario: Stale connection recovery

- **WHEN** connection becomes stale
- **THEN** pool_pre_ping detects and replaces it before use

---

### Requirement: Migration Commands

The application SHALL provide CLI commands for database migrations:

| Command | Description |
|---------|-------------|
| `flask db init` | Initialize migrations directory (run once) |
| `flask db migrate -m "message"` | Generate migration from model changes |
| `flask db upgrade` | Apply all pending migrations |
| `flask db downgrade` | Revert the most recent migration |
| `flask db current` | Show current migration revision |
| `flask db history` | Show migration history |

#### Scenario: Initialize migrations

- **WHEN** `flask db init` is run in fresh project
- **THEN** migrations/ directory is created with alembic.ini, env.py, versions/

#### Scenario: Apply migrations

- **WHEN** `flask db upgrade` is run
- **THEN** all pending migrations are applied to database

---

### Requirement: Health Check Integration

The `/health` endpoint SHALL include database connectivity status.

#### Scenario: Database connected

- **WHEN** GET /health with valid database connection
- **THEN** response includes `{"status": "healthy", "database": "connected"}`

#### Scenario: Database disconnected

- **WHEN** GET /health with database unavailable
- **THEN** response includes `{"status": "degraded", "database": "disconnected", "database_error": "[error message]"}`

---

### Requirement: Connection Error Handling

The application SHALL handle database connection failures gracefully. When the connection fails, the application SHALL log the error with host, port, and error type, SHALL continue to start (does not crash), and the health check SHALL report degraded status. Subsequent database operations SHALL raise appropriate errors. Passwords SHALL NEVER be logged in plaintext.

#### Scenario: Connection failure logging

- **WHEN** database connection fails
- **THEN** error is logged with masked password (e.g., postgresql://user:***@host:port/db)

#### Scenario: Application resilience

- **WHEN** Postgres server is stopped
- **THEN** application starts, logs error, health reports degraded

---

### Requirement: Startup Connection Verification

On application startup, the database layer SHALL attempt to connect and verify connectivity. The result SHALL be logged.

#### Scenario: Successful connection

- **WHEN** database connects successfully
- **THEN** log: `INFO: Database connected to postgresql://user@host:port/database`

#### Scenario: Failed connection

- **WHEN** database connection fails
- **THEN** log: `ERROR: Database connection failed: [error message]`

