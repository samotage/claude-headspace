---
validation:
  status: draft
  validated_at: null
---

## Product Requirements Document (PRD) — Project Controls & Management

**Project:** Claude Headspace
**Scope:** Project lifecycle management (CRUD), manual-only registration, inference pause/resume controls, dedicated Projects UI
**Sprint:** E4-S2
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace currently auto-discovers projects from the filesystem — any Claude Code session in any directory creates a project record automatically. This leads to noise: throwaway experiments, temp directories, and one-off sessions pollute the dashboard with orphaned projects that serve no purpose.

This PRD defines a project lifecycle management system that replaces auto-discovery with explicit manual registration. Users will manage projects through a dedicated `/projects` page with CRUD operations (add, edit, delete). Sessions for unregistered projects are rejected with a clear error message directing the user to register the project first.

Additionally, this sprint adds per-project inference controls — the ability to pause and resume LLM inference calls (turn summarisation, task summarisation, priority scoring) without affecting session tracking, hooks, or dashboard updates. This gives users cost and noise control over the intelligence layer on a project-by-project basis.

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

The user opens `/projects`, sees their three registered projects listed with agent counts and inference status. They click "Add Project" to register a new codebase they're starting work on. They pause inference on a project they're not actively prioritising. When they start a Claude Code session in an unregistered throwaway directory, the hook is cleanly rejected and the dashboard stays focused on what matters.

---

## 2. Scope

### 2.1 In Scope

- **Project CRUD API:** REST endpoints for listing, creating, reading, updating, and deleting projects
- **Project settings API:** Dedicated endpoints for getting/setting project-level settings (inference pause)
- **Projects management UI:** Dedicated `/projects` page with project list, add/edit modals, delete confirmation
- **Header navigation:** "Projects" tab added between Dashboard and Objective
- **Manual registration only:** Disable auto-discovery in `session_correlator.py` and `sessions.py`; reject unregistered project sessions with clear error
- **Inference pause/resume:** Per-project toggle to pause all inference calls (turn summarisation, task summarisation, instruction summarisation, priority scoring)
- **Inference gating:** Check pause state before every inference call in summarisation service and priority scoring service
- **Database migration:** Add `description`, `inference_paused`, `inference_paused_at`, `inference_paused_reason` columns to the `projects` table
- **Paused indicator:** Visual indicator on the projects list and dashboard project cards when inference is paused
- **SSE broadcast:** Broadcast project settings changes so the dashboard updates in real-time
- **Tests:** Unit tests for the projects API, route tests, and service-level gating tests

### 2.2 Out of Scope

- Project archiving / soft delete (projects are hard-deleted with cascade)
- Bulk project operations (import/export)
- Project-level configuration beyond inference pause (e.g., model selection per project)
- Project grouping or tagging
- Auto-migration of existing auto-discovered projects (they remain; user can delete unwanted ones via the new UI)
- File watcher configuration per project
- Changes to the inference service itself (gating is in the callers)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Navigate to `/projects` — see a list of all registered projects with name, path, agent count, and inference status
2. Click "Add Project" — modal opens with form fields (name, path, github_repo, description)
3. Submit a valid project — project created, appears in list immediately
4. Submit a duplicate path — error returned, no duplicate created
5. Click Edit on a project — modal opens pre-populated with current values
6. Update project metadata — changes saved, list refreshed
7. Click Delete on a project — confirmation dialog appears
8. Confirm delete — project and all its agents cascade-deleted, list refreshed
9. Start a Claude Code session in an unregistered directory — session rejected, hook returns error with clear message directing user to `/projects`
10. Click pause toggle on a project — inference calls stop for that project
11. Paused project — file watching, hooks, session tracking, dashboard display, SSE all continue normally
12. Click resume — inference calls resume for that project
13. Pause state persists across server restarts (stored in database)
14. "Projects" tab visible in header navigation between Dashboard and Objective

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

### Projects Management UI

**FR10:** The system shall provide a `/projects` page accessible via a "Projects" tab in the header navigation, positioned between Dashboard and Objective.

**FR11:** The projects page shall display a table of all registered projects showing: name, path, active agent count, inference status (active/paused), and an actions menu (edit, delete, pause/resume).

