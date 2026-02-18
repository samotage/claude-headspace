# Epic 4 Sprint Prompts for PRD Workshop

**Epic:** Epic 4 — Data Management & Wellness  
**Reference:** [`docs/roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md`](../roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md)

---

## Context Documents

| Document                                                                              | Purpose                                                                 |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [Epic 4 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md) | Primary reference for sprint scope, deliverables, acceptance criteria   |
| [Conceptual Overview](../conceptual/claude_headspace_v3.1_conceptual_overview.md)     | Domain concepts (waypoint, progress_summary, brain_reboot)              |
| [Overarching Roadmap](../roadmap/claude_headspace_v3.1_overarching_roadmap.md)        | Epic 4 goals, success criteria, dependencies                            |
| [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md) | Context on inference service, turn summarisation (E4-S4 builds on this) |

---

## Sprint Prompts

### Epic 4 Sprint 1: Archive System

**PRD:** `docs/prds/core/e4-s1-archive-system-prd.md`

> Create a PRD for the Archive System subsystem. Reference Sprint 1 (E4-S1) in the [Epic 4 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md#sprint-1-archive-system-e4-s1) and the artifact definitions in [Conceptual Overview Section 6](../conceptual/claude_headspace_v3.1_conceptual_overview.md#6-repo-artifacts).
>
> **Deliverables:**
>
> - Archive service that handles all artifact types (`src/services/archive_service.py`)
> - Archive waypoint.md when new version created (hook into E2-S2 waypoint editor)
> - Archive brain_reboot.md when new version exported (hook into E3-S5)
> - Archive progress_summary.md when new version generated (hook into E3-S4)
> - Timestamped archive filenames: `archive/{artifact}_{YYYY-MM-DD_HH-MM-SS}.md`
> - Archive directory creation if missing (`docs/brain_reboot/archive/`)
> - Retention policy configuration (keep_all, keep_last_n, time_based)
> - Archive retrieval and listing API
>
> **API Endpoints:**
>
> - GET `/api/projects/<id>/archives` — list archived versions for a project
> - GET `/api/projects/<id>/archives/<artifact>/<timestamp>` — retrieve specific archived version
>
> **Archive Directory Structure:**
>
> ```
> {project}/docs/brain_reboot/
> ├── waypoint.md                           # Current version
> ├── progress_summary.md                   # Current version
> ├── brain_reboot.md                       # Current version (if exported)
> └── archive/
>     ├── waypoint_2026-01-28_14-30-00.md   # Previous versions
>     ├── waypoint_2026-01-25_09-15-00.md
>     ├── progress_summary_2026-01-29_16-00-00.md
>     └── brain_reboot_2026-01-29_16-05-00.md
> ```
>
> **Config.yaml Addition:**
>
> ```yaml
> archive:
>   enabled: true
>   retention:
>     policy: keep_all # keep_all, keep_last_n, time_based
>     keep_last_n: 10 # Used when policy = keep_last_n
>     days: 90 # Used when policy = time_based
> ```
>
> **Integration Points:**
>
> - Hook into E2-S2 waypoint editor (`src/services/waypoint_editor.py`)
> - Hook into E3-S4 progress summary generator (`src/services/progress_summary_generator.py`)
> - Hook into E3-S5 brain reboot generator (`src/services/brain_reboot_generator.py`)
> - Uses Epic 1 Project model for project paths
>
> **Technical Decisions to Address:**
>
> - Archive trigger: hook into existing save operations (recommended) vs dedicated service
> - Filename format: `{artifact}_{YYYY-MM-DD_HH-MM-SS}.md` (decided)
> - Retention policy default: keep_all (recommended)
> - Error handling for file permission issues

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md (Section 6: Repo Artifacts)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md (Sprint 1 section, Config.yaml Additions)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 4 Sprint 2: Project Controls & Management

**PRD:** `docs/prds/core/e4-s2-project-controls-prd.md`

> Create a PRD for the Project Controls & Management subsystem. Reference Sprint 2 (E4-S2) in the [Epic 4 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md#sprint-2-project-controls--management-e4-s2).
>
> This sprint delivers full project lifecycle management with manual-only registration, replacing the current auto-discovery behavior. Users will manage projects explicitly through a dedicated Projects UI.
>
> **Deliverables:**
>
> **Project Lifecycle Management (New):**
>
> - Projects Management UI: dedicated `/projects` page listing all projects
> - Add Project: modal form to manually register new projects (name, path, github_repo, description)
> - Edit Project: modal form to update project metadata and settings
> - Delete Project: confirmation dialog with cascade delete of agents
> - Project CRUD API endpoints (see below)
> - Disable auto-discovery: sessions for unregistered projects are rejected with clear error message
> - "Projects" tab added to header navigation (between Dashboard and Objective)
>
> **Inference Controls (Original scope):**
>
> - Pause/resume inference toggle per project (integrated into Projects UI)
> - Inference service gating logic (check pause state before making calls)
> - Paused indicator on project card/header and in Projects list
> - Pause state persisted across server restarts
> - Database migration for new Project fields
>
> **API Endpoints:**
>
> | Endpoint                      | Method | Description                                    |
> | ----------------------------- | ------ | ---------------------------------------------- |
> | `/api/projects`               | GET    | List all projects with agent counts and status |
> | `/api/projects`               | POST   | Create new project                             |
> | `/api/projects/<id>`          | GET    | Get single project with full details           |
> | `/api/projects/<id>`          | PUT    | Update project metadata and settings           |
> | `/api/projects/<id>`          | DELETE | Delete project (cascades to agents)            |
> | `/api/projects/<id>/settings` | GET    | Get project settings only                      |
> | `/api/projects/<id>/settings` | PUT    | Update project settings only                   |
>
> **UI Routes:**
>
> | Route       | Method | Description              |
> | ----------- | ------ | ------------------------ |
> | `/projects` | GET    | Projects management page |
>
> **Data Model Changes:**
>
> ```python
> # Add to Project model
> class Project(Base):
>     ...
>     # Project metadata
>     description: Mapped[str | None] = mapped_column(Text, nullable=True)
>
>     # Inference settings
>     inference_paused: Mapped[bool] = mapped_column(default=False)
>     inference_paused_at: Mapped[datetime | None]
>     inference_paused_reason: Mapped[str | None]  # Optional reason for pause
> ```
>
> **Disabling Auto-Discovery:**
>
> Currently, projects are auto-created in `session_correlator.py` and `sessions.py`. This sprint changes that:
>
> ```python
> # BEFORE (auto-creates projects)
> project = db.session.query(Project).filter(Project.path == working_directory).first()
> if not project:
>     project = Project(name=project_name, path=working_directory)
>
> # AFTER (rejects unregistered projects)
> project = db.session.query(Project).filter(Project.path == working_directory).first()
> if not project:
>     raise ValueError(
>         f"Project not registered: {working_directory}. "
>         "Add the project via the Projects management UI first."
>     )
> ```
>
> **Rationale for Manual-Only:**
>
> - **Noise reduction** — Only track projects you deliberately want to monitor
> - **No orphans** — No accumulation of throwaway experiment projects
> - **Explicit control** — User decides what's tracked, not the system
> - **Clean dashboard** — Only meaningful projects appear
>
> **Inference Gating Logic:**
>
> ```python
> def should_run_inference(project_id: UUID) -> bool:
>     project = get_project(project_id)
>     if project.inference_paused:
>         logger.debug(f"Inference paused for project {project.name}")
>         return False
>     return True
> ```
>
> **What Pauses vs What Continues:**
>
> | Pauses (Inference)   | Continues              |
> | -------------------- | ---------------------- |
> | Turn summarisation   | File watching          |
> | Command summarisation   | Session/agent tracking |
> | Priority scoring     | Dashboard display      |
> | Progress summary gen | Hooks receiving        |
> |                      | SSE updates            |
>
> **Integration Points:**
>
> - Modifies `session_correlator.py` to reject unregistered projects
> - Modifies `sessions.py` hook receiver to reject unregistered projects
> - Integrates with E3-S1 inference service (add gating check)
> - Updates E3-S2 turn summariser, E3-S3 priority scorer
> - Uses Epic 1 dashboard patterns for UI
> - Uses Epic 1 Project model (extends it)
> - Adds Projects tab to header navigation (`_header.html`)
>
> **Technical Decisions (all decided):**
>
> - Auto-discovery: **disabled** — manual registration only
> - Delete behavior: cascade delete agents (orphaned agents serve no purpose)
> - Storage: database field on Project model
> - Default state: inference enabled by default
> - UI pattern: modal forms for add/edit (consistent with waypoint editor)
> - Navigation: "Projects" tab in header between Dashboard and Objective
>
> **Files to Create:**
>
> - `src/claude_headspace/routes/projects.py` — CRUD API endpoints + `/projects` page route
> - `templates/projects.html` — Projects management page
> - `templates/partials/_project_form_modal.html` — Add/edit project modal
> - `migrations/versions/xxx_add_project_management_fields.py` — DB migration
> - `tests/routes/test_projects.py` — API and route tests
>
> **Files to Modify:**
>
> - `src/claude_headspace/routes/__init__.py` — Register projects blueprint
> - `src/claude_headspace/models/project.py` — Add new fields
> - `src/claude_headspace/services/session_correlator.py` — Remove auto-create, add rejection
> - `src/claude_headspace/routes/sessions.py` — Remove auto-create, add rejection
> - `templates/partials/_header.html` — Add Projects nav tab

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md (Sprint 2 section, Data Model Changes, API Endpoints)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 4 Sprint 3: Activity Monitoring

**PRD:** `docs/prds/core/e4-s3-activity-monitoring-prd.md`

> Create a PRD for the Activity Monitoring subsystem. Reference Sprint 3 (E4-S3) in the [Epic 4 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md#sprint-3-activity-monitoring-e4-s3).
>
> **Deliverables:**
>
> - Turn rate calculation per agent (turns per hour)
> - Average turn time per agent (time between turns)
> - Rollup to project level (aggregate all agents in project)
> - Rollup to overall level (aggregate all projects)
> - Time-series storage for historical data (ActivityMetric model)
> - Dashboard panel: activity metrics display
> - Time-series chart: turns over time (day/week view)
> - Monitoring/metrics API endpoints
> - Database migration for ActivityMetric table
> - Periodic aggregation job (every 5 minutes)
> - 30-day retention with automatic pruning
>
> **API Endpoints:**
>
> - GET `/api/metrics/agents/<id>` — metrics for specific agent
> - GET `/api/metrics/projects/<id>` — aggregated metrics for project
> - GET `/api/metrics/overall` — system-wide aggregated metrics
>
> **Data Model:**
>
> ```python
> class ActivityMetric(Base):
>     __tablename__ = "activity_metrics"
>
>     id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
>     timestamp: Mapped[datetime] = mapped_column(default=func.now())
>     bucket_start: Mapped[datetime]  # Start of time bucket (hourly)
>
>     # Scope (one of these set)
>     agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
>     project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
>     is_overall: Mapped[bool] = mapped_column(default=False)
>
>     # Metrics
>     turn_count: Mapped[int]
>     avg_turn_time_seconds: Mapped[float | None]
>     active_agents: Mapped[int | None]  # For project/overall only
> ```
>
> **Metrics Calculations:**
>
> | Metric        | Formula                              | Level                   |
> | ------------- | ------------------------------------ | ----------------------- |
> | Turn Rate     | `turn_count / hours_active`          | Agent, Project, Overall |
> | Avg Turn Time | `sum(turn_duration) / turn_count`    | Agent, Project, Overall |
> | Active Agents | Count of agents with turns in period | Project, Overall        |
>
> **Integration Points:**
>
> - Uses Epic 1 Turn model for raw turn data
> - Uses Epic 1 Agent and Project models for rollups
> - Dashboard panel added to Epic 1 dashboard
> - Chart library: Chart.js (recommended)
>
> **Technical Decisions to Address:**
>
> - Metric calculation: periodic aggregation every 5 minutes (recommended)
> - Time-series storage: database table (ActivityMetric)
> - Chart library: Chart.js vs D3 vs simple CSS
> - Retention: 30 days rolling (recommended)
> - Granularity: hourly buckets for charts, store raw for detailed analysis

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md (Sprint 3 section, Data Model Changes)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 4 Sprint 4: Headspace Monitoring

**PRD:** `docs/prds/core/e4-s4-headspace-monitoring-prd.md`

> Create a PRD for the Headspace Monitoring subsystem. Reference Sprint 4 (E4-S4) in the [Epic 4 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md#sprint-4-headspace-monitoring-e4-s4).
>
> **Deliverables:**
>
> - Frustration score extraction (enhance turn summarisation prompt)
> - Frustration score stored on Turn model (user turns only)
> - Rolling frustration calculation (last 10 turns, last 30 minutes)
> - Traffic light indicator at top of dashboard (green/yellow/red)
> - Threshold detection (absolute spike, sustained high, rising trend)
> - Gentle playful alert system (dismissable banner)
> - Flow state detection (high throughput + low frustration)
> - Positive reinforcement messages for flow state
> - HeadspaceSnapshot model for tracking state over time
> - Configuration options (enable/disable, thresholds, messages)
> - Database migration for Turn.frustration_score and HeadspaceSnapshot
>
> **API Endpoints:**
>
> - GET `/api/headspace/current` — current frustration level and state
> - GET `/api/headspace/history` — time-series of frustration scores
>
> **Data Model Changes:**
>
> ```python
> # Add to Turn model
> class Turn(Base):
>     ...
>     frustration_score: Mapped[int | None]  # 0-10, user turns only
>
> # New model
> class HeadspaceSnapshot(Base):
>     __tablename__ = "headspace_snapshots"
>
>     id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
>     timestamp: Mapped[datetime] = mapped_column(default=func.now())
>     frustration_rolling_10: Mapped[float]  # Last 10 turns average
>     frustration_rolling_30min: Mapped[float]  # Last 30 min average
>     state: Mapped[str]  # green, yellow, red
>     turn_rate_per_hour: Mapped[float]
>     is_flow_state: Mapped[bool]
>     flow_duration_minutes: Mapped[int | None]
>     last_alert_at: Mapped[datetime | None]
>     alert_count_today: Mapped[int] = mapped_column(default=0)
> ```
>
> **Enhanced Turn Summary Prompt (with Frustration Extraction):**
>
> ```
> Summarise this user turn in 1-2 concise sentences.
>
> Also analyse the user's emotional state and rate their apparent frustration level 0-10:
> - 0-3: Calm, patient, constructive
> - 4-6: Showing some frustration (repetition, mild exasperation)
> - 7-10: Clearly frustrated (caps, punctuation, harsh language, repeated complaints)
>
> Consider:
> - Tone and language intensity
> - Punctuation patterns (!!!, ???, CAPS)
> - Repetition of previous requests
> - Explicit frustration signals ("again", "still not working", "why won't you")
> - Patience indicators (clear instructions, positive framing)
>
> Turn: {turn.text}
>
> Return JSON:
> {
>   "summary": "...",
>   "frustration_score": N
> }
> ```
>
> **Traffic Light Thresholds:**
>
> | Frustration Score | State  | Indicator                | Action                      |
> | ----------------- | ------ | ------------------------ | --------------------------- |
> | 0-3               | Green  | Subtle green dot         | None                        |
> | 4-6               | Yellow | Visible yellow indicator | Alert after 5 min sustained |
> | 7-10              | Red    | Prominent red warning    | Immediate gentle alert      |
>
> **Trigger Conditions:**
>
> | Trigger          | Condition                    | Action          |
> | ---------------- | ---------------------------- | --------------- |
> | Absolute spike   | Single turn frustration >= 8 | Immediate alert |
> | Sustained yellow | Avg >= 5 for 5+ minutes      | Alert           |
> | Sustained red    | Avg >= 7 for 2+ minutes      | Alert           |
> | Rising trend     | +3 points over last 5 turns  | Alert           |
> | Time-based       | Avg >= 4 for 30+ minutes     | Alert           |
>
> **Gentle Alert Messages:**
>
> The alert messages should be gentle, playful, and body-focused — not preachy or instructional:
>
> ```python
> GENTLE_ALERTS = [
>     "Think of your cortisol.",
>     "Your body's gonna hate you for this.",
>     "If you keep getting frustrated, you're going to pay for it later.",
>     "Who owns this, you or the robots?",
>     "The robots don't care if you're upset. But your body does.",
>     "Time for a glass of water?",
>     "Your future self called. They said chill.",
>     "Frustration is feedback. What's it telling you?",
> ]
> ```
>
> **Note:** Feel free to add more fun, creative messages in this style. The tone should be supportive and slightly humorous, never judgmental or dismissive.
>
> **Flow State Messages:**
>
> ```python
> FLOW_MESSAGES = [
>     "You've been in the zone for {minutes} minutes. Nice!",
>     "Flow state detected. Keep riding it.",
>     "Productive streak: {minutes} minutes and counting.",
>     "{turns} turns, low frustration. You're cooking.",
> ]
> ```
>
> **Config.yaml Addition:**
>
> ```yaml
> headspace:
>   enabled: true
>   thresholds:
>     yellow: 4
>     red: 7
>   alert_cooldown_minutes: 10
>   flow_detection:
>     min_turn_rate: 6 # turns per hour
>     max_frustration: 3 # frustration score
>     min_duration_minutes: 15
> ```
>
> **Integration Points:**
>
> - Enhances E3-S2 turn summarisation (same LLM call, extended prompt)
> - Uses E4-S3 activity metrics for flow detection (turn rate)
> - Dashboard header for traffic light indicator
> - Dashboard banner for alerts
> - Uses Epic 1 SSE for real-time indicator updates
>
> **Technical Decisions to Address:**
>
> - Frustration extraction: same LLM call as turn summary (decided)
> - Alert mechanism: dashboard banner (hard to miss)
> - Flow detection: turn rate threshold + frustration threshold
> - Alert cooldown: 10 minutes between alerts (configurable)
> - "I'm fine" button: suppresses alerts for 1 hour (recommended)

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic4_detailed_roadmap.md (Sprint 4 section, Data Model Changes, Config.yaml Additions)
- docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md (E3-S2 turn summarisation for integration context)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

## Usage

1. Copy the prompt for the target sprint
2. Run `/10: prd-workshop` (or your PRD creation workflow)
3. Paste the prompt when asked for PRD requirements
4. The PRD will be generated in the specified location
5. Reference the linked roadmap sections for additional detail if needed

---

## Sprint Dependencies

```
[Epic 3 Complete]
       │
       ▼
   E4-S1 (Archive System)
       │
       └──▶ E4-S2 (Project Controls & Management)
               │
               └──▶ E4-S3 (Activity Monitoring)
                       │
                       └──▶ E4-S4 (Headspace Monitoring)
                               │
                               └──▶ [Epic 4 Complete]
```

**Critical Path:** E4-S1 → E4-S2 → E4-S3 → E4-S4

**Note:** E4-S1 and E4-S3 could technically run in parallel (both depend on Epic 3), but E4-S4 needs E4-S3's metrics infrastructure for flow detection.
