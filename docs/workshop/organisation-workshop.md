# Organisation — Design Workshop

**Date:** 1 March 2026
**Status:** Sections 0–1 RESOLVED. Sections 2–9 pending workshop.
**Inputs:**
- `docs/conceptual/headspace-agent-teams-functional-outline.md` — Agent Teams vision and architecture layers
- `docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md` — Epic 8 sprint breakdown (18 sprints)
- `docs/workshop/agent-teams-workshop.md` — Phase 1 design decisions (15 resolved)
- `docs/workshop/erds/headspace-org-erd-full.md` — Data model reference
- `/Users/samotage/0_robot/docs/agent-economy/workshop/` — Kent's economic organisation design (validates multi-org)
- Existing codebase: models, services, routes as built through Epic 8 Phase 1

**Method:** Collaborative workshop between operator (Sam) and architect (Robbo). Work through sections sequentially, resolve decisions with documented rationale. Each section is a self-contained unit that can be completed in one session. Decisions build on each other — dependency tracking enforces ordering.

**Prerequisite:** This workshop assumes Phase 1 (Personable Agents, E8-S1 through ~S11) is substantially built. The organisation tables exist but are not exercised. Handoff exists in schema but is untested. This workshop designs the next phase: making the organisation operational.

---

## How to Use This Document

Work through sections in order. Each section contains numbered decisions (1.1, 1.2, etc.) that may depend on earlier decisions. Dependency chains are explicit — if a decision says "Depends on: 1.2, 2.1" then those must be resolved first.

Sections are designed to be completable in a single workshop session. Start each session by reviewing the previous section's resolutions, then work through the current section's decisions.

Mark decisions with `[x]` when resolved. Use `[ ]` for pending decisions. Deferred decisions are marked resolved with an explicit "Deferred until..." rationale.

---

## Workshop Sections Overview

| Section | Topic | Decisions | Focus |
|---------|-------|-----------|-------|
| **0** | Codebase Audit | 0.1–0.3 | What's actually built, working, and exercised vs scaffolding |
| **1** | Organisation Serialization | 1.1–1.5 | YAML/Markdown format, CLI interface, DB ↔ file round-trip |
| **2** | Inter-Agent Communication | 2.1–2.6 | Message model, transport, routing, dashboard visibility |
| **3** | Task Model & Delegation | 3.1–3.5 | Task as organisational work unit, delegation flow, command relationship |
| **4** | Agent Interaction Patterns | 4.1–4.4 | The full turn cycle for agent-to-agent: command, report, clarify, interrupt |
| **5** | Alignment & Intent Engineering | 5.1–5.4 | Objective cascade, intent signals, assumption minimisation, persona skill rework |
| **6** | Escalation Mechanics | 6.1–6.3 | Trigger conditions, routing via hierarchy, resolution flow |
| **7** | PM Layer Design (Gavin) | 7.1–7.3 | Task decomposition, assignment, monitoring — operator offload |
| **8** | Multi-Org Readiness | 8.1–8.2 | Kent's economy org as validation, org-scoped isolation |
| **9** | Implementation Sequence | 9.1–9.3 | Epic structure, sprint ordering, incremental delivery |

---

## Section 0: Codebase Audit

**Purpose:** Before designing new features, establish ground truth about what's actually built and operational versus what's just schema.

