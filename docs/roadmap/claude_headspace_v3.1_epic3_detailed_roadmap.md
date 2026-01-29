# Epic 3 Detailed Roadmap: Intelligence Layer

**Project:** Claude Headspace v3.1  
**Epic:** Epic 3 — Intelligence Layer  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-01-29

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 3 implementation. It breaks Epic 3 into 5 logical sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem.

**Epic 3 Goal:** Add LLM-powered summarisation and prioritisation at turn, task, and project levels. Generate brain_reboot artifacts from git history for rapid context restoration.

**Epic 3 Value Proposition:**

- **Turn Summarisation** — Real-time AI summaries of each turn for dashboard display
- **Task Summarisation** — AI-generated summaries when tasks complete
- **Priority Scoring** — Cross-project AI ranking aligned to current objective
- **Progress Summary** — LLM-generated narrative from git commit history
- **Brain Reboot** — Combined waypoint + progress_summary for rapid mental context restoration

**Success Criteria:**

- Agent turns show AI-generated summaries in dashboard (real-time)
- Completed tasks have AI summaries
- Dashboard shows AI-ranked priority scores per agent
- Project progress_summary generated from git commits
- Brain reboot combines progress_summary + waypoint for context restoration

**Architectural Foundation:** Builds on Epic 1's Flask application, database, SSE system, Task/Turn models, and dashboard UI. Epic 3 adds the intelligence layer via OpenRouter API integration.

**Dependency:** Epic 1 must be complete before Epic 3 begins.

---

## Epic 3 Story Mapping

| Story ID | Story Name                                       | Subsystem                 | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------------ | ------------------------- | ------------- | ------ | -------- |
| E3-S1    | OpenRouter API integration and inference service | `openrouter-integration`  | inference/    | 1      | P1       |
| E3-S2    | Turn and task summarisation                      | `turn-task-summarisation` | inference/    | 2      | P1       |
| E3-S3    | Cross-project priority scoring                   | `priority-scoring`        | inference/    | 3      | P1       |
| E3-S4    | Git analyzer and progress summary generation     | `git-analyzer`            | inference/    | 4      | P1       |
| E3-S5    | Brain reboot generation                          | `brain-reboot`            | inference/    | 5      | P1       |

---

## Sprint Breakdown

### Sprint 1: OpenRouter Integration & Inference Service (E3-S1)

**Goal:** Establish the LLM infrastructure with OpenRouter API integration, inference service, and InferenceCall logging.

**Duration:** 1-2 weeks  
**Dependencies:** Epic 1 complete (Flask app, database, models)

**Deliverables:**

- OpenRouter API client with retry/exponential backoff
- Inference service with model selection by level (Haiku vs Sonnet)
- InferenceCall SQLAlchemy model for logging all LLM calls
- Database migration for InferenceCall table
- Rate limiting (calls per minute, tokens per minute)
- Cost tracking (input/output tokens per call)
- Config.yaml schema for OpenRouter settings
- API key management (environment variable or config)
- Error handling for API failures (timeouts, rate limits, server errors)
- Health check endpoint for LLM connectivity
- API endpoints: GET `/api/inference/status`, GET `/api/inference/usage`

**Subsystem Requiring PRD:**

1. `openrouter-integration` — API client, inference service, InferenceCall logging, rate limiting

**PRD Location:** `docs/prds/inference/e3-s1-openrouter-integration-prd.md`

**Stories:**

- E3-S1: OpenRouter API integration and inference service

**Technical Decisions Required:**

- API client library: httpx vs requests — **recommend httpx for async support**
- Rate limiting strategy: token bucket vs sliding window — **recommend token bucket**
- API key storage: env var vs config.yaml — **recommend env var with config fallback**
- Retry strategy: exponential backoff with jitter — **decided**
- Model identifiers: OpenRouter format (e.g., `anthropic/claude-3-haiku`)

**Risks:**

- OpenRouter API downtime affecting all inference features
- Rate limit exhaustion during high activity
- API costs exceeding budget
- Latency affecting real-time summarisation

**Acceptance Criteria:**

- Inference service can call OpenRouter API successfully
- Model selection works by level (turn/task → Haiku, project/objective → Sonnet)
- InferenceCall records logged to Postgres with all metadata
- Rate limiting enforced (configurable calls/tokens per minute)
- API errors handled gracefully (retry with backoff, fallback behavior)
- Cost tracking visible via API endpoint
- Config loaded from config.yaml with env var override for API key

---

### Sprint 2: Turn & Task Summarisation (E3-S2)

**Goal:** Real-time turn summarisation and task completion summaries for dashboard display.

**Duration:** 1-2 weeks  
**Dependencies:** E3-S1 complete (inference service available)

