# Epic 4 Detailed Roadmap: Data Management & Wellness

**Project:** Claude Headspace v3.1  
**Epic:** Epic 4 — Data Management & Wellness  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-01-30

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 4 implementation. It breaks Epic 4 into 4 logical sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem.

**Epic 4 Goal:** Add data lifecycle management, project controls, activity monitoring, and developer wellness tracking (headspace/frustration monitoring).

**Epic 4 Value Proposition:**

- **Artifact Archiving** — Automatic version history for waypoint, brain_reboot, and progress_summary
- **Project Controls** — Pause/resume inference calls per project (cost and noise control)
- **Activity Monitoring** — Turn metrics, productivity patterns, time-series visualization
- **Headspace Monitoring** — Frustration tracking, flow state detection, gentle wellness alerts

**The Differentiator:** Claude Headspace isn't just about monitoring agents — it's about monitoring _you_. The headspace monitoring feature transforms this from a developer tool into a developer wellness tool, recognizing that your mental state directly impacts your effectiveness when working with AI agents.

**Success Criteria:**

- Create new waypoint → previous version archived with timestamp
- Create new brain_reboot → previous version archived
- Create new progress_summary → previous version archived
- Pause project → inference calls stop, other activity continues
- Activity metrics show turn rate/avg time per agent, project, overall
- Frustration indicator (traffic light) visible at top of dashboard
- High frustration triggers gentle alert ("Think of your cortisol")
- Flow state detected and celebrated ("You've been in the zone for 45 minutes")
- Time-series productivity patterns viewable

**Architectural Foundation:** Builds on Epic 1's Flask application, database, SSE system, and dashboard UI. Builds on Epic 3's inference service and turn summarisation. Epic 4 adds data lifecycle management and wellness monitoring.

**Dependency:** Epic 3 must be complete before Epic 4 begins (turn summarisation and progress summaries must exist).

---

## Epic 4 Story Mapping

| Story ID | Story Name                                        | Subsystem              | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------------- | ---------------------- | ------------- | ------ | -------- |
| E4-S1    | Archive artifacts when new versions created       | `archive-system`       | core/         | 1      | P2       |
| E4-S2    | Project lifecycle management & inference controls | `project-controls`     | core/         | 2      | P2       |
| E4-S3    | Track turn metrics and productivity patterns      | `activity-monitoring`  | core/         | 3      | P2       |
| E4-S4    | Track frustration and flow state for wellness     | `headspace-monitoring` | core/         | 4      | P2       |

---

## Sprint Breakdown

### Sprint 1: Archive System (E4-S1)

**Goal:** Automatic archiving of waypoint, brain_reboot, and progress_summary when new versions are created.

**Duration:** 1 week  
**Dependencies:** Epic 3 complete (progress_summary generation exists)

**Deliverables:**

- Archive service that handles all artifact types
- Archive waypoint.md when new version created (from E2-S2 waypoint editor)
- Archive brain_reboot.md when new version created (from E3-S5)
- Archive progress_summary.md when new version created (from E3-S4)
- Timestamped archive filenames: `archive/{artifact}_{YYYY-MM-DD_HH-MM-SS}.md`
- Archive directory creation if missing (`docs/brain_reboot/archive/`)
- Retention policy configuration (keep all, keep last N, time-based)
- API endpoint: GET `/api/projects/<id>/archives` (list archived versions)
- API endpoint: GET `/api/projects/<id>/archives/<artifact>/<timestamp>` (retrieve specific version)

**Subsystem Requiring PRD:**

1. `archive-system` — Archive service, retention policies, API endpoints

**PRD Location:** `docs/prds/core/e4-s1-archive-system-prd.md`

**Stories:**

- E4-S1: Archive artifacts when new versions created

**Technical Decisions Required:**

- Archive location: `archive/` subdirectory in `docs/brain_reboot/` — **decided**
- Filename format: `{artifact}_{YYYY-MM-DD_HH-MM-SS}.md` — **decided**
- Retention policy default: keep all versions — **recommend keep all for now**
- Archive trigger: hook into existing save operations vs dedicated service — **recommend hook into existing**

**Archive File Structure:**

```
{project}/docs/brain_reboot/
├── waypoint.md                           # Current version
├── progress_summary.md                   # Current version
├── brain_reboot.md                       # Current version (if exported)
└── archive/
    ├── waypoint_2026-01-28_14-30-00.md   # Previous versions
    ├── waypoint_2026-01-25_09-15-00.md
    ├── progress_summary_2026-01-29_16-00-00.md
    └── brain_reboot_2026-01-29_16-05-00.md
```

**Risks:**

- Archive directory growing very large over time
- File permission issues writing to project directories
- Race conditions if multiple archives triggered simultaneously

**Acceptance Criteria:**

- Edit waypoint via UI → previous version archived before save
- Generate new progress_summary → previous version archived
- Export brain_reboot → previous version archived (if exists)
- Archive files have correct timestamps
- Archive directory created if missing
- API returns list of archived versions per artifact
- API can retrieve specific archived version
- Retention policy configurable in config.yaml

---

