# Paperclip AI — Evaluation for Claude Headspace Agent Management

**Author:** Hawk (Technical Analyst)
**Date:** 2026-03-07
**Purpose:** Inform the design of Claude Headspace's agent management feature by documenting what Paperclip does, what it does well, and what's relevant to our use case — particularly for long-running agents, activity auditing, and client-facing accountability (Kenwood context).

---

## 1. What Paperclip Is

Paperclip is an open-source (MIT) TypeScript/React application that manages teams of AI agents as autonomous organisations. It positions itself as the "company" that agents work in — providing org structure, task management, budget enforcement, governance, and scheduling.

- **Repo:** github.com/paperclipai/paperclip
- **Stack:** Node.js 20+, Express 5, React 19, PostgreSQL (or embedded PGlite), Drizzle ORM
- **Adapters:** Claude Code CLI, OpenAI Codex CLI, generic process, HTTP webhook
- **License:** MIT, self-hosted, ~1.3k GitHub stars

### How It Differs From Headspace

| Aspect | Paperclip | Headspace |
|---|---|---|
| Role | Orchestrator — spawns and controls agents | Observer — monitors agents running independently |
| Agent relationship | Creates, schedules, invokes, terminates | Registers, tracks, summarises, interacts |
| Intelligence | Zero server-side LLM — agents self-report | Rich inference layer — summarises, scores, detects states |
| User model | "The board" governing autonomous agents | The developer managing their own sessions |
| Interaction | Fire-and-forget (no mid-run communication) | Real-time tmux bridge, click-to-focus |

**These are different products solving adjacent problems.** Paperclip is not a competitor, but several of its operational patterns are relevant to where Headspace is heading.

---

## 2. Features Relevant to Agent Management

### 2.1 Activity Audit Trail

**What Paperclip does:** Every mutation — task created, agent paused, config changed, approval decided — writes to an `activity_log` table with: actor type (agent/user/system), actor ID, action string (e.g. `issue.created`), entity type, entity ID, details (JSONB), timestamp. The UI exposes this as a filterable event feed.

**Why this matters for us:** Headspace already has an `Event` table with similar intent but narrower scope (hook events, state transitions). For Kenwood-style client accountability, we need a comprehensive audit trail that answers:
- What did each agent do, and when?
- Who (human or agent) initiated each action?
- What was the sequence of events that led to this outcome?

**Applicable pattern:**
- Append-only audit log with actor attribution (agent vs human vs system)
- Structured action types for queryable history
- JSONB details for flexible payload without schema changes
- Filterable UI for reviewing activity by agent, project, time range
- Export capability for client reporting

**Headspace gap:** Our Event table records hook events and state transitions but doesn't comprehensively capture all mutations. Expanding this to a full activity audit with actor attribution would provide the accountability layer needed for client work.

---

### 2.2 Agent Run History and Log Capture

**What Paperclip does:** Every agent invocation creates a `heartbeat_runs` record tracking:
- Start time, end time, duration
- Status (queued/running/succeeded/failed/cancelled/timed_out)
- Exit code and signal
- Token usage (input, output, cached) and cost
- stdout/stderr excerpts (capped at 32KB)
- Full run logs persisted to disk as NDJSON with SHA256 hash
- Session ID before and after (for continuity tracking)
- Context snapshot at invocation time (what task, why woken)

Fine-grained events within each run are stored in `heartbeat_run_events` with sequence numbers, event types, log levels, and payloads.

**Why this matters for us:** For long-running agents, we need to answer: "What happened during this session?" Currently Headspace tracks turns and commands, but doesn't have a unified "run" concept that captures the full lifecycle of an agent session from start to finish with structured metadata.

**Applicable patterns:**
- **Run as first-class entity:** A bounded unit of agent work with clear start/end, status, and metadata — distinct from the ongoing "agent" record
- **Structured log capture:** Not just raw transcript, but parsed events with types and levels
- **Context snapshot at start:** Recording what the agent was supposed to be working on when the run began (for retrospective analysis)
- **Exit classification:** Distinguishing success, failure, timeout, cancellation, and auth errors — not just "ended"
- **Log integrity:** Hash + size for tamper-evident log storage (relevant for client accountability)

---

### 2.3 Cost and Resource Tracking

