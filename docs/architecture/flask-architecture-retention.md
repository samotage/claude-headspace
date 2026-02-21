# Architecture Decision: Flask Architecture Retention

**Date:** 2026-02-21
**Status:** Decided — Retain Flask, invest in platform hardening
**Decision:** Do not migrate to Django. Strengthen the existing Flask architecture with targeted upgrades.

---

## 1. Background

As Claude Headspace has grown to 14 domain models, 50 service modules, 25 route blueprints, and 960+ tests, the question arose whether the application has outgrown Flask and should migrate to Django for its "batteries included" approach — ORM, admin panel, auth system, management commands, and opinionated project structure.

A comprehensive codebase investigation was conducted to assess migration feasibility, covering:
- Model layer and ORM usage
- Service layer architecture and framework coupling
- Route/template layer complexity
- Test suite and infrastructure dependencies

This document captures the findings and the decision rationale.

---

## 2. Decision

**Retain Flask.** The application's architecture is well-suited to Flask's flexibility, and the cost of migration far outweighs the benefits Django would provide for this specific application domain.

---

## 3. Codebase Profile (at time of assessment)

| Dimension | Count | Detail |
|-----------|-------|--------|
| Domain models | 14 | Project, Agent, Command, Turn, Event, InferenceCall, Objective, ObjectiveHistory, ActivityMetric, HeadspaceSnapshot, Organisation, Role, Persona, Position |
| Relationships | 32 | Including 3 self-referential (Agent predecessor, Turn answered_by, Position reports_to/escalates_to) |
| Check constraints | 4 | Priority consistency, timestamp ordering, scope XOR, parent FK presence |
| Composite indexes | 14+ | Multi-column indexes for query performance |
| Service modules | 50 | ~19,200 lines of service code |
| Route blueprints | 25 | 105 endpoints (~7,500 lines) |
| Templates | 31 | Jinja2 (~3,800 lines, 20 partial components) |
| JavaScript files | 37 | Vanilla JS (no framework) |
| Alembic migrations | 44 | Schema evolution history |
| Test files | 134 | ~960+ test cases across 4 tiers |
| Config keys | 200+ | YAML-based configuration |

---

## 4. Why Not Django

### 4.1 The ORM misconception

The initial premise — that Flask "doesn't have an ORM" — is incorrect. The application uses **SQLAlchemy via Flask-SQLAlchemy**, which is a full-featured ORM. SQLAlchemy is arguably more powerful than Django's ORM for this application's needs:

- **Explicit relationship control** with `cascade`, `order_by`, `back_populates`
- **Check constraints** defined declaratively in model `__table_args__`
- **PostgreSQL-native types** (JSONB, UUID) with first-class support
- **Event listeners** (e.g., Persona slug auto-generation via `@event.listens_for`)
- **Mapped type annotations** (SQLAlchemy 2.0+ modern syntax)

Django's ORM is simpler but less expressive. Migrating would mean losing or working around several patterns that are currently clean and well-tested.

### 4.2 The architecture is already "opinionated"

Django's primary advantage over Flask is convention — it tells you where things go. But Claude Headspace has already established its own conventions through organic growth:

- **Service layer** — 50 modules with clear separation of concerns
- **4-tier test architecture** — unit, route, integration, E2E
- **Blueprint organisation** — 25 route modules grouped by domain
- **Configuration system** — 200+ keys in structured YAML
- **Background task pattern** — consistent threading with graceful shutdown

These conventions are tailored to the application's domain (real-time monitoring, LLM integration, terminal control). Django's conventions are designed for CRUD web applications with user authentication — a different problem space.

### 4.3 SSE streaming is simpler in Flask

The real-time dashboard relies on Server-Sent Events via Flask's generator-based streaming:

```python
@app.route("/api/events/stream")
def stream_events():
    for message in broadcaster.get_events():
        yield f"data: {json.dumps(message)}\n\n"
```

Django would require either Django Channels (ASGI, significant complexity increase) or `StreamingHttpResponse` (less elegant, limited). Flask's WSGI generator pattern is a natural fit for SSE and works reliably.

### 4.4 Background processing fits Flask's model