### Sprint 2: Project Controls & Management (E4-S2)

**Goal:** Full project lifecycle management with manual-only registration, CRUD operations, dedicated Projects UI, and inference pause/resume controls.

**Duration:** 1-2 weeks  
**Dependencies:** E4-S1 complete (establishes project-level settings pattern), Epic 3 inference service

**Deliverables:**

**Project Lifecycle Management (New):**

- Projects Management UI: dedicated `/projects` page listing all projects
- Add Project: modal form to manually register new projects
- Edit Project: modal form to update project metadata and settings
- Delete Project: confirmation dialog with cascade delete of agents
- Project CRUD API endpoints (see below)
- Disable auto-discovery: sessions for unregistered projects are rejected

**Inference Controls (Original E4-S2 scope):**

- Pause/resume toggle per project (integrated into Projects UI)
- Inference service checks pause state before making calls
- Paused indicator on project card/header
- Pause state persisted across server restarts
- Config.yaml schema for default pause state

**Subsystem Requiring PRD:**

2. `project-controls` — Project lifecycle management, CRUD API, Projects UI, inference gating

**PRD Location:** `docs/prds/core/e4-s2-project-controls-prd.md`

**Stories:**

- E4-S2a: Project lifecycle management (add, edit, delete projects)
- E4-S2b: Projects Management UI
- E4-S2c: Disable auto-discovery (manual registration only)
- E4-S2d: Pause/resume inference calls per project

**API Endpoints:**

| Endpoint                      | Method | Description                                               |
| ----------------------------- | ------ | --------------------------------------------------------- |
| `/api/projects`               | GET    | List all projects with agent counts and status            |
| `/api/projects`               | POST   | Create new project (name, path, github_repo, description) |
| `/api/projects/<id>`          | GET    | Get single project with full details                      |
| `/api/projects/<id>`          | PUT    | Update project metadata and settings                      |
| `/api/projects/<id>`          | DELETE | Delete project (cascades to agents)                       |
| `/api/projects/<id>/settings` | GET    | Get project settings (inference_paused, etc.)             |
| `/api/projects/<id>/settings` | PUT    | Update project settings only                              |

**Projects UI Route:**

| Route       | Method | Description              |
| ----------- | ------ | ------------------------ |
| `/projects` | GET    | Projects management page |

**Technical Decisions Required:**

- Auto-discovery: **disabled** — manual registration only — **decided**
- Delete behavior: cascade delete agents — **decided** (orphaned agents serve no purpose)
- Storage: database field on Project model — **decided**
- Default state: inference enabled by default — **decided**
- What pauses: turn summarisation, task summarisation, priority scoring — **all inference calls**
- What continues: file watching, session tracking, dashboard display, hooks — **everything else**
- UI pattern: modal forms for add/edit (consistent with waypoint editor) — **decided**
- Navigation: "Projects" tab in header between Dashboard and Objective — **decided**

**Data Model Changes:**

```python
# Add to Project model
class Project(Base):
    ...
    # Project metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Optional description

    # Inference settings
    inference_paused: Mapped[bool] = mapped_column(default=False)
    inference_paused_at: Mapped[datetime | None]
    inference_paused_reason: Mapped[str | None]  # Optional reason for pause
```

**Disabling Auto-Discovery:**

Currently, projects are auto-created when sessions start (in `session_correlator.py` and `sessions.py`). This sprint changes that behavior:

```python
# In session_correlator.py — BEFORE (auto-creates)
project = db.session.query(Project).filter(Project.path == working_directory).first()
if not project:
    project = Project(name=project_name, path=working_directory)  # Auto-create

# In session_correlator.py — AFTER (rejects unregistered)
project = db.session.query(Project).filter(Project.path == working_directory).first()
if not project:
    raise ValueError(
        f"Project not registered: {working_directory}. "
        "Add the project via the Projects management UI first."
    )
```

**Rationale for Manual-Only:**

1. **Noise reduction** — Only track projects you deliberately want to monitor
2. **No orphans** — No accumulation of throwaway experiment projects
3. **Explicit control** — User decides what's tracked, not the system
4. **Clean dashboard** — Only meaningful projects appear

**Inference Gating Logic:**

```python
def should_run_inference(project_id: UUID) -> bool:
    project = get_project(project_id)
    if project.inference_paused:
        logger.debug(f"Inference paused for project {project.name}")
        return False
    return True

# In turn summariser
def summarise_turn(turn: Turn) -> str | None:
    if not should_run_inference(turn.task.agent.project_id):
        return None  # Skip summarisation
    # ... proceed with inference
```

**Projects UI Wireframe:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLAUDE >_headspace    [Dashboard] [Projects] [Objective] [Logging] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Projects                                        [+ Add Project]    │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Name           │ Path                 │ Agents │ Status │ ⚙ │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ claude-headspace│ ~/dev/.../headspace │ 3      │ ▶ Active│ ⋮ │   │
│  │ my-webapp      │ ~/dev/my-webapp      │ 1      │ ⏸ Paused│ ⋮ │   │
│  │ api-server     │ ~/dev/api-server     │ 0      │ ▶ Active│ ⋮ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ⋮ menu: Edit | Delete | Pause/Resume                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Risks:**