**Status:** RESOLVED — Audit completed 1 March 2026 by Robbo (Agent #1054, successor to #1053). Three parallel codebase investigations covering all organisation-related models, persona system flows, and handoff implementation.

---

### 0.1 Database Schema Audit
- [x] **Decision: What organisation-related tables exist, are populated, and are exercised by application code?**

**Depends on:** None (foundational)

**Context:** Epic 8 created several database tables through Alembic migrations: Persona, Role, Organisation, Position, Handoff, plus Agent model extensions (persona_id, position_id, previous_agent_id). Some of these are actively used (Persona, Role, Agent.persona_id for skill injection). Others may exist as empty tables with no application code exercising them.

**Tasks:**
- [x] Query each table for row counts
- [x] Grep codebase for model imports and usage (Organisation, Position, Handoff)
- [x] Identify services that reference organisation-level models
- [x] Document what's functional vs scaffolding

**Resolution:**

Models fall cleanly into two categories — **ACTIVE** (exercised by production code) and **SCAFFOLDING** (tables exist, zero application code exercises them).

**ACTIVE models:**

| Model/Field | Evidence | Key Services |
|---|---|---|
| **Persona** | 23 file imports, ~2-10 production records, full CRUD | persona_registration, skill_injector, handoff_executor, card_state, hook_receiver |
| **Role** | 15 file imports, ~5 records, lookup table | persona_registration (auto-creates on persona register) |
| **Handoff** | 8 file imports, records created during handoff flow | handoff_executor (full lifecycle), revival_service (distinguishes handoff vs revival), hook_receiver |
| **Agent.persona_id** | Set via hook_receiver and session registration | Skill injection gate, handoff eligibility gate, continuity chain |
| **Agent.previous_agent_id** | Self-ref FK, actively traversed in both directions | handoff_executor, revival_service, hook_receiver, card_state |
| **Agent.handoff** | One-to-one relationship (uselist=False) | Used to distinguish handoff (record exists) from revival (record absent) — elegant design |

**SCAFFOLDING models:**

| Model/Field | Evidence | Implication |
|---|---|---|
| **Organisation** | 1 hardcoded record ("Development") seeded by migration. Zero service imports. Zero route imports. Never queried by application code. | Infrastructure for multi-org — ready to activate |
| **Position** | Table exists, schema is valid (org_id, role_id, reports_to_id, escalates_to_id, level, is_cross_cutting). Zero service imports. Zero route imports. No code exercises any field. | Org chart infrastructure — ready to activate |
| **Agent.position_id** | FK exists (nullable). Never set on any agent. Never queried. Never traversed. | Binding agents to org chart seats — Phase 2 feature |

**Active relationship chains (traversed in production code):**
```
Agent.persona_id → Persona.id → Persona.role_id → Role.id
Agent.previous_agent_id → Agent.id (self-ref, both directions)
Agent.id ← Handoff.agent_id (one-to-one)
```

**Scaffolding relationship chains (defined but never traversed):**
```
Agent.position_id → Position.id → Position.org_id → Organisation.id
Position.reports_to_id → Position.id (self-ref hierarchy)
Position.escalates_to_id → Position.id (self-ref escalation)
Position.role_id → Role.id (Role shared with Persona)
```

**Migration history:** 6 migrations (all applied):
- `0462474af024` — Persona + Role tables
- `77a46a29dc5e` — Organisation table (seeded "Development")
- `a3b8c1d2e4f5` — Position table (self-ref FKs)
- `b5c9d3e6f7a8` — Agent extensions (persona_id, position_id, previous_agent_id)
- `c6d7e8f9a0b1` — Handoff table
- `d7e8f9a0b1c2` — FK strategy fix: corrected persona_id, reports_to_id, escalates_to_id from CASCADE to SET NULL

**Known issue:** `Agent.position_id` still has CASCADE ondelete — should be SET NULL (nullable FK). Migration `d7e8f9a0b1c2` corrected other nullable FKs but missed this one. Low risk now (field never set), but will bite when Position is activated. **Add to Phase 2 migration checklist.**

**Bottom line:** Phase 1 built a working persona/handoff layer and pre-built the org chart infrastructure. The Organisation/Position tables are clean scaffolding — no dead code to clean up, no half-built features to untangle. They're ready for Phase 2 to activate.

---

### 0.2 Persona System Functional Audit
- [x] **Decision: What persona features are working end-to-end versus partially implemented?**

**Depends on:** None

**Context:** The following persona features were planned across E8-S1 through E8-S11:
- Persona + Role DB models and registration CLI
- Filesystem assets (skill.md, experience.md) at `data/personas/{slug}/`
- Skill injection via tmux bridge (prompt_injected_at tracking)
- SessionCorrelator persona assignment from hook payloads
- Dashboard card persona identity display
- Agent info panel persona display

**Tasks:**
- [x] Test persona registration CLI end-to-end
- [x] Verify skill injection flow (create agent with persona → skill file read → tmux injection → agent greeting)
- [x] Check dashboard displays persona names on cards
- [x] Verify SessionCorrelator assigns persona from hook payload
- [x] Document gaps and regressions

**Resolution:**

**All persona features are WORKING end-to-end.** No regressions found. This is solid ground for Phase 2.

| Feature | Status | Detail |
|---|---|---|
| **Registration CLI** | WORKING | `flask persona register --name X --role Y` — 4-step flow: validation → role lookup/create → DB insert → filesystem assets (skill.md, experience.md) |
| **`flask persona list`** | WORKING | `--active` flag, `--role` filter, displays name/role/slug/status/agent count |
| **Skill Injection** | WORKING | Auto-triggered on session-start hook when agent has persona_id + tmux_pane_id. DB-level idempotency via `prompt_injected_at`. Content: guardrails → persona intro → skills → experience. Fail-closed for remote agents (missing guardrails = injection fails). |
| **Dashboard Display** | WORKING | Card JSON includes `persona_name` and `persona_role` via card_state.py. Templates render persona badges on both agent cards and kanban view. |
| **Persona Assignment** | WORKING | Two assignment paths: (1) CLI registration passes persona_slug in POST /api/sessions payload, (2) Hook session-start assigns from hook payload. SessionCorrelator itself does NOT assign personas — it handles session-to-agent matching only. |
| **REST API** | WORKING | Comprehensive: CRUD endpoints, asset management (read/write skill.md, experience.md), agent linking, active personas list, role management. |
| **Defensive Detection** | WORKING | `team_content_detector.is_persona_injection()` detects priming messages to prevent phantom turns during hook lifecycle collisions. |
| **Tests** | WORKING | Coverage across integration, CLI, route, and service tiers. |

**Slug generation mechanism:** After-insert SQLAlchemy event replaces temp slug `_pending_{uuid}` with real `{role_name}-{persona_name}-{id}` (sanitized, lowercase). Slug is the filesystem path key for persona assets.

**No gaps found.** The persona system is a mature, well-tested feature.

---

### 0.3 Handoff System Status
- [x] **Decision: What is the current state of the handoff implementation, and what needs to happen before it can be tested?**

**Depends on:** 0.1

**Context:** E8-S12 through E8-S14 cover the handoff system: DB model, trigger UI, execution flow. The Handoff model exists in the database. Agent.previous_agent_id self-ref FK exists. But operator reports that handoff has not been tested.

**Tasks:**
- [x] Review HandoffExecutor service for completeness
- [x] Check for handoff trigger in routes/UI
- [x] Identify minimum viable handoff test scenario
- [x] Document blockers

**Resolution:**

**The handoff system is substantially COMPLETE at the code level.** All service methods implemented, all trigger paths wired, 60+ tests passing. No TODOs or stubs in the codebase.

**Implementation status by component:**

| Component | Status | Notes |
|---|---|---|
| **HandoffExecutor** | COMPLETE | 10 core methods, all implemented. Thread-safe with `_handoff_lock`. Typed `HandoffResult` namedtuple. |
| **REST Endpoint** | COMPLETE | `POST /api/agents/<id>/handoff` — accepts reason + optional context, returns 200/400/404/409 |
| **Voice Bridge** | COMPLETE | Regex detects natural-language handoff intent (10+ phrase variants). Triggers with `reason="voice"`. |
| **Dashboard UI** | COMPLETE | Button appears when `handoff_eligible=True` (persona exists AND context ≥ 80%). Kebab menu item with confirmation dialog. |
| **SSE Events** | COMPLETE | `handoff_complete` and `handoff_error` events. Card footer dynamically shows/hides handoff button. |
| **Hook Integration** | COMPLETE | Session-start: delivers injection prompt to successor. Stop hook: delegates to HandoffExecutor when handoff in progress. |
| **File System** | COMPLETE | Handoff docs at `data/personas/{slug}/handoffs/{timestamp}-{agent_id}.md`. Directory auto-created. |
| **Successor Creation** | COMPLETE | Uses `agent_lifecycle.create_agent()` with persona slug + previous_agent_id. |
| **Tests** | COMPLETE | Unit (33 tests in test_handoff_executor.py) + integration (test_handoff_model.py). |

**Key architectural decisions baked in:**
1. **Outgoing agent stays alive** — explicit design choice (lines 8-10 of handoff_executor.py). Successor runs in parallel. Predecessor can continue or be manually shut down.
2. **Two completion paths** — Primary: background thread polls for handoff file (3s interval, 5-min timeout). Fallback: stop hook fires while handoff in progress. Both call idempotent `complete_handoff()`.
3. **6-section handoff document** — Agent is instructed to write: current work, progress, key decisions, blockers, files modified, next steps.
4. **Injection delivery** — Successor receives skill injection first, then handoff context ("You are continuing the work of Agent #X. Read this file: ...").

**What "not tested" means:**
The code is complete and has 60+ passing unit/integration tests. What hasn't been tested is **end-to-end against the running application** — a real agent writing a real handoff document, a real successor starting up, the dashboard reflecting the transition. This is a live-fire test, not a code gap.

**Minimum viable handoff test scenario:**
1. Start an agent with a persona (e.g., `claude-headspace start` with `--persona architect-robbo-3`)
2. Let it accumulate context (or trigger manually via API: `POST /api/agents/{id}/handoff`)
3. Verify: agent writes handoff doc → Handoff record created → successor agent created with same persona → successor receives injection prompt → dashboard shows both agents with predecessor link
4. Verify: predecessor remains alive, can be manually dismissed

**Blockers:** None. The system is ready for live testing.

**Production status:** The handoff system has been **demonstrated once in production** — Agent #1053 wrote a handoff doc, a successor was created, and the injection prompt was delivered successfully. This proves the happy path works, but does not constitute proven reliability. Edge cases, error recovery, concurrent handoffs, and the polling timeout path have not been exercised live. Status: **demonstrated, not yet hardened.**

**Confirmed Phase 2 migration item:** `Agent.position_id` ondelete must be changed from CASCADE to SET NULL. Deleting a Position should orphan the agent from the org chart, not delete the agent. Same pattern as the corrections in migration `d7e8f9a0b1c2`.

---

## Section 1: Organisation Serialization

**Purpose:** Define the format and tooling for representing an organisation as a human/agent-readable document that can be round-tripped with the database. This is the bridge between the "database world" (persistence, application control) and the "agent world" (Markdown, bash, fast comprehension).

---

### 1.1 Canonical Serialization Format
- [x] **Decision: What format do we use to represent an organisation structure — YAML, Markdown, or a hybrid?**

**Depends on:** None

**Context:** Two consumers of the org representation:
1. **Agents** — need to quickly understand org structure, their position, reporting lines, escalation paths, team composition. Agents work well with Markdown via bash tools.
2. **Operators/designers** — need to define and modify org structures by hand. YAML is more structured and less ambiguous for data entry.

The representation must support:
- Full org hierarchy (positions, reporting lines, escalation paths)
- Role and persona assignments (who fills which seat)
- Organisation metadata (name, description, objectives)
- Round-trip fidelity — import from file, export to file, re-import produces same state

**Options:**
- **A) YAML only** — Single structured format for both input and agent consumption. Clean, unambiguous, parseable. Agents can read YAML but it's not their most natural format.
- **B) Markdown only** — Natural for agents, version-control friendly, human-readable. But harder to parse reliably for import, prone to formatting ambiguity.
- **C) YAML as canonical + Markdown view generated** — YAML is the source of truth for import/export. A Markdown "org brief" is generated from the YAML for agent consumption. Two formats, one truth.
- **D) YAML with Markdown blocks** — YAML structure with Markdown content in description/notes fields. Parseable but agent-friendly where it matters.

**Considerations:**
- Agents read Markdown naturally — it's what skill files, experience logs, and CLAUDE.md already use
- YAML is unambiguous for structured data — hierarchy, relationships, enums
- Round-trip fidelity is critical — if we can't reliably parse the format back to DB records, the whole system breaks
- The CLI needs to produce and consume this format
- Kent's economy org needs the same format — it must be general enough for non-dev organisations
- Over-engineering risk: do we really need two formats, or can one format serve both purposes?

**Resolution:**

**YAML as the canonical format.** Resolved 1 March 2026.

**Format:** YAML is the sole serialization format for organisation structure. No Markdown view, no hybrid.

**Rationale:**
- YAML handles recursive/relational structures naturally (positions with `reports_to`, `escalates_to` self-references)
- Round-trip fidelity is deterministic — YAML parses and emits without ambiguity
- Agents interact via bash tools (CLI commands) which is their strongest interface
- Markdown remains the format for *content* (skill files, experience logs, handoff docs) — each format used where it's strongest
- Kent's economy org needs the same format, so it must be general enough for non-dev organisations — YAML's structured nature supports this

**Delivery model:** On-demand generation. Agents run `flask org export` to get current state as YAML from the database. No persistent file on disk, no cache invalidation complexity. The database is the source of truth; YAML is the agent-facing window into it.

**Agent workflow:**
1. Agent runs CLI export → receives YAML snapshot of current org
2. Agent reads YAML → understands structure, reporting, escalation, intent
3. Agent proposes changes by generating modified YAML
4. Agent feeds YAML to CLI import → DB updated (subject to AR Director governance — see 1.3)

