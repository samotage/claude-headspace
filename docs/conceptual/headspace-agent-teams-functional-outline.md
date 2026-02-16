# Claude Headspace — Agent Teams

**Date:** 15 February 2026
**Author:** Sam Sabey / OtageLabs
**Status:** BMAD Root Artefact — Ready for Epic Decomposition
**Context:** Extends Claude Headspace 3.1 agent orchestration with team-based agent management
**Method:** This document is the root artefact for the BMAD process. Use it to derive epics, user stories, sprint plans, and acceptance criteria for the Agent Teams module.
**Platform Vision:** This is the first organisation instance within the broader Agentic Workforce Platform vision. See `headspace-platform-vision.md` for the strategic frame. Build for the dev org's needs first, but design the persona system, org definitions, and workflow engine to be reusable by future organisations (Marketing, Production, Delivery).

---

## 1. Problem Statement

Claude Headspace currently manages multiple concurrent Claude Code agents as anonymous sessions identified by opaque IDs (e.g., `4b6f`, `a3e2`). This creates cognitive overhead for the operator: tracking which agent is doing what, understanding task provenance, and maintaining continuity across sessions is unnecessarily difficult. Agents have no identity, no persistent skill context, and no structured handoff capability when context windows fill up.

As workloads scale to 3+ concurrent agents working across multiple projects, the operator needs a team model — not just a process manager.

---

## 2. Vision

Headspace evolves from an agent orchestrator into a team simulator. The operator workshops messy ideas with Robbo (the architect) to produce tight specifications. Gavin (the PM) decomposes those specs into task assignments matched to persona capabilities. Named execution personas (Con, Al, May, Mark) build the work. Verner (QA lead) validates deliverables against the spec. Robbo reviews the final output before it returns to the operator.

Agents work "shifts" with structured handoff when context limits are reached, maintaining continuity through handover notes and durable skill files. The operator's experience shifts from "managing processes" to "running a team."

---

## 3. Design Principles

1. **Specification quality gates execution quality.** The workshop layer (operator + Robbo) must produce a tight spec before any team execution begins. Garbage in, garbage out. Or as the military principle goes: all plans become void once battle is joined, but a plan is necessary before going to war.
2. **Personas are lightweight, not elaborate.** A name, a paragraph of identity, and 5–10 behavioural preferences. Not a job description.
3. **Skill files are living documents.** Stored on disk, editable by agents, curated by the operator. They grow through work, not just configuration.
4. **Start simple, earn complexity.** Operator is the high-level orchestrator throughout. Gavin's autonomy increases incrementally across versions.
5. **Human-legible over technically clever.** "Con finished the auth migration" beats "agent-4b6f task complete."
6. **Two distinct modes.** Workshop (collaborative, document-producing) and Execution (task-scoped, code-producing) are first-class concepts, not afterthoughts.

---

## 4. Architecture Layers

### 4.1 Workshop Layer (Operator + Robbo)

**Purpose:** Messy creative thinking, requirement discovery, specification refinement.

**Mode:** Workshop — collaborative, iterative, document-producing. First-class mode in Headspace.

**How it works:**
- Operator describes what they want in natural language
- Robbo (the architect) engages in iterative Q&A to refine, challenge, and tighten the specification
- Robbo untangles messy thoughts and turns them into clear, concise instructions
- Output is a structured specification document suitable for task decomposition
- Maps to the existing agentic development loop: Change name → DoD → OpenSpec proposal → Q&A → Apply → Test

**Robbo's role:** Robbo does not touch the tools. He doesn't write code. He is the thinking partner — useful for analysis of what things do, challenging assumptions, and ensuring architectural coherence. His output is documents, not implementations.

**Session lifecycle:** A workshop session is scoped to producing a single specification. When the spec is complete, the operator assigns it to Gavin. The workshop session ends. A new workshop session is created if/when Robbo is needed again (e.g., for final review).

**Key requirement:** This layer resolves ambiguity before it becomes expensive downstream.