- Users may not realize they need to add projects before starting sessions
- Session rejection error message must be clear and actionable
- Users forgetting projects are paused (stale summaries)
- Pause state not checked consistently across all inference calls

**Acceptance Criteria:**

**Project Lifecycle:**

- Navigate to `/projects` → see list of all registered projects
- Click "Add Project" → modal opens with form (name, path, github_repo, description)
- Submit valid project → project created, appears in list
- Submit duplicate path → error message, no duplicate created
- Click Edit on project → modal opens with current values
- Update project → changes saved, list refreshed
- Click Delete on project → confirmation dialog appears
- Confirm delete → project and its agents deleted
- API endpoints return correct data and status codes

**Auto-Discovery Disabled:**

- Start Claude Code session in unregistered project → session rejected with clear error
- Error message directs user to add project via `/projects` UI
- No new projects auto-created in database

**Inference Controls:**

- Click pause button → project marked as paused
- Paused project → no inference calls made (turn/task summary, priority)
- Paused project → file watching, hooks, dashboard continue working
- Paused indicator visible in projects list and on dashboard project card
- Click resume → inference calls resume
- Pause state persists across server restarts

---

### Sprint 3: Activity Monitoring (E4-S3)

**Goal:** Track turn metrics and productivity patterns with time-series visualization.

**Duration:** 1 week  
**Dependencies:** Epic 1 complete (Turn model, events), Epic 3 complete (turn data flowing)

**Deliverables:**

- Turn rate calculation per agent (turns per hour)
- Average turn time per agent (time between turns)
- Rollup to project level (aggregate all agents in project)
- Rollup to overall level (aggregate all projects)
- Time-series storage for historical data
- Dashboard panel: activity metrics display
- Time-series chart: turns over time (day/week view)
- Monitoring/metrics API endpoint
- API endpoints: GET `/api/metrics/agents/<id>`, GET `/api/metrics/projects/<id>`, GET `/api/metrics/overall`

**Subsystem Requiring PRD:**

3. `activity-monitoring` — Turn metrics, rollups, time-series, metrics API

**PRD Location:** `docs/prds/core/e4-s3-activity-monitoring-prd.md`

**Stories:**

- E4-S3: Track turn metrics and productivity patterns

**Technical Decisions Required:**

- Metric calculation: real-time vs periodic aggregation — **recommend periodic (every 5 minutes)**
- Time-series storage: database table vs time-series DB — **recommend database table for simplicity**
- Chart library: Chart.js vs D3 vs simple CSS — **recommend Chart.js**
- Retention: how long to keep time-series data — **recommend 30 days rolling**
- Granularity: minute vs hour vs day buckets — **recommend hourly for charts, store raw**

**Data Model Changes:**

```python
class ActivityMetric(Base):
    __tablename__ = "activity_metrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    bucket_start: Mapped[datetime]  # Start of time bucket (hourly)

    # Scope (one of these set)
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    is_overall: Mapped[bool] = mapped_column(default=False)

    # Metrics
    turn_count: Mapped[int]
    avg_turn_time_seconds: Mapped[float | None]
    active_agents: Mapped[int | None]  # For project/overall only
```

**Metrics Calculations:**

| Metric             | Formula                                  | Level                   |
| ------------------ | ---------------------------------------- | ----------------------- |
| Turn Rate          | `turn_count / hours_active`              | Agent, Project, Overall |
| Avg Turn Time      | `sum(turn_duration) / turn_count`        | Agent, Project, Overall |
| Active Agents      | Count of agents with turns in period     | Project, Overall        |
| Productivity Score | `turn_rate * (1 - frustration_score/10)` | Agent, Project, Overall |

**Risks:**

- Metric calculation impacting performance
- Time-series table growing large
- Inaccurate metrics if turns have missing timestamps
- Dashboard becoming too cluttered with metrics

**Acceptance Criteria:**

- Turn rate displayed per agent on dashboard
- Average turn time displayed per agent
- Project-level metrics aggregate agent metrics
- Overall metrics aggregate all projects
- Time-series chart shows turns over day/week
- Metrics API returns current and historical data
- Hourly aggregation runs automatically
- 30-day retention enforced (old data pruned)

---

### Sprint 4: Headspace Monitoring (E4-S4)

**Goal:** Track user frustration and flow state to support developer wellness.

**Duration:** 1-2 weeks  
**Dependencies:** Epic 3 complete (turn summarisation infrastructure), E4-S3 complete (metrics infrastructure)

**Deliverables:**

- **Frustration Score Extraction:**
  - Enhance turn summarisation prompt to extract frustration score (0-10)
  - Frustration score stored on Turn model
  - Analyse user turns only (not agent turns)

- **Rolling Frustration Calculation:**
  - Rolling average over last 10 turns
  - Rolling average over last 30 minutes
  - Detect: absolute spike, sustained high, rising trend

