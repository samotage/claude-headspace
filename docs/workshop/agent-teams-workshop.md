# Agent Teams — Design Workshop

**Date:** 16 February 2026
**Status:** Active workshop — working through design decisions
**Inputs:** `headspace-platform-vision.md`, `headspace-agent-teams-functional-outline.md`
**Method:** Grounding pass completed — vision concepts mapped against actual codebase. Decisions below need resolution before epic/sprint decomposition.

---

## How to Use This Document

Work through sections in order. Each decision has context from the codebase grounding pass, options considered, and space for the resolution. Check items off as resolved. Some decisions depend on earlier ones — dependencies are noted.

---

## 1. Foundational Architecture Decisions

These shape everything downstream. Resolve first.

### 1.1 Persona Storage Model
- [x] **Decision: How are personas represented in the system?**

**Context:** The functional outline puts persona identity in config.yaml (§5.2) and skill files on disk (§5.3). The codebase is fully relational — Agent, Task, Turn, Event all use PostgreSQL FKs. Agent currently has no persona concept.

**Options:**
- **A) Config-only** — Personas defined in YAML. Agent gets `persona_slug` string field (no FK). Simple, but no relational queries or FK integrity.
- **B) DB model** — New `Persona` table. Agent gets `persona_id` FK. Full relational power. More upfront work.
- **C) Hybrid (config as source, DB as cache)** — Config.yaml defines personas. On startup, sync to Persona DB table via upsert. Agent gets `persona_id` FK. Operator edits YAML; system gets FK integrity.

**Considerations:**
- Codebase pattern is relational (everything is FK'd)
- Operator workflow: editing YAML is natural (already does this for all config)
- Future needs: "which agents did Con run this week?" requires relational queries
- Platform vision: personas exist independently of orgs — argues for a durable registry

**Resolution:** **DB + Filesystem hybrid.** Persona is a first-class database entity with a dual representation:

- **Database (PostgreSQL):** The `Persona` table is the authoritative registry of persona identity and metadata — slug, name, description, role_type, pool memberships, active status. Agent references Persona via `persona_id` FK. All relational queries are served from the database.
- **Filesystem (Markdown):** Each persona has a directory of markdown files that constitute its **skill assets** — the material loaded into an agent's system prompt at session startup:
  - **`skill.md`** — Core competencies, preferences, behavioural instructions. Stable, operator-curated. The "who you are and how you work" file.
  - **`experience.md`** — Append-only log of learned experience from completed work. Evolves through agent self-improvement and periodic curation. The "what you've done and learned" file.
- **DB-to-filesystem link:** The Persona record resolves to its asset directory via path convention (`{base_path}/personas/{slug}/`). The application manages asset lifecycle: creation on persona registration, loading at agent startup, archival on deactivation.
- **Config.yaml is NOT involved.** Config.yaml is for application configuration only. Persona definitions are domain data, not app config.

**Design principle:** Real-world modelling. Skills and experience are the analogues of a person — the naming is deliberate and the two-file structure maps to how people actually work.

---

### 1.2 Config Location
- [x] **Decision: Where do persona/pool definitions live?**

**Depends on:** 1.1

**Context:** Current config is project-level `config.yaml` (symlinked from `otl_support`). The functional outline proposes `~/.headspace/config.yaml` as a separate global config. The platform vision (§4.1) says personas exist independently of any organisation.

**Options:**
- **A) Extend project config.yaml** — Add `personas:` and `pools:` sections alongside existing 18 sections. Simple. But ties personas to one project's config.
- **B) New global config at `~/.headspace/config.yaml`** — Separate config layer for persona/org definitions. Matches the outline. Adds a second config loading path.
- **C) Hybrid** — Persona definitions in project config (where Headspace reads all config today). Skill files at `~/.headspace/personas/`. Identity is co-located with the app; experience is global.

**Considerations:**
- Current config loader (`deep_merge`, `apply_env_overrides`) only reads one YAML file
- Adding a second config source means extending config.py
- If personas are org-independent (vision §4.1), tying them to project config is limiting
- But in v1, there's one project (claude_headspace) running Headspace — the distinction is theoretical

**Resolution:** **Convention-based `data/` directory at project root. No config.yaml involvement.**

