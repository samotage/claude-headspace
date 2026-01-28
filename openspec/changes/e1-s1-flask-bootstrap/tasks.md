# Tasks: e1-s1-flask-bootstrap

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Project Structure Setup
- [ ] 2.1.1 Create `pyproject.toml` with package metadata and dependencies (Flask >= 3.0, PyYAML >= 6.0, python-dotenv >= 1.0)
- [ ] 2.1.2 Create `src/claude_headspace/` directory structure
- [ ] 2.1.3 Create `__init__.py` with version info

### 2.2 Configuration System
- [ ] 2.2.1 Implement `config.py` with YAML loading
- [ ] 2.2.2 Add environment variable override support (FLASK_SERVER_HOST, FLASK_SERVER_PORT, FLASK_DEBUG, FLASK_LOG_LEVEL)
- [ ] 2.2.3 Create default `config.yaml` at project root

### 2.3 Application Factory
- [ ] 2.3.1 Implement `app.py` with `create_app()` factory function
- [ ] 2.3.2 Configure Flask to use templates and static directories
- [ ] 2.3.3 Register error handlers (404, 500)
- [ ] 2.3.4 Set up structured logging (console + file)

### 2.4 Health Check Endpoint
- [ ] 2.4.1 Create `routes/health.py` blueprint
- [ ] 2.4.2 Implement `GET /health` returning `{"status": "healthy", "version": "..."}`
- [ ] 2.4.3 Register blueprint in application factory

### 2.5 Templates
- [ ] 2.5.1 Create `templates/base.html` with dark terminal theme
- [ ] 2.5.2 Create `templates/errors/404.html` extending base
- [ ] 2.5.3 Create `templates/errors/500.html` extending base

### 2.6 Tailwind CSS Pipeline
- [ ] 2.6.1 Create `package.json` with Tailwind dependencies
- [ ] 2.6.2 Create `tailwind.config.js` with theme colors
- [ ] 2.6.3 Create `postcss.config.js`
- [ ] 2.6.4 Create `static/css/src/input.css` with Tailwind directives and CSS custom properties
- [ ] 2.6.5 Add npm scripts: `build:css` and `watch:css`
- [ ] 2.6.6 Build initial CSS output to `static/css/main.css`

### 2.7 Logging Setup
- [ ] 2.7.1 Create `logs/` directory (add to .gitignore)
- [ ] 2.7.2 Configure logging with ISO 8601 timestamps
- [ ] 2.7.3 Set up dual output (console + logs/app.log)

## 3. Testing (Phase 3)

- [ ] 3.1 Test `flask run` starts server on configured port (SC-1)
- [ ] 3.2 Test `GET /health` returns 200 with correct JSON (SC-2)
- [ ] 3.3 Test config loads from `config.yaml` (SC-3)
- [ ] 3.4 Test environment variable overrides (SC-4)
- [ ] 3.5 Test 404 error page renders with styling (SC-5)
- [ ] 3.6 Test 500 error page renders without sensitive info (SC-6)
- [ ] 3.7 Test base template renders with theme (SC-7)
- [ ] 3.8 Test `npm run build:css` compiles successfully (SC-8)
- [ ] 3.9 Test application startup time < 2 seconds (SC-9)
- [ ] 3.10 Test log format includes timestamp, level, module (SC-10, SC-11)
- [ ] 3.11 Verify no deprecation warnings on startup (SC-12)

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
- [ ] 4.4 Update .gitignore for logs/ directory