**FR12:** The projects page shall provide an "Add Project" button that opens a modal form with fields: name (required), path (required), github_repo (optional), description (optional).

**FR13:** The add project modal shall validate that name and path are non-empty before submission and display server-side validation errors (e.g., duplicate path) inline.

**FR14:** Each project row shall have an actions menu (or action buttons) providing: Edit, Delete, and Pause/Resume inference.

**FR15:** The Edit action shall open a modal form pre-populated with the project's current values, allowing updates to name, path, github_repo, and description.

**FR16:** The Delete action shall show a confirmation dialog stating the project name and warning that all agents will be deleted. The dialog shall require explicit confirmation before proceeding.

**FR17:** The Pause/Resume action shall toggle `inference_paused` via the settings API and update the project's status indicator in the list without a full page reload.

**FR18:** The projects page shall display a paused indicator (e.g., pause icon, "Paused" label) on projects with `inference_paused = true`.

### Header Navigation

**FR19:** The header navigation (`_header.html`) shall include a "Projects" tab link positioned between Dashboard and Objective, in both desktop and mobile navigation.

**FR20:** The Projects tab shall use the active state styling when the user is on the `/projects` page, consistent with other navigation tabs.

### Disable Auto-Discovery

**FR21:** The `_create_agent_for_session` function in `session_correlator.py` shall no longer auto-create Project records. When a session's working directory does not match any registered project, the function shall raise a `ValueError` with a message directing the user to register the project via the `/projects` UI.

**FR22:** The `create_session` endpoint in `routes/sessions.py` shall no longer auto-create Project records. When `project_path` does not match any registered project, the endpoint shall return a 404 response with a message directing the user to register the project via the `/projects` UI.

**FR23:** The error messages for unregistered projects shall be clear and actionable, including the rejected path and a reference to the `/projects` management page. Example: `"Project not registered: /path/to/dir. Add the project via the Projects management UI at /projects first."`

### Inference Gating

**FR24:** The `SummarisationService` shall check the project's `inference_paused` state before making any inference call (`summarise_turn`, `summarise_task`, `summarise_instruction`). If paused, the method shall return `None` without calling the inference service, with a debug log message.

**FR25:** The `PriorityScoringService.score_all_agents()` shall exclude agents belonging to paused projects from the scoring batch. If all active agents belong to paused projects, scoring shall be skipped entirely.

**FR26:** The inference gating check shall query the project's `inference_paused` field via the agent's relationship chain (turn → task → agent → project, or task → agent → project). The check shall use the already-loaded ORM relationships to avoid additional database queries.

**FR27:** The following operations shall continue normally regardless of inference pause state: hook event processing, session correlation, file watching, SSE broadcasting, dashboard rendering, agent state transitions.

### Database Migration

**FR28:** An Alembic migration shall add the following columns to the `projects` table:
- `description` — `Text`, nullable
- `inference_paused` — `Boolean`, not null, default `false`
- `inference_paused_at` — `DateTime(timezone=True)`, nullable
- `inference_paused_reason` — `Text`, nullable

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** All project API endpoints shall validate input and return appropriate HTTP status codes (400 for validation errors, 404 for not found, 409 for conflicts, 500 for server errors).

**NFR2:** The cascade delete shall use SQLAlchemy's `cascade="all, delete-orphan"` on the Project → Agent relationship (already configured) to ensure agents are removed when a project is deleted.

**NFR3:** The projects page shall use vanilla JavaScript (no external dependencies) consistent with the existing dashboard UI pattern.

**NFR4:** Modal forms shall follow the pattern established by the waypoint editor (E2-S2) for consistency.

**NFR5:** All new routes and services shall have unit tests and route tests following the existing three-tier test architecture.

**NFR6:** The inference gating logic shall not introduce circular imports. The check shall be performed in the summarisation and priority scoring services, not in the inference service itself.

---

## 6. UI Overview

### Projects Page Layout