### 4.2 PM Layer (Gavin)

**Purpose:** Receives a clean specification from Robbo's workshop, decomposes it into tasks, assigns tasks to personas based on skill match and pool availability.

**Mode:** Execution — task-scoped, code-producing.

**How it works:**
- Operator assigns the workshop output (a tight spec) to Gavin
- Gavin decomposes into discrete, well-scoped tasks with clear acceptance criteria
- Each task is tagged with required skill domain (backend, frontend, database, devops, etc.)
- Tasks are assigned to available personas from the matching skill pool
- Gavin manages sequencing, dependencies, and escalation

**Evolution path:**
- **v1:** Operator acts as Gavin — manually decomposes and assigns tasks
- **v2:** Gavin drafts decomposition; operator reviews and approves before agents spin up
- **v3:** Gavin operates autonomously with escalation paths back to operator

**Key requirement:** Gavin's job is logistics and sequencing, not creative problem-solving. The spec has already been tightened upstream by Robbo.

### 4.3 Execution Layer (The Team)

**Purpose:** Named personas execute well-scoped tasks with skill-biased context.

**Mode:** Execution.

**How it works:**
- Agent spins up with persona identity + skill file loaded into context
- Executes the assigned task within its context window ("one day's work")
- When context approaches limits, performs structured handoff (see §6)
- On task completion, may propose updates to its skill file (see §7)
- Persona returns to available pool

### 4.4 QA Layer (Verner)

**Purpose:** Validates that the built work meets the specification's acceptance criteria through test creation and execution.

**Mode:** Execution.

**How it works:**
- Verner receives the original specification and writes tests against it
- After the team completes implementation, Verner executes tests against the build
- Verner resolves test vs implementation discrepancies pragmatically:
  - If the test is wrong (implementation is valid): Verner adjusts the test
  - If the implementation missed the spec: Verner sends it back to the relevant team member to fix
  - If it's architecturally ambiguous (is the spec wrong?): Verner escalates to Robbo
- Feedback loop continues until tests pass and Verner is satisfied

**Verner's cross-cutting role:** As QA lead, Verner has visibility across all skill domains — backend, frontend, database, integration. She needs this breadth to make judgment calls about whether a failing test reflects a test bug, an implementation bug, or a spec gap. She is the "god-type" role on the validation side, just as Robbo is on the design side.

### 4.5 Review Layer (Robbo)

**Purpose:** Architect validates that the final deliverable matches the original specification intent.

**How it works:**
- After Verner's QA pass, a new Robbo workshop session spins up
- Robbo reviews the completed work against the specification he helped create
- Robbo validates architectural coherence and spec compliance
- Robbo reports back to the operator: done, or issues to address
- Gavin may assign Robbo review tasks directly

**Session note:** The original workshop session that produced the spec will have ended by this point. The review is a fresh Robbo session with the spec and deliverables loaded as context.

### 4.6 Ops Layer (Leon)

**Purpose:** Monitors deployed projects for runtime failures, triages exceptions, and drives remediation — either by spawning fix agents automatically or escalating to the team.

**Mode:** Execution — but operating on a different lifecycle to the build cycle. Leon works on what's already shipped.

**How it works:**
- Applications report exceptions to Claude Headspace via a simple HTTP POST (no SDK, no vendor agent)
- Leon's subsystem ingests, deduplicates, and classifies exceptions by severity (critical/error/warning/noise)
- LLM analysis provides root cause triage — using existing inference service (lightweight model for triage, deeper model for complex analysis)
- Notifications surface failures via macOS notifications (critical/error) and dashboard panels (all severities)
- For auto-fixable exceptions, Leon proposes a fix approach with an operator approval gate
- On approval, Leon spawns a Claude Code agent (assigned to the appropriate team persona) to remediate
- Fix lifecycle tracked on dashboard: `NEW → ANALYSING → FIX_PROPOSED → FIX_IN_PROGRESS → FIX_COMMITTED → VERIFIED → RESOLVED`
- Post-fix verification optionally routes through Verner to confirm the exception no longer occurs