**Deliverables:**

- Turn summarisation service (Haiku, triggered on turn arrival)
- Task summarisation service (Haiku, triggered on task completion)
- Summary caching by content hash (avoid re-summarising identical content)
- Dashboard integration (display summaries on agent cards)
- Turn summary displayed inline on agent card
- Task summary displayed on task completion
- Prompt templates for turn and task summarisation
- Async processing (don't block SSE updates on inference)
- Summary field additions to Turn and Task models
- Database migration for summary fields
- API endpoints: POST `/api/summarise/turn/<id>`, POST `/api/summarise/task/<id>`

**Subsystem Requiring PRD:**

2. `turn-task-summarisation` — Turn/task summarisers, caching, dashboard integration

**PRD Location:** `docs/prds/inference/e3-s2-turn-task-summarisation-prd.md`

**Stories:**

- E3-S2: Turn and task summarisation

**Technical Decisions Required:**

- Summarisation trigger: immediate vs batched — **decided: immediate (real-time)**
- Cache storage: in-memory vs database — **recommend database for persistence**
- Cache key: content hash (SHA256 of turn.text)
- Summary length: concise (1-2 sentences) — **decided**
- Async implementation: background thread vs task queue — **recommend background thread for simplicity**

**Prompt Templates:**

```
Turn Summary Prompt:
Summarise this turn in 1-2 concise sentences focusing on what action was taken or requested:
Turn: {turn.text}
Actor: {turn.actor}
Intent: {turn.intent}

Task Summary Prompt:
Summarise the outcome of this completed task in 2-3 sentences:
Task started: {task.started_at}
Task completed: {task.completed_at}
Turns: {turn_count}
Final outcome: {final_turn.text}
```

**Risks:**

- Real-time summarisation causing latency in dashboard updates
- High API costs with many active turns
- Summary quality inconsistent across different turn types
- Cache invalidation issues

**Acceptance Criteria:**

- Turn arrives → summary generated within 2 seconds → displayed on dashboard
- Task completes → summary generated → displayed on agent card
- Identical turns return cached summary (no duplicate API calls)
- Dashboard shows turn summaries inline
- Task summaries visible in task history
- Async processing doesn't block SSE updates
- Summary fields persisted to database

---

### Sprint 3: Priority Scoring Service (E3-S3)

**Goal:** AI-driven cross-project priority scoring aligned to current objective.

**Duration:** 1-2 weeks  
**Dependencies:** E3-S2 complete (task summaries provide context)

**Deliverables:**

- Priority scoring service (Sonnet for intelligence)
- Cross-project batch scoring (score all agents in single call for efficiency)
- Objective alignment calculation
- Score factors: objective relevance, agent state, task duration, project context
- Priority score (0-100) and reason stored on Agent model
- Dashboard integration (priority badges, recommended next panel)
- Scoring triggers: task state change, objective change
- Re-score on objective update (all agents)
- Priority field additions to Agent model
- Database migration for priority fields
- Prompt template for priority scoring
- API endpoints: POST `/api/priority/score`, GET `/api/priority/rankings`

**Subsystem Requiring PRD:**

3. `priority-scoring` — Priority scorer, objective alignment, dashboard integration

**PRD Location:** `docs/prds/inference/e3-s3-priority-scoring-prd.md`

**Stories:**

- E3-S3: Cross-project priority scoring

**Technical Decisions Required:**

- Scoring frequency: on every state change vs debounced — **recommend debounced (5 second delay)**
- Batch vs individual scoring — **recommend batch for efficiency**
- Score range: 0-100 — **decided**
- Re-score trigger: objective change re-scores all agents — **decided**
- State-based modifiers: awaiting_input = +20, processing = +10, idle = 0

**Scoring Factors:**

| Factor              | Weight | Description                                           |
| ------------------- | ------ | ----------------------------------------------------- |
| Objective alignment | 40%    | How well does this agent's work align with objective? |
| Agent state         | 25%    | awaiting_input > processing > idle                    |
| Task duration       | 15%    | Longer tasks may need attention                       |
| Project context     | 10%    | Project waypoint priorities                           |
| Recent activity     | 10%    | Recently active vs stale                              |

**Prompt Template:**

```
Priority Scoring Prompt:
You are prioritising agents working across multiple projects.

Current Objective: {objective.text}
Constraints: {objective.constraints}

Agents to score:
{for agent in agents}
- Agent: {agent.session_uuid}
  Project: {agent.project.name}
  State: {agent.state}
  Current Task: {agent.current_task.summary or "None"}
  Task Duration: {task_duration}
  Waypoint Next Up: {agent.project.waypoint.next_up}
{endfor}

Score each agent 0-100 based on priority for user attention.
Return JSON: [{"agent_id": "...", "score": N, "reason": "..."}]
```

**Risks:**

- Batch scoring latency for many agents
- Objective changes causing scoring storms
- Score quality dependent on task summaries
- Users disagreeing with AI prioritisation

**Acceptance Criteria:**

- All agents have priority scores (0-100)
- Recommended next panel shows highest priority agent
- Priority badges displayed on agent cards
- Objective change triggers re-scoring of all agents
- Task state change triggers score update for that agent
- Priority reasons visible on hover/expand
- Scores persist across page reloads

---

### Sprint 4: Git Analyzer & Progress Summary (E3-S4)

**Goal:** Generate progress_summary from git commit history using LLM analysis.

**Duration:** 1-2 weeks  
**Dependencies:** E3-S1 complete (inference service available)

**Deliverables:**

- Git analyzer service (extract commits, diffs, file changes)
- Progress summary generator (Sonnet for narrative quality)
- Configurable commit scope:
  - Since last generation (default)
  - Last N commits
  - Time-based (last N days)
- Write progress_summary.md to target project (`docs/brain_reboot/`)
- Archive previous version with timestamp (`archive/progress_summary_YYYY-MM-DD.md`)
- Create directory structure if missing
- Dashboard UI: "Generate Progress Summary" button per project
- Progress summary display in project panel
- Trigger options: manual via dashboard, or on significant commit activity
- API endpoints: POST `/api/projects/<id>/progress-summary`, GET `/api/projects/<id>/progress-summary`

**Subsystem Requiring PRD:**

4. `git-analyzer` — Git analysis, progress summary generation, archiving

**PRD Location:** `docs/prds/inference/e3-s4-git-analyzer-prd.md`

**Stories:**

- E3-S4: Git analyzer and progress summary generation

**Technical Decisions Required:**

- Commit scope default: since last generation — **decided**
- Significant commit threshold: 10 commits since last summary — **recommend**
- Diff inclusion: include file-level diffs or just commit messages — **recommend commit messages + file list**
- Archive retention: keep all vs last N versions — **recommend keep all**
- Auto-trigger: optional, default off — **recommend manual first**

**Git Analysis Output:**

```python
class GitAnalysis:
    commits: list[Commit]  # Recent commits
    files_changed: list[str]  # Unique files modified
    authors: list[str]  # Contributors
    date_range: tuple[datetime, datetime]
    commit_count: int

class Commit:
    hash: str
    message: str
    author: str
    timestamp: datetime
    files: list[str]
```

**Prompt Template:**

```
Progress Summary Prompt:
Generate a narrative progress summary for this project based on recent git activity.

Project: {project.name}
Date Range: {start_date} to {end_date}
Commit Count: {commit_count}

Recent Commits:
{for commit in commits}
- {commit.hash[:8]}: {commit.message} ({commit.author}, {commit.timestamp})
{endfor}

Files Changed: {files_changed}

Write a 3-5 paragraph narrative summarising:
1. What major work was completed
2. What features or fixes were implemented
3. Current state of the project
4. Any patterns or themes in the work

Write in past tense, focus on accomplishments.
```

**Risks:**

- Large git histories causing long inference times
- Write permission errors to project directories
- Git commands failing (not a git repo, detached HEAD)
- Archive directory growing too large

**Acceptance Criteria:**

- Git analyzer extracts commits from project repo
- Progress summary generated from commit history (Sonnet)
- progress_summary.md written to `docs/brain_reboot/` in target project
- Previous version archived with timestamp
- Directory structure created if missing
- Dashboard shows "Generate Progress Summary" button
- Generated summary viewable in dashboard
- Configurable commit scope works (since_last, last_n, time_based)

---

### Sprint 5: Brain Reboot Generation (E3-S5)

**Goal:** Generate brain_reboot by combining waypoint + progress_summary for rapid context restoration.

**Duration:** 1 week  
**Dependencies:** E3-S4 complete (progress_summary available)

**Deliverables:**

- Brain reboot generator service (combine waypoint + progress_summary)
- Dynamic generation on demand (not stored by default)
- Dashboard modal to view brain reboot
- Export option (save to `docs/brain_reboot/brain_reboot.md`)
- Staleness detection (projects without recent activity)
- Stale project indicator on dashboard
- Context restoration prompt template
- Copy to clipboard functionality
- API endpoints: POST `/api/projects/<id>/brain-reboot`, GET `/api/projects/<id>/brain-reboot`

**Subsystem Requiring PRD:**

5. `brain-reboot` — Brain reboot generator, staleness detection, dashboard modal

**PRD Location:** `docs/prds/inference/e3-s5-brain-reboot-prd.md`

**Stories:**

- E3-S5: Brain reboot generation

**Technical Decisions Required:**

- Storage: dynamic generation vs stored file — **decided: dynamic, optional export**
- Staleness threshold: days since last agent activity — **recommend 7 days configurable**
- LLM enhancement: use LLM to synthesise or just concatenate — **recommend concatenate with formatting**
- Export format: markdown file in project repo — **decided**

**Brain Reboot Structure:**

```markdown
# Brain Reboot: {project.name}

Generated: {timestamp}

## Progress Summary

{progress_summary content}

## Waypoint (Path Ahead)

### Next Up

{waypoint.next_up}

### Upcoming

{waypoint.upcoming}

### Later

{waypoint.later}

### Not Now

{waypoint.not_now}

---

_Use this document to quickly restore context when returning to this project._
```

**Staleness Detection:**

| Days Since Activity | Status | Indicator                  |
| ------------------- | ------ | -------------------------- |
| 0-3 days            | Fresh  | Green                      |
| 4-7 days            | Aging  | Yellow                     |
| 8+ days             | Stale  | Red + "Needs Reboot" badge |

**Risks:**

- Missing waypoint or progress_summary files
- Staleness detection false positives (intentionally paused projects)
- Modal UX issues on mobile/small screens

**Acceptance Criteria:**

- Brain reboot combines waypoint + progress_summary
- Dashboard shows "Brain Reboot" button per project
- Modal displays brain reboot content
- Export saves to `docs/brain_reboot/brain_reboot.md`
- Copy to clipboard works
- Stale projects highlighted with indicator
- Staleness threshold configurable
- Missing files handled gracefully (show what's available)

---

## Subsystems Requiring OpenSpec PRDs

The following 5 subsystems need detailed PRDs created via OpenSpec. Each PRD will be generated as a separate change proposal and validated before implementation.

### PRD Directory Structure

```
docs/prds/
└── inference/                    # Intelligence layer components
    ├── e3-s1-openrouter-integration-prd.md
    ├── e3-s2-turn-task-summarisation-prd.md
    ├── e3-s3-priority-scoring-prd.md
    ├── e3-s4-git-analyzer-prd.md
    └── e3-s5-brain-reboot-prd.md
```

---

### 1. OpenRouter Integration

**Subsystem ID:** `openrouter-integration`  
**Sprint:** E3-S1  
**Priority:** P1  
**PRD Location:** `docs/prds/inference/e3-s1-openrouter-integration-prd.md`

**Scope:**

- OpenRouter API client with retry/backoff
- Inference service with model selection by level
- InferenceCall model and Postgres logging
- Rate limiting and cost tracking
- Config.yaml schema for OpenRouter settings
- API key management

**Key Requirements:**

- Must connect to OpenRouter API successfully
- Must select appropriate model by inference level
- Must log all inference calls to InferenceCall table
- Must enforce rate limits (calls per minute, tokens per minute)
- Must track costs (input/output tokens)
- Must handle API errors gracefully with retry
- Must support async calls for non-blocking operation

**OpenSpec Spec:** `openspec/specs/openrouter-integration/spec.md`

**Related Files:**

- `src/services/inference_service.py` (new)
- `src/services/openrouter_client.py` (new)
- `src/models/inference_call.py` (new)
- `migrations/versions/xxx_add_inference_call.py` (new)
- `config.yaml` (add openrouter section)

**Data Model Changes:**

```python
class InferenceCall(Base):
    __tablename__ = "inference_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    level: Mapped[str]  # turn, task, project, objective
    purpose: Mapped[str]  # turn_summary, task_summary, priority_score, etc.
    model: Mapped[str]  # anthropic/claude-3-haiku, etc.
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    input_hash: Mapped[str]  # SHA256 for caching
    result: Mapped[str]  # LLM output
    latency_ms: Mapped[int]

    # Optional foreign keys
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    turn_id: Mapped[UUID | None] = mapped_column(ForeignKey("turns.id"))
```

**Dependencies:** Epic 1 complete (Flask app, database)

**Acceptance Tests:**

- API client connects to OpenRouter
- Model selection by level works
- InferenceCall logged to database
- Rate limiting enforced
- Retry with backoff on failure
- Cost tracking accurate

---

### 2. Turn/Task Summarisation

**Subsystem ID:** `turn-task-summarisation`  
**Sprint:** E3-S2  
**Priority:** P1  
**PRD Location:** `docs/prds/inference/e3-s2-turn-task-summarisation-prd.md`

**Scope:**

- Turn summarisation service (Haiku, real-time)
- Task summarisation service (Haiku, on completion)
- Summary caching by content hash
- Dashboard integration
- Async processing
- Prompt engineering

**Key Requirements:**

- Must summarise turns in real-time as they arrive
- Must summarise tasks on completion
- Must cache summaries by content hash
- Must display summaries on dashboard agent cards
- Must not block SSE updates during inference
- Must use Haiku model for speed/cost efficiency

**OpenSpec Spec:** `openspec/specs/turn-task-summarisation/spec.md`

**Related Files:**

- `src/services/turn_summariser.py` (new)
- `src/services/task_summariser.py` (new)
- `src/models/turn.py` (add summary field)
- `src/models/task.py` (add summary field)
- `templates/partials/_agent_card.html` (update)

**Data Model Changes:**

```python
# Add to Turn model
class Turn(Base):
    ...
    summary: Mapped[str | None]  # Generated by turn summariser

# Add to Task model
class Task(Base):
    ...
    summary: Mapped[str | None]  # Generated on completion
```

**Dependencies:** E3-S1 complete (inference service)

**Acceptance Tests:**

- Turn arrives → summary generated < 2 seconds
- Task completes → summary generated
- Cached summaries returned instantly
- Dashboard shows turn summaries
- SSE updates not blocked

---

### 3. Priority Scoring

**Subsystem ID:** `priority-scoring`  
**Sprint:** E3-S3  
**Priority:** P1  
**PRD Location:** `docs/prds/inference/e3-s3-priority-scoring-prd.md`

**Scope:**

- Priority scoring service (Sonnet)
- Cross-project batch scoring
- Objective alignment calculation
- Dashboard integration (badges, recommended next)
- Scoring triggers (state change, objective change)

**Key Requirements:**

- Must score all agents 0-100 based on objective alignment
- Must provide priority reason for each score
- Must batch score for efficiency
- Must re-score on objective change
- Must update score on task state change
- Must use Sonnet model for intelligence

**OpenSpec Spec:** `openspec/specs/priority-scoring/spec.md`

**Related Files:**

- `src/services/priority_scorer.py` (new)
- `src/models/agent.py` (add priority fields)
- `templates/dashboard.html` (update recommended next)
- `templates/partials/_agent_card.html` (add priority badge)

**Data Model Changes:**

```python
# Add to Agent model
class Agent(Base):
    ...
    priority_score: Mapped[int | None]  # 0-100
    priority_reason: Mapped[str | None]  # Explanation from LLM
    priority_updated_at: Mapped[datetime | None]
```

**Dependencies:** E3-S2 complete (task summaries for context)

**Acceptance Tests:**

- All agents have priority scores
- Recommended next shows highest priority
- Priority badges displayed
- Objective change triggers re-score
- State change triggers score update

---

### 4. Git Analyzer

**Subsystem ID:** `git-analyzer`  
**Sprint:** E3-S4  
**Priority:** P1  
**PRD Location:** `docs/prds/inference/e3-s4-git-analyzer-prd.md`

**Scope:**

- Git analyzer service (commits, diffs, files)
- Progress summary generator (Sonnet)
- Configurable commit scope
- Write to target project repo
- Archive previous versions
- Dashboard UI integration

**Key Requirements:**

- Must extract commits from project git repo
- Must generate narrative progress summary
- Must support configurable commit scope (since_last, last_n, time_based)
- Must write to `docs/brain_reboot/progress_summary.md`
- Must archive previous version with timestamp
- Must create directory structure if missing
- Must handle git errors gracefully

**OpenSpec Spec:** `openspec/specs/git-analyzer/spec.md`

**Related Files:**

- `src/services/git_analyzer.py` (new)
- `src/services/progress_summary_generator.py` (new)
- `templates/partials/_project_panel.html` (add button)
- `src/routes/projects.py` (add endpoints)

**Data Model Changes:**

None (writes to external project files)

**Dependencies:** E3-S1 complete (inference service)

**Acceptance Tests:**

- Git commits extracted correctly
- Progress summary generated from commits
- File written to target project
- Previous version archived
- Directory created if missing
- Configurable scope works

---

### 5. Brain Reboot

**Subsystem ID:** `brain-reboot`  
**Sprint:** E3-S5  
**Priority:** P1  
**PRD Location:** `docs/prds/inference/e3-s5-brain-reboot-prd.md`

**Scope:**

- Brain reboot generator (waypoint + progress_summary)
- Dynamic generation on demand
- Dashboard modal
- Export option
- Staleness detection
- Copy to clipboard

**Key Requirements:**

- Must combine waypoint + progress_summary
- Must generate dynamically (not stored by default)
- Must display in dashboard modal
- Must support export to file
- Must detect stale projects
- Must handle missing files gracefully

**OpenSpec Spec:** `openspec/specs/brain-reboot/spec.md`

**Related Files:**

- `src/services/brain_reboot_generator.py` (new)
- `templates/partials/_brain_reboot_modal.html` (new)
- `templates/partials/_project_panel.html` (add button)
- `static/js/brain_reboot.js` (new)
- `src/routes/projects.py` (add endpoints)

**Data Model Changes:**

None (combines existing files)

**Dependencies:** E3-S4 complete (progress_summary available)

**Acceptance Tests:**

- Brain reboot combines waypoint + progress_summary
- Modal displays content correctly
- Export saves file to project
- Copy to clipboard works
- Stale projects highlighted
- Missing files handled gracefully

---

## Sprint Dependencies & Critical Path

```
[Epic 1 Complete]
       │
       ▼
   E3-S1 (OpenRouter Integration)
       │
       ├──▶ E3-S2 (Turn/Task Summarisation)
       │        │
       │        └──▶ E3-S3 (Priority Scoring)
       │
       └──▶ E3-S4 (Git Analyzer + Progress Summary)
                │
                └──▶ E3-S5 (Brain Reboot)
```

**Critical Path:** E3-S1 → E3-S2 → E3-S3

**Parallel Tracks:**

- E3-S4 (Git Analyzer) can run in parallel with E3-S2/E3-S3 after E3-S1
- E3-S5 (Brain Reboot) depends only on E3-S4, independent of E3-S2/E3-S3

**Recommended Sequence:**

1. E3-S1 (OpenRouter Integration) — foundational, blocks all other sprints
2. E3-S2 (Turn/Task Summarisation) — core intelligence feature
3. E3-S4 (Git Analyzer) — can start in parallel with E3-S3
4. E3-S3 (Priority Scoring) — needs task summaries from E3-S2
5. E3-S5 (Brain Reboot) — final sprint, needs progress_summary from E3-S4

**Total Duration:** 5-7 weeks

---

## Technical Decisions Made

### Decision 1: Model Selection by Level

**Decision:** Use Haiku for turn/task summarisation, Sonnet for project/objective level.

**Rationale:**

- Haiku is fast (~200ms) and cheap (~$0.00025/1K tokens)
- Turn summarisation is high-volume (many turns per session)
- Sonnet is smarter, better for nuanced prioritisation and narrative generation
- Project-level operations are less frequent, can afford slower/smarter model

**Impact:**

- Need model selection logic in inference service
- Config.yaml specifies model per level
- Cost tracking should distinguish by model

---

### Decision 2: Real-time Turn Summarisation

**Decision:** Summarise each turn as it arrives (not batched or lazy).

**Rationale:**

- Dashboard should show summaries immediately for UX
- Haiku is fast enough for real-time use
- Caching prevents duplicate API calls

**Impact:**

- Higher API call volume
- Need async processing to not block SSE
- Caching critical for cost control

---

### Decision 3: Batch Priority Scoring

**Decision:** Score all agents in a single LLM call for efficiency.

**Rationale:**

- Sonnet can handle complex multi-agent analysis in one call
- Reduces API calls and latency
- Cross-project comparison requires seeing all agents together

**Impact:**

- Prompt design must handle variable agent count
- JSON response parsing required
- May need chunking for very large agent counts (>20)

---

### Decision 4: Dynamic Brain Reboot

**Decision:** Generate brain_reboot dynamically on demand, optional export.

**Rationale:**

- Avoids stale cached files
- Always reflects current waypoint + progress_summary
- Export option for those who want persistent files
- Reduces file management complexity

**Impact:**

- Slightly slower (combines files on each request)
- No version history of brain_reboot itself
- Modal UI required for display

---

### Decision 5: Progress Summary from Commits

**Decision:** Generate progress_summary from git commit history, configurable scope.

**Rationale:**

- Git is source of truth for what was done
- Commit messages contain intent
- File changes show scope of work
- Configurable scope handles different workflows

**Impact:**

- Need git access to all monitored projects
- May miss work not committed
- Commit message quality affects summary quality

---

## Open Questions

### 1. Inference Cost Budget

**Question:** Should there be a configurable cost budget/limit?

**Options:**

- **Option A:** No limit, trust rate limiting
- **Option B:** Daily/monthly cost cap, pause inference when exceeded
- **Option C:** Warning threshold only, alert user but don't stop

**Recommendation:** Option C — warning threshold to avoid surprise bills while not breaking functionality.

**Decision needed by:** E3-S1 implementation

---

### 2. Summary Feedback Loop

**Question:** Should users be able to rate/improve summaries?

**Options:**

- **Option A:** No feedback (MVP)
- **Option B:** Thumbs up/down on summaries
- **Option C:** Edit summaries, use edited version for future similar turns

**Recommendation:** Option A for Epic 3, consider Option B for future.

**Decision needed by:** E3-S2 implementation

---

### 3. Priority Score Visibility

**Question:** Should priority scores be visible to all users or hideable?

**Options:**

- **Option A:** Always visible
- **Option B:** Hideable via toggle in settings
- **Option C:** Only show to "power users" based on config

**Recommendation:** Option B — some users may find scores distracting.

**Decision needed by:** E3-S3 implementation

---

### 4. Auto-Trigger Progress Summary

**Question:** Should progress_summary auto-generate after N commits?

**Options:**

- **Option A:** Manual only (user clicks button)
- **Option B:** Auto after N commits (configurable, default 10)
- **Option C:** Auto on schedule (daily, weekly)

**Recommendation:** Option A for initial release, add Option B later.

**Decision needed by:** E3-S4 implementation

---

## Risks & Mitigation

### Risk 1: OpenRouter API Costs

**Risk:** High inference volume (especially turn-level) may be expensive.

**Impact:** Medium (affects adoption if costs too high)

**Mitigation:**

- Use Haiku for high-volume operations (turn/task)
- Implement caching to avoid duplicate calls
- Rate limiting to prevent runaway costs
- Cost tracking and alerts
- Make summarisation optional per project

**Monitoring:** Track daily/weekly costs, alert if exceeding threshold

---

### Risk 2: Inference Latency

**Risk:** LLM API calls may add latency to dashboard updates.

**Impact:** Medium (degrades UX)

**Mitigation:**

- Async processing (don't block SSE)
- Haiku for speed-critical operations
- Caching for repeated content
- Show "summarising..." placeholder while waiting
- Graceful degradation if API slow

**Monitoring:** Track P95 latency, alert if >2 seconds

---

### Risk 3: Rate Limit Exhaustion

**Risk:** Burst activity may exceed OpenRouter rate limits.

**Impact:** Medium (temporary loss of intelligence features)

**Mitigation:**

- Token bucket rate limiting
- Queue overflow handling (drop or defer)
- Exponential backoff on 429 errors
- Alert on frequent rate limit hits
- Configurable limits in config.yaml

**Monitoring:** Track rate limit hits per hour

---

### Risk 4: Summary Quality Inconsistency

**Risk:** LLM summaries may vary in quality or miss key information.

**Impact:** Low (users can see original text)

**Mitigation:**

- Careful prompt engineering
- Include original text as fallback
- Consistent prompt templates
- Test with diverse turn types
- Consider feedback mechanism in future

**Monitoring:** User feedback, manual review of sample summaries

---

### Risk 5: Git Access Failures

**Risk:** Projects may not have git repos or have permission issues.

**Impact:** Low (only affects progress_summary generation)

**Mitigation:**

- Graceful error handling
- Clear error messages (not a git repo, permission denied)
- Skip progress_summary for non-git projects
- Don't block other features on git failures

**Monitoring:** Track git operation failures per project

---

## Success Metrics

From Epic 3 Acceptance Criteria:

### Test Case 1: Turn Summarisation

**Setup:** Active Claude Code session generating turns.

**Success:**

- ✅ Turn arrives → summary generated < 2 seconds
- ✅ Summary displayed on agent card inline
- ✅ Cached summary returned instantly for identical content
- ✅ InferenceCall logged with token counts

---

### Test Case 2: Task Summarisation

**Setup:** Complete a task in Claude Code session.

**Success:**

- ✅ Task completes → summary generated
- ✅ Summary displayed on agent card
- ✅ Summary persisted to database
- ✅ InferenceCall logged

---

### Test Case 3: Priority Scoring

**Setup:** Multiple agents across projects, objective set.

**Success:**

- ✅ All agents have priority scores (0-100)
- ✅ Recommended next panel shows highest priority agent
- ✅ Priority badges displayed on agent cards
- ✅ Change objective → all agents re-scored
- ✅ Priority reasons visible

---

### Test Case 4: Progress Summary Generation

**Setup:** Project with git history.

**Success:**

- ✅ Click "Generate Progress Summary" button
- ✅ Summary generated from git commits
- ✅ progress_summary.md written to project
- ✅ Previous version archived with timestamp
- ✅ Summary visible in dashboard

---

### Test Case 5: Brain Reboot

**Setup:** Project with waypoint and progress_summary.

**Success:**

- ✅ Click "Brain Reboot" button
- ✅ Modal shows combined waypoint + progress_summary
- ✅ Export saves brain_reboot.md to project
- ✅ Copy to clipboard works
- ✅ Stale projects show indicator

---

### Test Case 6: End-to-End Intelligence Flow

**Setup:** Fresh Epic 3 deployment with Epic 1 complete.

**Success:**

- ✅ Set objective → agents scored
- ✅ Start Claude Code session → turns summarised
- ✅ Complete task → task summarised, priority updated
- ✅ Generate progress summary → narrative from commits
- ✅ View brain reboot → context restoration available

---

## Data Model Changes Summary

### New Model: InferenceCall

```python
class InferenceCall(Base):
    __tablename__ = "inference_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    level: Mapped[str]  # turn, task, project, objective
    purpose: Mapped[str]  # turn_summary, task_summary, priority_score, progress_summary
    model: Mapped[str]  # anthropic/claude-3-haiku, anthropic/claude-3-5-sonnet
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    input_hash: Mapped[str]  # SHA256 for cache lookup
    result: Mapped[str]  # LLM output text
    latency_ms: Mapped[int]
    error: Mapped[str | None]  # Error message if failed

    # Foreign keys (all optional)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    turn_id: Mapped[UUID | None] = mapped_column(ForeignKey("turns.id"))

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="inference_calls")
    agent: Mapped["Agent"] = relationship(back_populates="inference_calls")
    task: Mapped["Task"] = relationship(back_populates="inference_calls")
    turn: Mapped["Turn"] = relationship(back_populates="inference_calls")
```

### Additions to Existing Models

```python
# Turn model additions
class Turn(Base):
    ...
    summary: Mapped[str | None]  # Generated by turn summariser
    summary_generated_at: Mapped[datetime | None]

# Task model additions
class Task(Base):
    ...
    summary: Mapped[str | None]  # Generated on completion
    summary_generated_at: Mapped[datetime | None]

# Agent model additions
class Agent(Base):
    ...
    priority_score: Mapped[int | None]  # 0-100
    priority_reason: Mapped[str | None]  # Explanation from LLM
    priority_updated_at: Mapped[datetime | None]
```

---

## Config.yaml Additions

```yaml
# OpenRouter LLM Configuration
openrouter:
  api_key: ${OPENROUTER_API_KEY} # Environment variable reference
  base_url: https://openrouter.ai/api/v1

  # Model selection by inference level
  models:
    turn: anthropic/claude-3-haiku # Fast, cheap for high-volume
    task: anthropic/claude-3-haiku # Fast, cheap for high-volume
    project: anthropic/claude-3-5-sonnet # Smarter for narratives
    objective: anthropic/claude-3-5-sonnet # Smarter for prioritisation

  # Rate limiting
  rate_limit:
    calls_per_minute: 60
    tokens_per_minute: 100000

  # Caching
  caching:
    enabled: true
    ttl_seconds: 3600 # 1 hour cache TTL

  # Retry configuration
  retry:
    max_attempts: 3
    base_delay_seconds: 1
    max_delay_seconds: 30

# Progress Summary Configuration
progress_summary:
  commit_scope: since_last # since_last, last_n, time_based
  last_n_commits: 50 # Used when commit_scope = last_n
  time_based_days: 30 # Used when commit_scope = time_based

# Brain Reboot Configuration
brain_reboot:
  staleness_threshold_days: 7 # Days before project marked stale
```

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order:

### Phase 1: Foundation (Week 1-2)

1. **openrouter-integration** (`docs/prds/inference/e3-s1-openrouter-integration-prd.md`) — API client, inference service, logging

**Rationale:** All other sprints depend on the inference service.

---

### Phase 2: Core Intelligence (Week 3-4)

2. **turn-task-summarisation** (`docs/prds/inference/e3-s2-turn-task-summarisation-prd.md`) — Turn/task summarisers, caching, dashboard

**Rationale:** Most visible intelligence feature, provides context for priority scoring.

---

### Phase 3: Prioritisation (Week 4-5)

3. **priority-scoring** (`docs/prds/inference/e3-s3-priority-scoring-prd.md`) — Priority scorer, objective alignment, dashboard

**Rationale:** Uses task summaries from E3-S2, drives recommended next feature.

---

### Phase 4: Project Intelligence (Week 3-5, Parallel)

4. **git-analyzer** (`docs/prds/inference/e3-s4-git-analyzer-prd.md`) — Git analysis, progress summary generation

**Rationale:** Can run in parallel with E3-S2/E3-S3, only needs E3-S1.

---

### Phase 5: Context Restoration (Week 6-7)

5. **brain-reboot** (`docs/prds/inference/e3-s5-brain-reboot-prd.md`) — Brain reboot generator, staleness, modal

**Rationale:** Depends on E3-S4 for progress_summary, final capstone feature.

---

## Document History

| Version | Date       | Author          | Changes                                         |
| ------- | ---------- | --------------- | ----------------------------------------------- |
| 1.0     | 2026-01-29 | PM Agent (John) | Initial detailed roadmap for Epic 3 (5 sprints) |

---

**End of Epic 3 Detailed Roadmap**