- **Persona definitions** live in the database (resolved by 1.1).
- **Pool definitions** live in the database (follows persona — domain data, not app config).
- **Skill assets** live at `data/personas/{role}-{name}-{id}/` — a `data/` directory at the project root with subdirectories per subsystem (`personas/`, `pools/`, `teams/`, etc.).
- **Slug format:** `{role}-{name}-{id}` derived from the persona's `role_type`, `name`, and database `id`. Provides natural filesystem sorting — all personas of the same role cluster together, then sort alphabetically by name, with the ID as a uniqueness tiebreaker.
- **No config.yaml key needed.** The `data/` path is a project convention, not a configurable setting. Self-explanatory to anyone maintaining the system.
- **Config.yaml remains app config only** — no persona, pool, or domain data definitions.

---

### 1.3 Organisation Model — v1 Scope
- [x] **Decision: Do we add an Organisation DB model in v1?**

**Depends on:** 1.1

**Context:** Platform vision introduces Organisations as first-class entities with hierarchy, workflow patterns, and role assignments. The functional outline's dev org is the only org in v1.

**Options:**
- **A) No Organisation model in v1** — Hard-code the dev org assumption. Build Organisation model when the second org (Marketing) arrives. Design Persona model so it can gain `org_id` FK later.
- **B) Minimal Organisation model in v1** — Create the table (id, slug, name, workflow_pattern, created_at) even if there's only one row. Agent or Persona gets `org_id` FK. Future-proofs from the start.

**Considerations:**
- YAGNI vs. future-proofing
- One extra migration + model now saves a potentially disruptive migration later
- The functional outline (§9.1) doesn't mention orgs — it's all persona → agent
- But the vision (§4.2) says each org defines hierarchy, workflow, roles

**Resolution:** **Yes — minimal Organisation table in v1.** One small migration now avoids a disruptive one later. Exact schema (fields, FKs, relationships to Persona/Agent) to be defined during ERD design (separate session).

---

### 1.4 Agent Mode Field
- [x] **Decision: How do we represent workshop vs execution mode?**

**Context:** The functional outline (§9.1) says Agent gains a `mode` field: `workshop` | `execution`. Workshop mode (Robbo) is "collaborative, iterative, document-producing." Execution mode is "task-scoped, code-producing."

**Options:**
- **A) Enum field on Agent** — `mode = Column(Enum(AgentMode), default='execution')`. Simple, direct.
- **B) Derive from persona role_type** — If Robbo's role_type is `workshop`, his agents are always workshop mode. No separate field needed.
- **C) Both** — Role_type is the persona's *capability*, mode is the agent's *current operating mode*. A persona could theoretically operate in different modes (Robbo does workshop AND review).

**Considerations:**
- The outline says Robbo does workshop (spec creation) AND review (post-QA validation) — same persona, different sessions, same mode?
- Review is arguably workshop mode too (document-producing, not code-producing)
- If mode always derives from persona, the field is redundant
- If a persona can switch modes, the field has value

**Resolution:** **No mode field on Agent. Mode is a prompt-level concern, not a data model concern.** An agent's behaviour (workshop vs execution) is determined by the persona's `skill.md` content — the system prompt instructions that shape how the agent operates. The database models identity and relationships; behaviour comes from the prompt. A database enum cannot meaningfully constrain or describe what an agent actually does (execute code, read/write files, produce documents, etc.).

---

## 2. Data Model Decisions

Specific schema questions once foundational decisions are made.

### 2.1 Persona Table Schema
- [x] **Decision: What fields does the Persona model need?**

**Depends on:** 1.1, 1.3

**Draft schema (if DB model chosen):**
```
Persona
  id              int (PK)
  slug            str (unique) — "con", "robbo", "gavin"
  name            str — "Con", "Robbo", "Gavin"
  description     text — core identity paragraph
  role_type       enum — workshop | pm | execution | qa | ops
  is_active       bool (default true) — soft disable
  created_at      datetime
  updated_at      datetime
```

**Open sub-questions:**
- [x] Pool membership: JSONB array on Persona (`pools = ["backend", "database"]`) vs. separate Pool/PoolMembership tables?
- [x] Org FK: Include nullable `org_id` now (forward-compatible) or add later?
- [x] Skill file path: Store the path to `~/.headspace/personas/{slug}/skill.md` on the model, or derive from slug convention?

**Resolution:** **Resolved via ERD workshop. See `docs/workshop/erds/headspace-org-erd-full.md`.**

Schema:
```
Role
  id              int (PK)
  name            str — "developer", "tester", "pm", "architect"
  description     text
  created_at      datetime

Persona
  id              int (PK)
  slug            str (unique) — generated as "{role}-{name}-{id}"
  name            str — "Con", "Robbo", "Gavin"
  description     text
  status          str — "active" | "archived"
  role_id         int (FK to Role)
  created_at      datetime
```