- **Traffic Light Indicator:**
  - Always visible at top of dashboard
  - Green (0-3): mood good
  - Yellow (4-6): getting frustrated
  - Red (7-10): warning, warning
  - Subtle when green, prominent when yellow/red

- **Gentle Playful Alerts:**
  - Trigger on sustained yellow (>5 min) or any red
  - Messages: "Think of your cortisol", "Your body's gonna hate you for this", "Who owns this, you or the robots?"
  - Dismissable but re-triggers if frustration continues

- **Flow State Detection:**
  - High turn throughput + low frustration = flow
  - Display: "You've been in the zone for 45 minutes"
  - Positive reinforcement for good states

- **Configuration:**
  - Enable/disable headspace monitoring in config.yaml
  - Configurable thresholds for yellow/red
  - Configurable alert messages

- **API Endpoints:**
  - GET `/api/headspace/current` — Current frustration level and state
  - GET `/api/headspace/history` — Time-series of frustration scores

**Subsystem Requiring PRD:**

4. `headspace-monitoring` — Frustration tracking, flow state, traffic light, alerts

**PRD Location:** `docs/prds/core/e4-s4-headspace-monitoring-prd.md`

**Stories:**

- E4-S4: Track frustration and flow state for wellness

**Technical Decisions Required:**

- Frustration extraction: part of turn summary prompt vs separate call — **recommend same prompt**
- Alert mechanism: dashboard banner vs modal vs toast — **recommend banner (hard to miss)**
- Flow detection: turn rate threshold + frustration threshold — **recommend >6 turns/hour + frustration <3**
- Alert cooldown: how long before re-alerting — **recommend 10 minutes**
- History retention: how long to keep frustration scores — **recommend 7 days**

**Data Model Changes:**

```python
# Add to Turn model
class Turn(Base):
    ...
    frustration_score: Mapped[int | None]  # 0-10, user turns only

# New table for headspace state
class HeadspaceSnapshot(Base):
    __tablename__ = "headspace_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())

    # Current state
    frustration_rolling_10: Mapped[float]  # Last 10 turns average
    frustration_rolling_30min: Mapped[float]  # Last 30 min average
    state: Mapped[str]  # green, yellow, red

    # Flow detection
    turn_rate_per_hour: Mapped[float]
    is_flow_state: Mapped[bool]
    flow_duration_minutes: Mapped[int | None]

    # Alert tracking
    last_alert_at: Mapped[datetime | None]
    alert_count_today: Mapped[int] = mapped_column(default=0)
```

**Enhanced Turn Summary Prompt:**

```
Summarise this user turn in 1-2 concise sentences.

Also analyse the user's emotional state and rate their apparent frustration level 0-10:
- 0-3: Calm, patient, constructive
- 4-6: Showing some frustration (repetition, mild exasperation)
- 7-10: Clearly frustrated (caps, punctuation, harsh language, repeated complaints)

Consider:
- Tone and language intensity
- Punctuation patterns (!!!, ???, CAPS)
- Repetition of previous requests
- Explicit frustration signals ("again", "still not working", "why won't you")
- Patience indicators (clear instructions, positive framing)

Turn: {turn.text}

Return JSON:
{
  "summary": "...",
  "frustration_score": N
}
```

**Alert Messages (Randomised):**

```python
GENTLE_ALERTS = [
    "Think of your cortisol.",
    "Your body's gonna hate you for this.",
    "If you keep getting frustrated, you're going to pay for it later.",
    "Who owns this, you or the robots?",
    "The robots don't care if you're upset. But your body does.",
    "Time for a glass of water?",
    "Your future self called. They said chill.",
    "Frustration is feedback. What's it telling you?",
]

FLOW_MESSAGES = [
    "You've been in the zone for {minutes} minutes. Nice!",
    "Flow state detected. Keep riding it.",
    "Productive streak: {minutes} minutes and counting.",
    "{turns} turns, low frustration. You're cooking.",
]
```

**Traffic Light Logic:**

| Frustration Score | State  | Indicator                | Action                      |
| ----------------- | ------ | ------------------------ | --------------------------- |
| 0-3               | Green  | Subtle green dot         | None                        |
| 4-6               | Yellow | Visible yellow indicator | Alert after 5 min sustained |
| 7-10              | Red    | Prominent red warning    | Immediate gentle alert      |

**Threshold Triggers:**

| Trigger          | Condition                   | Action          |
| ---------------- | --------------------------- | --------------- |
| Absolute spike   | Single turn frustration ≥ 8 | Immediate alert |
| Sustained yellow | Avg ≥ 5 for 5+ minutes      | Alert           |
| Sustained red    | Avg ≥ 7 for 2+ minutes      | Alert           |
| Rising trend     | +3 points over last 5 turns | Alert           |
| Time-based       | Avg ≥ 4 for 30+ minutes     | Alert           |

**Risks:**

- Frustration detection being inaccurate (false positives/negatives)
- Alerts being annoying rather than helpful
- Users disabling feature and missing wellness signals
- Privacy concerns about emotional analysis

**Acceptance Criteria:**

