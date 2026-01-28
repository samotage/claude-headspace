## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Dependencies Setup

- [x] 2.1.1 Add flask-sqlalchemy>=3.1 to pyproject.toml
- [x] 2.1.2 Add flask-migrate>=4.0 to pyproject.toml
- [x] 2.1.3 Add psycopg2-binary>=2.9 to pyproject.toml
- [x] 2.1.4 Run pip install to install dependencies

### 2.2 Configuration Extension

- [x] 2.2.1 Add database section defaults to config.py DEFAULTS
- [x] 2.2.2 Add database environment variable mappings to config.py ENV_MAPPINGS
- [x] 2.2.3 Add DATABASE_URL support to config.py (takes precedence)
- [x] 2.2.4 Update config.yaml with database section example

### 2.3 Database Module

- [x] 2.3.1 Create src/claude_headspace/database.py with SQLAlchemy instance
- [x] 2.3.2 Implement build_database_url() function with password masking for logs
- [x] 2.3.3 Implement init_database() function for Flask app integration
- [x] 2.3.4 Implement check_database_health() function for health checks
- [x] 2.3.5 Configure connection pooling options (pool_size, pool_timeout, pool_recycle, pool_pre_ping)

### 2.4 Application Factory Integration

- [x] 2.4.1 Import and initialize database module in app.py
- [x] 2.4.2 Initialize Flask-Migrate in app.py
- [x] 2.4.3 Add startup connection verification with logging
- [x] 2.4.4 Ensure app starts even if database connection fails

### 2.5 Health Check Extension

- [x] 2.5.1 Import check_database_health in routes/health.py
- [x] 2.5.2 Add database status to health check response
- [x] 2.5.3 Return "degraded" status when database disconnected
- [x] 2.5.4 Include database_error field when connection fails

### 2.6 Models Package

- [x] 2.6.1 Create src/claude_headspace/models/__init__.py (empty for Sprint 2)

### 2.7 Flask-Migrate Initialization

- [x] 2.7.1 Run flask db init to create migrations directory
- [x] 2.7.2 Verify migrations directory structure created

## 3. Testing (Phase 3)

### 3.1 Unit Tests

- [x] 3.1.1 Test database configuration loading from config.yaml
- [x] 3.1.2 Test environment variable overrides for all database fields
- [x] 3.1.3 Test DATABASE_URL precedence over individual fields
- [x] 3.1.4 Test build_database_url() with various configurations
- [x] 3.1.5 Test password masking in logging (no plaintext passwords)

### 3.2 Integration Tests

- [x] 3.2.1 Test health endpoint with valid database connection returns "connected"
- [x] 3.2.2 Test health endpoint with invalid database returns "degraded" status
- [x] 3.2.3 Test application starts when database is unavailable
- [x] 3.2.4 Test flask db commands are available (init, migrate, upgrade, downgrade)

### 3.3 Connection Pool Tests

- [x] 3.3.1 Test pool_size configuration is applied
- [x] 3.3.2 Test pool_timeout configuration is applied
- [x] 3.3.3 Test pool_pre_ping recovers from stale connections

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: flask db upgrade works with valid Postgres
- [ ] 4.4 Manual verification: /health shows database: connected
- [ ] 4.5 Manual verification: App starts with Postgres stopped, health shows degraded