**Exception ingestion sources:**
- Flask apps (including Headspace itself) via `got_request_exception` signal
- Any Python app via lightweight logging handler
- Claude Code hook failures (already flowing through hook receiver)
- Any HTTP-capable application via raw POST to the endpoint

**Leon's cross-cutting role:** Like Verner on the validation side, Leon needs visibility across all domains to diagnose runtime failures. A 500 might be a database constraint violation (May's domain), a nil reference in a controller (Con's domain), or a broken component render (Al's domain). Leon needs to understand enough to triage correctly and route fixes to the right persona.

**Relationship to Verner:** Leon catches problems in production; Verner catches them during build. Post-fix verification is the handoff point — Leon identifies the problem, an agent fixes it, Verner can verify the fix closes the loop.

**Key design decisions:**
- No external SaaS dependency — runs entirely within Headspace using existing PostgreSQL, SSE, and inference service
- Simple ingestion API — any app can POST; no SDK lock-in
- Auto-remediation is opt-in with operator approval gate by default
- Trusted projects can be configured to skip approval for low-severity fixes

---

## 4.7 Full Workflow

### Build Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPERATOR (You)                           │
│                   High-level orchestrator                        │
└──────────┬──────────────────────────────────┬───────────────────┘
           │ 1. Workshop                       │ 8. Review complete
           ▼                                   │
┌─────────────────────┐                        │
│  ROBBO (Architect)  │                        │
│  Workshop Mode      │◀───────────────────────┤
│  Produces spec      │  7. Final review       │
└──────────┬──────────┘     (new session)      │
           │ 2. Spec ready                     │
           ▼                                   │
┌─────────────────────┐                        │
│  GAVIN (PM)         │                        │
│  Decomposes tasks   │                        │
│  Assigns to team    │                        │
└──────────┬──────────┘                        │
           │ 3. Tasks assigned                 │
           ▼                                   │
┌─────────────────────┐                        │
│  TEAM               │                        │
│  Con, Al, May, Mark │                        │
│  Execute tasks      │                        │
└──────────┬──────────┘                        │
           │ 4. Build complete                 │
           ▼                                   │
┌─────────────────────┐                        │
│  VERNER (QA Lead)   │                        │
│  Write & run tests  │───┐                    │
│  Validate vs spec   │   │ 5. Fix needed      │
└──────────┬──────────┘   │    (back to team   │
           │              │     or escalate     │
           │ 6. QA pass   │     to Robbo)       │
           │              └────────────────►    │
           └────────────────────────────────────┘
```

### Ops Cycle (Post-Deployment)

```
┌──────────────────┐
│  DEPLOYED APP    │
│  Exception POST  │
└────────┬─────────┘
         │
         ▼
┌─────────────────────┐
│  LEON (Ops)         │
│  Ingest, dedup,     │
│  classify, analyse  │
└────────┬────────────┘
         │
         ├── Noise/transient → Log & dismiss
         │
         ├── Auto-fixable → Propose fix → Operator approves
         │                                      │
         │                    ┌─────────────────┘
         │                    ▼
         │              ┌───────────────┐
         │              │  TEAM MEMBER  │
         │              │  (fix agent)  │
         │              └───────┬───────┘
         │                      │
         │                      ▼
         │              ┌───────────────┐
         │              │  VERNER       │
         │              │  Verify fix   │
         │              └───────┬───────┘
         │                      │
         │                      ▼
         │              Exception → RESOLVED
         │
         └── Architectural / complex → Escalate
                    │
                    ▼
              Gavin → Robbo → Operator