- User turns have frustration score extracted (0-10)
- Traffic light indicator visible at top of dashboard
- Green when frustration low, yellow/red when elevated
- Indicator becomes more prominent as frustration rises
- Gentle alert appears on sustained high frustration
- Alert message is playful, not preachy
- Alert dismissable but re-triggers if frustration continues
- Flow state detected: high throughput + low frustration
- Flow state message displayed ("You've been in the zone...")
- Headspace monitoring can be toggled off in config
- Thresholds configurable in config.yaml
- History API returns frustration time-series

---

## Subsystems Requiring OpenSpec PRDs

The following 4 subsystems need detailed PRDs created via OpenSpec. Each PRD will be generated as a separate change proposal and validated before implementation.

### PRD Directory Structure

```
docs/prds/
└── core/                    # Core infrastructure components
    ├── e4-s1-archive-system-prd.md
    ├── e4-s2-project-controls-prd.md
    ├── e4-s3-activity-monitoring-prd.md
    └── e4-s4-headspace-monitoring-prd.md
```

---

### 1. Archive System

**Subsystem ID:** `archive-system`  
**Sprint:** E4-S1  
**Priority:** P2  
**PRD Location:** `docs/prds/core/e4-s1-archive-system-prd.md`

**Scope:**

- Archive service for all artifact types
- Hook into existing save operations
- Timestamped archive filenames
- Archive directory management
- Retention policy configuration
- Archive retrieval API

**Key Requirements:**

- Must archive waypoint.md when new version saved
- Must archive brain_reboot.md when new version exported
- Must archive progress_summary.md when new version generated
- Must create archive directory if missing
- Must use consistent timestamp format
- Must provide API to list and retrieve archives
- Must support configurable retention policy

**OpenSpec Spec:** `openspec/specs/archive-system/spec.md`

**Related Files:**

- `src/services/archive_service.py` (new)
- `src/services/waypoint_editor.py` (update to call archive)
- `src/services/progress_summary_generator.py` (update to call archive)
- `src/services/brain_reboot_generator.py` (update to call archive)
- `src/routes/archives.py` (new)
- `config.yaml` (add archive section)

**Data Model Changes:**

None (archives are files in project directories)

**Config.yaml Additions:**

```yaml
archive:
  enabled: true
  retention:
    policy: keep_all # keep_all, keep_last_n, time_based
    keep_last_n: 10 # Used when policy = keep_last_n
    days: 90 # Used when policy = time_based
```

**Dependencies:** Epic 3 complete (E3-S4 progress_summary, E3-S5 brain_reboot)

**Acceptance Tests:**

- Save waypoint → previous archived
- Generate progress_summary → previous archived
- Export brain_reboot → previous archived
- Archive directory created if missing
- API lists archives correctly
- API retrieves specific archive

---

### 2. Project Controls

**Subsystem ID:** `project-controls`  
**Sprint:** E4-S2  
**Priority:** P2  
**PRD Location:** `docs/prds/core/e4-s2-project-controls-prd.md`

**Scope:**

- Pause/resume inference toggle
- Project settings storage
- Inference gating logic
- Dashboard UI for controls
- API endpoints for settings

**Key Requirements:**

- Must allow pausing inference per project
- Must persist pause state in database
- Must gate all inference calls through pause check
- Must continue file watching, hooks, dashboard when paused
- Must show clear indicator when project paused
- Must provide API for get/set settings

**OpenSpec Spec:** `openspec/specs/project-controls/spec.md`

**Related Files:**

- `src/models/project.py` (add inference_paused field)
- `src/services/inference_service.py` (add gating check)
- `src/services/turn_summariser.py` (check before calling)
- `src/services/task_summariser.py` (check before calling)
- `src/services/priority_scorer.py` (check before calling)
- `src/routes/projects.py` (add settings endpoint)
- `templates/partials/_project_card.html` (add pause button)
- `migrations/versions/xxx_add_project_settings.py` (new)

**Data Model Changes:**

```python
class Project(Base):
    ...
    inference_paused: Mapped[bool] = mapped_column(default=False)
    inference_paused_at: Mapped[datetime | None]
```

**Dependencies:** E4-S1 complete, Epic 3 inference service

**Acceptance Tests:**

- Pause project → inference stops
- Resume project → inference resumes
- Other activity continues when paused
- Pause state persists across restarts
- API works correctly

---

### 3. Activity Monitoring

**Subsystem ID:** `activity-monitoring`  
**Sprint:** E4-S3  
**Priority:** P2  
**PRD Location:** `docs/prds/core/e4-s3-activity-monitoring-prd.md`

**Scope:**

- Turn rate calculation
- Average turn time calculation
- Rollup aggregations (project, overall)
- Time-series storage
- Dashboard metrics panel
- Time-series charts
- Metrics API

**Key Requirements:**

- Must calculate turn rate per agent
- Must calculate average turn time per agent
- Must aggregate to project and overall levels
- Must store time-series data for historical analysis
- Must display metrics on dashboard
- Must provide chart visualization
- Must enforce retention policy (30 days)
- Must expose metrics via API

**OpenSpec Spec:** `openspec/specs/activity-monitoring/spec.md`

**Related Files:**

