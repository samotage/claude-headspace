# Proposal Summary: e1-s2-database-setup

## Architecture Decisions
- Use Flask-SQLAlchemy for ORM integration with Flask application factory pattern
- Use Flask-Migrate (wrapping Alembic) for version-controlled migrations
- Use psycopg2-binary for Postgres connectivity
- Graceful degradation: app starts even when database unavailable
- Connection pooling with pre-ping for reliability

## Implementation Approach
- Extend existing Sprint 1 code rather than replacing it
- Add database.py module with SQLAlchemy instance and helper functions
- Extend config.py with database configuration defaults and env var mappings
- Extend health.py to include database status
- Follow Flask application factory pattern for initialization

## Files to Modify
### Extend
- `src/claude_headspace/app.py` - Add SQLAlchemy and Flask-Migrate initialization
- `src/claude_headspace/config.py` - Add database defaults and env var mappings
- `src/claude_headspace/routes/health.py` - Add database connectivity status
- `config.yaml` - Add database section
- `pyproject.toml` - Add dependencies

### Create New
- `src/claude_headspace/database.py` - SQLAlchemy setup and helpers
- `src/claude_headspace/models/__init__.py` - Model base (empty for Sprint 2)
- `migrations/` - Flask-Migrate directory (via flask db init)

## Acceptance Criteria
- SC-1: Application connects to Postgres on startup when credentials valid
- SC-2: `flask db init` creates migrations directory
- SC-3: `flask db migrate` generates migration files
- SC-4: `flask db upgrade` applies pending migrations
- SC-5: `flask db downgrade` reverts migrations
- SC-6: Connection pooling uses configured pool_size
- SC-7: Config loads from config.yaml with env var overrides
- SC-8: DATABASE_URL takes precedence over individual fields
- SC-9: /health includes database status (connected/disconnected)
- SC-10: Connection errors logged with actionable messages
- SC-11: Connection established within 5 seconds
- SC-12: Connection pool recovers from transient failures
- SC-13: No passwords logged in plaintext

## Constraints and Gotchas
- Postgres must be running for full functionality (but app starts without it)
- Password masking required in all log output
- Test database name derived with `_test` suffix
- Connection timeout is 5 seconds to prevent startup hangs
- pool_pre_ping=True ensures stale connections are detected

## Git Change History

### Related Files
- Config: _bmad/_config/agents/core-bmad-master.customize.yaml, _bmad/core/config.yaml
- No existing database-related files (greenfield for this subsystem)

### OpenSpec History
- No previous changes to database subsystem

### Implementation Patterns
- Existing config pattern: DEFAULTS dict + ENV_MAPPINGS for overrides
- Health endpoint returns JSON with status field
- Application factory pattern with register_blueprints()

## Q&A History
- No clarifications needed - PRD was complete and unambiguous

## Dependencies
- flask-sqlalchemy>=3.1
- flask-migrate>=4.0
- psycopg2-binary>=2.9
- External: Postgres server running and accessible

## Testing Strategy
- Unit tests for config loading and URL building
- Unit tests for password masking
- Integration tests for health endpoint with/without database
- Integration tests for flask db commands
- Tests for connection pool configuration

## OpenSpec References
- proposal.md: openspec/changes/e1-s2-database-setup/proposal.md
- tasks.md: openspec/changes/e1-s2-database-setup/tasks.md
- spec.md: openspec/changes/e1-s2-database-setup/specs/database/spec.md