```
+-----------------------------------------------------------------------+
|  CLAUDE >_headspace    [Dashboard] [Projects] [Objective] [Logging]...  |
+-----------------------------------------------------------------------+
|                                                                         |
|  Projects                                            [+ Add Project]    |
|  -------------------------------------------------------------------   |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | Name              | Path                 | Agents | Status    | .. | |
|  +-------------------------------------------------------------------+ |
|  | claude-headspace  | ~/dev/.../headspace  | 3      | Active    | :  | |
|  | my-webapp         | ~/dev/my-webapp      | 1      | Paused    | :  | |
|  | api-server        | ~/dev/api-server     | 0      | Active    | :  | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  : menu -> Edit | Delete | Pause/Resume                                |
|                                                                         |
+-----------------------------------------------------------------------+
```

### Add/Edit Project Modal

```
+-------------------------------------------+
|  Add Project                         [x]  |
+-------------------------------------------+
|                                           |
|  Name *        [________________________] |
|  Path *        [________________________] |
|  GitHub Repo   [________________________] |
|  Description   [________________________] |
|                [________________________] |
|                                           |
|              [Cancel]  [Save Project]     |
+-------------------------------------------+
```

### Delete Confirmation Dialog

```
+-------------------------------------------+
|  Delete Project                      [x]  |
+-------------------------------------------+
|                                           |
|  Are you sure you want to delete          |
|  "claude-headspace"?                      |
|                                           |
|  This will also delete 3 agents and       |
|  all their tasks and turns.               |
|                                           |
|              [Cancel]  [Delete]           |
+-------------------------------------------+
```

---

## 7. Data Model Changes

### Project Model Extensions

```python
class Project(db.Model):
    __tablename__ = "projects"

    # Existing fields
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    github_repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_branch: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # NEW — Project metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NEW — Inference settings
    inference_paused: Mapped[bool] = mapped_column(default=False)
    inference_paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    inference_paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Existing relationship (already has cascade)
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="project", cascade="all, delete-orphan"
    )
```

### Migration

```python
# migrations/versions/xxx_add_project_management_fields.py
def upgrade():
    op.add_column('projects', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('inference_paused', sa.Boolean(),
                  nullable=False, server_default='false'))
    op.add_column('projects', sa.Column('inference_paused_at',
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column('projects', sa.Column('inference_paused_reason',
                  sa.Text(), nullable=True))

def downgrade():
    op.drop_column('projects', 'inference_paused_reason')
    op.drop_column('projects', 'inference_paused_at')
    op.drop_column('projects', 'inference_paused')
    op.drop_column('projects', 'description')
```

---

## 8. API Endpoints

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

### UI Route

| Route | Method | Description |
|---|---|---|
| `/projects` | GET | Projects management page |

---

## 9. Technical Context (for implementers)

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

The `_get_project_for_turn` helper traverses `turn.task.agent.project` using already-loaded ORM relationships. The same pattern applies to `summarise_task()` and `summarise_instruction()` (via `task.agent.project`).

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

- **Modal forms:** Follow the waypoint editor pattern (`templates/partials/_waypoint_modal.html`) for add/edit modals
- **Route registration:** Follow the pattern in `app.py`'s `register_blueprints()`
- **Blueprint structure:** Follow `routes/sessions.py` for API endpoint structure
- **Error handling:** Return consistent JSON error responses with appropriate status codes
- **SSE broadcasting:** Use `get_broadcaster().broadcast()` for real-time updates
- **Database access:** Use `db.session` for queries, `db.session.commit()` for writes
- **Cascade delete:** Already configured on `Project.agents` relationship

---

## 10. Files to Create

| File | Purpose |
|---|---|
| `src/claude_headspace/routes/projects.py` | CRUD API endpoints + `/projects` page route |
| `templates/projects.html` | Projects management page |
| `templates/partials/_project_form_modal.html` | Add/edit project modal |
| `migrations/versions/xxx_add_project_management_fields.py` | Database migration |
| `tests/routes/test_projects.py` | API and route tests |
| `tests/services/test_inference_gating.py` | Inference gating unit tests |

## 11. Files to Modify

