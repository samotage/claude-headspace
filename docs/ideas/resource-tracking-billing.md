# Idea: Resource Tracking & Project Billing

**Status:** Idea — Not yet assigned to an epic  
**Author:** PM Agent (John)  
**Date:** 2026-01-30  
**Priority:** Future consideration (post-Epic 4)

---

## 1. Problem Statement

Claude Headspace currently tracks agent activity and productivity metrics, but lacks visibility into:

- **Agent utilization per project** — How many agents worked on a project each day? Agents come and go throughout a work session.
- **Time investment per project** — How many hours were spent on a project? What was the overall time span vs actual active work time?
- **Project costing** — Foundation for understanding what resources a project consumed, enabling future billing/invoicing capabilities.

### Why This Matters

When working across multiple projects with multiple agents, you need to answer questions like:

- "How much time did I spend on Project X this week?"
- "What was my peak agent usage on Tuesday?"
- "Can I bill a client for 4 hours of AI-assisted development?"

The current Activity Monitoring (E4-S3) focuses on productivity patterns (turn rate, turn time). This idea focuses on **resource consumption** — a complementary but distinct concern.

---

## 2. Proposed Features

### 2.1 Agent Tracking (per project, per day)

Track the number of agents active on each project, each day.

**Metrics:**

| Metric          | Description                        | Example      |
| --------------- | ---------------------------------- | ------------ |
| Agent Count     | Distinct agents active that day    | 3 agents     |
| Agent Sessions  | Total sessions (includes restarts) | 5 sessions   |
| Peak Concurrent | Max agents running simultaneously  | 2 concurrent |

**Visualization:**

- Bar chart: Agent count per day (last 7/14/30 days)
- Line chart: Agent count over time (hourly granularity)
- Project comparison: Side-by-side agent usage across projects

### 2.2 Time Tracking (per project, per day)

Track time investment in each project, distinguishing between active work and total time span.

**Metrics:**

| Metric      | Description                          | Example           |
| ----------- | ------------------------------------ | ----------------- |
| Active Time | Sum of agent activity periods        | 4 hours           |
| Time Span   | First agent start → last agent close | 9am-6pm (9 hours) |
| Utilization | Active time / Time span              | 44%               |

**Context this provides:**

> "Worked on Project X from 9am-6pm (9 hour span), with 4 hours of active agent work."

This distinction is important because:

- **Time span** shows when you were "on" the project
- **Active time** shows actual productive work
- **Utilization** shows how focused vs fragmented the work was

### 2.3 Simple Billing Report

Generate project summaries for billing or time tracking purposes.

**Report Contents:**

- Project name and period (daily/weekly/monthly)
- Total agent count and sessions
- Total active hours and time span
- Turn count (from E4-S3)
- Exportable format (CSV, JSON)

**Example Report:**

```
Project: claude-headspace
Period: 2026-01-27 to 2026-01-30

Days Worked: 4
Total Agent Sessions: 12
Total Active Hours: 18.5h
Total Time Span: 32h
Average Utilization: 58%
Total Turns: 847

Daily Breakdown:
- Mon 27: 3 agents, 5.2h active, 9am-5pm span
- Tue 28: 4 agents, 6.1h active, 8am-7pm span
- Wed 29: 2 agents, 3.8h active, 10am-3pm span
- Thu 30: 3 agents, 3.4h active, 9am-1pm span
```

**UI Integration:**

- New "Reports" tab or panel in dashboard
- Date range selector
- Project filter
- Export button (CSV/JSON)

---

## 3. Future Considerations (Out of Scope Initially)

The following features are valuable but deferred to keep initial scope manageable:

### 3.1 Token Usage Tracking

- Track tokens consumed per turn (requires OpenRouter API integration)
- Store input/output token counts on Turn model
- Aggregate token usage by agent, project, day

### 3.2 Cost Quantification

- Map token usage to actual costs (model-specific pricing)
- Track inference costs per project
- Rate card configuration (cost per hour, cost per token)

### 3.3 Full Invoicing

