# Proposal Summary: e1-s1-flask-bootstrap

## Architecture Decisions
- Use Flask application factory pattern (`create_app()`) for testability
- Configuration hierarchy: defaults -> config.yaml -> environment variables
- Tailwind CSS with PostCSS build pipeline (not CDN) for maintainability
- Structured logging with dual output (console + file)
- Dark terminal theme from existing Claude Monitor v2 design

## Implementation Approach
- Create new `src/claude_headspace/` Python package structure
- Use `pyproject.toml` for modern Python packaging
- Implement config loader with PyYAML and python-dotenv
- Register blueprints for modular route organization
- Use CSS custom properties for theme colors, integrated with Tailwind

## Files to Modify

### Python Application (NEW)
- `src/claude_headspace/__init__.py` - Package init with version
- `src/claude_headspace/app.py` - Application factory
- `src/claude_headspace/config.py` - Configuration loader
- `src/claude_headspace/routes/__init__.py` - Routes package
- `src/claude_headspace/routes/health.py` - Health check blueprint

### Templates (NEW)
- `templates/base.html` - Base template with dark theme
- `templates/errors/404.html` - Not found error page
- `templates/errors/500.html` - Server error page

### Static Assets (NEW)
- `static/css/src/input.css` - Source CSS with Tailwind directives
- `static/css/main.css` - Compiled Tailwind CSS (generated)

### Configuration (NEW)
- `pyproject.toml` - Python package metadata and dependencies
- `config.yaml` - Application configuration (server settings)
- `package.json` - Node dependencies for Tailwind
- `tailwind.config.js` - Tailwind configuration with theme colors
- `postcss.config.js` - PostCSS configuration

### Tests (NEW)
- `tests/conftest.py` - Pytest fixtures
- `tests/test_app.py` - Application tests

## Acceptance Criteria
- `flask run` starts server on configured port (default 5050)
- `GET /health` returns `{"status": "healthy", "version": "..."}`
- 404/500 error pages render with dark terminal theme
- Environment variables override config.yaml values
- Logs include timestamp, level, module, and message
- `npm run build:css` compiles Tailwind successfully

## Constraints and Gotchas
- Flask 3.0+ requires Python 3.10+
- Tailwind requires Node.js for build pipeline
- Logs directory must be created and gitignored
- Error pages must not expose sensitive info in production mode
- CSS custom properties must match established Claude Monitor theme exactly

## Git Change History

### Related Files
- None - this is a greenfield implementation

### OpenSpec History
- None - first change in this subsystem

### Implementation Patterns
- Greenfield project: no existing patterns to follow
- Follow Flask best practices: blueprints, application factory
- Follow Python packaging conventions: src/ layout, pyproject.toml

## Q&A History
- No clarifications needed - PRD was comprehensive and clear

## Dependencies

### Python Dependencies
- Flask >= 3.0
- PyYAML >= 6.0
- python-dotenv >= 1.0

### Node Dependencies (devDependencies)
- tailwindcss
- postcss
- autoprefixer
- postcss-cli

## Testing Strategy

### Unit Tests
- Test application factory creates valid app instance
- Test config loading from file and environment
- Test health endpoint returns correct response
- Test error handlers return styled pages

### Integration Tests
- Test server startup and shutdown
- Test log file creation and format
- Test CSS build pipeline

## OpenSpec References
- proposal.md: openspec/changes/e1-s1-flask-bootstrap/proposal.md
- tasks.md: openspec/changes/e1-s1-flask-bootstrap/tasks.md
- specs:
  - openspec/changes/e1-s1-flask-bootstrap/specs/flask-app/spec.md
  - openspec/changes/e1-s1-flask-bootstrap/specs/health-check/spec.md
  - openspec/changes/e1-s1-flask-bootstrap/specs/error-handling/spec.md
  - openspec/changes/e1-s1-flask-bootstrap/specs/logging/spec.md
  - openspec/changes/e1-s1-flask-bootstrap/specs/configuration/spec.md
  - openspec/changes/e1-s1-flask-bootstrap/specs/tailwind-css/spec.md