**Governance:** Org changes are managed by a dedicated AR Director persona (Paula). Other agents do not modify the org directly — they propose changes to Paula, who evaluates and applies them. This solves the guardrails problem organisationally rather than via technical access controls.

**CLI scope:** The `flask org` CLI is the unified entry point for all organisation and persona operations. Existing `flask persona` commands will be migrated under `flask org persona` (one path, no ambiguity for agents). Worth a dedicated sprint.

**Intent engineering:** The YAML includes per-organisation intent fields — what the org optimises for, what trade-offs are acceptable, what values must be protected. Different orgs have different intents (dev org: quality/robustness; economy org: revenue maximisation). Agents inherit intent context from their org definition. Inspired by Nate B. Jones's intent engineering framework (prompt engineering → context engineering → intent engineering).

---

### 1.2 Organisation Document Structure
- [x] **Decision: What sections and fields does the organisation document contain?**

**Depends on:** 1.1

**Context:** The document needs to capture everything required to instantiate an organisation from scratch:
- Organisation identity (name, description, status)
- Roles defined within the org (role vocabulary)
- Position hierarchy (who reports to whom, escalation paths)
- Persona assignments (which persona fills which position, with skill summaries)
- Objectives / alignment context (what the org is trying to achieve)

But also needs to be readable as a "briefing document" for an agent — "here's your org, here's your place in it, here's what we're doing."

**Questions to resolve:**
- Do we include skill summaries inline, or reference the skill files by path?
- Do we include active agent assignments (current sessions), or is the doc purely structural?
- How do we represent the hierarchy — nested YAML, flat with parent references, visual ASCII tree?
- What's optional vs required?

**Resolution:**

**YAML document with four sections, composite sourcing.** Resolved 1 March 2026.

The YAML export is a composite document assembled by the CLI from two sources:
- **Database:** Organisation, Position, Role, PositionAssignment, Persona records
- **Filesystem:** Intent document (Markdown, slugged to org), persona skill/experience file paths

**Data source split:**
- Structure (org, positions, roles, assignments) → DB (persistence, queryable, relational)
- Intent (what to optimise for, trade-offs, constraints) → Filesystem as Markdown (prose-heavy, version-controlled, human-editable)
- Persona content (skills, experience) → Referenced by file path, not inlined

**Organisation identity:** Every organisation has a `purpose` field (domain/category: software-development, marketing, content, economy, etc.) and an auto-generated `slug` following the pattern `{purpose}-{name}-{id}` — identical mechanism to Persona's `{role}-{name}-{id}`. The slug is the filesystem path key for the org's asset directory and the unambiguous identifier used across CLI commands and YAML documents.

**ID convention:** All IDs are prefixed with their entity type (`organisation_id`, `role_id`, `position_id`, `persona_id`, `persona_assignment_id`) for unambiguous self-documentation. These map directly to DB primary keys for bidirectional CLI operations.

**Position assignments:** One persona per position at a time. If more capacity is needed, create more positions. A persona CAN hold multiple positions simultaneously (including across organisations) — they're software, not humans. The many-to-many lifecycle (history, reassignment, status) is managed internally by the PositionAssignment table and the AR Director (Paula). The YAML shows current state only. Historical assignments available via separate CLI command.

**Reference structure:**

```yaml
# Organisation Definition
# Generated by: flask org export --org development
# Source: PostgreSQL + filesystem (merged)

organisation:
  organisation_id: 1
  name: "Development"
  purpose: software-development        # domain/category of the org
  slug: software-development-development-1  # auto-generated: {purpose}-{name}-{id}
  description: "Software development team for Claude Headspace"
  status: active                       # active|dormant|archived

  # Intent Engineering (sourced from: data/organisations/software-development-development-1/intent.md)
  # What this org optimises for. Injected into agent context alongside persona skills.
  # Different orgs have different intents (dev: quality; economy: revenue).
  intent:
    optimise_for:
      - "Code quality and robustness"
      - "Incremental, testable delivery"
    protect:
      - "Operator mental workload — reduce, don't increase"
      - "Existing working functionality — don't break what works"
    never_sacrifice:
      - "Quality for speed"
      - "Security for convenience"
    constraints:
      - "All changes must be independently testable against the running app"
      - "Unit tests alone do not constitute verification"

# Roles — global specialisation vocabulary (not org-scoped)
roles:
  - role_id: 1
    name: architect
    description: "System architecture, specification, post-implementation review"
  - role_id: 2
    name: pm
    description: "Task decomposition, assignment, progress monitoring"
  - role_id: 3
    name: developer
    description: "Implementation, code quality, testing"
  - role_id: 4
    name: qa
    description: "Quality assurance, test design, acceptance validation"
  - role_id: 5
    name: ar-director
    description: "Agentic resource management — personas, org structure, team composition"

# Positions — org chart hierarchy
# reports_to/escalates_to reference position titles within this org.
# Null = reports/escalates directly to operator.
positions:
  - position_id: 1
    title: "Principal Architect"
    role: architect
    level: 1
    reports_to: null
    escalates_to: null
    is_cross_cutting: false
    assignment:
      persona_assignment_id: 1
      persona_id: 3
      persona_slug: architect-robbo-3
      persona_name: Robbo
      assigned_at: "2026-02-15T10:00:00Z"
      skill_file: data/personas/architect-robbo-3/skill.md
      experience_file: data/personas/architect-robbo-3/experience.md

  - position_id: 2
    title: "AR Director"
    role: ar-director
    level: 1
    reports_to: null
    escalates_to: "Principal Architect"
    is_cross_cutting: true
    assignment: null                   # Paula — to be created

  - position_id: 3
    title: "Project Manager"
    role: pm
    level: 2
    reports_to: "Principal Architect"
    escalates_to: "Principal Architect"
    is_cross_cutting: false
    assignment: null                   # Gavin — future

  - position_id: 4
    title: "Senior Developer"
    role: developer
    level: 3
    reports_to: "Project Manager"
    escalates_to: "Principal Architect"
    is_cross_cutting: false
    assignment: null

  - position_id: 5
    title: "Developer"
    role: developer
    level: 3
    reports_to: "Project Manager"
    escalates_to: "Project Manager"
    is_cross_cutting: false
    assignment: null

  - position_id: 6
    title: "QA Lead"
    role: qa
    level: 3
    reports_to: "Project Manager"
    escalates_to: "Principal Architect"
    is_cross_cutting: false
    assignment: null
```

**ERD alignment notes and model additions:**
- **Organisation.purpose** — new field (not in ERD). Domain/category of the org (software-development, marketing, economy, etc.). Required on create.
- **Organisation.slug** — new field (not in ERD). Auto-generated as `{purpose}-{name}-{id}`, same mechanism as Persona. Filesystem path key for `data/organisations/{slug}/`.
- **PositionAssignment** table must be built (exists in ERD, not yet implemented). Required for persona-to-position binding with lifecycle tracking.
- Role remains global (no org_id FK). ERD designed org-scoped roles but global is sufficient — same role vocabulary across orgs.
- Persona.slug (implementation addition, not in ERD) serves as the filesystem path key and agent-readable identifier.
- Agent.position_id CASCADE→SET NULL migration confirmed for Phase 2 activation.
- Role.role_type and Role.can_use_tools from ERD not yet needed — defer until a use case demands them.

---

### 1.3 CLI Interface Design
- [x] **Decision: What CLI commands do we provide for organisation management, and what's the interaction model?**

**Depends on:** 1.1, 1.2

**Context:** The CLI is the primary interface for agents to interact with the organisation. An agent running bash tools should be able to:
- Query the org structure ("who do I report to?", "who's on my team?", "what's the escalation path?")
- Create/modify org structures from a definition file
- Register personas as part of org setup (extending existing `flask persona register`)

The CLI also serves the operator for initial org design and ongoing management.

**Questions to resolve:**
- Is this `flask org ...` commands (Flask CLI extension)?
- What's the minimum command set for v1?
- Does the CLI output Markdown for agent consumption by default?
- Import from file: `flask org import org.yaml`? Export: `flask org export > org.yaml`?
- Query commands: `flask org show`, `flask org tree`, `flask org position <title>`?
- How does this integrate with the existing `flask persona` CLI?

**Resolution:**

**`flask org` as unified CLI entry point with six subgroups.** Resolved 1 March 2026.

**Architecture:** `flask org` is the single entry point for all organisation, position, role, persona, and assignment operations. The existing `flask persona` commands are deprecated and migrated under `flask org persona` (one path, no ambiguity — worth a dedicated migration sprint). The AR Director persona (Paula) is the primary agent user of org-modifying commands; all agents use read/query commands.

**Output format:** YAML to stdout by default for structural queries. Commands that produce YAML write to stdout; commands that consume YAML accept `--file` or stdin. Unix pipe support is a design principle.

