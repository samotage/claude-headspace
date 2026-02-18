---
validation:
  status: valid
  validated_at: '2026-02-02T13:15:11+11:00'
---

## Product Requirements Document (PRD) — Project Controls Backend

**Project:** Claude Headspace
**Scope:** Project CRUD API, manual-only registration, inference pause/resume controls, database migration
**Sprint:** E4-S2a
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft
**Depends on:** None
**Depended on by:** E4-S2b (Project Controls UI)

---

## Executive Summary

Claude Headspace currently auto-discovers projects from the filesystem — any Claude Code session in any directory creates a project record automatically. This leads to noise: throwaway experiments, temp directories, and one-off sessions pollute the dashboard with orphaned projects that serve no purpose.

This PRD defines the backend services for a project lifecycle management system. It replaces auto-discovery with explicit manual registration via REST API endpoints for creating, reading, updating, and deleting projects. Sessions for unregistered projects are rejected with a clear error message directing the user to register the project first.

Additionally, this sprint adds per-project inference controls — the ability to pause and resume LLM inference calls (turn summarisation, command summarisation, instruction summarisation, priority scoring) without affecting session tracking, hooks, or dashboard updates. This gives users cost and noise control over the intelligence layer on a project-by-project basis.

The companion PRD (E4-S2b) covers the UI layer that consumes these API endpoints.

---

## 1. Context & Purpose

### 1.1 Context

The existing project creation logic lives in two places:

1. **`session_correlator.py`** (`_create_agent_for_session`) — when a hook event arrives for an unknown session and working directory, a new Project and Agent are auto-created from the directory name.
2. **`routes/sessions.py`** (`create_session`) — the CLI launcher endpoint auto-creates projects from `project_path` if not already registered.

This auto-discovery was appropriate during early development (Epic 1) when getting sessions visible quickly was the priority. Now that the system is mature with inference costs, priority scoring, and summarisation, uncontrolled project creation is a liability:

- Dashboard fills with one-off experiment projects
- Inference calls are wasted on projects the user doesn't care about
- No way to remove or manage stale projects
- No way to pause inference for a project temporarily (e.g., during a cost-sensitive period)

The Project model currently has minimal fields: `id`, `name`, `path`, `github_repo`, `current_branch`, `created_at`. It needs metadata fields (`description`) and inference control fields (`inference_paused`, `inference_paused_at`, `inference_paused_reason`).

### 1.2 Target User

Developers running multiple concurrent Claude Code sessions across several projects who want explicit control over which projects appear on the dashboard and which incur inference costs.

### 1.3 Success Moment

The user registers three projects via the API. They pause inference on a project they're not actively prioritising. When they start a Claude Code session in an unregistered throwaway directory, the hook is cleanly rejected and the dashboard stays focused on what matters.

---

## 2. Scope

### 2.1 In Scope

- **Project CRUD API:** REST endpoints for listing, creating, reading, updating, and deleting projects
- **Project settings API:** Dedicated endpoints for getting/setting project-level settings (inference pause)
- **Manual registration only:** Disable auto-discovery in `session_correlator.py` and `sessions.py`; reject unregistered project sessions with clear error
- **Inference pause/resume:** Per-project toggle to pause all inference calls (turn summarisation, command summarisation, instruction summarisation, priority scoring)
- **Inference gating:** Check pause state before every inference call in summarisation service and priority scoring service
- **Database migration:** Add `description`, `inference_paused`, `inference_paused_at`, `inference_paused_reason` columns to the `projects` table
- **SSE broadcast:** Broadcast project changes and settings changes so the dashboard updates in real-time
- **Tests:** Unit tests for the projects API, route tests, and service-level gating tests

### 2.2 Out of Scope

- Projects management UI (covered by E4-S2b)
- Header navigation changes (covered by E4-S2b)
- Project archiving / soft delete (projects are hard-deleted with cascade)
- Bulk project operations (import/export)
- Project-level configuration beyond inference pause (e.g., model selection per project)
- Project grouping or tagging
- Auto-migration of existing auto-discovered projects (they remain; user can delete unwanted ones via the API or future UI)
- File watcher configuration per project
- Changes to the inference service itself (gating is in the callers)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. `GET /api/projects` returns a list of all registered projects with name, path, agent count, and inference status
2. `POST /api/projects` with valid data creates a project and returns 201
3. `POST /api/projects` with a duplicate path returns 409 Conflict
4. `GET /api/projects/<id>` returns full project details including agent list
5. `PUT /api/projects/<id>` updates project metadata and returns 200
6. `DELETE /api/projects/<id>` deletes the project and all its agents (cascade) and returns 200
7. Start a Claude Code session in an unregistered directory — session rejected, hook returns error with clear message directing user to register the project
8. `PUT /api/projects/<id>/settings` with `inference_paused: true` stops inference calls for that project
9. Paused project — file watching, hooks, session tracking, dashboard display, SSE all continue normally
10. `PUT /api/projects/<id>/settings` with `inference_paused: false` resumes inference calls
11. Pause state persists across server restarts (stored in database)
12. Project changes and settings changes broadcast SSE events

