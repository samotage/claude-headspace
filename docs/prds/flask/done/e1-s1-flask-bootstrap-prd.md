---
validation:
  status: valid
  validated_at: '2026-01-29T08:26:55+11:00'
---

# Product Requirements Document (PRD) — Flask Bootstrap

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 1 — Flask application foundation
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the foundational Flask application for Claude Headspace v3.1. The Flask Bootstrap sprint establishes a runnable application with proper configuration management, health monitoring, error handling, and the dark terminal aesthetic that defines the product's visual identity.

The deliverable is a production-ready Flask application skeleton that all subsequent sprints will build upon. It must be testable (via application factory pattern), configurable (YAML + environment overrides), and visually polished (Tailwind CSS with the established terminal theme).

**Key Outcomes:**
- Runnable Flask application via `flask run`
- Configuration loaded from `config.yaml` with environment variable overrides
- Health check endpoint for monitoring
- Styled error pages (404, 500)
- Base HTML template with dark terminal aesthetic
- Tailwind CSS build pipeline for styling

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace v3.1 is a complete rewrite with an event-driven architecture. Sprint 1 establishes the Flask foundation that all other sprints depend on — database setup, domain models, API endpoints, and the dashboard UI all require a properly structured Flask application.

The existing Claude Monitor (v2) uses a working dark terminal theme that should be preserved and systematized in v3.1 using Tailwind CSS for maintainability.

### 1.2 Target User

Developers building Claude Headspace and end users who will interact with the dashboard. The application must start reliably and present a polished, professional interface from day one.

### 1.3 Success Moment

A developer clones the repository, runs `flask run`, and sees a styled health page with the dark terminal aesthetic — confirming the application is properly configured and ready for feature development.

---

## 2. Scope

### 2.1 In Scope

- Flask application that starts via standard `flask run` command
- Configuration loading from `config.yaml` at project root
- Environment variable overrides for all config values
- Health check endpoint (`GET /health`) returning JSON status
- Error handler for 404 (Not Found) with styled page
- Error handler for 500 (Internal Server Error) with styled page
- Structured logging to console and file
- Python project structure with `pyproject.toml` and `src/` layout
- Tailwind CSS build pipeline (PostCSS-based, not CDN)
- Base HTML template with dark terminal theme
- Development vs production mode configuration

### 2.2 Out of Scope

- Database connection or ORM setup (Sprint 2)
- Domain models (Sprint 3)
- API endpoints beyond health check (later sprints)
- Authentication or authorization
- SSE or real-time features (Sprint 7)
- Dashboard UI beyond base template (Sprint 8)
- Docker or containerization
- CI/CD pipeline configuration

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC-1:** `flask run` starts the server successfully on the configured port
2. **SC-2:** `GET /health` returns HTTP 200 with JSON body `{"status": "healthy", "version": "<app_version>"}`
3. **SC-3:** Configuration values load correctly from `config.yaml`
4. **SC-4:** Environment variables override corresponding config values (e.g., `FLASK_DEBUG=true` overrides `server.debug`)
5. **SC-5:** Requesting a non-existent route returns a styled 404 error page
6. **SC-6:** Triggering a server error returns a styled 500 error page (no sensitive information exposed)
7. **SC-7:** Base HTML page renders with dark terminal theme colors and monospace font
8. **SC-8:** Tailwind CSS builds successfully via npm/npx command

### 3.2 Non-Functional Success Criteria

1. **SC-9:** Application starts in under 2 seconds in development mode
2. **SC-10:** Logs include timestamps, log level, and source module
3. **SC-11:** Log output appears in both console and `logs/app.log` file
4. **SC-12:** No Python deprecation warnings on startup

---

## 4. Functional Requirements (FRs)

### FR1: Application Startup

The application starts via the standard Flask CLI command (`flask run`). The server binds to the host and port specified in configuration.

### FR2: Configuration Loading

The application loads configuration from `config.yaml` at the project root. The configuration file uses the following schema:

```yaml
server:
  host: "127.0.0.1"
  port: 5050
  debug: false
```

### FR3: Environment Variable Overrides

Environment variables override configuration file values. The mapping follows the pattern `FLASK_<SECTION>_<KEY>` in uppercase:

| Config Key | Environment Variable |
|------------|---------------------|
| `server.host` | `FLASK_SERVER_HOST` |
| `server.port` | `FLASK_SERVER_PORT` |
| `server.debug` | `FLASK_DEBUG` |

### FR4: Health Check Endpoint

The application exposes a health check endpoint:

- **Route:** `GET /health`
- **Response:** HTTP 200 with JSON body
- **Body:** `{"status": "healthy", "version": "<version>"}`

The version comes from the application configuration or package metadata.

### FR5: Error Handling — 404

When a request is made to a non-existent route, the application returns:

- **Status:** HTTP 404
- **Content:** Styled HTML error page with dark theme
- **Message:** User-friendly "Page not found" message

### FR6: Error Handling — 500

When an unhandled exception occurs, the application returns:

- **Status:** HTTP 500
- **Content:** Styled HTML error page with dark theme
- **Message:** User-friendly "Something went wrong" message
- **Security:** No stack traces, file paths, or sensitive information in production mode

### FR7: Logging

The application logs to both console (stdout) and a file (`logs/app.log`). Log entries include:

