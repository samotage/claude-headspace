# Idea: Platform Hardening & Upgrades

**Status:** Idea — Not yet assigned to an epic
**Date:** 2026-02-21
**Priority:** Future consideration — incremental adoption as needs arise

---

## 1. Context

As Claude Headspace grows (14 models, 50 services, 25 blueprints, 960+ tests), the application benefits from targeted platform investments that harden the existing Flask architecture rather than migrating to a different framework. These upgrades address specific pain points without the risk and cost of a full rewrite.

See also: [Architecture Decision: Flask Retention](../architecture/flask-architecture-retention.md)

---

## 2. Proposed Upgrades

### 2.1 Background Task System (Celery)

**Problem:** 9 background services use raw `threading.Thread` with Flask app context wrappers. This works but lacks retry logic, scheduling, task monitoring, and graceful scaling.

**Proposal:** Introduce Celery with a Redis broker for background task management.

**Services that would migrate to Celery tasks:**
- `agent_reaper` — inactive agent cleanup
- `activity_aggregator` — hourly metrics computation
- `priority_scoring` — agent priority batch scoring
- `headspace_monitor` — frustration/flow tracking
- `commander_availability` — tmux pane status checks
- `tmux_watchdog` — turn gap detection
- `context_poller` — context usage monitoring
- `file_watcher` — transcript file monitoring
- `hook_deferred_stop` — deferred stop processing

**Benefits:**
- Built-in retry with exponential backoff
- Task scheduling (replace manual interval loops)
- Monitoring via Flower dashboard
- Worker-level concurrency control
- Graceful shutdown without `atexit` hacks

**Estimated effort:** 2-3 weeks

---

### 2.2 Dependency Injection Container

**Problem:** Services discover each other via `current_app.extensions["service_name"]` — a loose, untyped dictionary lookup. This makes dependency graphs implicit and harder to test.

**Proposal:** Adopt the `dependency-injector` library (or a lightweight custom registry) to formalise service wiring.

**What changes:**
- Services declare dependencies explicitly in their constructors
- A container wires everything at startup
- Tests can override individual services cleanly
- Circular dependency detection at startup rather than runtime

**Benefits:**
- Explicit dependency graph (visible, testable)
- Better IDE support (typed references instead of string lookups)
- Easier service mocking in tests
- No more `current_app.extensions` scattered across 8+ services

**Estimated effort:** 1-2 weeks

---

### 2.3 Admin & Data Inspection Interface (Flask-Admin)

**Problem:** Inspecting model data requires direct database queries or custom API calls. No admin UI exists for browsing agents, commands, turns, events, or inference calls.

**Proposal:** Add Flask-Admin with model views for all 14 domain models.

**What it provides:**
- CRUD interface for all models (list, detail, create, edit, delete)
- Filterable/searchable model lists
- Inline relationship display
- Export to CSV
- Custom admin actions (e.g., "reprocess summary", "reap agent")

**Configuration:** ~5 lines per model, plus optional custom views for complex models (Agent, Command).

**Estimated effort:** 1 week

---

### 2.4 API Schema Validation

**Problem:** Request validation is manual — each route handler checks `request.get_json()` fields individually. No consistent error response format. No API documentation.

**Proposal:** Adopt Pydantic or marshmallow for request/response schema validation.

**Options:**
- **Pydantic** — already used in `event_schemas.py`, natural extension. Pair with `flask-pydantic` for automatic request validation.
- **marshmallow** — more established in Flask ecosystem. Pair with `flask-marshmallow` + `marshmallow-sqlalchemy` for model serialisation.

**Benefits:**
- Consistent validation with structured error responses
- Auto-generated API documentation (via apispec or flask-smorest)
- Type-safe request parsing
- Model serialisation without manual `to_dict()` methods

**Estimated effort:** 2-3 weeks (incremental, can be adopted per-blueprint)

---

### 2.5 Authentication & Authorisation

**Problem:** Claude Headspace currently has no authentication. The dashboard, APIs, and hook endpoints are all open. This is acceptable for single-user local deployment but becomes a concern as the application matures — especially with the voice bridge, tmux response bridge, and any future multi-user or remote access scenarios.

**Proposal:** Implement authentication with a phased approach.

**Phase 1 — API Key Authentication (minimal):**
- Shared API key for hook endpoints (Claude Code → Headspace)
- Optional API key for dashboard access
- Key stored in `config.yaml` or `.env`
- Middleware checks `Authorization` header or `X-API-Key`

**Phase 2 — Session-Based Authentication:**
- Login page with username/password
- Flask-Login for session management
- User model (simple — likely single-user or small team)
- Protected routes with `@login_required`
- SSE endpoint authentication via token parameter

**Phase 3 — Token-Based Authentication (optional):**
- JWT tokens for API access (useful if external tools integrate)
- OAuth2 if third-party integrations emerge
- Per-user API keys with scoping

**Considerations:**
- Voice bridge already has optional API key auth (`voice_auth.py`) — extend this pattern
- Hook endpoints need authentication that doesn't break Claude Code's hook scripts
- SSE connections are long-lived — session/token expiry needs careful handling
- Tailscale network already provides network-level access control

**Estimated effort:** Phase 1: 1 week. Phase 2: 2-3 weeks. Phase 3: 2-3 weeks.

---

### 2.6 Blueprint Package Refactoring

**Problem:** Some blueprints are very large — `voice_bridge.py` is 48KB, `projects.py` is 28KB, `hooks.py` is 25KB. These are hard to navigate and maintain.

**Proposal:** Convert large blueprints into packages with sub-modules.

**Example structure:**
```
routes/
  hooks/
    __init__.py          # Blueprint registration
    session.py           # session-start, session-end
    tool_use.py          # pre-tool-use, post-tool-use
    prompt.py            # user-prompt-submit
    lifecycle.py         # stop, notification, permission-request
  voice_bridge/
    __init__.py          # Blueprint registration
    auth.py              # Authentication
    streaming.py         # Audio streaming endpoints
    commands.py          # Voice command processing
```

**Benefits:**
- Smaller, focused files
- Easier code review and navigation
- Blueprint registration remains identical (Flask supports package blueprints natively)

**Estimated effort:** 1-2 weeks

---

## 3. Priority Recommendation

These upgrades are independent and can be adopted incrementally:

| Upgrade | Impact | Effort | Suggested Priority |
|---------|--------|--------|--------------------|
| Flask-Admin | High (immediate utility) | 1 week | Do first |
| Dependency injection | Medium (code quality) | 1-2 weeks | Do when refactoring services |
| Celery background tasks | High (reliability) | 2-3 weeks | Do when background services cause issues |
| API schema validation | Medium (developer experience) | 2-3 weeks | Do incrementally per-blueprint |
| Authentication (Phase 1) | Medium (security baseline) | 1 week | Do before any remote/multi-user access |
| Blueprint refactoring | Low (maintainability) | 1-2 weeks | Do when touching large blueprints |

**Total estimated effort:** 8-14 weeks if done all at once, but designed for incremental adoption.

---

## 4. What This Replaces

These upgrades collectively address the concerns that might otherwise motivate a framework migration (e.g., to Django):

- **Django Admin** → Flask-Admin (equivalent functionality)
- **Django management commands** → Celery tasks (better for background work)
- **Django's opinionated structure** → DI container + blueprint packages
- **Django REST Framework** → Pydantic/marshmallow validation
- **Django Auth** → Flask-Login + API key auth
