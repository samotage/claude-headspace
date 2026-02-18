# Epic 3 Sprint Prompts for PRD Workshop

**Epic:** Epic 3 — Intelligence Layer  
**Reference:** [`docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md`](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md)

---

## Context Documents

| Document                                                                              | Purpose                                                                      |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md) | Primary reference for sprint scope, deliverables, acceptance criteria        |
| [Conceptual Overview](../conceptual/claude_headspace_v3.1_conceptual_overview.md)     | Domain concepts (inference levels, brain_reboot, waypoint, progress_summary) |
| [Overarching Roadmap](../roadmap/claude_headspace_v3.1_overarching_roadmap.md)        | Epic 3 goals, success criteria, dependencies                                 |
| [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md) | Context on existing infrastructure (Command/Turn models, SSE, dashboard)        |

---

## Sprint Prompts

### Epic 3 Sprint 1: OpenRouter Integration & Inference Service

**PRD:** `docs/prds/inference/e3-s1-openrouter-integration-prd.md`

> Create a PRD for the OpenRouter Integration subsystem. Reference Sprint 1 (E3-S1) in the [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md#sprint-1-openrouter-integration--inference-service-e3-s1) and the inference levels table in [Conceptual Overview Section 3](../conceptual/claude_headspace_v3.1_conceptual_overview.md#3-inference-logging--setup).
>
> **Deliverables:**
>
> - OpenRouter API client with retry/exponential backoff
> - Inference service with model selection by level (Haiku for turn/command, Sonnet for project/objective)
> - InferenceCall database model for logging all LLM calls
> - Database migration for InferenceCall table
> - Rate limiting (configurable calls per minute, tokens per minute)
> - Cost tracking (input/output tokens per call)
> - Error handling for API failures (timeouts, rate limits, server errors)
> - Health check for LLM connectivity
>
> **API Endpoints:**
>
> - GET `/api/inference/status` — inference service health and configuration
> - GET `/api/inference/usage` — usage statistics and cost tracking
>
> **Inference Levels (from Conceptual Overview):**
>
> | Level     | Purpose                                         | Model  |
> | --------- | ----------------------------------------------- | ------ |
> | turn      | Summarise individual turn for dashboard display | Haiku  |
> | task      | Summarise completed task outcome                | Haiku  |
> | project   | Generate progress_summary, brain_reboot         | Sonnet |
> | objective | Cross-project prioritisation, alignment         | Sonnet |
>
> **Integration Points:**
>
> - Uses Epic 1 Flask application and database infrastructure
> - Config stored in `config.yaml` (see roadmap for schema)
> - API key via environment variable `OPENROUTER_API_KEY`
>
> **Technical Decisions to Address:**
>
> - API client library: httpx (recommended for async) vs requests
> - Rate limiting strategy: token bucket vs sliding window
> - Retry strategy: exponential backoff with jitter
> - Caching: by input content hash to avoid duplicate calls

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md (Section 3: Inference, Logging & Setup)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md (Sprint 1 section, Config.yaml Additions, Data Model Changes)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 3 Sprint 2: Turn & Command Summarisation

**PRD:** `docs/prds/inference/e3-s2-turn-command-summarisation-prd.md`

> Create a PRD for the Turn & Command Summarisation subsystem. Reference Sprint 2 (E3-S2) in the [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md#sprint-2-turn--task-summarisation-e3-s2).
>
> **Deliverables:**
>
> - Turn summarisation service (Haiku, triggered real-time as turns arrive)
> - Command summarisation service (Haiku, triggered on command completion)
> - Summary caching by content hash (avoid re-summarising identical content)
> - Dashboard integration (display summaries on agent cards)
> - Async processing (don't block SSE updates during inference)
> - Summary fields added to Turn and Command models
> - Database migration for summary fields
>
> **API Endpoints:**
>
> - POST `/api/summarise/turn/<id>` — trigger turn summarisation (or automatic)
> - POST `/api/summarise/command/<id>` — trigger command summarisation (or automatic)
>
> **Turn Summary Prompt Template:**
>
> ```
> Summarise this turn in 1-2 concise sentences focusing on what action was taken or requested:
>
> Turn: {turn.text}
> Actor: {turn.actor}
> Intent: {turn.intent}
> ```
>
> **Command Summary Prompt Template:**
>
> ```
> Summarise the outcome of this completed task in 2-3 sentences:
>
> Command started: {command.started_at}
> Command completed: {command.completed_at}
> Turns: {turn_count}
> Final outcome: {final_turn.text}
> ```
>
> **Integration Points:**
>
> - Uses E3-S1 inference service for LLM calls
> - Integrates with Epic 1 Turn and Command models
> - Updates dashboard agent cards via Epic 1 SSE system
> - Caching uses InferenceCall.input_hash from E3-S1
>
> **Technical Decisions to Address:**
>
> - Summarisation trigger: real-time on turn arrival (decided)
> - Cache storage: database (InferenceCall table) vs in-memory
> - Summary length: 1-2 sentences for turns, 2-3 for tasks
> - Async implementation: background thread vs command queue

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md (Section 3: inference levels)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md (Sprint 2 section, Data Model Changes)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 3 Sprint 3: Priority Scoring Service

**PRD:** `docs/prds/inference/e3-s3-priority-scoring-prd.md`

> Create a PRD for the Priority Scoring subsystem. Reference Sprint 3 (E3-S3) in the [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md#sprint-3-priority-scoring-service-e3-s3).
>
> **Deliverables:**
>
> - Priority scoring service (Sonnet for intelligence)
> - Cross-project batch scoring (score all agents in single LLM call)
> - Objective alignment calculation
> - Priority score (0-100) and reason stored on Agent model
> - Dashboard integration (priority badges on agent cards)
> - Recommended next panel uses priority scores
> - Scoring triggers: command state change, objective change
> - Re-score all agents when objective changes
> - Database migration for priority fields on Agent
>
> **API Endpoints:**
>
> - POST `/api/priority/score` — trigger priority scoring (batch)
> - GET `/api/priority/rankings` — get current priority rankings
>
> **Scoring Factors:**
>
> | Factor              | Weight | Description                                      |
> | ------------------- | ------ | ------------------------------------------------ |
> | Objective alignment | 40%    | How well does agent's work align with objective? |
> | Agent state         | 25%    | awaiting_input > processing > idle               |
> | Task duration       | 15%    | Longer tasks may need attention                  |
> | Project context     | 10%    | Project waypoint priorities                      |
> | Recent activity     | 10%    | Recently active vs stale                         |
>
> **Priority Scoring Prompt Template:**
>
> ```
> You are prioritising agents working across multiple projects.
>
> Current Objective: {objective.text}
> Constraints: {objective.constraints}
>
> Agents to score:
> {for agent in agents}
> - Agent: {agent.session_uuid}
>   Project: {agent.project.name}
>   State: {agent.state}
>   Current Command: {agent.current_command.summary or "None"}
>   Task Duration: {task_duration}
>   Waypoint Next Up: {agent.project.waypoint.next_up}
> {endfor}
>
> Score each agent 0-100 based on priority for user attention.
> Return JSON: [{"agent_id": "...", "score": N, "reason": "..."}]
> ```
>
> **Integration Points:**
>
> - Uses E3-S1 inference service for LLM calls
> - Uses E3-S2 command summaries for context in scoring prompt
> - Integrates with Epic 1 Objective model and Agent model
> - Updates dashboard recommended next panel
> - Updates agent card priority badges
>
> **Technical Decisions to Address:**
>
> - Scoring frequency: debounced (5 second delay recommended) vs immediate
> - Batch vs individual scoring: batch recommended for efficiency
> - Score range: 0-100 (decided)
> - State-based modifiers: awaiting_input = +20, processing = +10, idle = 0

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md (Section 1: prioritisation concept)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md (Sprint 3 section, Data Model Changes)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 3 Sprint 4: Git Analyzer & Progress Summary

**PRD:** `docs/prds/inference/e3-s4-git-analyzer-prd.md`

> Create a PRD for the Git Analyzer & Progress Summary subsystem. Reference Sprint 4 (E3-S4) in the [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md#sprint-4-git-analyzer--progress-summary-e3-s4) and the progress_summary definition in [Conceptual Overview Section 6](../conceptual/claude_headspace_v3.1_conceptual_overview.md#6-repo-artifacts).
>
> **Deliverables:**
>
> - Git analyzer service (extract commits, diffs, file changes from project repos)
> - Progress summary generator (Sonnet for narrative quality)
> - Configurable commit scope: since_last, last_n, time_based
> - Write progress_summary.md to target project's `docs/brain_reboot/` directory
> - Archive previous version with timestamp (`archive/progress_summary_YYYY-MM-DD.md`)
> - Create directory structure if missing
> - Dashboard UI: "Generate Progress Summary" button per project
> - Progress summary display in project panel
>
> **API Endpoints:**
>
> - POST `/api/projects/<id>/progress-summary` — generate progress summary
> - GET `/api/projects/<id>/progress-summary` — retrieve current progress summary
>
> **Progress Summary Prompt Template:**
>
> ```
> Generate a narrative progress summary for this project based on recent git activity.
>
> Project: {project.name}
> Date Range: {start_date} to {end_date}
> Commit Count: {commit_count}
>
> Recent Commits:
> {for commit in commits}
> - {commit.hash[:8]}: {commit.message} ({commit.author}, {commit.timestamp})
> {endfor}
>
> Files Changed: {files_changed}
>
> Write a 3-5 paragraph narrative summarising:
> 1. What major work was completed
> 2. What features or fixes were implemented
> 3. Current state of the project
> 4. Any patterns or themes in the work
>
> Write in past tense, focus on accomplishments.
> ```
>
> **Repo Artifact Location (from Conceptual Overview):**
>
> ```
> <target_project>/
> └── docs/
>     └── brain_reboot/
>         ├── progress_summary.md              (current)
>         └── archive/
>             ├── progress_summary_2025-01-10.md
>             └── ...
> ```
>
> **Integration Points:**
>
> - Uses E3-S1 inference service for LLM calls
> - Uses Epic 1 Project model for project paths
> - Reads git history from target project repositories
> - Writes files to target project directories (not Claude Headspace repo)
>
> **Technical Decisions to Address:**
>
> - Commit scope default: since_last (recommended)
> - Significant commit threshold for auto-trigger (if enabled)
> - Diff inclusion: commit messages + file list (recommended) vs full diffs
> - Archive retention: keep all versions (recommended)
> - Git error handling: graceful failure for non-git projects

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md (Section 6: Repo Artifacts)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md (Sprint 4 section, Config.yaml Additions)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 3 Sprint 5: Brain Reboot Generation

**PRD:** `docs/prds/inference/e3-s5-brain-reboot-prd.md`

> Create a PRD for the Brain Reboot subsystem. Reference Sprint 5 (E3-S5) in the [Epic 3 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md#sprint-5-brain-reboot-generation-e3-s5) and the brain_reboot definition in [Conceptual Overview Section 6](../conceptual/claude_headspace_v3.1_conceptual_overview.md#62-artifact-definitions).
>
> **Deliverables:**
>
> - Brain reboot generator (combine waypoint + progress_summary)
> - Dynamic generation on demand (not stored by default)
> - Dashboard modal to view brain reboot content
> - Export option (save to `docs/brain_reboot/brain_reboot.md` in target project)
> - Copy to clipboard functionality
> - Staleness detection (projects without recent activity)
> - Stale project indicator on dashboard
>
> **API Endpoints:**
>
> - POST `/api/projects/<id>/brain-reboot` — generate brain reboot
> - GET `/api/projects/<id>/brain-reboot` — retrieve generated brain reboot
>
> **Brain Reboot Definition (from Conceptual Overview):**
>
> > **brain_reboot** - The combined view (waypoint + progress_summary) that enables rapid mental context restoration when returning to a stale project.
>
> **Brain Reboot Output Structure:**
>
> ```markdown
> # Brain Reboot: {project.name}
>
> Generated: {timestamp}
>
> ## Progress Summary
>
> {progress_summary content}
>
> ## Waypoint (Path Ahead)
>
> ### Next Up
>
> {waypoint.next_up}
>
> ### Upcoming
>
> {waypoint.upcoming}
>
> ### Later
>
> {waypoint.later}
>
> ### Not Now
>
> {waypoint.not_now}
>
> ---
>
> _Use this document to quickly restore context when returning to this project._
> ```
>
> **Staleness Detection:**
>
> | Days Since Activity | Status | Indicator                  |
> | ------------------- | ------ | -------------------------- |
> | 0-3 days            | Fresh  | Green                      |
> | 4-7 days            | Aging  | Yellow                     |
> | 8+ days             | Stale  | Red + "Needs Reboot" badge |
>
> **Integration Points:**
>
> - Uses E3-S4 progress_summary from target project
> - Uses Epic 2 waypoint from target project (or Epic 1 if waypoint editor not yet built)
> - Dashboard modal overlays existing UI
> - Staleness based on Epic 1 Agent.last_seen_at
>
> **Technical Decisions to Address:**
>
> - Storage: dynamic generation (decided) vs stored file
> - Staleness threshold: configurable in config.yaml (default 7 days)
> - LLM enhancement: concatenate with formatting (recommended) vs LLM synthesis
> - Missing files handling: show available content, indicate what's missing

Review conceptual design and guidance at:

- docs/conceptual/claude_headspace_v3.1_conceptual_overview.md (Section 6: Repo Artifacts, brain_reboot definition)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic3_detailed_roadmap.md (Sprint 5 section, Config.yaml Additions)
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
[Epic 1 Complete]
       │
       ▼
   E3-S1 (OpenRouter Integration)
       │
       ├──▶ E3-S2 (Turn/Command Summarisation)
       │        │
       │        └──▶ E3-S3 (Priority Scoring)
       │
       └──▶ E3-S4 (Git Analyzer + Progress Summary)
                │
                └──▶ E3-S5 (Brain Reboot)
```

**Critical Path:** E3-S1 → E3-S2 → E3-S3

**Parallel Track:** E3-S4 can start after E3-S1 completes (independent of E3-S2/E3-S3)