Key changes from original draft:
- **`role_type` moved to Role table** — Role is a shared lookup referenced by both Persona and Position. Persona has `role_id` FK.
- **`slug` is generated** from `{role_name}-{persona_name}-{id}` for filesystem path (`data/personas/{slug}/`). Belongs to Persona — single join to Role for the role name.
- **`status` replaces `is_active`** — allows `active|archived` (extensible).
- **Pool membership deferred** — not modelled in v1 ERD. Pools may emerge as a view over Position/Role relationships.
- **No `org_id` on Persona** — Persona is org-independent. Org relationship is through Position (via Agent).
- **Skill file path derived from slug convention** — not stored on the model.

---

### 2.2 Agent Model Extensions
- [x] **Decision: What fields does Agent gain?**

**Depends on:** 1.1, 1.4, 2.1

**Current Agent fields (17):** id, session_uuid, claude_session_id, project_id, iterm_pane_id, tmux_pane_id, tmux_session, started_at, last_seen_at, ended_at, transcript_path, priority_score, priority_reason, priority_updated_at, context_percent_used, context_remaining_tokens, context_updated_at

**Proposed additions:**
- `persona_id` — FK to Persona (nullable, for backward compat)
- `mode` — enum if not derived from persona (see 1.4)

**Considerations:**
- Nullable FK means existing agents (pre-persona) still work
- `Agent.name` property currently returns `"ProjectName/uuid-prefix"` — with persona, returns `persona.name`
- Agent.state property is derived from current task — unchanged

**Resolution:** **Two new nullable FKs: `persona_id` (FK to Persona) and `position_id` (FK to Position).** No `mode` field (resolved in 1.4 — mode is prompt-level). Both nullable for backward compatibility with existing agents. Agent serves as the join between Persona and Position — when an agent is active with both FKs set, that persona is filling that position.

---

### 2.3 Persona Availability Constraint
- [x] **Decision: How do we enforce "one persona, one active agent at a time"?**

**Depends on:** 2.1, 2.2

**Context:** Functional outline §5.5: "A persona can only be active in one agent at a time."

**Options:**
- **A) Application-level check** — SessionCorrelator checks `Agent.query.filter_by(persona_id=X, ended_at=None).count() == 0` before assignment. No DB constraint.
- **B) Partial unique index** — `CREATE UNIQUE INDEX ON agents (persona_id) WHERE ended_at IS NULL AND persona_id IS NOT NULL`. DB enforces it. Race-condition proof.
- **C) Both** — Application check for friendly error messages + DB constraint as safety net.

**Considerations:**
- Partial unique index is clean and PostgreSQL supports it well
- Application check gives better error messages
- Need to handle the case where reaper hasn't cleaned up a dead agent yet (persona appears "busy" but isn't)

**Resolution:** **No constraint. Multiple agents can share the same persona simultaneously.** The "one persona, one active agent" rule from the functional outline is dropped. This is a computer system — duplicating a persona (spinning up multiple Cons) is advantageous. Enforcing human-based scarcity constraints on digital entities is unnecessary.

---

## 3. Skill File Infrastructure

### 3.1 Skill File Location & Structure
- [ ] **Decision: Where do skill files live and what's the directory layout?**

**Context:** Functional outline §5.3 proposes:
```
~/.headspace/personas/
  con/
    skill.md       # Core skills and preferences
    experience.md  # Append-only experience log
```

**Open questions:**
- [ ] Is `~/.headspace/` the right root? Or `~/.claude/headspace/` to co-locate with Claude Code's own config?
- [ ] Per-org skill extensions (vision §4.4): Where do "Con's dev-org-specific skills" vs "Con's global skills" live?
- [ ] Who creates the directory structure? App startup? CLI command? Manual setup?
- [ ] Token budget management (outline §7.3: 300-500 tokens target): Enforced by the app or advisory?

**Resolution:** _pending_

---

### 3.2 Skill File Loading Mechanism
- [ ] **Decision: How do skill files get into the agent's Claude Code context?**

**Context:** The functional outline says agents spin up "with persona identity + skill file loaded into context." But Claude Code sessions start independently — Headspace learns about them via hooks. The skill file needs to be in the context *at launch*.