- `src/models/activity_metric.py` (new)
- `src/services/activity_tracker.py` (new)
- `src/services/metrics_aggregator.py` (new)
- `src/routes/metrics.py` (new)
- `templates/partials/_metrics_panel.html` (new)
- `static/js/metrics_chart.js` (new)
- `migrations/versions/xxx_add_activity_metrics.py` (new)

**Data Model Changes:**

```python
class ActivityMetric(Base):
    __tablename__ = "activity_metrics"

    id: Mapped[UUID]
    timestamp: Mapped[datetime]
    bucket_start: Mapped[datetime]
    agent_id: Mapped[UUID | None]
    project_id: Mapped[UUID | None]
    is_overall: Mapped[bool]
    turn_count: Mapped[int]
    avg_turn_time_seconds: Mapped[float | None]
    active_agents: Mapped[int | None]
```

**Dependencies:** Epic 1 complete (Turn model), Epic 3 complete

**Acceptance Tests:**

- Turn rate calculated per agent
- Avg turn time calculated per agent
- Project rollup aggregates correctly
- Overall rollup aggregates correctly
- Time-series chart displays data
- Metrics API returns data
- Old data pruned (30 days)

---

### 4. Headspace Monitoring

**Subsystem ID:** `headspace-monitoring`  
**Sprint:** E4-S4  
**Priority:** P2  
**PRD Location:** `docs/prds/core/e4-s4-headspace-monitoring-prd.md`

**Scope:**

- Frustration score extraction
- Rolling frustration calculation
- Traffic light indicator
- Threshold detection
- Gentle alert system
- Flow state detection
- Configuration options
- Headspace API

**Key Requirements:**

- Must extract frustration score (0-10) from user turns
- Must calculate rolling averages (10 turns, 30 minutes)
- Must display traffic light indicator (green/yellow/red)
- Must trigger gentle alerts on sustained high frustration
- Must detect and celebrate flow state
- Must be configurable (enable/disable, thresholds)
- Must provide API for current state and history
- Must not be preachy or dismissive

**OpenSpec Spec:** `openspec/specs/headspace-monitoring/spec.md`

**Related Files:**

- `src/models/turn.py` (add frustration_score field)
- `src/models/headspace_snapshot.py` (new)
- `src/services/headspace_monitor.py` (new)
- `src/services/turn_summariser.py` (enhance prompt)
- `src/routes/headspace.py` (new)
- `templates/partials/_headspace_indicator.html` (new)
- `templates/partials/_headspace_alert.html` (new)
- `static/js/headspace.js` (new)
- `migrations/versions/xxx_add_headspace.py` (new)
- `config.yaml` (add headspace section)

**Data Model Changes:**

```python
# Add to Turn model
class Turn(Base):
    ...
    frustration_score: Mapped[int | None]

# New model
class HeadspaceSnapshot(Base):
    __tablename__ = "headspace_snapshots"

    id: Mapped[UUID]
    timestamp: Mapped[datetime]
    frustration_rolling_10: Mapped[float]
    frustration_rolling_30min: Mapped[float]
    state: Mapped[str]  # green, yellow, red
    turn_rate_per_hour: Mapped[float]
    is_flow_state: Mapped[bool]
    flow_duration_minutes: Mapped[int | None]
    last_alert_at: Mapped[datetime | None]
    alert_count_today: Mapped[int]
```

**Config.yaml Additions:**

```yaml
headspace:
  enabled: true
  thresholds:
    yellow: 4
    red: 7
  alert_cooldown_minutes: 10
  flow_detection:
    min_turn_rate: 6 # turns per hour
    max_frustration: 3 # frustration score
    min_duration_minutes: 15
  messages:
    gentle_alerts:
      - "Think of your cortisol."
      - "Your body's gonna hate you for this."
      - "If you keep getting frustrated, you're going to pay for it later."
      - "Who owns this, you or the robots?"
    flow_messages:
      - "You've been in the zone for {minutes} minutes. Nice!"
      - "Flow state detected. Keep riding it."
```

**Dependencies:** Epic 3 complete (turn summarisation), E4-S3 complete (metrics infrastructure)

**Acceptance Tests:**

- User turns have frustration score
- Traffic light shows correct state
- Indicator prominent when yellow/red
- Gentle alert on sustained frustration
- Alert message is playful
- Flow state detected correctly
- Flow message displayed
- Feature can be disabled
- Thresholds configurable
- API returns headspace data

---

## Sprint Dependencies & Critical Path

```
[Epic 3 Complete]
       │
       ▼
   E4-S1 (Archive System)
       │
       └──▶ E4-S2 (Project Controls)
               │
               └──▶ E4-S3 (Activity Monitoring)
                       │
                       └──▶ E4-S4 (Headspace Monitoring)
                               │
                               └──▶ [Epic 4 Complete]
```

**Critical Path:** Epic 3 → E4-S1 → E4-S2 → E4-S3 → E4-S4

**Parallel Tracks:**

- E4-S1 and E4-S3 could technically run in parallel (both depend on Epic 3, not each other)
- E4-S4 depends on E4-S3 for metrics infrastructure