| File | Change |
|---|---|
| `src/claude_headspace/app.py` | Register `projects_bp` in `register_blueprints()` |
| `src/claude_headspace/routes/__init__.py` | Export `projects_bp` |
| `src/claude_headspace/models/project.py` | Add `description`, `inference_paused`, `inference_paused_at`, `inference_paused_reason` fields |
| `src/claude_headspace/services/session_correlator.py` | Remove auto-create in `_create_agent_for_session()`, raise `ValueError` for unregistered projects |
| `src/claude_headspace/routes/sessions.py` | Remove auto-create in `create_session()`, return 404 for unregistered projects |
| `src/claude_headspace/services/summarisation_service.py` | Add inference pause check before `summarise_turn()`, `summarise_task()`, `summarise_instruction()` |
| `src/claude_headspace/services/priority_scoring.py` | Filter out agents from paused projects in `score_all_agents()` |
| `templates/partials/_header.html` | Add "Projects" tab between Dashboard and Objective (desktop + mobile) |

---

## 12. What Pauses vs What Continues

| Pauses (Inference) | Continues (Everything Else) |
|---|---|
| Turn summarisation | Hook event processing |
| Task summarisation | Session correlation & tracking |
| Instruction summarisation | File watching |
| Priority scoring (for that project's agents) | Dashboard display & rendering |
| | SSE broadcasting |
| | Agent state transitions |
| | Event writing (audit trail) |
| | Notification service |

---

## 13. Risks & Mitigation

### Risk 1: Users Don't Realize Manual Registration Is Required

**Risk:** Users start Claude Code sessions in a new project directory and are confused when the session doesn't appear on the dashboard.

**Mitigation:**
- Clear, actionable error message in the hook response: includes the rejected path and a link to `/projects`
- The error is logged at INFO level so it appears in the Headspace logging tab
- Consider adding a notification (via the existing notification service) when a session is rejected

### Risk 2: Users Forget Projects Are Paused

**Risk:** Inference is paused for a project, summaries stop generating, but the user forgets and wonders why summaries are stale.

**Mitigation:**
- Visible "Paused" indicator on the projects list and dashboard project cards
- SSE event on pause/resume ensures dashboard updates immediately
- `inference_paused_at` timestamp shows how long inference has been paused

### Risk 3: Cascade Delete Removes Valuable History

**Risk:** Deleting a project removes all agents, tasks, turns, and events — potentially losing useful historical data.

**Mitigation:**
- Confirmation dialog explicitly states what will be deleted (agent count)
- This is the intended behavior — orphaned agents serve no purpose without a project
- Future sprint could add project archiving (out of scope for this PRD)

### Risk 4: Inference Gating Check Not Applied Consistently

**Risk:** A new inference call path is added in a future sprint without the pause check, allowing inference to run on paused projects.

**Mitigation:**
- Gating is implemented in the summarisation and priority scoring services which are the only current callers
- Test coverage for the gating logic ensures it's verified
- The pattern is documented in this PRD for future implementers

---

## 14. Acceptance Criteria

### Project Lifecycle

- [ ] Navigate to `/projects` — see list of all registered projects
- [ ] Click "Add Project" — modal opens with form (name, path, github_repo, description)
- [ ] Submit valid project — project created, appears in list
- [ ] Submit duplicate path — error message, no duplicate created
- [ ] Click Edit on project — modal opens with current values
- [ ] Update project — changes saved, list refreshed
- [ ] Click Delete on project — confirmation dialog appears with agent count warning
- [ ] Confirm delete — project and its agents deleted
- [ ] API endpoints return correct data and status codes (201, 200, 404, 409)

### Auto-Discovery Disabled

- [ ] Start Claude Code session in unregistered project — session rejected with clear error
- [ ] Error message directs user to add project via `/projects` UI
- [ ] No new projects auto-created in database
- [ ] Previously registered projects continue to work normally

### Inference Controls

- [ ] Click pause button — project marked as paused, timestamp recorded
- [ ] Paused project — no inference calls made (turn/task/instruction summary, priority scoring)
- [ ] Paused project — file watching, hooks, dashboard continue working
- [ ] Paused indicator visible in projects list
- [ ] Click resume — inference calls resume, paused timestamp cleared
- [ ] Pause state persists across server restarts

### Navigation

- [ ] "Projects" tab visible in header between Dashboard and Objective
- [ ] Tab shows active state when on `/projects` page
- [ ] Tab works in both desktop and mobile navigation