```

### Escalation Paths

```
Build:  Team member stuck → Gavin → Robbo → Operator
QA:     Verner finds ambiguity → Robbo → Operator
Ops:    Leon finds exception → auto-fix or → Gavin → Robbo → Operator
```

---

## 5. Persona System

### 5.1 Persona Definition

A persona consists of:

| Component | Location | Mutability |
|-----------|----------|------------|
| **Identity** (name, core description) | Config (Headspace) | Stable — rarely changes |
| **Skill file** (capabilities, preferences, learned experience) | Disk (project or global) | Evolves over time |
| **Pool membership** (skill domain tags) | Config (Headspace) | Operator-managed |

### 5.2 Identity (Config)

Lightweight. Stored in Headspace configuration.

```yaml
personas:
  con:
    name: "Con"
    description: "Backend systems specialist. Favours explicit over clever, always considers edge cases, writes rollback plans for destructive changes."
    pools:
      - backend
      - database
  al:
    name: "Al"
    description: "Frontend expert. Strong on accessibility, component architecture, and user interaction patterns. Prefers progressive enhancement."
    pools:
      - frontend
      - ui
  may:
    name: "May"
    description: "Database administrator. Schema design, migration safety, query optimisation, data integrity. Conservative with destructive operations."
    pools:
      - database
      - backend
  gavin:
    name: "Gavin"
    description: "Project manager. Decomposes specifications into tasks, manages sequencing and dependencies, tracks progress across the team."
    pools:
      - pm
  robbo:
    name: "Robbo"
    description: "Overall architect and workshop partner. System design, technical direction, cross-cutting architectural decisions. Untangles messy thinking into clear specs. Does not touch tools or write code — produces documents and reviews deliverables."
    pools:
      - architecture
      - workshop
      - review
  verner:
    name: "Verner"
    description: "QA lead. Writes tests from specifications, executes them against implementations, and resolves discrepancies pragmatically. Cross-cutting visibility across all domains to make judgment calls on test vs implementation vs spec issues."
    pools:
      - qa
      - backend
      - frontend
      - database
      - integration
  leon:
    name: "Leon"
    description: "Operations lead. Monitors deployed projects for exceptions and failures, triages severity, drives auto-remediation by spawning fix agents or escalating. Cross-cutting visibility across all domains for runtime diagnosis."
    pools:
      - ops
      - backend
      - frontend
      - database
      - integration
  mark:
    name: "Mark"
    description: "Full-stack generalist. Comfortable across the stack, good at cross-cutting concerns and integration work."
    pools:
      - backend
      - frontend
      - integration
```

### 5.3 Skill Files (Disk)

Stored on disk so they can be iterated on — by the operator, by the agent itself, or by a reviewing persona.

**Structure:**

```
~/.headspace/personas/
  con/
    skill.md          # Core skills and preferences (~100-200 tokens)
    experience.md     # Recent experience log (prunable)
  al/
    skill.md
    experience.md
  ...
```

**skill.md example (Con):**

```markdown
# Con — Skill Profile

## Core Competencies
- Ruby on Rails backend development
- Database migrations (Rails, raw SQL)
- API design (REST, JSON:API)
- Data modelling and schema design
- Background job architecture (Sidekiq, Solid Queue)

## Preferences
- Explicit over clever
- Always write rollback plans for destructive changes
- Favour database constraints over application-level validation
- Test migrations against production-scale data before applying
- Prefer service objects over fat models

## Learned Experience
- Has working familiarity with Stimulus controllers from auth UI task (2026-02-10)
- Experienced with Turbo Streams for real-time updates from monitoring dashboard work (2026-02-08)
```

**experience.md** is the append-only log of task completions and learnings. Periodically summarised/pruned — either by the operator or by an automated curation step.

### 5.4 Persona Pools

Pools are skill-domain groupings. A persona can belong to multiple pools.

```yaml
pools:
  workshop:
    personas: [robbo]
  architecture:
    personas: [robbo]
  review:
    personas: [robbo]
  pm:
    personas: [gavin]
  backend:
    personas: [con, may, mark]
  frontend:
    personas: [al, mark]
  database:
    personas: [may, con]
  integration:
    personas: [mark]
  qa:
    personas: [verner]
  ops:
    personas: [leon]