**What Paperclip does:**
- `cost_events` table: provider, model, input/output tokens, cost in cents, timestamp
- Attribution chain: cost -> agent -> issue -> project -> goal
- Per-agent monthly budget with auto-pause on breach
- Per-company monthly budget
- Billing codes for cross-team cost attribution
- Cumulative running totals on `agent_runtime_state` for fast display
- Cost rollup queries by agent, project, company

**Why this matters for us:** We already have the `resource-tracking-billing.md` and `usage-budget-tracking.md` ideas docs exploring this space. When Claude Code moves to API-based pricing, cost tracking becomes critical. Even under subscription, tracking resource consumption (time, turns, context usage) is valuable for:
- Client billing (Kenwood): "Project X consumed N agent-hours this week"
- Resource planning: "This project is consuming more agent time than expected"
- Efficiency analysis: "Agent A completes similar tasks with fewer turns than Agent B"

**Applicable patterns:**
- **Multi-level attribution:** Cost/resource -> agent -> command -> project (mirrors our existing model hierarchy)
- **Cumulative counters on agent record:** Avoid expensive aggregation queries for dashboard display
- **Daily aggregation model:** Aligns with our existing `ActivityMetric` pattern and the `DailyProjectMetric` model proposed in `resource-tracking-billing.md`
- **Budget alerts:** Configurable thresholds with notification on approach/breach

**Note:** Under subscription pricing, "cost" means agent-hours and turn counts, not dollars. The tracking infrastructure is the same; only the unit changes.

---

### 2.4 Session Continuity Across Runs

**What Paperclip does:** Stores Claude session IDs in `agent_task_sessions`, keyed by `(agent, adapter, task)`. When an agent resumes work on the same task, the stored session ID is passed to `claude --resume <sessionId>`. If the session is stale (Claude reports "no conversation found"), it auto-retries with a fresh session and clears the stored reference.

**Why this matters for us:** Brain reboot already generates context snapshots. Per-task session tracking would enhance this by:
- Linking session IDs to specific objectives/commands
- Enabling "resume where you left off on X" after working on Y
- Providing session lineage: "this objective was worked on across sessions A, B, and C"

**Applicable patterns:**
- **Task-keyed session storage:** `(agent_id, task_key) -> session_params`
- **Stale session detection and auto-recovery:** Don't fail on expired sessions; retry fresh
- **Session lineage:** Recording which sessions contributed to which objectives

---

### 2.5 Agent Configuration Versioning

**What Paperclip does:** Every agent config change creates an `agent_config_revisions` record with: changed keys, before/after snapshots, change source (patch/rollback), who made the change. Board can roll back to any prior revision.

**Why this matters for us:** As the persona system matures and agents get richer configuration (skills, experience, role assignments, prompt templates), tracking what changed and when becomes important for:
- Debugging: "The agent started behaving differently after config change X"
- Accountability: "Who changed the agent's instructions?"
- Recovery: "Roll back to the config that was working"

**Applicable pattern:**
- Before/after JSON snapshots on config mutation
- Rollback by re-applying a historical snapshot
- Change attribution (who/what triggered the change)

---

### 2.6 Execution Locking and Contention

**What Paperclip does:** Atomic task checkout via SQL — only one agent can "own" a task at a time. Uses `executionRunId` and `executionLockedAt` fields with SQL-level atomicity. If another run targets the same task, it's stored as a deferred wakeup and promoted when the current run finishes.

**Why this matters for us:** Currently Headspace has one-agent-per-command with no contention. But for multi-agent scenarios where agents share a project or objective:
- Preventing two agents from working on the same thing simultaneously
- Queuing work when a resource is locked
- Clean handoff when one agent finishes and another picks up

**Applicable pattern (future):**
- Execution locks on commands/objectives with atomic checkout
- Deferred work queue: "agent B wants to work on X, but agent A has it — queue B for when A is done"
- Lock timeout: if an agent holds a lock too long (stale), surface it for intervention

---

### 2.7 Structured Agent Error Classification

**What Paperclip does:** Classifies agent failures with specific error codes:
- `adapter_failed` — process spawn error
- `claude_auth_required` — login expired (extracts login URL from stderr)
- `process_lost` — orphaned run detected on server restart
- `max_turns_reached` — Claude hit turn limit
- Timeout detection with two-stage kill (SIGTERM then SIGKILL after grace period)

