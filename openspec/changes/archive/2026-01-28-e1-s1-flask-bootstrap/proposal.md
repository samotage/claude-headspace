# Proposal: e1-s1-flask-bootstrap

## Why

Claude Headspace v3.1 requires a complete rewrite with an event-driven architecture. Sprint 1 establishes the Flask foundation that all other sprints depend on — database setup, domain models, API endpoints, and the dashboard UI all require a properly structured Flask application.

## What Changes

- Create Flask application with application factory pattern for testability
- Implement configuration loading from `config.yaml` with environment variable overrides
- Add health check endpoint (`GET /health`) returning JSON status
- Create styled error pages (404, 500) with dark terminal theme
- Set up structured logging to console and file
- Establish Python project structure with `pyproject.toml` and `src/` layout
- Implement Tailwind CSS build pipeline (PostCSS-based)
- Create base HTML template with dark terminal aesthetic

## Impact

### Affected specs
- None (greenfield project - first sprint)

### Affected code
This creates new files:

**Python Application:**
- `src/claude_headspace/__init__.py` - Package init
- `src/claude_headspace/app.py` - Application factory
- `src/claude_headspace/config.py` - Configuration loader
- `src/claude_headspace/routes/health.py` - Health check route

**Templates:**
- `templates/base.html` - Base template with dark theme
- `templates/errors/404.html` - Not found error page
- `templates/errors/500.html` - Server error page

**Static Assets:**
- `static/css/main.css` - Compiled Tailwind CSS
- `static/css/src/input.css` - Source CSS with Tailwind directives

**Configuration:**
- `pyproject.toml` - Python package metadata and dependencies
- `package.json` - Node dependencies for Tailwind
- `tailwind.config.js` - Tailwind configuration
- `postcss.config.js` - PostCSS configuration

**Tests:**
- `tests/test_app.py` - Application tests

### Breaking changes
None - this is a greenfield implementation.