```

**Note:** Robbo is excluded from execution pools (backend, frontend, etc.) — he workshops and reviews but does not build. Verner and Leon have cross-cutting *visibility* across all domains for QA and ops purposes respectively, but their pool assignments are role-specific — they validate and monitor, they don't implement.

### 5.5 Persona Selection

When spinning up an agent for a task:

1. Identify required skill domain from task metadata
2. Filter pool to available personas (not currently assigned to an active agent)
3. Select first available (v1 — simple round-robin or FIFO)
4. Future: prefer persona with affinity (e.g., Con worked on this codebase yesterday)

**Constraint:** A persona can only be active in one agent at a time. This preserves the cognitive benefit — if Con is doing two things at once, the naming loses its value.

---

## 6. Context Handoff ("End of Day")

### 6.1 Concept

An agent's context window is a finite workday. When approaching capacity, the agent performs a structured handoff — packing up its desk for the next shift.

### 6.2 Handoff Trigger

Context usage approaching threshold (e.g., 80% of window consumed). Detection mechanism TBD — could be token counting, turn counting, or model self-assessment.

### 6.3 Handoff Artefact

The outgoing agent produces a structured handoff document:

```markdown
# Handoff: Con — Session 2026-02-15T14:30

## Task
Implement user authentication for RAGlue admin panel

## Status
In progress — 70% complete

## What Was Done
- Created User model with email/password authentication
- Implemented session controller with login/logout
- Added authorization concern for admin-only routes
- Wrote migration for users table

## What Remains
- Password reset flow (email integration needed)
- Session timeout handling
- Tests for authorization concern

## Blockers / Notes
- Email provider not yet configured — may need to check with operator
- Found a potential issue with the existing Document model's user_id foreign key — needs migration

## Files Modified
- app/models/user.rb (new)
- app/controllers/sessions_controller.rb (new)
- app/controllers/concerns/authorization.rb (new)
- db/migrate/20260215_create_users.rb (new)
- config/routes.rb (modified)

## Suggested Next Steps
1. Pick up password reset flow
2. Resolve email provider question with operator
3. Write authorization tests before adding more protected routes
```

### 6.4 Handoff Mechanics

1. Outgoing agent writes handoff artefact to disk (project-level)
2. Outgoing agent session ends
3. New agent session spins up with same persona (Con)
4. New agent receives: persona identity + skill file + handoff artefact + task context
5. New agent continues from where the previous session left off

### 6.5 Separation of Concerns

| Type | Scope | Location | Lifespan |
|------|-------|----------|----------|
| **Handoff notes** | Today's work-in-progress | Project directory | Ephemeral — consumed by next session |
| **Skill file updates** | Durable capability growth | `~/.headspace/personas/` | Persistent — curated over time |
| **Task completion record** | What was delivered | Headspace state / logs | Persistent — audit trail |

---

## 7. Skill File Evolution

### 7.1 Self-Improvement

At session close (task complete or handoff), the agent may propose additions to its skill file. These represent durable learnings — not task-specific state.

**Example:** Con finishes a task that involved unexpected Stimulus controller work. Con proposes appending to `skill.md`:
> "Has working familiarity with Stimulus controllers from auth UI task (2026-02-15)"

### 7.2 Review / Curation

Skill file updates need guardrails to prevent bloat and drift.

**v1:** Agent proposes updates; operator reviews and approves/rejects.
**v2:** Updates append to a "pending" section; operator periodically curates.
**v3:** A curation step (automated or persona-driven) periodically summarises and prunes experience logs, keeping skill files under a target token budget (e.g., 200 tokens core + 300 tokens experience max).

### 7.3 Skill File Discipline

The skill file has two sections with different management approaches:

- **Core identity** — stable, operator-defined, rarely changes. The "who you are" section.
- **Learned experience** — append-only log that gets periodically summarised/pruned. The "what you've done" section.

Target total size: 300–500 tokens. Large enough to meaningfully prime the context, small enough to not waste it.

---

## 8. Concurrency & Resource Management

### 8.1 Agent Concurrency

Maximum concurrent agents is operator-configured (default: 3). This is a hard limit driven by practical considerations — cognitive load for the operator, system resources, API costs.

### 8.2 Pool Exhaustion

If all personas in a required pool are active, the task queues until a persona becomes available. The operator is notified.

### 8.3 Cross-Cutting Tasks

Some tasks span multiple skill domains. Options:

- **Assign to a generalist** (e.g., Mark) who can work across the stack
- **Decompose further** at the PM layer into domain-specific subtasks
- **Flag for operator** if the task can't be cleanly scoped to one domain

---

## 9. Integration with Existing Headspace Architecture

### 9.1 Domain Model Extension

The existing Headspace 3.1 domain model (Objective → Project → Agent → Task → Turn) extends as follows:

```
Persona (pool of named identities)
    │
    ├── role_type: workshop | pm | execution | qa
    │
    └── assigned to → Agent (1:1 while active)
                          │
                          ├── mode: workshop | execution
                          │
                          └── Task → Turn (existing model unchanged)
