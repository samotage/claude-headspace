---
validation:
  status: valid
  validated_at: '2026-02-02T18:06:24+11:00'
---

## Product Requirements Document (PRD) — Activity Monitoring

**Project:** Claude Headspace
**Scope:** Turn-level activity metrics with time-series storage, aggregation, and visualization
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft
**Epic:** 4 | **Sprint:** 3

---

## Executive Summary

Claude Headspace currently provides real-time status and AI-generated summaries for active Claude Code agents, but lacks quantitative visibility into agent productivity patterns. Operators managing multiple concurrent agents across projects cannot see how active each agent is, how quickly turns are being processed, or how workload distributes over time.

Activity Monitoring introduces turn rate and average turn time metrics at the agent, project, and system-wide levels, backed by time-series storage for historical trend analysis. Metrics are periodically aggregated into hourly buckets, retained for 30 days, and displayed on a dedicated Activity page with interactive charts and toggle-able time windows (day, week, month).

This sprint also establishes the foundational metrics infrastructure that E4-S4 (Headspace Monitoring) depends on for flow state detection, frustration scoring, and wellness alerts.

---

## 1. Context & Purpose

### 1.1 Context

The dashboard shows agent state (idle, processing, awaiting input) and priority scores, but provides no quantitative activity data. Operators cannot answer questions like "How many turns has this agent processed in the last hour?" or "Which project has the most activity this week?" without manually inspecting turn logs.

Activity Monitoring fills this gap by computing and storing structured metrics derived from existing Turn, Agent, and Project data. This builds on the turn data flowing through Epic 1's core models and Epic 3's intelligence layer.

### 1.2 Target User

Operators (developers/team leads) who manage multiple concurrent Claude Code agents across projects and need quantitative insight into agent productivity and workload distribution.

### 1.3 Success Moment

An operator opens the Activity page and immediately sees turn rates and average turn times for each agent, with a time-series chart showing activity trends over the past week — enabling them to identify idle agents, spot productivity patterns, and understand workload distribution without inspecting raw logs.

---

## 2. Scope

### 2.1 In Scope

- Turn rate calculation per agent (turns per hour)
- Average turn time per agent (time between consecutive turns)
- Rollup to project level (aggregate metrics across all agents in a project)
- Rollup to overall level (aggregate metrics across all projects)
- Time-series storage at hourly granularity for historical trend analysis
- Automatic periodic metric aggregation at regular intervals
- 30-day data retention with automatic pruning of older records
- Dedicated "Activity" page accessible from main navigation menu
- Agent-level, project-level, and overall metrics display panels
- Interactive time-series chart with day/week/month view toggle
- Hover tooltips on chart showing exact values and time period
- Graceful empty states when no activity data exists
- Metrics API endpoints for agent, project, and overall levels (current and historical)
- Database migration for time-series metrics storage

### 2.2 Out of Scope

- Flow state detection, frustration scoring, and wellness alerts (E4-S4)
- Productivity score calculation incorporating frustration weighting (E4-S4)
- Real-time per-turn metric updates (periodic aggregation only; page reload for latest data)
- Auto-updating charts via SSE (charts update on page reload)
- CSV/JSON export of metrics data
- Alerting or notifications based on metric thresholds
- Dedicated time-series database (PostgreSQL is sufficient)
- Agent-to-agent or project-to-project comparison views
- Inline metrics on the existing dashboard agent cards

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Turn rate (turns per hour) is displayed per agent on the Activity page
2. Average turn time is displayed per agent on the Activity page
3. Project-level metrics correctly aggregate from all agents within the project
4. Overall metrics correctly aggregate from all projects
5. Time-series chart displays historical turn data with day, week, and month view toggles
6. Hovering on chart data points shows exact metric values and the time period they represent
7. Metrics API endpoints return both current snapshot and historical time-series data
8. Metric aggregation runs automatically at regular intervals without manual intervention
9. Data older than 30 days is automatically pruned

### 3.2 Non-Functional Success Criteria

1. No measurable performance degradation to the existing dashboard when aggregation runs
2. Activity page loads within acceptable response times with 30 days of hourly data
3. Empty states display gracefully when agents, projects, or the system have no activity data yet

---

## 4. Functional Requirements (FRs)

### Metrics Calculation

**FR1:** The system calculates turn rate for each active agent, expressed as turns per hour, derived from Turn records within the aggregation window.

**FR2:** The system calculates average turn time for each active agent, defined as the mean elapsed time between consecutive turns within the aggregation window.

**FR3:** The system aggregates agent-level metrics to the project level by combining metrics from all agents belonging to that project, including a count of active agents in the period.

**FR4:** The system aggregates project-level metrics to the overall (system-wide) level by combining metrics from all projects, including a count of active agents across the system.

### Time-Series Storage