9 background services run as daemon threads within the Flask process. This pattern works because:
- Single-server deployment (no horizontal scaling needed)
- Services need direct access to the same in-memory state (session registry, broadcaster queues)
- Thread lifecycle is managed cleanly via `threading.Event` for graceful shutdown

Django's approach would push toward Celery (adding Redis/RabbitMQ infrastructure dependency) or management commands (less integrated with the web process). The current pattern is simpler and sufficient.

### 4.5 Django's "batteries" aren't relevant here

| Django Feature | Relevance to Claude Headspace |
|---------------|-------------------------------|
| Admin panel | Useful but achievable via Flask-Admin (~1 week) |
| Auth system | No users/login currently; when needed, Flask-Login is sufficient |
| Forms framework | Forms are vanilla JavaScript; Django forms add no value |
| Management commands | Background threads serve this role; Celery is a better upgrade path |
| Class-based views | Debatable improvement; function-based routes are clear and simple |
| Django REST Framework | Pydantic/marshmallow validation achieves the same with less overhead |

### 4.6 The migration cost is prohibitive

**Estimated effort: 4-6 months** touching 40-60% of the codebase.

| Migration task | Effort | Risk |
|---------------|--------|------|
| 14 models → Django ORM | 2-3 weeks | Check constraints, JSONB, self-referential FKs need careful mapping |
| 44 Alembic migrations → Django migrations | 3-4 weeks | Custom backfills, constraint evolution, enum handling |
| 25 blueprints → Django views/URLconfs | 3-4 weeks | Mechanical but large surface area |
| 31 Jinja2 templates → Django templates | 1 week | Mostly syntax; `tojson` filter and `url_for` need adapting |
| 9 background thread services → Celery/commands | 2-3 weeks | Django lacks Flask's app context pattern for threads |
| Service discovery refactor | 1-2 weeks | Replace `current_app.extensions` with Django app registry |
| SSE streaming adaptation | 1-2 weeks | Channels or StreamingHttpResponse |
| 134 test files rewrite | 3-4 weeks | 31 route tests use Flask test client; conftest is Flask-specific |
| CSRF, middleware, error handlers | 1 week | Django has built-in equivalents but different API |

During this period, no new features ship. The application's test coverage — currently a significant asset — would need to be rebuilt from scratch for the route and integration tiers.

---

## 5. Framework Coupling Analysis

### 5.1 Service layer: 68% framework-agnostic

34 of 50 services have zero Flask imports. The core business logic is portable:

**Fully portable (no Flask dependency):**
- State machine, intent detector (600 lines, 70+ regex patterns)
- Inference service, OpenRouter client, inference cache, rate limiter
- Broadcaster (thread-safe SSE distribution)
- Tmux bridge (1,695 lines of subprocess control)
- Git analyzer, git metadata
- Notification service, permission summarizer
- Event schemas, prompt registry, session registry
- Archive service, waypoint editor, brain reboot
- JSONL parser, transcript reader, path constants
- Progress summary, staleness detection

**Flask-coupled (16 services, 32%):**
- 9 background thread services (need `app.app_context()` for DB access)
- 8 services using `current_app.extensions["service_name"]` for service discovery
- 1 service using Flask request/response helpers (`voice_auth.py`)

### 5.2 Model layer: Coupled via `db.Model` base class

All 14 models inherit from `db.Model` (Flask-SQLAlchemy). The model logic itself — fields, relationships, constraints — is pure SQLAlchemy and could be ported to any SQLAlchemy-based setup. The coupling is at the base class level, not in the business logic.

### 5.3 Route layer: Fully Flask-specific

All 25 blueprints use Flask-specific APIs:
- `@bp.route()` decorators (105 endpoints)
- `request` object (~350+ uses)
- `jsonify()` (~150+ uses)
- `render_template()` (24 uses)
- `url_for()` (30+ template uses)
- `current_app` (60+ uses)

This layer would require complete rewriting in any migration scenario.

### 5.4 Test layer: Heavily Flask-coupled

- 52 service tests — mostly portable (mock-based)
- 31 route tests — fully Flask-specific (`app.test_client()`)
- 13 integration tests — factory-boy based (portable, but DB setup is Flask-specific)
- 7 E2E tests — Playwright-based (framework-agnostic)