```

The Persona is a new first-class entity. The Agent gains a `persona_id` field and a `mode` field. Everything downstream (Task, Turn, state machine) is unchanged.

**Persona role types:**
- **workshop** — Robbo. Produces documents, not code. Collaborative with operator.
- **pm** — Gavin. Decomposes and assigns. Manages sequencing.
- **execution** — Con, Al, May, Mark. Builds things.
- **qa** — Verner. Writes and executes tests. Validates deliverables.
- **ops** — Leon. Monitors runtime, triages exceptions, drives remediation.

**Agent modes:**
- **workshop** — Collaborative, iterative, document-producing. Used by Robbo.
- **execution** — Task-scoped, code-producing. Used by everyone else.

### 9.2 State Model Impact

The existing Task state machine (idle → commanded → processing → awaiting_input → complete) is unaffected. Personas layer above this — they're about identity and skill loading, not execution mechanics.

One new state transition is added: **handoff** — triggered by context threshold, results in session teardown and fresh session spinup with same persona.

### 9.3 Config Extension

Existing `config.yaml` gains a `personas` section and `pools` section (see §5.2 and §5.4).

### 9.4 File System

New directory structure alongside existing Headspace config:

```
~/.headspace/
  config.yaml              # Existing — extended with persona/pool config
  personas/                # New
    robbo/
      skill.md
      experience.md
    gavin/
      skill.md
      experience.md
    con/
      skill.md
      experience.md
    al/
      skill.md
      experience.md
    may/
      skill.md
      experience.md
    mark/
      skill.md
      experience.md
    verner/
      skill.md
      experience.md
    leon/
      skill.md
      experience.md
  handoffs/                # New — ephemeral handoff artefacts
    {project}/
      {persona}-{timestamp}.md