**FR5:** Metrics are stored at hourly bucket granularity, enabling time-series queries for charting and historical analysis.

**FR6:** Each stored metric record is scoped to exactly one of: a specific agent, a specific project, or overall (system-wide).

**FR7:** The system automatically aggregates and stores new metric records at regular intervals (recommended: every 5 minutes).

**FR8:** The system automatically prunes metric records older than 30 days.

### Activity Page

**FR9:** A dedicated "Activity" page is accessible from the main navigation menu, labelled "Activity."

**FR10:** The Activity page displays current metrics (turn rate, average turn time) for each agent, grouped by project.

**FR11:** The Activity page displays aggregated metrics at the project level and overall level.

**FR12:** The Activity page includes a time-series chart showing turn activity over time.

**FR13:** The chart supports day, week, and month view toggles to control the displayed time window.

**FR14:** Hovering over chart data points displays a tooltip with the exact metric value and the time period it represents.

**FR15:** When no activity data exists for an agent, project, or overall, the page displays a clear empty state message (e.g., "No activity data yet").

### API

**FR16:** An API endpoint returns current and historical metrics for a specific agent.

**FR17:** An API endpoint returns current and historical aggregated metrics for a specific project.

**FR18:** An API endpoint returns current and historical system-wide aggregated metrics.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Metric aggregation must not block or degrade the responsiveness of the existing dashboard or API endpoints.

**NFR2:** The Activity page must render within acceptable response times when displaying up to 30 days of hourly-granularity data.

**NFR3:** The retention pruning process must handle large volumes of expired records without locking tables or degrading query performance.

---

## 6. UI Overview

### 6.1 Activity Page Layout

The Activity page is a new top-level page accessible from the main navigation menu. It contains:

1. **Overall Summary Panel** — System-wide turn rate, average turn time, and total active agent count displayed at the top.

2. **Time-Series Chart** — A line or bar chart showing turn count over time. Toggle buttons for day/week/month view. Hover tooltips show exact values and the time bucket they represent. Displays "No activity data yet" when empty.

3. **Project Sections** — Below the chart, metrics grouped by project. Each project section shows:
   - Project name and aggregated metrics (turn rate, avg turn time, active agent count)
   - Per-agent rows within the project showing individual turn rate and average turn time

### 6.2 Navigation

A new "Activity" item is added to the main navigation menu, positioned logically among existing items (Dashboard, Help, etc.).

---

## 7. Technical Context (Implementation Guidance)

*This section provides technical recommendations for implementers. These are not hard requirements — the implementation may deviate if better approaches are identified.*

### 7.1 Recommended Data Model

```python
class ActivityMetric(Base):
    __tablename__ = "activity_metrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    bucket_start: Mapped[datetime]  # Start of hourly time bucket

    # Scope (exactly one of these set)
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    is_overall: Mapped[bool] = mapped_column(default=False)

    # Metrics
    turn_count: Mapped[int]
    avg_turn_time_seconds: Mapped[float | None]
    active_agents: Mapped[int | None]  # For project/overall scope only
```

### 7.2 Recommended API Endpoints

- `GET /api/metrics/agents/<id>` — metrics for a specific agent
- `GET /api/metrics/projects/<id>` — aggregated metrics for a project
- `GET /api/metrics/overall` — system-wide aggregated metrics

### 7.3 Metrics Formulas

| Metric | Formula | Applicable Levels |
|--------|---------|-------------------|
| Turn Rate | `turn_count / hours_active` | Agent, Project, Overall |
| Avg Turn Time | `sum(turn_durations) / turn_count` | Agent, Project, Overall |
| Active Agents | Count of agents with turns in period | Project, Overall |

### 7.4 Technical Recommendations

- **Aggregation interval:** Every 5 minutes (follow AgentReaper threading pattern)
- **Chart library:** Chart.js via CDN (matches existing vanilla JS, no build step)
- **Retention pruning:** Run as part of the periodic aggregation job
- **Indexes:** Composite indexes on `(agent_id, bucket_start)`, `(project_id, bucket_start)`, and `(is_overall, bucket_start)` for efficient time-range queries

### 7.5 Integration Points

- Uses Epic 1 Turn model (`timestamp`, `actor`, `command_id`) for raw turn data
- Uses Epic 1 Agent and Project models for scope relationships
- Follows background job pattern from AgentReaper service
- E4-S2 split into E4-S2a (backend) and E4-S2b (frontend); no direct conflict but shares Project model
- E4-S4 (Headspace Monitoring) will build on this metrics infrastructure for flow detection and wellness scoring

### 7.6 Dependencies

- Epic 1 (core models: Turn, Agent, Project)
- Epic 3 (turn data flowing through hook lifecycle)
- E4-S1 (archive system — establishes file management patterns)
- E4-S2a/E4-S2b (project controls — project-level settings established)