### 3.2 Non-Functional Success Criteria

1. Project list API responds within 200ms for up to 50 projects
2. Project creation/update/delete operations complete within 500ms
3. Inference gating check adds negligible overhead (< 1ms) to each inference call path
4. Cascade delete completes within 2 seconds for a project with up to 100 agents

---

## 4. Functional Requirements (FRs)

### Project CRUD API

**FR1:** The system shall provide a `GET /api/projects` endpoint that returns all projects with their `id`, `name`, `path`, `github_repo`, `description`, `current_branch`, `inference_paused`, `created_at`, and an `agent_count` (number of active agents).

**FR2:** The system shall provide a `POST /api/projects` endpoint that creates a new project. Required fields: `name`, `path`. Optional fields: `github_repo`, `description`. Returns 201 on success.

**FR3:** The `POST /api/projects` endpoint shall reject duplicate `path` values with a 409 Conflict response and a descriptive error message.

**FR4:** The system shall provide a `GET /api/projects/<id>` endpoint that returns full project details including agent list and inference settings.

**FR5:** The system shall provide a `PUT /api/projects/<id>` endpoint that updates project metadata (`name`, `path`, `github_repo`, `description`). Returns 200 on success, 404 if not found, 409 if updated `path` conflicts with another project.

**FR6:** The system shall provide a `DELETE /api/projects/<id>` endpoint that deletes the project and all associated agents (cascade). Returns 200 on success, 404 if not found.

### Project Settings API

**FR7:** The system shall provide a `GET /api/projects/<id>/settings` endpoint that returns the project's settings (`inference_paused`, `inference_paused_at`, `inference_paused_reason`).

**FR8:** The system shall provide a `PUT /api/projects/<id>/settings` endpoint that updates project settings. Accepted fields: `inference_paused` (bool), `inference_paused_reason` (string, optional). When `inference_paused` is set to `true`, `inference_paused_at` is automatically set to the current timestamp. When set to `false`, `inference_paused_at` and `inference_paused_reason` are cleared.

**FR9:** When inference is paused or resumed via the settings API, the system shall broadcast an SSE event (`project_settings_changed`) so the dashboard updates in real-time.

### Disable Auto-Discovery

**FR10:** The `_create_agent_for_session` function in `session_correlator.py` shall no longer auto-create Project records. When a session's working directory does not match any registered project, the function shall raise a `ValueError` with a message directing the user to register the project.

**FR11:** The `create_session` endpoint in `routes/sessions.py` shall no longer auto-create Project records. When `project_path` does not match any registered project, the endpoint shall return a 404 response with a message directing the user to register the project.

**FR12:** The error messages for unregistered projects shall be clear and actionable, including the rejected path and a reference to the `/projects` management page. Example: `"Project not registered: /path/to/dir. Add the project via the Projects management UI at /projects first."`

### Inference Gating

**FR13:** The `SummarisationService` shall check the project's `inference_paused` state before making any inference call (`summarise_turn`, `summarise_task`, `summarise_instruction`). If paused, the method shall return `None` without calling the inference service, with a debug log message.

**FR14:** The `PriorityScoringService.score_all_agents()` shall exclude agents belonging to paused projects from the scoring batch. If all active agents belong to paused projects, scoring shall be skipped entirely.

**FR15:** The inference gating check shall query the project's `inference_paused` field via the agent's relationship chain (turn → command → agent → project, or command → agent → project). The check shall use the already-loaded ORM relationships to avoid additional database queries.

**FR16:** The following operations shall continue normally regardless of inference pause state: hook event processing, session correlation, file watching, SSE broadcasting, dashboard rendering, agent state transitions.

### SSE Broadcasting

**FR17:** When a project is created, updated, or deleted via the CRUD API, the system shall broadcast a `project_changed` SSE event with the action (`created`, `updated`, `deleted`) and the project ID.

### Database Migration

**FR18:** An Alembic migration shall add the following columns to the `projects` table:
- `description` — `Text`, nullable
- `inference_paused` — `Boolean`, not null, default `false`
- `inference_paused_at` — `DateTime(timezone=True)`, nullable
- `inference_paused_reason` — `Text`, nullable

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** All project API endpoints shall validate input and return appropriate HTTP status codes (400 for validation errors, 404 for not found, 409 for conflicts, 500 for server errors).