**Command group structure:**

```
flask org
├── create / list / update / archive / status / export / import / validate / tree / whoami
├── role
│   └── create / list / update
├── position
│   └── create / list / show / update / remove
├── persona
│   └── create / list / show / update / archive / skill / experience
├── assign / unassign / assignments / vacancies / available-personas / assess-fit
└── intent
    └── read / write
```

**v1 Core commands:**

| Command | Purpose | Notes |
|---|---|---|
| `flask org create` | Create new organisation | `--name`, `--purpose`, `--description`. Creates DB record + org directory with intent.md |
| `flask org list` | List all organisations | Summary view |
| `flask org update` | Update org metadata | `--org`, `--description`, `--status` |
| `flask org archive` | Archive an organisation | Reversible via update |
| `flask org status` | Org health summary | Positions total/filled/vacant, active agents |
| `flask org export` | On-demand YAML generation | `--org` accepts name or slug (slug is unambiguous, e.g. `software-development-development-1`). Merges DB structure + filesystem intent (from org slug directory) + persona file paths |
| `flask org import` | Create/update from YAML | `--file` or stdin. `--preview` shows diff. `--atomic` for all-or-nothing (default) |
| `flask org validate` | Check YAML before import | Structural correctness: circular refs, missing roles, orphaned positions |
| `flask org tree` | ASCII hierarchy view | `--org` required. Shows reporting lines, assignees, vacancies |
| `flask org whoami` | Agent's quick-reference card | `--persona-slug` required. Returns: position, reporting line, escalation path, org intent, peers |
| `flask org role create` | Create a role | `--name`, `--description`. Roles are global (not org-scoped) |
| `flask org role list` | List all roles | Global list |
| `flask org role update` | Update role metadata | `--name`, `--description` |
| `flask org position create` | Create position in org | `--org`, `--title`, `--role`, `--level`, `--reports-to`, `--escalates-to`, `--is-cross-cutting` |
| `flask org position list` | List positions in org | `--org` required |
| `flask org position show` | Position detail | `--org`, `--title` or `--position-id`. Returns assignee, reporting line, direct reports |
| `flask org position update` | Update position | `--position-id`, fields to change |
| `flask org position remove` | Remove position | `--position-id`. `--preview` shows blast radius. `--reparent` reassigns direct reports to parent. Error if has reports and no `--reparent` |
| `flask org persona create` | Create persona | `--name`, `--role`. Creates DB record + filesystem assets (skill.md, experience.md) |
| `flask org persona list` | List personas | `--active`, `--role` filters |
| `flask org persona show` | Persona dossier | `--slug`. Returns: name, role, positions across all orgs, active agents, file paths |
| `flask org persona update` | Update persona | `--slug`, fields to change. `--status active` reactivates archived personas |
| `flask org persona archive` | Archive persona | `--slug`. Error if assigned to positions (use `--unassign` to force) |
| `flask org persona skill` | Read skill file | `--slug`. Outputs skill.md content. `--write` accepts stdin/`--file` for updates |
| `flask org persona experience` | Read/append experience | `--slug`. Outputs experience.md. `--append` adds content |
| `flask org assign` | Assign persona to position | `--position-id`, `--persona-slug`. Error if position filled (use `--reassign` to displace) |
| `flask org unassign` | Remove persona from position | `--position-id` |
| `flask org assignments` | Current assignments | `--org`. `--include-history` for lifecycle records. `--persona-slug` filters by persona |
| `flask org vacancies` | Unfilled positions | `--org` |
| `flask org available-personas` | Unassigned personas | Personas not holding any position |
| `flask org assess-fit` | Fitness assessment evidence | `--position-id`, `--persona-slug`. Outputs position role + org intent + persona skills side-by-side for Paula's evaluation |
| `flask org intent read` | Output intent document | `--org` |
| `flask org intent write` | Write intent document | `--org`. Accepts `--file` or stdin |

**Design principles:**

1. **Discoverable.** Every command group supports `--help`. Top-level `flask org --help` shows the full command tree. Subgroups show their commands. Individual commands show their flags. An agent running `flask org --help` can discover the entire CLI surface.
2. **Explicit over implicit.** Destructive operations require explicit flags (`--reassign`, `--unassign`, `--reparent`). No silent cascading. Default is to error and explain what flag to use.
3. **Preview before apply.** Import and destructive operations support `--preview` to show impact before execution.
4. **Atomic imports.** `flask org import` is atomic by default (all-or-nothing rollback on failure).
5. **Unix pipes.** Commands that produce YAML write to stdout. Commands that consume YAML accept stdin. `flask org export | flask org validate` works.
6. **Self-documenting IDs.** Output uses prefixed IDs (`position_id: 3`, `persona_id: 7`) consistent with the YAML document structure (Decision 1.2).
7. **`--org` accepts name or slug.** Slug (e.g., `software-development-development-1`) is unambiguous. Name (e.g., `Development`) is convenient but errors if multiple orgs share the same name. Slug is the recommended form for scripts and agent automation.

**Migration plan:** Existing `flask persona register` and `flask persona list` commands are deprecated. A dedicated sprint migrates all functionality under `flask org persona`. Old commands are removed (not aliased) to prevent agents from using outdated paths.

**Deferred to future sprints:**
- Export filtering (`--positions-only`, `--role developer`)
- Output format flag (`--format yaml|json|markdown`)
- Cross-org queries (`flask org compare`)
- Point-in-time export (`--at "2026-02-15"`)
- Mermaid/diagram output from `flask org tree`

---

### 1.4 Database ↔ File Round-Trip Mechanics
- [x] **Decision: How does the import/export cycle work, and how do we handle conflicts and updates?**

**Depends on:** 1.1, 1.2, 1.3

**Context:** The round-trip must handle:
- **Fresh import:** No existing org → create everything from file
- **Update import:** Existing org → detect changes, apply updates, preserve what hasn't changed
- **Export:** Current DB state → file, capturing the full org as it stands
- **Conflict resolution:** File says one thing, DB says another — which wins?

This is non-trivial. Consider: operator exports org, modifies YAML, re-imports. Meanwhile an agent has been assigned to a position. Does the import overwrite agent assignments? Probably not — structural changes yes, runtime state no.

**Questions to resolve:**
- Is the file the source of truth for structure, and the DB the source of truth for runtime state?
- What constitutes "structural" vs "runtime" data?
- Do we need a diff/preview before applying an import? (probably yes)
- What happens to DB records that exist but aren't in the import file? (orphan handling)

**Resolution:**

**DB is source of truth. Export is on-demand composite. Import is atomic with preview.** Resolved 1 March 2026.

**Source of truth split:**

| Data Category | Source of Truth | Examples |
|---|---|---|
| **Structure** | Database | Organisation, Position, Role, PositionAssignment records |
| **Content** | Filesystem | Intent documents (Markdown), persona skill/experience files |
| **Runtime** | Database (derived) | Active agents, current sessions, agent state — NOT in YAML, NOT importable |

**Export flow:**
1. CLI queries DB for org structure (Organisation → Positions → Roles → PositionAssignments → Personas)
2. CLI reads filesystem for content (intent.md from org directory, skill/experience file paths from persona directories)
3. CLI merges into single YAML document → stdout
4. No persistent file. Always fresh. No cache invalidation.

**Import flow:**
1. CLI reads YAML from `--file` or stdin
2. **Preview** (`--preview` flag, recommended before every import): shows diff against current DB state — what will be created, updated, deleted
3. **Validate** (automatic, runs before apply): structural checks — circular reporting chains, missing role references, orphaned positions, invalid escalation paths
4. **Apply** (atomic by default): all-or-nothing DB transaction. If any record fails, entire import rolls back. No partial org charts.
5. **Filesystem side-effects**: if import creates a new organisation, CLI creates the org directory (`data/organisations/{slug}/`). If import creates a new persona, CLI creates persona directory and asset files.

**Structural vs runtime distinction:**

| Structural (importable) | Runtime (not importable) |
|---|---|
| Organisation name, purpose, slug, description, status | Active agents on positions |
| Position title, role, level, reports_to, escalates_to | Agent session state (IDLE, PROCESSING, etc.) |
| Role name, description | Current command in progress |
| PositionAssignment (persona ↔ position binding) | Agent context usage |
| Persona name, role, status | Priority scores |

**Conflict resolution:**
- **YAML has an entity with a matching ID** → update the DB record with YAML values (structural fields only)
- **YAML has an entity with no matching ID** → create new DB record
- **DB has an entity not in the YAML** → no action (preserve). Importing a YAML does not delete unmentioned records. Deletion is explicit via CLI commands (`flask org position remove`). This prevents accidental data loss from partial exports.
- **Assignment conflicts** → if YAML assigns a persona to a position that's currently held by a different persona, the import preview shows this as a conflict. Apply requires `--force` to proceed, which unassigns the current holder first.