---

## 6. SQLAlchemy ORM Capabilities in Use

These SQLAlchemy features work well and would be harder or impossible to replicate in Django's ORM:

### Check constraints (4 models)

```python
# Agent: priority fields must be all-null or all-not-null
CheckConstraint(
    "(priority_score IS NULL AND priority_reason IS NULL AND priority_updated_at IS NULL) OR "
    "(priority_score IS NOT NULL AND priority_reason IS NOT NULL AND priority_updated_at IS NOT NULL)",
    name='ck_agents_priority_consistency',
)

# ActivityMetric: exactly one scope (overall XOR agent XOR project)
CheckConstraint(
    "(is_overall = true AND agent_id IS NULL AND project_id IS NULL) OR "
    "(is_overall = false AND agent_id IS NOT NULL AND project_id IS NULL) OR "
    "(is_overall = false AND project_id IS NOT NULL AND agent_id IS NULL)",
    name='ck_activity_metrics_scope_consistency',
)
```

Django supports `CheckConstraint` (3.2+) but requires custom migrations rather than declarative `__table_args__`.

### Relationship ordering and cascades

```python
commands: Mapped[list["Command"]] = relationship(
    "Command",
    back_populates="agent",
    cascade="all, delete-orphan",
    order_by="Command.started_at.desc()",
)
```

Django has no equivalent to `order_by` in relationship declarations or `delete-orphan` cascade behaviour.

### Event listeners

```python
@event.listens_for(Persona, "after_insert")
def _set_persona_slug(mapper, connection, target):
    slug = f"{target.role.name.lower()}-{target.name.lower()}-{target.id}"
    connection.execute(
        Persona.__table__.update()
        .where(Persona.__table__.c.id == target.id)
        .values(slug=slug)
    )
```

Django's `post_save` signal is similar but runs outside the same database transaction by default, introducing subtle reliability differences.

### PostgreSQL-native types

- `JSONB` columns (4 total) with native binary encoding
- `UUID` column with Python UUID conversion (`as_uuid=True`)
- Both work in Django (JSONField, UUIDField) but with less control over indexing strategies

---

## 7. Recommended Path Forward

Instead of migrating frameworks, invest in targeted upgrades that address the actual pain points. See [Platform Hardening & Upgrades](../ideas/platform-hardening-upgrades.md) for detailed proposals:

| Upgrade | What it addresses | Effort |
|---------|-------------------|--------|
| **Flask-Admin** | Data inspection / admin UI | 1 week |
| **Dependency injection** | Service discovery cleanup | 1-2 weeks |
| **Celery** | Background task reliability | 2-3 weeks |
| **Pydantic/marshmallow** | API schema validation | 2-3 weeks |
| **Authentication** | Security baseline | 1-3 weeks (phased) |
| **Blueprint packages** | Large file maintainability | 1-2 weeks |

**Total: 8-14 weeks** for all upgrades — less than half the cost of a Django migration, with zero regression risk to existing features and tests.

---

## 8. When to Revisit This Decision

Reconsider framework choice if:

- **Multi-user authentication becomes a core requirement** — Django's auth ecosystem is genuinely superior for complex user/permission models
- **The application needs horizontal scaling** — Flask's single-process threading model has limits; at that point, consider FastAPI (async-native) rather than Django
- **The ORM needs significantly change** — If SQLAlchemy patterns consistently fight the application's needs (unlikely given current clean usage)
- **A major rewrite is planned anyway** — If large portions of the codebase are being rewritten for other reasons, the incremental cost of a framework change drops

---

## 9. Conclusion

Claude Headspace is not a typical CRUD web application. It is a real-time monitoring dashboard with background processing, LLM integration, terminal control, and SSE streaming. Flask's flexibility and the team's established conventions serve this domain better than Django's CRUD-oriented batteries. The existing SQLAlchemy ORM is more powerful than Django's ORM for the application's needs. The migration cost (4-6 months, 40-60% codebase rewrite) is not justified by the marginal benefits Django would provide.

The right investment is platform hardening — Flask-Admin, Celery, dependency injection, and API validation — which delivers the same outcomes at a fraction of the cost and risk.
