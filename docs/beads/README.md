# Beads: Overview & Adoption Plan for Claude Headspace

## Context

[Beads](https://github.com/steveyegge/beads) (`bd`) is a distributed, git-backed graph issue tracker designed for AI coding agents, created by Steve Yegge. This document summarises the project, evaluates its design decisions, and outlines which ideas Claude Headspace should adopt natively within its existing Python/Postgres/Flask architecture.

**We are not adopting Beads as a dependency.** We are studying its design and cherry-picking the concepts that fit our platform, implementing them natively.

---

## Part 1: Beads Overview

### What It Is

Beads provides persistent, structured memory for AI coding agents by replacing ad-hoc markdown plans with a dependency-aware task graph. It's a CLI tool (`bd`) that lives alongside a codebase and gives agents a way to track, decompose, and coordinate work across sessions.

- **Repository:** https://github.com/steveyegge/beads
- **Language:** Go (92%), with npm packaging
- **Backend:** Dolt (version-controlled SQL database) with JSONL for git portability
- **License:** MIT
- **Stats (Feb 2026):** 16.5k stars, 994 forks, 238+ contributors, 6,325+ commits
- **Latest release:** v0.52.0

### The Problem It Solves

AI agents lose context during extended tasks. They work from markdown files, forget what they've done, can't track dependencies between subtasks, and create merge conflicts when multiple agents operate concurrently. Beads addresses this with:

1. A proper command graph with dependencies and blocking semantics
2. Hash-based IDs that prevent merge collisions
3. Memory compaction that preserves context without consuming the full window
4. A `ready` command that answers "what should I work on next?"

### Architecture

Beads uses a two-layer data model:

```
CLI Command → Dolt (SQL) Write → Dolt Commit → JSONL Export → Git Commit
Git Pull → Auto-Import Detection → Dolt Update → Query Execution
```

- **Dolt** provides SQL semantics with cell-level merge and native branching
- **JSONL** provides git portability (the `.beads/issues.jsonl` file is committed to the repo)
- **Daemon mode** runs an RPC server for concurrent access; **direct mode** for single-agent use

Directory structure per project:
```
.beads/
├── dolt/           # Dolt database
├── issues.jsonl    # Git-portable issue data
├── metadata.json   # Config (prefix, settings)
└── .socket         # Daemon Unix socket
```

### Data Model

**Issues** (the core entity):

| Field | Purpose |
|-------|---------|
| `id` | Hash-based (e.g., `bd-a1b2`), adaptive length |
| `title` | Short description |
| `type` | bug, feature, task, epic, chore |
| `status` | open, in_progress, blocked, deferred, closed, tombstone, pinned |
| `priority` | 0 (critical) to 4 (backlog) |
| `description` | Detailed description |
| `acceptance_criteria` | Definition of done |
| `assignee` | Who's working on it |
| `spec_id` | Link to specification file |
| `external_ref` | Link to external tracker (gh-123, jira-PROJ-456) |
| `parent_id` | Hierarchical nesting (epic → command → subtask) |
| `notes`, `design` | Working notes, design decisions |

**Dependencies** (relationships between issues):

| Type | Semantics |
|------|-----------|
| `blocks` | Sequential — B waits for A to close |
| `parent-child` | Hierarchical blocking |
| `related` | Non-blocking association |
| `discovered-from` | Work discovered during other work |
| `conditional-blocks` | Error path — B runs only if A fails |
| `waits-for` | Fanout gate — B waits for all of A's children |

**Events** (audit trail): Every mutation is logged with actor, timestamp, and change details.

### Key Design Decisions

#### Hash-Based Adaptive IDs

Instead of sequential IDs (which collide when multiple agents create tasks concurrently), Beads generates short hex prefixes from UUIDs. The length adapts to database size:

- 0–500 issues: 4-char IDs (`bd-a1b2`)
- 501–1500 issues: 5-char IDs (`bd-a1b2c`)
- 1501+ issues: 6-char IDs

Collision resolution tries progressively longer hashes (base, base+1, base+2) with 10 nonces per tier. Generation takes ~300ns per ID.

#### `ready` Semantics

The `bd ready` command returns issues with no open blockers and no assignee — the answer to "what should I work on next?" Internally, this uses a materialised cache table (rebuilt on dependency/status changes) rather than recursive CTEs, achieving a 25x speedup on large databases.

#### Molecules (Workflow Templates)

Beads has a "chemistry" metaphor for reusable workflows:

- **Protos** (solid): Frozen templates — reusable epic structures with variables
- **Molecules** (liquid): Persistent instantiations — live work with dependency graphs
- **Wisps** (vapour): Ephemeral instantiations — throwaway exploration, garbage-collected

A molecule is just an epic (parent + children) with workflow semantics. Children are parallel by default; only explicit dependencies create sequence. Templates can be bonded together (sequential, parallel, conditional).

#### Memory Compaction

Closed issues accumulate detail that wastes context window. Beads implements tiered compaction:

- **Tier 1:** Recently closed — light summarisation
- **Tier 2–4:** Progressively more aggressive compression
- Agent-driven: the agent decides when and what to compact via `bd admin compact --analyze`
- Original detail is recoverable via `bd restore <id>`

#### Claim Semantics

`bd update <id> --claim` atomically sets assignee + transitions to `in_progress`. Fails if already claimed. Prevents two agents grabbing the same work.

#### Hierarchical Task Nesting

Issues support parent-child relationships via `parent_id`. Child IDs use dotted notation:

```
bd-a3f8       (epic)
bd-a3f8.1     (task)
bd-a3f8.1.1   (subtask)
```

### CLI Surface (Key Commands)

| Command | Purpose |
|---------|---------|
| `bd init` | Initialise Beads in a project |
| `bd ready` | Show unblocked, unassigned work |
| `bd create "Title" -t task -p 1` | Create an issue |
| `bd update <id> --claim` | Atomically claim work |
| `bd update <id> --status closed` | Close an issue |
| `bd close <id> --reason "text"` | Close with reason |
| `bd show <id>` | View issue details + audit trail |
| `bd list --status open --assignee Con` | Filtered query |
| `bd dep add <child> <parent>` | Add dependency |
| `bd dep tree <id>` | Visualise dependency tree |
| `bd stale --days 7` | Find stale issues |
| `bd admin compact --analyze` | Find compaction candidates |
| `bd mol pour <proto-id>` | Instantiate a workflow template |
| `bd sync` | Manual sync (export → commit → push) |

### Operational Modes

- **Standard:** Commands committed to the repo alongside code
- **Stealth** (`bd init --stealth`): Local-only, nothing committed
- **Contributor** (`bd init --contributor`): Routes planning to `~/.beads-planning`, keeping experimental work out of PRs

### External Integrations

Beads integrates with Claude Code (hooks), GitHub Copilot, Cursor, Aider, and Factory.ai — plus Jira, Linear, and GitLab for external tracker linking.

---

## Part 2: What We Adopt for Claude Headspace

### Why Not Adopt Beads Directly

| Concern | Detail |
|---------|--------|
| **Go binary dependency** | Headspace is Python/Flask. Shelling out to `bd` adds a process boundary, error handling complexity, and a second install requirement |
| **Dolt database** | Second database engine alongside Postgres. Different backup, migration, and operational story |
| **Git-backed storage** | Headspace is a centralised server, not distributed. We don't need JSONL portability or git-based sync |
| **Loss of control** | Adopting Beads means accepting their data model, CLI interface, and release cadence. Headspace needs tight integration with personas, priority scoring, and the dashboard |
| **CLI-only interface** | Beads is designed for terminal agents. Headspace has a web dashboard, SSE, voice bridge — the interaction surface is fundamentally different |

### What We Do Adopt

We implement these Beads concepts natively in Python/Postgres within the existing Headspace architecture.

#### 1. The Task/Command Rename

**Beads insight:** A "command" is a project-level work unit, not a single prompt→response cycle.

**Headspace change:** Rename the current `Task` model to `Command`. A Command is a single user instruction cycle within an Agent session (the current 5-state lifecycle: COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE). This frees "Task" to mean a project-level work unit.

**New hierarchy:**
```
Project → Command (project-level work) → Command (session-level execution) → Turn (individual exchange)
```

A single Task may span multiple Commands across multiple Agent sessions and Personas.

#### 2. Hash-Based Command IDs

**Beads insight:** Sequential IDs collide when multiple agents create tasks concurrently. Short hash-based IDs are human-readable and merge-safe.

**Headspace implementation:**
- Generate short hex prefixes from UUIDs (e.g., `hs-a1b2`)
- Adaptive length based on command count (4–6 chars)
- Collision resolution via progressive lengthening
- Standard integer PKs remain in Postgres for joins; hash IDs are the display/reference format

#### 3. Dependency Graph + `ready` Semantics

**Beads insight:** Commands have blocking relationships. The most valuable query is "what has no open blockers?" (`bd ready`).

**Headspace implementation:**
- `task_dependencies` join table with `blocker_command_id` and `blocked_command_id`
- Dependency types: `blocks` (sequential), `parent-child` (hierarchical), `related` (informational)
- `ready` query: tasks where status is open, no unresolved blockers, optionally filtered by assignee persona
- Materialised/cached result for dashboard performance (rebuild on dependency or status change)
- Dashboard integration: project cards show ready command count; PM persona (Gavin) uses this to assign work

#### 4. Hierarchical Task Nesting

**Beads insight:** Epics contain tasks which contain subtasks. Parent-child via self-referential FK with dotted notation for display.

**Headspace implementation:**
- `parent_id` self-referential FK on Command model
- Display format: `hs-a3f8.1.1` (dotted notation derived from hash + child index)
- Gavin (PM persona) creates epics from specs, decomposes into tasks, and agents may create subtasks during execution
- Dashboard shows collapsible hierarchy

#### 5. Claim Semantics

**Beads insight:** `--claim` atomically assigns + transitions to `in_progress`. Prevents double-assignment.

**Headspace implementation:**
- API endpoint for atomic claim: sets `assignee_persona_id` + transitions state to `in_progress` in a single transaction
- Row-level locking (`SELECT ... FOR UPDATE`) prevents race conditions
- Returns error if already claimed by another persona
- Gavin assigns, or personas self-claim from the ready pool

#### 6. Memory Compaction for Commands

**Beads insight:** Completed work accumulates detail that wastes context. Summarise and archive progressively.

**Headspace implementation:**
- Extend existing `SummarisationService` to generate Command-level completion summaries (currently only generates Command/Turn summaries)
- When a Command completes: LLM generates a compressed summary, full detail remains in Postgres but is excluded from context assembly
- Progressive compaction: recent completions keep more detail; older ones compress further
- Brain reboot integration: include task graph state + completion summaries in exported context

#### 7. Workflow Templates (Simplified Molecules)

**Beads insight:** Reusable epic structures with variables enable repeatable workflows.

**Headspace implementation (v2+):**
- Task templates: predefined epic/task/subtask structures stored as JSON in config or database
- Gavin instantiates templates when decomposing specs: "this is a standard API endpoint — use the API template"
- Simpler than Beads' chemistry metaphor: just templates with variable substitution, no proto/mol/wisp phases
- Templates evolve through use: skill file learning captures which templates work well

#### 8. Command States

**Beads insight:** Issues have clear status progression with meaningful states.

**Headspace implementation:**
- Command states: `backlog`, `ready`, `in_progress`, `blocked`, `review`, `done`, `deferred`
- `ready` is computed (no open blockers + not assigned), but can also be explicitly set
- `blocked` is auto-set when a blocking dependency is added
- State transitions are validated (e.g., can't go from `backlog` to `done` directly)
- Audit trail: every state change logged with actor, timestamp, reason (extends existing Event model)

### What We Skip

| Beads Feature | Why We Skip It |
|---|---|
| **Git-backed JSONL storage** | Postgres is richer for querying, aggregation, dashboard feeds. No distributed sync needed |
| **Dolt database** | Postgres + Alembic handles our migrations, versioning, and querying needs |
| **Daemon/RPC mode** | Headspace is already a running Flask server with API endpoints |
| **Stealth/contributor modes** | Not relevant to centralised server architecture |
| **External tracker integrations** (Jira, Linear, GitLab) | Out of scope; Headspace is the tracker |
| **Formula/chemistry metaphor** (protos, wisps, bonding) | Over-engineered for our needs; simple templates suffice |
| **CLI-first interface** | Our interface is the web dashboard + persona API + voice bridge |
| **Stale issue detection** | Already have StalenessService for session-level staleness; extend naturally |
| **Label system** | Use Postgres columns and tags; no need for label-based state dimensions |

---

## Part 3: Integration with Agent Teams Vision

### How Commands Flow Through the Team

```
Operator + Robbo (Workshop)
    │
    ▼ (Clean spec)
Gavin (PM Persona)
    │
    ├─ Creates Epic (hs-a3f8) from spec
    ├─ Decomposes into Commands (hs-a3f8.1, hs-a3f8.2, hs-a3f8.3)
    ├─ Sets dependencies (hs-a3f8.2 blocks hs-a3f8.3)
    └─ Assigns by skill domain (Con: backend, Al: frontend)
    │
    ▼
Con (Backend Developer Persona)
    │
    ├─ Claims hs-a3f8.1 (atomic claim)
    ├─ Works through multiple Commands (session-level)
    │   ├─ Command 1: "implement the auth endpoint"
    │   ├─ Command 2: "add input validation"
    │   └─ Command 3: "write tests"
    ├─ Hits context limit → handoff to fresh Con session
    │   └─ New session picks up hs-a3f8.1 (Task persists)
    └─ Completes → Command state: done, summary generated
    │
    ▼
Verner (QA Persona)
    │
    ├─ hs-a3f8.3 unblocked (dependency resolved)
    ├─ Claims and validates against acceptance criteria
    └─ Signs off → escalates to Robbo if issues found
    │
    ▼
Robbo (Review)
    └─ Reviews deliverables against spec intent
```

### Data Model Sketch

```sql
-- New: Project-level work unit
CREATE TABLE task (
    id              SERIAL PRIMARY KEY,
    hash_id         VARCHAR(8) UNIQUE NOT NULL,    -- e.g., 'hs-a1b2'
    project_id      INTEGER REFERENCES project(id),
    parent_id       INTEGER REFERENCES task(id),    -- hierarchy
    title           TEXT NOT NULL,
    description     TEXT,
    acceptance_criteria TEXT,
    type            VARCHAR(20) DEFAULT 'command',     -- epic, task, subtask, chore, bug
    state           VARCHAR(20) DEFAULT 'backlog',  -- backlog, ready, in_progress, blocked, review, done, deferred
    priority        SMALLINT DEFAULT 2,             -- 0=critical, 4=backlog
    assignee_persona_id INTEGER REFERENCES persona(id),
    created_by_persona_id INTEGER REFERENCES persona(id),
    spec_id         TEXT,                           -- link to spec/PRD file
    completion_summary TEXT,                        -- LLM-generated on completion
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Dependencies between tasks
CREATE TABLE task_dependency (
    id              SERIAL PRIMARY KEY,
    blocker_command_id INTEGER REFERENCES task(id) NOT NULL,
    blocked_command_id INTEGER REFERENCES task(id) NOT NULL,
    dep_type        VARCHAR(20) DEFAULT 'blocks',   -- blocks, parent_child, related
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(blocker_command_id, blocked_command_id)
);

-- Renamed: Session-level execution unit (currently called Task)
-- ALTER TABLE task RENAME TO command;
-- command.command_id (FK → command) links execution to project-level work
```

### Dashboard Integration

- **Project cards:** Show ready command count, in-progress tasks by persona, blocked count
- **Command board view:** Kanban columns by state (backlog → ready → in_progress → review → done)
- **Dependency visualisation:** Simple tree/graph view per epic
- **Priority scoring enhancement:** Use task priority + dependency graph position + objective alignment
- **Persona workload:** Which personas have what claimed, what's ready for each skill domain

---

## Part 4: Implementation Sequence

This work spans multiple epics and depends on the Agent Teams foundation (personas, organisations). Suggested ordering:

1. **Task/Command rename** — Mechanical refactor of existing model/services/routes/tests. No new features, just terminology alignment. Can be done independently.

2. **Command model + dependency graph** — New model, join table, basic CRUD API. Core schema from the data model sketch above.

3. **Hash ID generation** — Utility service for adaptive hash IDs. Applied to Command model.

4. **Ready query + claim semantics** — API endpoints for `ready` (filtered by persona/project) and atomic `claim`. Dashboard integration.

5. **Task ↔ Command linking** — Add `command_id` FK to Command (renamed Task). Connect session-level execution to project-level work.

6. **Dashboard command board** — Kanban view for project-level tasks. Dependency tree visualisation. Ready/blocked indicators.

7. **Command-level summarisation** — Extend SummarisationService for project-level command completion summaries. Memory compaction on older completed tasks.

8. **Workflow templates** — Reusable epic/task structures. Gavin instantiates them during spec decomposition.

9. **Priority scoring evolution** — Incorporate task priority, dependency position, and blocking status into the existing priority scoring algorithm.

Items 1–5 are foundational. Items 6–9 build on top and integrate with the Agent Teams persona system as it matures.

---

## References

- [Beads repository](https://github.com/steveyegge/beads)
- [Beads architecture doc](https://github.com/steveyegge/beads/blob/main/docs/ARCHITECTURE.md)
- [Beads adaptive IDs](https://github.com/steveyegge/beads/blob/main/docs/ADAPTIVE_IDS.md)
- [Beads molecules](https://github.com/steveyegge/beads/blob/main/docs/MOLECULES.md)
- [Beads CLI reference](https://github.com/steveyegge/beads/blob/main/docs/CLI_REFERENCE.md)
- [Headspace platform vision](../conceptual/headspace-platform-vision.md)
- [Agent teams functional outline](../conceptual/headspace-agent-teams-functional-outline.md)
- [Agent teams alignment analysis](../workshop/agent-teams-alignment-analysis.md)
- [Organisation ERD](../workshop/erds/headspace-org-erd-full.md)