**NFR2:** The cascade delete shall use SQLAlchemy's `cascade="all, delete-orphan"` on the Project → Agent relationship (already configured) to ensure agents are removed when a project is deleted.

**NFR3:** All new routes and services shall have unit tests and route tests following the existing three-tier test architecture.

**NFR4:** The inference gating logic shall not introduce circular imports. The check shall be performed in the summarisation and priority scoring services, not in the inference service itself.

---

## 6. API Endpoints

### Project CRUD

| Endpoint | Method | Description | Request Body | Response |
|---|---|---|---|---|
| `/api/projects` | GET | List all projects | — | `200: [{id, name, path, github_repo, description, current_branch, inference_paused, created_at, agent_count}]` |
| `/api/projects` | POST | Create project | `{name, path, github_repo?, description?}` | `201: {id, name, path, ...}` / `409: duplicate path` |
| `/api/projects/<id>` | GET | Get project detail | — | `200: {id, name, path, ..., agents: [...]}` / `404` |
| `/api/projects/<id>` | PUT | Update project | `{name?, path?, github_repo?, description?}` | `200: {id, name, ...}` / `404` / `409` |
| `/api/projects/<id>` | DELETE | Delete project + agents | — | `200: {status: "deleted"}` / `404` |

### Project Settings

| Endpoint | Method | Description | Request Body | Response |
|---|---|---|---|---|
| `/api/projects/<id>/settings` | GET | Get settings | — | `200: {inference_paused, inference_paused_at, inference_paused_reason}` |
| `/api/projects/<id>/settings` | PUT | Update settings | `{inference_paused, inference_paused_reason?}` | `200: {inference_paused, ...}` / `404` |

---

## 7. Technical Context (for implementers)

### Inference Gating Implementation

The gating check should be added at the **caller level** (summarisation service, priority scoring service), not in the inference service itself. This keeps the inference service generic and avoids it needing knowledge of project models.

**Summarisation Service gating pattern:**

```python
# In SummarisationService.summarise_turn()
def summarise_turn(self, turn, db_session=None) -> str | None:
    # ... existing early-return checks ...

    # NEW: Check inference pause state
    project = self._get_project_for_turn(turn)
    if project and project.inference_paused:
        logger.debug(
            f"Skipping turn summarisation for turn {turn.id}: "
            f"inference paused for project {project.name}"
        )
        return None

    # ... existing inference call ...
```

The `_get_project_for_turn` helper traverses `turn.command.agent.project` using already-loaded ORM relationships. The same pattern applies to `summarise_task()` and `summarise_instruction()` (via `task.agent.project`).

**Priority Scoring gating pattern:**

```python
# In PriorityScoringService.score_all_agents()
def score_all_agents(self, db_session) -> dict:
    agents = (
        db_session.query(Agent)
        .filter(Agent.ended_at.is_(None))
        .join(Agent.project)
        .filter(Project.inference_paused == False)  # NEW: exclude paused projects
        .all()
    )
    # ... rest of scoring logic unchanged ...
```

### Auto-Discovery Removal

**session_correlator.py** — In `_create_agent_for_session()`, the Project auto-creation block:

```python
# CURRENT (auto-creates)
project = db.session.query(Project).filter(Project.path == working_directory).first()
if not project:
    project_name = working_directory.rstrip("/").split("/")[-1]
    project = Project(name=project_name, path=working_directory)
    db.session.add(project)
    db.session.flush()

# NEW (rejects unregistered)
project = db.session.query(Project).filter(Project.path == working_directory).first()
if not project:
    raise ValueError(
        f"Project not registered: {working_directory}. "
        "Add the project via the Projects management UI at /projects first."
    )
```

**routes/sessions.py** — In `create_session()`, the Project auto-creation block:

```python
# CURRENT (auto-creates)
project = Project.query.filter_by(path=project_path).first()
if project is None:
    project = Project(name=project_name, path=project_path, current_branch=current_branch)
    db.session.add(project)
    db.session.flush()

# NEW (rejects unregistered)
project = Project.query.filter_by(path=project_path).first()
if project is None:
    return jsonify({
        "error": f"Project not registered: {project_path}. "
                 "Add the project via the Projects management UI at /projects first.",
    }), 404
```

### Blueprint Registration

The new `projects_bp` must be registered in `app.py`'s `register_blueprints()` function alongside existing blueprints.

### SSE Events

When project settings change, broadcast:

```python
broadcaster.broadcast("project_settings_changed", {
    "project_id": project.id,
    "inference_paused": project.inference_paused,
    "inference_paused_at": project.inference_paused_at.isoformat() if project.inference_paused_at else None,
    "timestamp": datetime.now(timezone.utc).isoformat(),
})
```