**Why this matters for us:** Headspace's agent reaper handles stale agents, but doesn't classify *why* an agent stopped. For long-running agents and client accountability:
- "Agent stopped because auth expired" vs "agent completed its work" vs "agent timed out" vs "agent crashed" are very different situations
- Each failure mode suggests a different recovery action
- Client reports should distinguish productive completions from failures

**Applicable pattern:**
- Enumerated exit reasons on agent/command records
- Auth-specific detection and recovery guidance
- Orphan detection on server restart (we have the reaper, but could classify better)

---

## 3. Features NOT Relevant to Headspace

For completeness — things Paperclip has that we should **not** adopt:

| Feature | Why Not |
|---|---|
| Heartbeat scheduling / cron-style agent invocation | Headspace observes agents, doesn't invoke them. A cron is a different product. |
| Multi-company data isolation | Headspace is single-instance multi-project. No need for tenant isolation. |
| Governance / approval gates | Corporate overhead for a solo developer. Not our user. |
| Org hierarchy with CEO/CTO/board metaphor | Over-engineered. Our persona system serves the same purpose without the corporate theatre. |
| Multi-adapter support (Codex, HTTP webhook) | Headspace is Claude Code-specific by design. |
| Skills injection via filesystem (`--add-dir`) | Only works if you control agent launch. We observe; we don't launch. |
| Secrets management (encrypted at rest, multi-provider) | Headspace uses `.env`. Not a problem that needs solving at our scale. |

---

## 4. Patterns for the Agent Management Feature

Drawing from the evaluation, here are the structural patterns most relevant to designing Headspace's agent management:

### 4.1 The "Run" as a First-Class Entity

Currently Headspace tracks agents and commands. Introduce a **Run** concept: a bounded period of agent activity with clear start/end, status, metadata, and log references. This gives us:
- A unit of work for reporting ("Agent completed 3 runs today")
- A container for resource metrics ("Run consumed N turns over M minutes")
- A reviewable artifact for clients ("Here's what happened in each run")

### 4.2 Comprehensive Activity Audit

Expand the Event table (or create a dedicated audit log) to capture all meaningful mutations with actor attribution. Every action should be traceable to who did it, when, and why. This is the foundation for client-facing accountability.

### 4.3 Resource Tracking (Time-Based)

Under subscription, track agent-hours, turn counts, and session depths per project. Structure the data model so that when API pricing arrives, adding token/cost columns is additive — not a redesign. The `DailyProjectMetric` model from `resource-tracking-billing.md` is the right shape.

### 4.4 Exit Classification

When an agent session ends, classify *why*: completed, timed out, auth expired, crashed, user-terminated, context exhausted. This feeds both the dashboard (operational awareness) and reports (client accountability).

### 4.5 Session Lineage

Track which Claude sessions worked on which objectives, across restarts and context resets. This provides continuity narrative: "Objective X was worked on across 4 sessions over 2 days, completing after session D."

---

## 5. Kenwood-Specific Considerations

For client-facing agent work, the accountability requirements are:

1. **What was done:** Comprehensive activity log with human-readable summaries (we already have LLM-powered summarisation — this is a significant advantage over Paperclip's raw logs)
2. **How long it took:** Agent-hours per project per day, with active time vs wall clock time
3. **What the outcome was:** Command completion summaries linked to project objectives
4. **What went wrong:** Classified failure modes with timestamps and context
5. **Audit trail:** Immutable event log proving the sequence of events

Headspace's intelligence layer (summarisation, intent detection, frustration scoring) means our audit trail is *richer* than Paperclip's — we don't just log "agent ran for 20 minutes", we log "agent completed 3 subtasks, asked 2 clarifying questions, showed mild frustration during CSS debugging, and completed the feature."

That's the differentiator for client accountability: not just proving work happened, but proving it was *intelligent, monitored work*.

---

## 6. Source Material

- Repository analysed: github.com/paperclipai/paperclip (shallow clone, 2026-03-07)
- Existing Headspace ideas: `docs/ideas/resource-tracking-billing.md`, `docs/ideas/usage-budget-tracking.md`
- Full codebase read: ~30 schema files, ~20 service modules, ~17 route groups, 4 adapter implementations
- Analysis confidence: High — based on source code examination, not marketing claims