**Recommended Sequence:**

1. E4-S1 (Archive System) — establishes file management patterns
2. E4-S2 (Project Controls) — uses project settings pattern
3. E4-S3 (Activity Monitoring) — builds metrics infrastructure
4. E4-S4 (Headspace Monitoring) — uses metrics infrastructure, adds wellness layer

**Total Duration:** 3-4 weeks

---

## Technical Decisions Made

### Decision 1: Archive on Every Save

**Decision:** Archive previous version every time a new version is saved (not just significant changes).

**Rationale:**

- Simple to implement (no change detection needed)
- Complete history preserved
- User can always roll back
- Storage is cheap

**Impact:**

- More archive files created
- Need retention policy to manage growth
- Simple implementation

---

### Decision 2: Pause Means Inference Only

**Decision:** Pause only stops inference calls; everything else continues.

**Rationale:**

- Clear, predictable behavior
- Users can still see agent activity
- Cost control without losing visibility
- Closing sessions is the way to stop tracking entirely

**Impact:**

- Simple mental model for users
- Inference service needs pause check
- Dashboard continues to update

---

### Decision 3: Frustration in Same Inference Call

**Decision:** Extract frustration score during turn summarisation (same LLM call).

**Rationale:**

- Minimal extra cost (already calling LLM)
- Consistent timing (summary and frustration together)
- Single prompt easier to maintain

**Impact:**

- Turn summarisation prompt must be enhanced
- Both summary and frustration extracted from same response
- Requires JSON response format

---

### Decision 4: Traffic Light Always Visible

**Decision:** Headspace indicator always visible at top of dashboard, prominence increases with frustration.

**Rationale:**

- Can't miss it when frustrated
- Doesn't intrude when calm (subtle green)
- Progressive disclosure of warning
- No notifications needed (dashboard-only)

**Impact:**

- Dashboard header needs indicator space
- CSS transitions for prominence changes
- SSE updates for real-time indicator changes

---

### Decision 5: Gentle and Playful Alerts

**Decision:** Alert messages are gentle, playful, and body-focused — not preachy or instructional.

**Rationale:**

- User requested this tone explicitly
- "Your cortisol" framing is personal and physical
- Humor diffuses tension
- "Who owns this, you or the robots?" is empowering

**Impact:**

- Alert message pool needs careful curation
- Messages should be configurable for personalization
- Avoid anything that could feel judgmental

---

## Open Questions

### 1. Archive Retention Default

**Question:** What should the default retention policy be?

**Options:**

- **Option A:** Keep all versions forever (simple, but storage grows)
- **Option B:** Keep last 10 versions per artifact (bounded, may lose history)
- **Option C:** Keep 90 days of versions (time-based, predictable cleanup)

**Recommendation:** Option A (keep all) as default — users can configure differently if storage is a concern.

**Decision needed by:** E4-S1 implementation

---

### 2. Activity Metrics Dashboard Location

**Question:** Where should activity metrics be displayed?

**Options:**

- **Option A:** Dedicated metrics tab
- **Option B:** Metrics panel on dashboard sidebar
- **Option C:** Inline on agent cards
- **Option D:** Combination (summary inline, detail in tab)

**Recommendation:** Option D — inline summary on cards, detailed charts in dedicated panel/tab.

**Decision needed by:** E4-S3 implementation

---

### 3. Frustration False Positive Handling

**Question:** What if frustration detection is wrong (user not actually frustrated)?

**Options:**

- **Option A:** Ignore false positives (user can dismiss)
- **Option B:** Add "I'm fine" button that suppresses alerts for 1 hour
- **Option C:** Learn from dismissals (reduce sensitivity over time)

**Recommendation:** Option B — simple "I'm fine" button with temporary suppression.

**Decision needed by:** E4-S4 implementation

---

### 4. Flow State Celebration Frequency

**Question:** How often should flow state be celebrated?

**Options:**

- **Option A:** Once when entering flow state
- **Option B:** Every 15 minutes of sustained flow
- **Option C:** Only on exit from flow (summary of duration)

**Recommendation:** Option B — periodic reinforcement feels good without being annoying.

**Decision needed by:** E4-S4 implementation

---

## Risks & Mitigation

### Risk 1: Archive Directory Bloat

**Risk:** Archive directories may grow very large over time with frequent saves.

**Impact:** Low (storage is cheap, but could affect git repo size)

**Mitigation:**

- Configurable retention policy
- Archive cleanup command (manual or scheduled)
- Gitignore archive directories if desired
- Monitor archive sizes in metrics endpoint

**Monitoring:** Track archive file counts and total size per project

---

### Risk 2: Frustration Detection Inaccuracy

**Risk:** LLM may misinterpret tone, leading to false positives/negatives.

**Impact:** Medium (annoying alerts or missed warnings)

**Mitigation:**

- Conservative thresholds initially
- "I'm fine" dismiss button with cooldown
- Tune prompts based on real user data
- Make thresholds configurable
- Allow users to disable feature

**Monitoring:** Track dismiss rate, alert frequency, user feedback

---