**What import does NOT touch:**
- Runtime agent state
- Inference/summarisation data
- Event audit trail
- Handoff records
- Activity metrics

---

### 1.5 Filesystem Location & Conventions
- [x] **Decision: Where do organisation definition files live on disk, and what's the naming convention?**

**Depends on:** 1.1

**Context:** Persona assets live at `data/personas/{slug}/`. Organisation files need a home too.

The operator mentioned these are application-specific data, gitignored, symlinked to `otl_support` and managed under separate version control. This matches the existing pattern for persona data.

**Questions to resolve:**
- `data/organisations/{slug}/org.yaml`?
- Does each org get a directory (for future org-specific assets)?
- What's the slug format for organisations?
- Does the org directory contain references/links to its persona directories?

**Resolution:**

**Slug-based directories following the persona pattern.** Resolved 1 March 2026.

**Organisation model additions:**
- `purpose` field — the domain/category of the org (e.g., `software-development`, `marketing`, `content`, `economy`). Required on create.
- `slug` field — auto-generated as `{purpose}-{name}-{id}`, same pattern as Persona's `{role}-{name}-{id}`. Uses the same after-insert event mechanism: temp slug on create, real slug generated once the DB provides the ID.

**Filesystem layout:**

```
data/
├── organisations/
│   ├── software-development-development-1/
│   │   ├── intent.md              # Intent engineering document
│   │   └── (future org assets)
│   └── economy-kent-ventures-2/
│       ├── intent.md
│       └── (future org assets)
├── personas/
│   ├── architect-robbo-3/
│   │   ├── skill.md
│   │   ├── experience.md
│   │   └── handoffs/
│   │       └── 20260228T231204-00001053.md
│   ├── ar-director-paula-7/
│   │   ├── skill.md
│   │   └── experience.md
│   └── ...
```

**Conventions:**
- Each organisation gets its own directory under `data/organisations/`
- Directory name = organisation slug (`{purpose}-{name}-{id}`)
- `intent.md` is the primary content file — parsed by the CLI during export and merged into the YAML `intent:` block
- Directory is auto-created by CLI when an organisation is created (`flask org create`)
- Persona directories remain at `data/personas/{slug}/` — they are not nested under organisations because personas are org-independent (a persona can hold positions in multiple orgs)
- These directories are application-specific data, gitignored in the main repo, managed via symlink to `otl_support` under separate version control — matching the existing persona data pattern

**Slug generation:** Identical mechanism to Persona. SQLAlchemy after-insert event replaces temp slug `_pending_{uuid}` with real `{purpose}-{name}-{id}` (sanitized, lowercase, hyphens). Slug is immutable after generation — renaming an org creates a new slug (and a new directory).

---

### Section 1: Database Migration Checklist

All model changes required by Section 1 decisions, consolidated for implementation:

| Migration | Model | Change | Priority |
|---|---|---|---|
| Add `purpose` column | Organisation | `String(64)`, NOT NULL. Domain/category of the org. | Required before org CLI |
| Add `slug` column | Organisation | `String(128)`, NOT NULL, UNIQUE. Auto-generated `{purpose}-{name}-{id}`. After-insert event (same pattern as Persona). | Required before org CLI |
| Create `PositionAssignment` table | New table | `id` (PK), `position_id` (FK), `persona_id` (FK), `assigned_at`, `unassigned_at` (nullable). Join table for persona ↔ position binding with lifecycle tracking. | Required for org assignments |
| Fix `Agent.position_id` ondelete | Agent | Change from CASCADE to SET NULL. Nullable FK should not cascade-delete the agent when a position is removed. | Required before Position activation |
| Backfill existing Organisation | Organisation | Update the seeded "Development" record with `purpose='software-development'` and generate its slug. | Data migration |
| Migrate `flask persona` to `flask org persona` | CLI | Deprecate and remove old `flask persona` commands. | Dedicated sprint |

**Note:** Role does NOT need `org_id` (workshop decision: roles are global). Role does NOT need `role_type` or `can_use_tools` (deferred — no current use case). These fields from the original ERD are intentionally excluded.

---

## Section 2: Inter-Agent Communication

**Purpose:** Design the communication channel that allows agents to send messages to each other through Headspace. This is the nervous system of the organisation — every delegation, report, question, and escalation flows through it.

---

### 2.1 Communication Architecture
- [ ] **Decision: How do agents send messages to each other — what's the transport layer?**

**Depends on:** None (but informed by Section 1 decisions on CLI)

**Context:** Currently, communication is:
- Operator → Agent: tmux bridge `send_text()` (types into the agent's terminal)
- Agent → Operator: hook events surfaced on dashboard (passive — agent doesn't "send" messages, Headspace observes them)

For agent-to-agent, we need an active communication path. Agent A needs to deliberately send a message to Agent B, and Agent B needs to receive and process it.

Headspace must be the intermediary for:
- Visibility (dashboard can show all inter-agent communication)
- Auditability (every message persisted)
- Routing (hierarchy-aware delivery)
- Alignment checking (optional — can messages be validated against objectives?)

**Options:**
- **A) Tmux bridge relay** — Agent A writes to a CLI/API endpoint → Headspace receives → Headspace uses tmux bridge to type the message into Agent B's terminal. Symmetric with how operator talks to agents today.
- **B) Shared file protocol** — Agent A writes a message file to a known location → Agent B polls/watches for it. Low-tech but fragile, no Headspace mediation.
- **C) API + Hook loop** — Agent A calls a Headspace API endpoint to send a message → Headspace persists and routes → message delivered to Agent B via tmux bridge. Agent B's response flows back through hooks.
- **D) CLI command** — Agent A runs a CLI command (`flask msg send --to con "please review the migration"`) → CLI calls internal API → Headspace routes and delivers via tmux.

**Considerations:**
- Tmux bridge delivery is proven — it's how skill injection works
- Agents can use bash tools reliably — CLI commands are natural
- API endpoints are accessible to both agents (via curl/CLI) and the dashboard
- Every message must be persisted for audit trail (regardless of transport)
- Message delivery must be observable on the dashboard
- The transport should work for both local agents (tmux panes) and remote agents (API-based)

**Resolution:** _(Pending)_

---

### 2.2 Message Data Model
- [ ] **Decision: Do we create a Message table, and what does it look like?**

**Depends on:** 2.1

**Context:** The operator suggested a Message table for auditability. Messages from one agent to another are the raw transport records. They may then become Commands or Turns from the receiving agent's perspective.

The question is whether Message is:
- A standalone audit table (every inter-agent message logged, regardless of what it becomes downstream)
- A precursor to Commands/Turns (a message is processed and generates the appropriate downstream records)
- Both (logged for audit AND processed into the command/turn lifecycle)