- Generate invoice documents
- Client/project billing rates
- Tax handling
- Payment tracking

### 3.4 Budget Alerts

- Set budget limits per project
- Alert when approaching/exceeding budget
- Automatic pause when budget exceeded

---

## 4. Data Model Sketch

```python
from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

class DailyProjectMetric(Base):
    """Aggregated daily metrics for a project."""
    __tablename__ = "daily_project_metrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    date: Mapped[date]  # The calendar day

    # Agent tracking
    agent_count: Mapped[int]        # Distinct agents active that day
    agent_sessions: Mapped[int]     # Total agent sessions (includes restarts)
    peak_concurrent: Mapped[int]    # Max agents running at same time

    # Time tracking
    first_activity_at: Mapped[datetime]  # First agent started
    last_activity_at: Mapped[datetime]   # Last agent closed
    active_minutes: Mapped[int]          # Sum of agent active periods

    # Turn tracking (complements E4-S3)
    turn_count: Mapped[int]

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="daily_metrics")


# Future: Token tracking extension
class DailyTokenUsage(Base):
    """Token usage per project per day (future)."""
    __tablename__ = "daily_token_usage"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    date: Mapped[date]

    # Token counts
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    total_tokens: Mapped[int]

    # Cost (if known)
    estimated_cost_usd: Mapped[float | None]
```

---

## 5. Integration Points

### Dependencies

| Dependency                 | Why Needed                                   |
| -------------------------- | -------------------------------------------- |
| Epic 1: Agent model        | Agent lifecycle tracking (start/stop times)  |
| Epic 1: Project model      | Project association                          |
| E4-S3: Activity Monitoring | Metrics infrastructure, aggregation patterns |
| E3: Turn model             | Turn counts per project                      |

### Integration with Existing Systems

- **Dashboard:** New "Reports" panel alongside existing metrics
- **API:** New endpoints for report generation and data retrieval
- **SSE:** Real-time updates to daily metrics as activity occurs
- **Config:** Report settings (default period, export format preferences)

### Suggested API Endpoints

```
GET /api/reports/projects/<id>/daily?start=YYYY-MM-DD&end=YYYY-MM-DD
GET /api/reports/projects/<id>/summary?period=week|month
GET /api/reports/projects/<id>/export?format=csv|json&period=week
GET /api/reports/overall/summary?period=week|month
```

---

## 6. Open Questions

1. **Aggregation timing:** Real-time updates or end-of-day batch calculation?
   - Recommend: Incremental updates with end-of-day finalization

2. **Active time calculation:** How to define "active"?
   - Option A: Any turn activity within time window
   - Option B: Agent in processing/awaiting_input state
   - Recommend: Option A (simpler, based on turn timestamps)

3. **Multi-project agents:** How to handle agents that work across projects?
   - Current system assumes 1 agent = 1 project
   - If this changes, need to apportion time

4. **Historical backfill:** Should we backfill metrics from existing turn data?
   - Recommend: Yes, on feature launch, calculate from existing turns

---

## 7. Success Criteria (When Implemented)

- [ ] Daily agent count tracked per project
- [ ] Active time and time span calculated per day
- [ ] Simple report viewable in dashboard
- [ ] Report exportable as CSV/JSON
- [ ] Metrics aggregated automatically (no manual trigger)
- [ ] 30-day retention of daily metrics (configurable)

---

## 8. Recommended Roadmap Placement

This feature could be implemented as:

| Option | Placement       | Rationale                                |
| ------ | --------------- | ---------------------------------------- |
| A      | E4-S5           | Natural extension of Activity Monitoring |
| B      | Epic 5 Sprint 1 | Distinct concern, starts new epic        |
| C      | Standalone PRD  | One-off feature outside epic structure   |

**Recommendation:** Option A (E4-S5) if scope stays limited to data collection and simple reports. Option B if billing/invoicing becomes a larger initiative.

---

## Document History

| Version | Date       | Author          | Changes              |
| ------- | ---------- | --------------- | -------------------- |
| 0.1     | 2026-01-30 | PM Agent (John) | Initial idea capture |