### Risk 3: Wellness Feature Feeling Invasive

**Risk:** Users may feel monitored/judged by emotional analysis.

**Impact:** Medium (users disable feature, defeating purpose)

**Mitigation:**

- Clear opt-in/opt-out in settings
- Gentle, playful tone (not clinical)
- Framed as self-care tool, not surveillance
- All data local (not sent anywhere)
- Transparent about what's being analysed

**Monitoring:** Track feature enable/disable rates

---

### Risk 4: Metrics Performance Impact

**Risk:** Metrics calculations may slow down dashboard or database.

**Impact:** Low (deferred calculations, small data volume)

**Mitigation:**

- Periodic aggregation (not real-time calculation)
- Database indexes on time columns
- Retention policy limits data volume
- Cache computed metrics

**Monitoring:** Track aggregation job duration, query times

---

### Risk 5: Alert Fatigue

**Risk:** Too many alerts may cause users to ignore or disable them.

**Impact:** Medium (defeats purpose of wellness feature)

**Mitigation:**

- Alert cooldown (10 minutes minimum between alerts)
- Escalation only (don't alert on every yellow)
- "I'm fine" suppression option
- Daily alert limit (configurable)
- Focus on gentle tone, not urgency

**Monitoring:** Track alerts per day, dismiss rate, disable rate

---

## Success Metrics

From Epic 4 Acceptance Criteria:

### Test Case 1: Artifact Archiving

**Setup:** Edit waypoint, generate progress_summary, export brain_reboot.

**Success:**

- ✅ Edit waypoint → previous version archived with timestamp
- ✅ Generate progress_summary → previous version archived
- ✅ Export brain_reboot → previous version archived
- ✅ Archive directory created automatically
- ✅ API lists all archived versions
- ✅ API can retrieve specific archived version

---

### Test Case 2: Project Controls

**Setup:** Project with active inference calls.

**Success:**

- ✅ Click pause → inference calls stop
- ✅ File watching, hooks, dashboard continue
- ✅ Paused indicator visible on project
- ✅ Click resume → inference calls resume
- ✅ Pause state persists across server restart
- ✅ API can get/set project settings

---

### Test Case 3: Activity Monitoring

**Setup:** Active agents generating turns.

**Success:**

- ✅ Turn rate displayed per agent
- ✅ Average turn time displayed per agent
- ✅ Project-level metrics aggregate correctly
- ✅ Overall metrics aggregate correctly
- ✅ Time-series chart shows turn history
- ✅ Metrics API returns data
- ✅ Old data pruned after 30 days

---

### Test Case 4: Headspace Monitoring

**Setup:** User generating turns with varying frustration levels.

**Success:**

- ✅ User turns have frustration score extracted
- ✅ Traffic light indicator visible at dashboard top
- ✅ Green when frustration low (0-3)
- ✅ Yellow when frustration moderate (4-6)
- ✅ Red when frustration high (7-10)
- ✅ Indicator becomes prominent as frustration rises
- ✅ Gentle alert appears on sustained high frustration
- ✅ Alert message is playful, not preachy
- ✅ Alert dismissable with "I'm fine" button
- ✅ Flow state detected (high throughput + low frustration)
- ✅ Flow message displayed

---

### Test Case 5: End-to-End Epic 4 Flow

**Setup:** Fresh Epic 4 deployment with Epic 3 complete.

**Success:**

- ✅ Save waypoint → previous archived
- ✅ Pause project → inference stops
- ✅ Activity metrics displayed on dashboard
- ✅ Generate turns → frustration tracked
- ✅ Frustration rises → traffic light changes
- ✅ Sustained frustration → gentle alert
- ✅ Good flow → positive reinforcement
- ✅ Time-series shows productivity patterns

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order:

### Phase 1: Archive System (Week 1)

1. **archive-system** (`docs/prds/core/e4-s1-archive-system-prd.md`) — Archive service, retention, API

**Rationale:** Foundational file management that other features may use.

---

### Phase 2: Project Controls (Week 1-2)

2. **project-controls** (`docs/prds/core/e4-s2-project-controls-prd.md`) — Pause/resume inference, settings

**Rationale:** Establishes project-level settings pattern, integrates with inference service.

---

### Phase 3: Activity Monitoring (Week 2-3)

3. **activity-monitoring** (`docs/prds/core/e4-s3-activity-monitoring-prd.md`) — Turn metrics, rollups, charts

**Rationale:** Builds metrics infrastructure that E4-S4 will use for flow detection.

---

### Phase 4: Headspace Monitoring (Week 3-4)

4. **headspace-monitoring** (`docs/prds/core/e4-s4-headspace-monitoring-prd.md`) — Frustration, flow, alerts

**Rationale:** Capstone feature, depends on metrics infrastructure from E4-S3.

---

## Document History

| Version | Date       | Author          | Changes                                         |
| ------- | ---------- | --------------- | ----------------------------------------------- |
| 1.0     | 2026-01-30 | PM Agent (John) | Initial detailed roadmap for Epic 4 (4 sprints) |

---

**End of Epic 4 Detailed Roadmap**