**Options:**
- **A) CLI launcher injection** — `claude-headspace start --persona con` reads skill.md and injects it into the session's system prompt (via CLAUDE.md or a custom mechanism).
- **B) Claude Code memory mechanism** — Leverage Claude Code's own `~/.claude/` memory files to persist persona context.
- **C) Hook-based injection** — On `session-start` hook, Headspace sends persona context back to the session via tmux bridge. Late injection (after session starts) but doesn't require CLI changes.
- **D) Project-level CLAUDE.md injection** — Generate a persona-specific section in the project's CLAUDE.md before session launch.

**Considerations:**
- Option A is cleanest but requires CLI wrapper changes
- Option C is pragmatic — tmux bridge already exists for sending text to sessions
- Option D risks CLAUDE.md conflicts if multiple personas run on the same project
- The functional outline's v1 has operator-as-Gavin, so the operator is already manually launching sessions — they could use the CLI flag

**Resolution:** _pending_

---

## 4. Session & Lifecycle Integration

### 4.1 Persona Assignment Flow
- [ ] **Decision: When and how does a persona get assigned to an agent?**

**Depends on:** 1.1, 2.2, 3.2

**Context:** Currently, agents are created reactively: Claude Code session starts → hook fires → SessionCorrelator creates Agent. There's no pre-assignment step.

**Options:**
- **A) At session launch** — `claude-headspace start --persona con` passes persona slug in session-start hook payload. SessionCorrelator looks up persona, sets `agent.persona_id`.
- **B) Post-creation assignment** — Agent created without persona (as today). Operator assigns persona via dashboard UI or API call. Agent gains persona_id after the fact.
- **C) Both** — CLI flag for pre-assignment, dashboard UI for post-hoc assignment or reassignment.

**Considerations:**
- Option A is the clean path for v1 (operator launches sessions manually)
- Option B supports the case where an unplanned session starts and needs persona assignment
- The functional outline assumes personas are known before launch (operator picks from pool)
- Need to update the `session-start` hook payload to include persona slug

**Resolution:** _pending_

---

### 4.2 Dashboard Identity Display
- [ ] **Decision: How does persona identity appear on the agent card?**

**Depends on:** 2.2

**Context:** Current card shows `hero_chars` (2 chars) + `hero_trail` (6 chars) from session UUID. With personas, identity becomes meaningful.

**Options:**
- **A) Replace hero with persona name** — "Con" instead of "4b6f8a". Full name, not initials.
- **B) Persona name + UUID suffix** — "Con (4b6f)" for when Con has had multiple sessions.
- **C) Persona name as primary, UUID in detail view** — Hero shows "Con", session UUID moves to the info/detail panel.

**Sub-questions:**
- [ ] Color coding per persona? Per role_type? Per pool?
- [ ] Persona avatar/icon? (initials in a colored circle is the minimal version)
- [ ] What shows for agents without a persona? (backward compat — keep UUID display)

**Resolution:** _pending_

---

### 4.3 Workshop Mode — UI Implications
- [ ] **Decision: Does workshop mode need distinct visual treatment?**

**Depends on:** 1.4

**Context:** Workshop mode (Robbo) is fundamentally different — no code, documents only. The state machine is the same, but the *meaning* of states differs.

**Open questions:**
- [ ] Different card styling for workshop vs execution agents?
- [ ] Different Kanban column grouping? (Workshop agents in their own swim lane?)
- [ ] Different state labels? ("Drafting..." instead of "Processing..."?)
- [ ] Workshop output display? (Robbo produces documents — show document links on card?)

**Resolution:** _pending_

---

## 5. Forward-Compatibility Decisions

Design now, build later. These ensure v1 choices don't paint us into a corner.

### 5.1 Handoff Design Hooks (v2)
- [ ] **Decision: What v1 design choices does the handoff system (v2) need us to make now?**

**Context:** Handoff (§6) requires: detect context threshold → produce handoff artefact → end session → spin up new session with same persona. v2 scope, but v1 data model choices affect it.

**Considerations:**
- Agent model needs to support "this agent is a continuation of that agent" (linked list of sessions per persona per task?)
- Handoff artefact storage: ephemeral files at `~/.headspace/handoffs/{project}/{persona}-{timestamp}.md`
- Persona must be re-assignable to a new agent without breaking the "one active agent per persona" constraint (old agent ends first)
- Does the current Agent model need a `predecessor_id` FK? Or is that v2 migration territory?

**Resolution:** _pending_

---

### 5.2 PM Layer Hooks (v3)
- [ ] **Decision: What v1 design choices does Gavin's PM automation (v3) need us to make now?**

**Context:** In v3, Gavin receives specs and drafts task decomposition. Currently, Tasks belong to Agents (1:N). There's no concept of "a PM assigns tasks across agents."