When a project is created, updated, or deleted, broadcast:

```python
broadcaster.broadcast("project_changed", {
    "action": "created" | "updated" | "deleted",
    "project_id": project.id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
})
```

### Existing Patterns to Follow

- **Route registration:** Follow the pattern in `app.py`'s `register_blueprints()`
- **Blueprint structure:** Follow `routes/sessions.py` for API endpoint structure
- **Error handling:** Return consistent JSON error responses with appropriate status codes
- **SSE broadcasting:** Use `get_broadcaster().broadcast()` for real-time updates
- **Database access:** Use `db.session` for queries, `db.session.commit()` for writes
- **Cascade delete:** Already configured on `Project.agents` relationship

---

## 8. Files to Create

| File | Purpose |
|---|---|
| `src/claude_headspace/routes/projects.py` | CRUD API endpoints |
| `migrations/versions/xxx_add_project_management_fields.py` | Database migration |
| `tests/routes/test_projects.py` | API and route tests |
| `tests/services/test_inference_gating.py` | Inference gating unit tests |

## 9. Files to Modify

| File | Change |
|---|---|
| `src/claude_headspace/app.py` | Register `projects_bp` in `register_blueprints()` |
| `src/claude_headspace/routes/__init__.py` | Export `projects_bp` |
| `src/claude_headspace/models/project.py` | Add `description`, `inference_paused`, `inference_paused_at`, `inference_paused_reason` fields |
| `src/claude_headspace/services/session_correlator.py` | Remove auto-create in `_create_agent_for_session()`, raise `ValueError` for unregistered projects |
| `src/claude_headspace/routes/sessions.py` | Remove auto-create in `create_session()`, return 404 for unregistered projects |
| `src/claude_headspace/services/summarisation_service.py` | Add inference pause check before `summarise_turn()`, `summarise_task()`, `summarise_instruction()` |
| `src/claude_headspace/services/priority_scoring.py` | Filter out agents from paused projects in `score_all_agents()` |

---

## 10. What Pauses vs What Continues

| Pauses (Inference) | Continues (Everything Else) |
|---|---|
| Turn summarisation | Hook event processing |
| Command summarisation | Session correlation & tracking |
| Instruction summarisation | File watching |
| Priority scoring (for that project's agents) | Dashboard display & rendering |
| | SSE broadcasting |
| | Agent state transitions |
| | Event writing (audit trail) |
| | Notification service |

---

## 11. Risks & Mitigation

### Risk 1: Users Don't Realize Manual Registration Is Required

**Risk:** Users start Claude Code sessions in a new project directory and are confused when the session doesn't appear on the dashboard.

**Mitigation:**
- Clear, actionable error message in the hook response: includes the rejected path and a link to `/projects`
- The error is logged at INFO level so it appears in the Headspace logging tab
- Consider adding a notification (via the existing notification service) when a session is rejected

### Risk 2: Inference Gating Check Not Applied Consistently

**Risk:** A new inference call path is added in a future sprint without the pause check, allowing inference to run on paused projects.

**Mitigation:**
- Gating is implemented in the summarisation and priority scoring services which are the only current callers
- Test coverage for the gating logic ensures it's verified
- The pattern is documented in this PRD for future implementers

---

## 12. Acceptance Criteria

### Project Lifecycle (API)

- [ ] `GET /api/projects` returns list of all registered projects with agent counts
- [ ] `POST /api/projects` creates a project and returns 201
- [ ] `POST /api/projects` with duplicate path returns 409
- [ ] `GET /api/projects/<id>` returns full project details with agents
- [ ] `PUT /api/projects/<id>` updates metadata and returns 200
- [ ] `DELETE /api/projects/<id>` cascade-deletes project and agents
- [ ] API endpoints return correct status codes (201, 200, 404, 409)

### Auto-Discovery Disabled

- [ ] Start Claude Code session in unregistered project — session rejected with clear error
- [ ] Error message directs user to add project via `/projects` UI
- [ ] No new projects auto-created in database
- [ ] Previously registered projects continue to work normally

### Inference Controls

- [ ] `PUT /api/projects/<id>/settings` with `inference_paused: true` pauses inference
- [ ] Paused project — no inference calls made (turn/command/instruction summary, priority scoring)
- [ ] Paused project — file watching, hooks, dashboard continue working
- [ ] `PUT /api/projects/<id>/settings` with `inference_paused: false` resumes inference
- [ ] Pause state persists across server restarts

### SSE Broadcasting

- [ ] Project CRUD operations broadcast `project_changed` SSE events
- [ ] Settings changes broadcast `project_settings_changed` SSE events