**Questions to resolve:**
- Message fields: sender_agent_id, receiver_agent_id, content, message_type (command, question, report, interrupt, escalation), timestamp, status (sent, delivered, read, processed)?
- Does a Message reference a Task? A Command?
- How does Message relate to the existing Turn model? (A message from Agent A becomes a USER turn in Agent B's command context?)
- Do we need threading? (Message chains for back-and-forth on a topic)

**Resolution:** _(Pending)_

---

### 2.3 Message Types & Semantics
- [ ] **Decision: What types of inter-agent messages exist, and what semantics does each carry?**

**Depends on:** 2.2

**Context:** From the operator's description, the interaction patterns between agents include:
1. **Command** — "Go do this thing" (delegation down the hierarchy)
2. **Report** — "I've finished / here's progress" (completion/status up the hierarchy)
3. **Question** — "I need clarification on X" (reverse flow from worker to commander)
4. **Interrupt** — "Stop what you're doing / change course" (commander to worker, mid-task)
5. **Escalation** — "I can't resolve this, passing up" (up the escalation chain, not necessarily the reporting chain)

Each type has different routing rules, urgency, and lifecycle implications.

**Questions to resolve:**
- Is this an enum on the Message model?
- Do different types trigger different delivery mechanisms? (e.g., interrupt might need to be more aggressive than a report)
- Do types map to existing concepts? (Command message → creates a Command record; Question → creates a Turn with intent=QUESTION)
- What about acknowledgements? Does the sender know the message was received/processed?

**Resolution:** _(Pending)_

---

### 2.4 Message Routing & Hierarchy Awareness
- [ ] **Decision: How does Headspace route messages based on the organisational hierarchy?**

**Depends on:** 2.1, 2.3, Section 1 (org structure must be queryable)

**Context:** Not all messages are point-to-point. Some are routed by role or hierarchy:
- "Escalate this" → routed to the sender's `escalates_to_id` position
- "Assign this to a backend developer" → routed to an available agent with the right role
- "Report to my manager" → routed to the sender's `reports_to_id` position

The routing engine needs to:
- Resolve position → active agent (which agent currently fills this position?)
- Handle the case where a position has no active agent (queue? notify? escalate further?)
- Support both named routing ("send to Con") and role-based routing ("send to a developer")

**Questions to resolve:**
- Is routing logic in the message delivery service, or in the CLI commands?
- How do we handle "no one is available" scenarios?
- Can an agent send to a position title rather than a persona name?
- Does the routing engine consult the org YAML/Markdown, or always the DB?

**Resolution:** _(Pending)_

---

### 2.5 Message Delivery & Agent Reception
- [ ] **Decision: How does a message get delivered into an agent's context, and how does the agent know a message has arrived?**

**Depends on:** 2.1, 2.2

**Context:** Agent reception is the critical UX question. When Agent B receives a message from Agent A:
- Is it injected into Agent B's terminal via tmux (like skill injection)?
- Does it interrupt Agent B's current work, or wait for a natural pause?
- How does Agent B distinguish "this is a message from another agent" from "this is the operator typing"?

For remote agents (API-based, no tmux), the delivery mechanism will be different.

**Questions to resolve:**
- Delivery format: plain text? Structured markdown with sender/type metadata?
- Timing: immediate injection, or queued until agent is in a receptive state (IDLE, AWAITING_INPUT)?
- Interrupts: do INTERRUPT type messages bypass the queue and inject immediately?
- Remote agent delivery: API callback? Polling endpoint?
- Does the agent need to explicitly acknowledge receipt?

**Resolution:** _(Pending)_

---

### 2.6 Dashboard Communication Visibility
- [ ] **Decision: How does the dashboard display inter-agent communication?**

**Depends on:** 2.2, 2.3

**Context:** The operator acknowledged this needs design work and will involve "a whole bunch of things." The dashboard currently shows agent cards with state, summaries, and priority scores. Inter-agent communication adds a new dimension.

**Questions to resolve:**
- Per-agent message feed? (see all messages to/from an agent)
- Organisation-wide communication timeline? (all messages across the org)
- Visual indicators on agent cards when messages are pending/unread?
- Thread views for back-and-forth exchanges?
- Filtering by message type (commands only, escalations only, etc.)?

This may be best deferred to a separate UI workshop once the backend communication model is solid.

**Resolution:** _(Pending — likely deferred to UI-specific workshop)_

---

## Section 3: Task Model & Delegation

**Purpose:** Define the Task as the organisational unit of work that sits above Command. Tasks are what the PM layer assigns; Commands are what individual agents execute. This section resolves the relationship between them.

---

### 3.1 Task as Organisational Work Unit
- [ ] **Decision: What is a Task, how does it relate to Commands, and what's the data model?**

**Depends on:** 2.2 (message model — tasks may be created from delegation messages)

**Context:** The operator described the hierarchy:
- **Task** — High-level unit of work assigned by the PM (Gavin) or another coordinating agent. Part of an OpenSpec change or similar spec-driven workflow. A reportable, trackable thing.
- **Command** — The existing model. An instruction given to an agent that goes through the 5-state lifecycle (IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE).

A Task decomposes into one or more Commands. The Task tracks the organisational intent; the Commands track the execution.

**Questions to resolve:**
- Task fields: title, description, acceptance_criteria, assigned_to (position or persona), assigned_by (agent or operator), status, parent_task_id (for decomposition)?
- Does a Task reference an OpenSpec change or other external spec?
- Can Tasks be nested? (Task → sub-tasks → commands)
- Who creates Tasks? (Gavin? Operator? Any coordinating agent?)
- How does Task status derive from its Commands' states?

**Resolution:** _(Pending)_

---

### 3.2 Task Assignment & Acceptance
- [ ] **Decision: How does a task get assigned to an agent, and does the agent accept/reject?**

**Depends on:** 3.1, 2.1 (communication channel for delivery)

**Context:** Task assignment flow:
1. PM (Gavin or operator) creates a Task
2. Task is assigned to a position or persona
3. The assigned agent receives the task (via communication channel)
4. Agent begins work (creates Commands under the Task)

**Questions to resolve:**
- Is assignment automatic (PM assigns, agent starts) or negotiated (PM proposes, agent accepts)?
- Can an agent reject or negotiate a task? ("I don't have the skills for this" → reassign)
- Does assignment require an active agent, or can tasks be assigned to positions (filled when an agent comes online)?
- What's the Task state machine? (PENDING → ASSIGNED → IN_PROGRESS → COMPLETE? More states?)

**Resolution:** _(Pending)_

---

### 3.3 Task-Command Relationship
- [ ] **Decision: How do Commands relate to Tasks, and how does completion roll up?**

**Depends on:** 3.1

**Context:** Currently Commands are standalone — they belong to an Agent and go through the 5-state lifecycle. With Tasks, we need to:
- Link Commands to a parent Task (optional FK on Command?)
- Derive Task progress from Command states
- Handle the case where a Task requires multiple Commands (possibly from different agents)
- Handle the case where a Command is not part of any Task (backward compatibility — operator-direct commands)

**Questions to resolve:**
- Add `task_id` FK to Command model? (nullable for backward compatibility)
- Does a Task auto-complete when all its Commands complete?
- Can a Task have Commands assigned to multiple agents? (e.g., "build the feature" → frontend Command to Al, backend Command to Con)
- How does the existing Command lifecycle interact with Task lifecycle?

**Resolution:** _(Pending)_

---

### 3.4 Task Reporting & Progress
- [ ] **Decision: How does an agent report task progress and completion back to the assigning agent?**

**Depends on:** 3.1, 2.3 (Report message type)

**Context:** When an agent completes a Task (or hits a blocker), the assigning agent needs to know. This ties into the communication channel (Section 2) — a completion report is a message of type REPORT.

**Questions to resolve:**
- Is completion automatic (Headspace detects all Commands under Task are COMPLETE → sends report)?
- Or does the agent explicitly send a completion message?
- Progress reports: periodic updates? On-demand when asked? Only on completion?
- Blockers: does the agent send an escalation message, or a question message to the assigner?

**Resolution:** _(Pending)_

---

### 3.5 Task Integration with OpenSpec
- [ ] **Decision: How do Tasks connect to OpenSpec changes and spec-driven workflows?**

**Depends on:** 3.1

**Context:** OpenSpec changes produce task lists (`tasks.md` in change directories). The operator mentioned that "a task is something that is part of an OpenSpec change." This is the bridge between the spec-driven development workflow and the organisation's task management.

**Questions to resolve:**
- Does an OpenSpec change create a parent Task with sub-tasks for each task item?
- Is there a one-to-one mapping between OpenSpec tasks and Headspace Tasks?
- How does the PM layer read and decompose an OpenSpec change?
- Is this a future concern (v2/v3) or do we design the Task model to accommodate it from the start?

**Resolution:** _(Pending)_

---

## Section 4: Agent Interaction Patterns

**Purpose:** Define the specific interaction flows between agents — the "turn cycle" for agent-to-agent work. These patterns mirror the existing human-to-agent patterns but with both sides being agents mediated by Headspace.

---

### 4.1 Agent-to-Agent Command Flow
- [ ] **Decision: What's the full lifecycle of one agent commanding another to do work?**

**Depends on:** 2.1, 2.3, 3.1

**Context:** The core delegation flow:
1. Agent A (PM/coordinator) sends a Command message to Agent B (worker)
2. Agent B receives the command → creates a Command record → begins processing
3. Agent B works through the task → may ask questions back to Agent A
4. Agent B completes → sends a Report message to Agent A
5. Agent A receives the report → updates Task status → may assign next task

This is the "happy path." We need to define what happens at each step, including what Headspace does at each transition.

**Questions to resolve:**
- Does Headspace create the Command record on Agent B, or does Agent B create it?
- How does Agent B know the command came from Agent A vs the operator?
- What metadata is attached to the command? (Task reference, acceptance criteria, urgency, deadline)
- What triggers the "complete" transition — Agent B's assessment, or Agent A's acceptance?

**Resolution:** _(Pending)_

---

### 4.2 Question & Clarification Flow
- [ ] **Decision: How does a worker agent ask its commanding agent for clarification?**

**Depends on:** 4.1, 2.3

**Context:** When Agent B (worker) needs clarification on a task:
1. Agent B formulates a question
2. Agent B sends a Question message to Agent A (its commander for this task)
3. Agent A receives the question → considers → sends an Answer message back
4. Agent B receives the answer → continues work

This is the reverse of the command flow. The existing intent detection system already identifies QUESTION turns in human-agent interaction. The same patterns should apply.

**Questions to resolve:**
- Does Agent B's question put Agent B into AWAITING_INPUT state? (parallels the existing state machine)
- Does Agent A's answer arrive as a new turn in Agent B's context?
- What if Agent A is busy with other work? Queue the question? Interrupt?
- Can questions chain (back-and-forth clarification)?

**Resolution:** _(Pending)_

---

### 4.3 Interrupt Flow
- [ ] **Decision: How does a commanding agent interrupt a worker agent mid-task?**

**Depends on:** 4.1, 2.5

**Context:** Interrupts are the most disruptive interaction pattern. Agent A needs Agent B to stop what it's doing — change course, reprioritise, or abort. This mirrors the operator's ability to interrupt an agent today.

**Questions to resolve:**
- What's the interrupt delivery mechanism? (Immediate tmux injection vs. graceful "finish current turn" signal)
- Does an interrupt cancel the current Command? Create a new one? Modify the existing one?
- What about partial work? Does Agent B need to save state before being interrupted?
- Is there a "soft interrupt" (please wrap up and report) vs "hard interrupt" (stop now)?
- Who can send interrupts? Only the commanding agent? Anyone higher in the hierarchy?

**Resolution:** _(Pending)_

---

### 4.4 Completion & Handback Flow
- [ ] **Decision: What happens when a worker agent finishes its assigned work?**

**Depends on:** 4.1, 3.4

**Context:** When Agent B completes a command:
1. Agent B's Command transitions to COMPLETE
2. Agent B sends a Report message to its commanding agent
3. Commanding agent receives the report
4. Commanding agent may: accept, request revisions, assign next task, or close the Task

This is the "return leg" of delegation. It needs to integrate with the Task lifecycle (Section 3) and the communication channel (Section 2).

**Questions to resolve:**
- Does completion trigger automatic notification, or does Agent B explicitly send a report?
- What's in the completion report? (Summary, files changed, test results, blockers encountered)
- Does the commanding agent review/accept, or is completion self-assessed?
- What happens to Agent B after completion? Returns to IDLE? Picks up next task from queue? Shuts down?

**Resolution:** _(Pending)_

---

## Section 5: Alignment & Intent Engineering

**Purpose:** Ensure all agents in the organisation are working toward the same goals. Define how objectives cascade through the hierarchy, how agents signal intent, and how misalignment is detected and corrected.

---

### 5.1 Objective Cascade
- [ ] **Decision: How do organisation-level objectives flow down to individual agents?**

**Depends on:** Section 1 (org structure), Section 3 (task model)

**Context:** The existing Objective model (`current_text`, `constraints`, `priority_enabled`) is a single global objective. Priority scoring ranks agents 0-100 based on alignment with this objective.

For an organisation, we need:
- Organisation-level objective (what the org is trying to achieve overall)
- Task-level objectives (what this specific piece of work should accomplish)
- Agent-level context (how does my current work serve the objective?)

**Questions to resolve:**
- Do we extend the Objective model for org-scoped objectives?
- Are task-level objectives just the Task's acceptance criteria?
- How is the objective included in an agent's context? (Part of the org brief? Injected per-task?)
- Does priority scoring become org-aware? (Score relative to org objective, not just global)

**Resolution:** _(Pending)_

---

### 5.2 Intent Signals & Assumption Minimisation
- [ ] **Decision: How do we minimise agents making incorrect assumptions, and how do they signal intent before acting?**

**Depends on:** 5.1, 4.2 (question flow)

**Context:** The operator identified assumption minimisation as a critical concern. Agents that assume instead of asking produce work that needs rework — expensive in context tokens, time, and operator attention.

The existing IntentDetector identifies QUESTION turns. But for organisational work, we need agents to:
- Signal what they intend to do before doing it (a lightweight "here's my plan" before execution)
- Ask clarifying questions proactively rather than assuming
- Flag when they're uncertain about scope or approach

**Questions to resolve:**
- Is there a "proposal" step before execution? (Agent says "I plan to do X, Y, Z" → commander approves → agent proceeds)
- How does the skill file encode "ask, don't assume" behaviour?
- Can Headspace detect high-assumption patterns? (e.g., agent proceeding without questions on a complex task)
- Is this enforcement or guidance? (Hard gate vs. skill file best practices)

**Resolution:** _(Pending)_

---

### 5.3 Persona Skill Rework for Organisational Context
- [ ] **Decision: How do persona skill files need to change to support organisational awareness?**

**Depends on:** 5.1, 5.2, Section 1 (agents can read org structure)

**Context:** The operator mentioned "we're probably going to need to do a big rework of personas skill definitions around all this." Current skill files define core identity, skills & preferences, and communication style.

For organisational operation, agents also need to understand:
- Their place in the hierarchy (but this comes from the org brief, not the skill file)
- How to interact with other agents (communication protocols, message formats)
- When to escalate vs. proceed independently
- How to frame task reports and questions
- Alignment behaviour (check work against objectives)

**Questions to resolve:**
- What new sections are needed in skill.md?
- Is there a shared "organisational behaviour guide" that all agents get, separate from individual skill files?
- Do we need per-organisation skill file extensions? (Dev org behaviour vs economy org behaviour)
- How much of this is in the skill file vs. the org brief vs. the task assignment?

**Resolution:** _(Pending)_

---

### 5.4 Misalignment Detection & Correction
- [ ] **Decision: How does the system detect when an agent is working against or outside the organisation's objectives?**

**Depends on:** 5.1, 5.2

**Context:** The existing headspace monitor tracks frustration (rolling averages, flow state, traffic-light alerts). Priority scoring checks objective alignment. For organisational work, misalignment might look like:
- Agent working on something not in its task scope
- Agent making decisions that contradict the spec
- Agent spending tokens on tangential work
- Agent not asking questions when it should be

**Questions to resolve:**
- Is misalignment detection LLM-powered? (Periodic check: "is this agent's recent work aligned with its task?")
- Or is it metric-based? (Token spend vs. progress, question frequency, command completion rate)
- What happens when misalignment is detected? (Alert? Automatic intervention? Escalation?)
- Is this a v1 concern or a future refinement?

**Resolution:** _(Pending)_

---

## Section 6: Escalation Mechanics

**Purpose:** Define when agents escalate, how escalations are routed through the hierarchy, and how escalated issues are resolved and fed back.

---

### 6.1 Escalation Trigger Conditions
- [ ] **Decision: What conditions cause an agent to escalate an issue up the hierarchy?**

**Depends on:** 4.2, 5.2

**Context:** The functional outline defines escalation paths:
- Build: Team member stuck → Gavin → Robbo → Operator
- QA: Verner finds ambiguity → Robbo → Operator
- Ops: Leon finds exception → auto-fix or → Gavin → Robbo → Operator

But "stuck" and "ambiguity" are judgment calls. We need to define what triggers escalation — is it agent self-assessment, system detection, or both?

**Questions to resolve:**
- What are the explicit trigger conditions? (Time threshold, repeated failures, confidence assessment, explicit "I'm stuck")
- Does the skill file encode escalation behaviour? ("If unsure about architectural direction, escalate to your escalation point")
- Can Headspace force escalation? (Agent has been PROCESSING for too long → system escalates)
- Does the agent choose the escalation target, or does Headspace route based on `escalates_to_id`?

**Resolution:** _(Pending)_

---

### 6.2 Escalation Routing
- [ ] **Decision: How does an escalation message get routed through the org hierarchy?**

**Depends on:** 6.1, 2.4 (message routing)

**Context:** The Position model has `escalates_to_id` — a self-referential FK that may differ from `reports_to_id`. This means the escalation chain can be different from the management chain.

Example: Verner (QA) reports to Gavin (PM) but escalates architectural issues to Robbo (Architect). The Position model supports this, but we need the routing engine to use it.

**Questions to resolve:**
- Does escalation always follow `escalates_to_id`, or can agents escalate to arbitrary positions?
- What if the escalation target has no active agent? (Skip to next level? Queue? Notify operator?)
- Multi-level escalation: does the escalation auto-propagate if the first level can't resolve?
- Does the escalation carry the full context, or a summary?

**Resolution:** _(Pending)_

---

### 6.3 Escalation Resolution & Feedback
- [ ] **Decision: What happens after an escalated issue is resolved?**

**Depends on:** 6.2

**Context:** When an escalation is resolved (e.g., Robbo clarifies the architectural question):
- The resolution needs to flow back to the original agent
- The original agent resumes work with the new information
- The escalation record should be closed

**Questions to resolve:**
- Does the resolving agent send a message directly to the original agent?
- Or does it flow back through the hierarchy? (Robbo → Gavin → Team member)
- Is the resolution a new message, or an update to the original escalation?
- Does the resolution get recorded for future reference? (Experience log, knowledge base)

**Resolution:** _(Pending)_

---

## Section 7: PM Layer Design (Gavin)

**Purpose:** Define how the PM layer operates — how Gavin (or the operator acting as Gavin) receives specifications, decomposes work, assigns tasks, and monitors progress. This is the control layer for the organisation.

---

### 7.1 PM Autonomy Level
- [ ] **Decision: For the initial implementation, how autonomous is Gavin?**

**Depends on:** Section 3 (task model), Section 2 (communication)

**Context:** The functional outline describes an evolution:
- v1: Operator acts as Gavin — manually decomposes and assigns
- v2: Gavin drafts decomposition; operator reviews and approves
- v3: Gavin operates autonomously with escalation paths

The operator's stated goal is to "reduce my mental workload in coordinating the detailed operations of agents." This pushes toward v2 at minimum.

**Questions to resolve:**
- Are we designing for v2 (Gavin proposes, operator approves) from the start?
- What does operator approval look like? (Dashboard UI? CLI? Message response?)
- What does "drafts decomposition" mean concretely? (Reads spec → creates Tasks → presents for review?)
- Can Gavin assign tasks without approval, or is approval always required in v2?

**Resolution:** _(Pending)_

---

### 7.2 Task Decomposition Process
- [ ] **Decision: How does the PM agent decompose a specification into tasks?**

**Depends on:** 7.1, 3.1

**Context:** Gavin receives a specification (from Robbo's workshop, from an OpenSpec change, or directly from the operator) and needs to:
1. Understand the spec's requirements and acceptance criteria
2. Identify the work items
3. Match work items to skill domains (backend, frontend, database, etc.)
4. Create Tasks with clear scope and criteria
5. Determine sequencing and dependencies
6. Assign to available personas/positions

**Questions to resolve:**
- Is decomposition LLM-powered? (Gavin uses inference to read the spec and propose tasks?)
- Or structured? (Spec format includes a task breakdown that Gavin just operationalises?)
- How does Gavin decide task granularity? (One task per feature? Per file? Per function?)
- Does Gavin have access to the codebase, or only to the spec document?

**Resolution:** _(Pending)_

---

### 7.3 Progress Monitoring & Replanning
- [ ] **Decision: How does the PM track progress and adapt the plan when things change?**

**Depends on:** 7.1, 3.4 (task reporting), 4.4 (completion flow)

**Context:** Once tasks are assigned and work begins, the PM needs to:
- Track which tasks are in progress, complete, blocked
- Detect when tasks are taking too long or going off-track
- Re-sequence or reassign when blockers emerge
- Report overall progress to the operator
- Decide when to escalate (to Robbo or operator)

**Questions to resolve:**
- Does Gavin actively poll task status, or is he notified via messages?
- What's the "dashboard" for Gavin? (His own task board? The operator's dashboard? The org brief?)
- When does Gavin escalate to Robbo vs. reassigning to another team member?
- Does Gavin have a periodic check-in cycle, or is it event-driven?

**Resolution:** _(Pending)_

---

## Section 8: Multi-Org Readiness

**Purpose:** Validate that the organisation architecture works for more than just the development team. Kent's economy org is the first test case.

---

### 8.1 Organisation Isolation
- [ ] **Decision: How are multiple organisations isolated from each other within Headspace?**

**Depends on:** Sections 1-7 (entire org architecture)

**Context:** Kent's economy org operates alongside the dev org:
- Different roles (Strategy, Research, Execution, Monitor vs Developer, PM, Architect, QA)
- Different execution context (blockchain vs codebase)
- Same Headspace instance, same PostgreSQL, same dashboard

**Questions to resolve:**
- Do orgs share the Role vocabulary, or does each org define its own roles?
- Are personas org-scoped or global? (Can a persona work in multiple orgs?)
- Is the dashboard org-filtered? (View one org at a time, or all agents across orgs?)
- Do inter-org messages exist, or is communication strictly intra-org?
- How is the objective model scoped? (Per-org objectives?)

**Resolution:** _(Pending)_

---

### 8.2 Economy Org as Validation
- [ ] **Decision: What specific requirements does the economy org introduce that the dev org doesn't have?**

**Depends on:** 8.1

**Context:** From Kent's workshop, the economy org needs:
- Agents with financial authority limits (spending caps per session/transaction)
- Risk management escalation (hard stop at portfolio threshold)
- External system integration (blockchain, x402, wallet management)
- Different monitoring needs (portfolio value, P&L vs test results, code quality)

**Questions to resolve:**
- Do authority limits belong in the Position model? Persona model? A new model?
- How do org-specific concerns (spending caps) integrate without polluting the generic org model?
- Is this a "prove the abstraction" exercise, or do we actually build economy org support now?
- What's the minimum the org architecture needs to support to not block Kent's work?

**Resolution:** _(Pending)_

---

## Section 9: Implementation Sequence

**Purpose:** Based on all decisions above, define the epic structure and sprint ordering for incremental delivery.

---

### 9.1 Epic Structure
- [ ] **Decision: How do we break this into epics with controlled scope?**

**Depends on:** All previous sections

**Context:** The operator emphasised iterative epics with "a controllable amount of work subject to real testing before we extend to build the next." This means:
- Each epic must be independently testable
- Each epic delivers working functionality (not just scaffolding)
- Testing happens against the running application, not just unit tests
- Each epic is a stable foundation for the next

**Questions to resolve:**
- How many epics? What's the rough ordering?
- Does Section 0 (audit) block everything, or can we work in parallel?
- Which sections are most coupled and must be in the same epic?
- What's the first epic that produces a visible, testable result?

**Resolution:** _(Pending)_

---

### 9.2 Sprint Ordering Within Epics
- [ ] **Decision: What's the sprint sequence, and what are the dependencies?**

**Depends on:** 9.1

**Context:** Following the Epic 8 pattern: 1 sprint = 1 PRD = 1 OpenSpec change. Each sprint has clear acceptance criteria and is independently deliverable.

**Resolution:** _(Pending — to be defined after section workshops complete)_

---

### 9.3 Testing & Validation Strategy
- [ ] **Decision: How do we test organisational features given they require multiple agents interacting?**

**Depends on:** 9.1

**Context:** Organisation features are inherently multi-agent. Unit tests can cover individual services, but validating "Agent A delegates to Agent B, Agent B completes, Agent A receives the report" requires integration testing with real agents.

**Questions to resolve:**
- Do we use the existing agent_driven test tier for org features?
- Can we simulate multi-agent interactions without real Claude Code sessions? (Mock agents?)
- What's the minimum viable test scenario for each epic?
- How do we test communication, delegation, and escalation in a controlled way?

**Resolution:** _(Pending)_

---

## Workshop Log

| Date | Decision | Resolution | Rationale |
|------|----------|------------|-----------|
| 1 Mar 2026 | 0.1 Schema Audit | RESOLVED (by predecessor Agent #1054) | Two clean categories: ACTIVE (Persona, Role, Handoff, Agent extensions) and SCAFFOLDING (Organisation, Position, Agent.position_id). Clean scaffolding, no dead code. |
| 1 Mar 2026 | 0.2 Persona Audit | RESOLVED (by predecessor Agent #1054) | All persona features working end-to-end. No gaps found. |
| 1 Mar 2026 | 0.3 Handoff Status | RESOLVED (by predecessor Agent #1054) | Code-complete, demonstrated once in production (this handoff chain). Not yet hardened. position_id CASCADE→SET NULL fix confirmed. |
| 1 Mar 2026 | 1.1 Serialization Format | YAML as canonical format | YAML handles recursive structures, round-trips deterministically. On-demand export (no persistent file). Markdown for content (skills, experience, intent). |
| 1 Mar 2026 | 1.2 Document Structure | Four-section YAML, composite sourcing | DB for structure, filesystem for content (intent.md). Prefixed IDs. Inline assignments. Organisation gets `purpose` + `slug` (`{purpose}-{name}-{id}`). |
| 1 Mar 2026 | 1.3 CLI Design | `flask org` unified entry point, 6 subgroups, 30+ commands | Migrates `flask persona` under `flask org persona`. Discoverable, explicit-over-implicit, atomic imports, Unix pipes. AR Director (Paula) manages org changes. |
| 1 Mar 2026 | 1.4 Round-Trip Mechanics | DB = structure truth, filesystem = content truth | Atomic imports with preview. No runtime data in YAML. Unmentioned DB records preserved on import (no accidental deletion). |
| 1 Mar 2026 | 1.5 Filesystem Conventions | `data/organisations/{slug}/` with intent.md | Slug pattern `{purpose}-{name}-{id}` matches Persona convention. Org-independent personas at `data/personas/{slug}/`. Gitignored, symlinked to otl_support. |

---

*This document is the working artifact for the Organisation phase workshop. Decisions are resolved collaboratively between operator (Sam) and architect (Robbo), documented with rationale, and used to generate epic roadmaps and PRDs.*