```

---

## 10. Version Roadmap

### v1 — Personas, Pools & Workshop Mode (Operator as PM)
- Workshop mode as first-class Headspace concept (distinct from execution mode)
- Robbo as workshop partner — operator + Robbo produce specs
- Persona definitions in config
- Skill files on disk, loaded into agent context at spinup
- Pool-based persona selection (manual or auto-assign by skill domain)
- Operator manually decomposes tasks and assigns to agents (operator is Gavin)
- Human-legible agent identity in Headspace UI
- Verner writes and executes tests post-implementation
- Robbo reviews deliverables in a fresh workshop session

### v2 — Handoff & Skill Evolution
- Context threshold detection and structured handoff
- Handoff artefact generation and consumption
- Skill file update proposals from agents
- Experience log with manual curation
- Persona affinity (prefer familiar personas for follow-up work)

### v3 — PM Automation (Gavin)
- Gavin persona receives specs from Robbo, drafts task decomposition
- Operator review/approval gate before execution
- Gavin manages task sequencing and dependency ordering
- Gavin monitors team progress and flags blockers
- Escalation paths: Team → Gavin → Robbo → Operator
- Verner escalation path: Verner → Robbo → Operator

### v4 — Autonomous Teams
- Gavin operates with minimal operator intervention
- Automated skill file curation and pruning
- Cross-persona collaboration (Con flags frontend issue → routed to Al)
- Verner integrated into the execution loop (tests written in parallel with implementation)
- Team retrospectives — automated post-project analysis of what worked

### v5 — Ops & Auto-Remediation (Leon)
- Exception ingestion endpoint (HTTP POST, no SDK required)
- Deduplication and fingerprinting
- LLM-driven severity classification and root cause analysis
- Dashboard exception panel with real-time SSE updates
- macOS and email notifications
- Auto-remediation with operator approval gate
- Agent spawning for fixes, lifecycle tracking (NEW → RESOLVED)
- Post-fix verification through Verner
- Trusted project configuration for unattended low-severity fixes

---

## 11. Open Questions

1. **Handoff trigger mechanism:** Token counting vs turn counting vs model self-assessment? Each has tradeoffs in accuracy and implementation complexity.
2. **Skill file format:** Plain markdown as proposed, or structured YAML/TOML for machine-readability? Markdown is more natural for LLM consumption but harder to parse programmatically.
3. **Persona count:** How many personas per pool is optimal? Too few and you hit pool exhaustion; too many and the naming loses memorability.
4. **PM layer scope:** Should Gavin have visibility into agent progress (turn-level), or only task-level status? More visibility = better orchestration but more complexity.
5. **Skill file scope:** Global personas (shared across all projects) vs project-specific personas? Global is simpler; project-specific allows specialisation.
6. **Experience persistence:** How long before experience entries are pruned? Time-based? Token-budget-based? Manual only?

---

## 12. Relationship to External Patterns

This design draws from observed patterns in the agentic development ecosystem:

- **Claude Code Teams:** Validated the pattern that clean specs → good multi-agent execution (Maybell project, Feb 2026)
- **TD (Task-Driven) pattern:** Context limit detection and state summarisation for handoff
- **Sidecar pattern:** Companion process monitoring agent state
- **OpenClaw team skills:** Community convergence on role-based agent specialisation

The differentiation in Headspace's approach is the human-legible persona layer with persistent skill evolution — most multi-agent frameworks focus on functional routing without identity or learning.

---

## BMAD Decomposition Guidance

This document is the root artefact for the Agent Teams module. The following epic structure is suggested based on dependency ordering and the version roadmap:

| Epic | Scope | Dependencies | Approx. Version |
|------|-------|-------------|-----------------|
| **1. Persona System & Workshop Mode** | Persona config, skill files on disk, pool definitions, workshop as first-class mode, Robbo as workshop partner, basic persona selection | Headspace 3.1 core (Agent, Task, Turn model) | v1 |
| **2. QA Integration** | Verner persona, test-from-spec workflow, feedback loop between QA and execution team, escalation paths | Epic 1 | v1 |
| **3. Context Handoff** | Threshold detection, handoff artefact generation/consumption, session teardown and respawn with same persona, experience logging | Epic 1 | v2 |
| **4. Skill File Evolution** | Self-improvement proposals, experience log curation, token budget management, pending review workflow | Epic 1, Epic 3 | v2 |
| **5. PM Automation** | Gavin receives specs, drafts decomposition, operator approval gate, task sequencing, progress monitoring, escalation management | Epics 1–4 | v3 |
| **6. Autonomous Teams** | Minimal-intervention operation, automated curation, cross-persona collaboration, parallel QA, team retrospectives | Epics 1–5 | v4 |
| **7. Ops & Auto-Remediation** | Leon persona, exception ingestion endpoint, dedup/fingerprinting, LLM triage, dashboard panel, notifications, auto-remediation with approval gate, agent spawning for fixes, post-fix verification via Verner | Epics 1–2 (minimum), benefits from Epics 3–5 | v5 |

Each epic should be decomposed into sprints with clear acceptance criteria derived from the relevant sections of this document. The open questions in §11 should be resolved during sprint planning for the affected epics.

*Use this document as the single source of truth for deriving all downstream BMAD artefacts.*