**Considerations:**
- Task model may eventually need a `assigned_by_persona_id` or `parent_task_id` for PM-decomposed work
- The current Task belongs to one Agent. Cross-agent task assignment would need a different model (WorkItem? Assignment?)
- For v1, operator-as-Gavin means no code changes — but should we add nullable fields now?
- Or: keep Task model as-is, add a higher-level WorkItem model in v3 that links to multiple Tasks across Agents?

**Resolution:** _pending_

---

### 5.3 Multi-Org Readiness (Phase 2+)
- [ ] **Decision: What naming/structure conventions should v1 follow to not conflict with multi-org?**

**Context:** Phase 2 introduces Marketing org. Phase 4 introduces cross-org persona sharing.

**Considerations:**
- If Persona model exists in v1, should it have a nullable `org_id` FK from the start?
- Config structure: `personas:` at root level (global) vs `organisations.dev.personas:` (org-scoped)
- Skill file paths: `~/.headspace/personas/{slug}/` (global) vs `~/.headspace/orgs/{org}/personas/{slug}/` (org-scoped)
- Pool definitions: global or per-org?

**Resolution:** _pending_

---

## 6. Implementation Sequence Alignment

Once decisions above are resolved, map to implementation order.

### 6.1 Sprint Structure
- [ ] **Decision: How many sprints for Epic 1 (Persona System & Workshop Mode)?**
- [ ] Map resolved decisions to sprint deliverables
- [ ] Define acceptance criteria for each sprint
- [ ] Identify what can be tested against the running app at each stage

### 6.2 Migration Strategy
- [ ] **Decision: One migration or phased?**
- [ ] Persona table migration
- [ ] Agent extensions migration
- [ ] Availability constraint migration
- [ ] Order and dependencies

### 6.3 Test Strategy
- [ ] Targeted test plan for persona system
- [ ] Integration test approach (real DB)
- [ ] What to verify against the running app (not just unit tests)

---

## Workshop Log

Track decisions and rationale as we resolve them.

| Date | Decision | Resolution | Rationale |
|------|----------|------------|-----------|
| 2026-02-16 | 1.1 Persona Storage Model | DB + Filesystem hybrid: Persona table in PostgreSQL (identity, metadata, relational queries) + markdown files on disk (skill.md, experience.md as system prompt assets). Config.yaml excluded — app config only. | Codebase is fully relational (FK integrity required). Markdown files are accessible to system agents, support version control, and map to real-world modelling (people have skills and accumulate experience). |
| 2026-02-16 | 1.2 Config Location | Convention-based `data/` directory at project root. Persona/pool definitions in DB. Skill assets at `data/personas/{role}-{name}-{id}/`. No config.yaml involvement — path is a project convention, not a setting. | Domain data belongs in the project tree (not hidden dot-paths), organised by subsystem. Slug format `{role}-{name}-{id}` gives natural filesystem sorting by role then name. Config.yaml stays pure app config. |
| 2026-02-16 | 1.3 Organisation Model | Yes — minimal Organisation table in v1. Exact schema deferred to ERD design session. | One small migration now avoids a disruptive one later. The platform vision makes orgs first-class; having the table from the start means Persona/Agent can reference it cleanly when relationships are defined. |
| 2026-02-16 | 1.4 Agent Mode Field | No mode field on Agent. Mode is a prompt-level concern expressed through persona skill.md content, not a database column. | A DB enum cannot meaningfully describe or constrain agent behaviour. Agents can execute code, read/write files, produce documents — their mode is shaped by system prompt instructions, not schema. |
| 2026-02-17 | 2.1 Persona Table Schema | Persona: id, slug (generated {role}-{name}-{id}), name, description, status, role_id FK, created_at. Role extracted as shared lookup table. | Role is system-wide vocabulary shared by Persona ("I am") and Position ("I need"). Slug belongs to Persona for filesystem path. Status replaces is_active. No org_id on Persona — org relationship through Position via Agent. |
| 2026-02-17 | 2.2 Agent Extensions | Two new nullable FKs: persona_id, position_id. No mode field. Agent is the join between Persona and Position. | Nullable FKs for backward compat. Agent having both FKs means it serves as the PositionAssignment — no separate join table needed. |
| 2026-02-17 | 2.3 Availability Constraint | No constraint. Multiple agents can share the same persona simultaneously. | Enforcing human scarcity on digital entities is unnecessary. Duplicating a persona (multiple Cons) is advantageous. |

---

*This document is the working artifact for the Agent Teams design workshop. Update it as decisions are made.*