- Timestamp (ISO 8601 format)
- Log level (DEBUG, INFO, WARNING, ERROR)
- Logger name (module)
- Message

Log level is configurable via environment variable `FLASK_LOG_LEVEL` (default: INFO).

### FR8: Base HTML Template

The application serves a base HTML template that establishes:

- Document structure (DOCTYPE, html, head, body)
- Meta tags (charset, viewport)
- Tailwind CSS stylesheet link
- Dark terminal theme applied to body
- Block regions for child templates (title, content)

### FR9: Tailwind CSS Build

The application includes a Tailwind CSS build pipeline that:

- Processes source CSS with Tailwind directives
- Outputs compiled CSS to `static/css/` directory
- Can be run via npm script (`npm run build:css`)
- Supports watch mode for development (`npm run watch:css`)

### FR10: Development vs Production Mode

The application behaves differently based on mode:

| Behavior | Development | Production |
|----------|-------------|------------|
| Debug mode | Enabled | Disabled |
| Auto-reload | Enabled | Disabled |
| Error details | Shown | Hidden |
| Log level | DEBUG | INFO |

Mode is determined by `server.debug` config value or `FLASK_DEBUG` environment variable.

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Project Structure

The project follows Python packaging best practices:

```
claude_headspace/
├── pyproject.toml          # Package metadata and dependencies
├── config.yaml             # Application configuration
├── package.json            # Node dependencies (Tailwind)
├── tailwind.config.js      # Tailwind configuration
├── src/
│   └── claude_headspace/   # Python package
│       ├── __init__.py
│       ├── app.py          # Application factory
│       ├── config.py       # Config loader
│       └── routes/
│           └── health.py   # Health check route
├── templates/
│   ├── base.html           # Base template
│   └── errors/
│       ├── 404.html
│       └── 500.html
├── static/
│   └── css/
│       └── main.css        # Compiled Tailwind CSS
├── logs/                   # Log files (gitignored)
└── tests/
    └── test_app.py
```

### NFR2: Dependency Management

Python dependencies are specified in `pyproject.toml` with pinned versions. Key dependencies:

- Flask >= 3.0
- PyYAML >= 6.0
- python-dotenv >= 1.0

### NFR3: Testability

The application factory pattern enables testing without side effects. Tests can create isolated application instances with custom configurations.

---

## 6. Technical Context (Implementation Guidance)

This section provides implementation guidance for developers. These are recommendations, not requirements.

### 6.1 Application Factory Pattern

Use Flask's application factory pattern for testability:

```python
def create_app(config_path: str = "config.yaml") -> Flask:
    app = Flask(__name__)
    # Load config, register blueprints, setup logging
    return app
```

### 6.2 Configuration Loading Strategy

1. Load defaults from code
2. Override with values from `config.yaml`
3. Override with environment variables
4. Use `python-dotenv` to load `.env` file in development

### 6.3 Theme Color Palette

Preserve the established Claude Monitor theme using CSS custom properties:

```css
:root {
    /* Backgrounds */
    --bg-void: #08080a;
    --bg-deep: #0c0c0e;
    --bg-surface: #111114;
    --bg-elevated: #18181c;
    --bg-hover: #1e1e24;

    /* Accent colors */
    --cyan: #56d4dd;
    --green: #73e0a0;
    --amber: #e0b073;
    --red: #e07373;
    --blue: #7399e0;
    --magenta: #d073e0;

    /* Text */
    --text-primary: #e8e8ed;
    --text-secondary: #a0a0ab;
    --text-muted: #6a6a78;

    /* Borders */
    --border: #252530;
    --border-bright: #363644;

    /* Font */
    --font-mono: 'SF Mono', 'Monaco', 'Menlo', 'JetBrains Mono', 'Consolas', monospace;
}
```

### 6.4 Tailwind Configuration

Configure Tailwind to use the theme colors and extend with custom utilities. Use the `content` array to scan templates for class usage (PurgeCSS).

### 6.5 Logging Configuration

Use Python's `logging.config.dictConfig()` for structured logging setup. Consider using JSON formatter for production logs.

---

## 7. Acceptance Tests

| Test ID | Description | Expected Result |
|---------|-------------|-----------------|
| AT-1 | Run `flask run` from project root | Server starts, logs show "Running on http://127.0.0.1:5050" |
| AT-2 | GET `/health` | Returns 200 with `{"status": "healthy", "version": "..."}` |
| AT-3 | GET `/nonexistent` | Returns 404 with styled error page |
| AT-4 | Set `FLASK_SERVER_PORT=8080` and start | Server runs on port 8080 |
| AT-5 | Check `logs/app.log` after requests | Log entries present with timestamps |
| AT-6 | View base page in browser | Dark background, monospace font, theme colors applied |
| AT-7 | Run `npm run build:css` | CSS compiles without errors |
| AT-8 | Set `FLASK_DEBUG=true` | Debug mode enabled, auto-reload active |

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tailwind build pipeline adds complexity | Medium | Document build steps clearly; provide npm scripts |
| Config schema changes break setups | Low | Version config schema; provide migration guide |
| Log file permissions on shared systems | Low | Make log path configurable; document permissions |

---

## 9. Dependencies

- **External:** None (Sprint 1 has no dependencies)
- **Blocks:** Sprint 2 (Database Setup), Sprint 3 (Domain Models), all subsequent sprints

---

## 10. Open Questions

None — all questions resolved during workshop.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
