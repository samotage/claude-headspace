# Agent Teams — Design Workshop

**Date:** 16-20 February 2026
**Status:** Complete — all 15 decisions resolved, Epic 8 roadmap generated
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

**Context:** The functional outline puts persona identity in config.yaml (§5.2) and skill files on disk (§5.3). The codebase is fully relational — Agent, Command, Turn, Event all use PostgreSQL FKs. Agent currently has no persona concept.

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

**Context:** The functional outline (§9.1) says Agent gains a `mode` field: `workshop` | `execution`. Workshop mode (Robbo) is "collaborative, iterative, document-producing." Execution mode is "command-scoped, code-producing."

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
- Agent.state property is derived from current command — unchanged

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
- [x] **Decision: Where do skill files live and what's the directory layout?**

**Context:** Functional outline §5.3 proposes:
```
~/.headspace/personas/
  con/
    skill.md       # Core skills and preferences
    experience.md  # Append-only experience log
```

**Open questions:**
- [x] Is `~/.headspace/` the right root? Or `~/.claude/headspace/` to co-locate with Claude Code's own config?
- [x] Per-org skill extensions (vision §4.4): Where do "Con's dev-org-specific skills" vs "Con's global skills" live?
- [x] Who creates the directory structure? App startup? CLI command? Manual setup?
- [x] Token budget management (outline §7.3: 300-500 tokens target): Enforced by the app or advisory?

**Resolution:** **Location resolved in 1.2: `data/personas/{slug}/skill.md` and `data/personas/{slug}/experience.md`.** Remaining sub-questions:

- **Per-org skill extensions:** Deferred. Personas are org-independent (2.1). V1 has one org. Org-specific overlays are Phase 2+ if the need emerges.
- **Directory creation:** The application manages it. Persona registration (via CLI command or API) creates the directory and seeds template files. CLI is the preferred interface because it's agent-operable via tools — no MCP context pollution. Agents can also update skill files and experience logs through the same filesystem path as part of their self-improvement loop.
- **Token budget:** No management. Skill files are lightweight priming signals that activate training the model already has, not knowledge dumps. Token limits will continue increasing. If skill file size ever becomes an issue, we'll address it then. No advisory display, no enforcement, no target range.

---

### 3.2 Skill File Loading Mechanism
- [x] **Decision: How do skill files get into the agent's Claude Code context?**

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

**Resolution:** **First-prompt injection via tmux bridge, triggered post-registration (BMAD pattern).**

The existing `agent_lifecycle.create_agent()` already spins up Claude Code sessions in detached tmux sessions via `claude-headspace start`. The persona layer adds:

1. `create_agent()` gains an optional `persona_slug` parameter
2. Persona slug is passed through the CLI to the registration payload
3. Hook receiver processes `session-start` → detects persona slug → looks up Persona → sets `agent.persona_id`
4. **Post-registration:** Headspace reads `data/personas/{slug}/skill.md` + `experience.md` and sends the combined content as the **first user message** via the existing tmux bridge `send_text()`
5. Agent reads its skill file and responds in character (e.g., "Hi, I'm Con. Backend developer. What would you like me to work on?")

Key design points:
- **No system prompt hacking.** Persona identity is a conversation-level concern, injected as a user message — the same BMAD priming pattern that's proven effective.
- **`claude-headspace start` unchanged for general sessions.** Persona injection only applies when the system creates an agent for a specific persona. General-purpose sessions (operator launches CLI directly) remain anonymous.
- **Existing infrastructure.** The tmux bridge `send_text()` is battle-tested. No new transport mechanism needed.
- **Two creation paths preserved:** CLI (`claude-headspace start`) for general sessions, system-initiated (`create_agent()` with persona) for persona-backed agents.

---

## 4. Session & Lifecycle Integration

### 4.1 Persona Assignment Flow
- [x] **Decision: When and how does a persona get assigned to an agent?**

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

**Resolution:** **Two assignment paths, no post-hoc reassignment.**

Both paths converge to the same injection pipeline (resolved in 3.2):

1. **System-initiated:** `create_agent(persona_slug="con")` — the production path for dashboard or future PM automation (Gavin v3). Passes persona slug through to the hook payload.
2. **CLI-initiated:** `claude-headspace start --persona con` — operator's escape hatch for ad-hoc persona sessions (debugging skill files, quick testing). Passes persona slug in the session-start hook payload.

In both cases:
- Vanilla Claude Code session starts → hook fires → SessionCorrelator creates Agent with `persona_id` set at registration time
- Post-registration: skill.md + experience.md injected via tmux bridge (per 3.2)
- Agent responds in character

**Post-hoc reassignment is excluded.** Assigning a persona to an already-running anonymous agent is a mid-conversation identity injection — a brain transplant. If an agent needs a persona, start it with one. Anonymous sessions (operator launches CLI without `--persona`) remain anonymous.

---

### 4.2 Dashboard Identity Display
- [x] **Decision: How does persona identity appear on the agent card?**

**Depends on:** 2.2

**Context:** Current card shows `hero_chars` (2 chars) + `hero_trail` (6 chars) from session UUID. With personas, identity becomes meaningful.

**Options:**
- **A) Replace hero with persona name** — "Con" instead of "4b6f8a". Full name, not initials.
- **B) Persona name + UUID suffix** — "Con (4b6f)" for when Con has had multiple sessions.
- **C) Persona name as primary, UUID in detail view** — Hero shows "Con", session UUID moves to the info/detail panel.

**Sub-questions:**
- [x] Color coding per persona? Per role_type? Per pool?
- [x] Persona avatar/icon? (initials in a colored circle is the minimal version)
- [x] What shows for agents without a persona? (backward compat — keep UUID display)

**Resolution:** **Persona name as hero, role as suffix. Technical details preserved elsewhere.**

- **Hero text:** Persona name (e.g., "Con") replaces the UUID hero (`hero_chars` + `hero_trail`). Role shown as a suffix (e.g., "Con — developer").
- **Technical details:** Session UUID, claude_session_id, pane IDs, and other technical identifiers remain accessible in the agent info panel on the dashboard and in project/activity page agent summaries.
- **Anonymous agents:** Agents without a persona retain the existing UUID-based hero display. Full backward compatibility.
- **No colour coding.** Not needed at this stage.
- **No avatar/icon.** Name as text is sufficient. Keep it simple.

---

### 4.3 Workshop Mode — UI Implications
- [x] **Decision: Does workshop mode need distinct visual treatment?**

**Depends on:** 1.4

**Context:** Workshop mode (Robbo) is fundamentally different — no code, documents only. The state machine is the same, but the *meaning* of states differs.

**Open questions:**
- [x] Different card styling for workshop vs execution agents?
- [x] Different Kanban column grouping? (Workshop agents in their own swim lane?)
- [x] Different state labels? ("Drafting..." instead of "Processing..."?)
- [x] Workshop output display? (Robbo produces documents — show document links on card?)

**Resolution:** **No distinct visual treatment in v1. Kanban evolution deferred — build bottom-up.**

- **Card styling:** No difference between workshop and execution agents. The role suffix (4.2) provides enough context. Keeping it simple given existing complexity.
- **State labels / swim lanes / output display:** All deferred.

**Deferred dependency — Kanban hierarchy:**

The current Kanban tracks **agent state** at the atomic level (command/turn processing, minutes-to-hours timescale). Workshop and persona-driven work introduces a higher-level concern: **work item progress** across multi-day, multi-session event horizons. This creates a natural two-level hierarchy:

- **Level 1 — Work Items:** Workshops, feature implementations, review cycles. Multi-day. Survives agent restarts and handoffs. Output of one work item feeds into the next.
- **Level 2 — Agent Activity:** The current atomic Kanban. Minutes-to-hours. What's happening right now.

This is **not designed in v1.** The correct implementation sequence is bottom-up: personas first → basic organisation → then the Kanban evolves based on what's actually running. The work-item layer and Kanban modifications will become clear once personas and org structure are operational and providing real data about how multi-session work flows through the system.

---

## 5. Forward-Compatibility Decisions

Design now, build later. These ensure v1 choices don't paint us into a corner.

### 5.1 Handoff Design Hooks (v2)
- [x] **Decision: What v1 design choices does the handoff system (v2) need us to make now?**

**Context:** Handoff (§6) requires: detect context threshold → produce handoff artefact → end session → spin up new session with same persona. v2 scope, but v1 data model choices affect it.

**Considerations:**
- Agent model needs to support "this agent is a continuation of that agent" (linked list of sessions per persona per command?)
- Handoff artefact storage: ephemeral files at `~/.headspace/handoffs/{project}/{persona}-{timestamp}.md`
- Persona must be re-assignable to a new agent without breaking the "one active agent per persona" constraint (old agent ends first)
- Does the current Agent model need a `predecessor_id` FK? Or is that v2 migration territory?

**Resolution:** **Hybrid handoff — DB metadata + filesystem content, operator-initiated trigger.**

#### Storage: DB for orchestration, filesystem for context

- **DB (Handoff record):** Lightweight metadata — id (int PK), agent_id (FK, outgoing agent), reason (context_limit, shift_end, task_boundary), file_path (pointer to handoff document), created_at. Plus a **text field containing the injection prompt** for the successor agent. This prompt is sent directly via tmux bridge — no tools needed for the successor to receive it.
- **Filesystem (handoff document):** Rich markdown written by the outgoing agent at `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`. Contains first-person context: what was being worked on, current progress, key decisions and rationale, blockers, files modified, next steps. The successor agent reads this file using its own tools (Read, Grep, etc.).

**Design principle:** The DB content IS the orchestration prompt ("Continuing from Agent 4b6f8a2c. Read `data/personas/con/handoffs/20260220T143025-4b6f8a2c.md` to pick up context. The task is: ..."). The file IS the detailed context. Two-phase bootstrap: successor gets the prompt immediately, deepens understanding by reading the file.

#### Trigger: operator-initiated via dashboard

- Headspace monitors `context_percent_used` on each agent
- When context reaches a configurable threshold, a **handoff button appears on the agent card**
- **Operator decides when to trigger** — not automatic
- This deliberately allows compaction to work naturally. The operator judges whether compaction is handling context well enough or whether a clean handoff is needed
- Manual trigger also serves as the **debugging and tuning mechanism** — wind down the threshold, fire the handoff, inspect the output, refine the prompt. Human-in-the-loop iteration on handoff quality before any automation
- Future: once the handoff prompt is tuned and reliable, auto-trigger can be added. But v1 is manual only

#### Handoff flow

1. Headspace detects context threshold → handoff button appears on agent card
2. Operator clicks handoff button
3. Headspace sends handoff instruction to outgoing agent via tmux bridge: "Write your handoff document to `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`"
4. Agent writes the file using its Write tool (agent-as-author — it has the richest context)
5. Agent confirms completion in conversation
6. Headspace detects confirmation via existing hook/turn processing
7. Headspace creates Handoff DB record (metadata + injection prompt pointing to the file)
8. Outgoing agent session ends
9. New agent spins up with same persona (via `create_agent()` with persona_slug)
10. Headspace sends injection prompt from Handoff DB record via tmux bridge
11. Successor agent reads the handoff file with its own tools → continues work

#### Agent continuity chain

- Agent gains `previous_agent_id` (nullable self-referential FK) linking consecutive sessions for the same body of work
- First agent in a chain has `previous_agent_id = NULL`
- The Handoff record belongs to the outgoing agent. The successor finds it via the `previous_agent_id` chain (for system/operator querying — the agent itself receives the prompt directly)

#### File lifecycle

- Handoff files accumulate under `data/personas/{slug}/handoffs/`
- No cleanup in v1 — files are small text documents
- Cleanup will be addressed as part of a future system management PRD (covering DB trimming, temp file cleanup, and other housekeeping as a single effort)

#### Key design rationale

- **Agent-as-author:** The outgoing agent knows what it was thinking — dead ends explored, reasoning behind approaches, where it was mid-problem. Headspace can reconstruct *what happened* from DB data but not *what the agent understood*. First-person context is what makes handoffs work.
- **File-native consumption:** Agents read files naturally via tools. No custom API endpoint needed to serve handoff content. Rich markdown with code snippets, file trees, decision logs — no DB column size concerns.
- **Consistent with persona asset pattern:** skill.md, experience.md, handoffs/ — all filesystem assets under the persona tree, same mental model.
- **Prompt compliance is iterable:** The manual trigger creates a tight feedback loop for tuning the handoff instruction prompt. Write the prompt, fire it, inspect the output, refine. Once reliable, automation can follow.

---

### 5.2 PM Layer Hooks (v3)
- [x] **Decision: What v1 design choices does Gavin's PM automation (v3) need us to make now?**

**Context:** In v3, Gavin receives specs and drafts task decomposition. Currently, Commands belong to Agents (1:N). There's no concept of "a PM assigns tasks across agents."

**Resolution:** **Deferred until personas and handoffs are operational.** The PM layer (Gavin assigning work across agents) requires a concrete understanding of how cross-agent task decomposition works. That understanding will come from running the persona system and seeing how multi-agent work actually flows. No premature schema additions — Command model stays as-is for now.

---

### 5.3 Multi-Org Readiness (Phase 2+)
- [x] **Decision: What naming/structure conventions should v1 follow to not conflict with multi-org?**

**Context:** Phase 2 introduces Marketing org. Phase 4 introduces cross-org persona sharing.

**Resolution:** **Deferred.** Personas are org-independent by design (decision 2.1 — no org_id on Persona, org relationship through Position via Agent). This already avoids painting v1 into a corner. Multi-org naming and structure conventions will be designed when the second org (Marketing) is on the horizon, informed by operational experience with the dev org.

---

## 6. Implementation Sequence Alignment

Once decisions above are resolved, map to implementation order.

### 6.1 Sprint Structure
- [x] **Decision: How many sprints for Epic 8 (Personable Agents)?**
- [x] Map resolved decisions to sprint deliverables
- [x] Define acceptance criteria for each sprint
- [x] Identify what can be tested against the running app at each stage

**Resolution:** **14 sprints, linear sequencing, detailed roadmap generated.** See `docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md`. Sprints are intentionally atomic — each is independently testable with a clear "done" signal. Grouped into 5 phases: Data Foundation (S1-S4), Filesystem + Registration (S5-S6), Agent Identity (S7-S9), Dashboard Display (S10-S11), Handoff System (S12-S14).

### 6.2 Migration Strategy
- [x] **Decision: One migration or phased?**
- [x] Persona table migration
- [x] Agent extensions migration
- [x] Availability constraint migration
- [x] Order and dependencies

**Resolution:** **Phased migrations — one per sprint as needed.** S1: Role + Persona tables. S2: Organisation table. S3: Position table. S4: Agent extensions (3 nullable FKs). S12: Handoff table. Each migration is additive and non-breaking. No availability constraint migration (decision 2.3 — no constraint).

### 6.3 Test Strategy
- [x] Targeted test plan for persona system
- [x] Integration test approach (real DB)
- [x] What to verify against the running app (not just unit tests)

**Resolution:** **Defined per sprint in the roadmap.** Each sprint has acceptance criteria that specify what to test. Model sprints (S1-S4, S12) testable with DB queries. Registration (S6) testable end-to-end (CLI + DB + filesystem). Agent identity (S7-S9) requires running agent with real hooks. Dashboard (S10-S11) requires visual verification via Playwright screenshots. Handoff (S13-S14) requires full end-to-end cycle with running agents.

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
| 2026-02-17 | 3.1 Skill File Location & Structure | Location resolved by 1.2. App manages directory creation via CLI/API on persona registration. Per-org extensions deferred. No token budget management. | Skill files are lightweight priming signals, not knowledge dumps — no budget needed. CLI is the preferred management interface because agents can operate it via tools (no MCP pollution). Org-specific overlays are Phase 2+ if the need emerges. |
| 2026-02-17 | 3.2 Skill File Loading Mechanism | First-prompt injection via tmux bridge (BMAD pattern). `create_agent()` gains optional `persona_slug`. Post-registration, Headspace reads skill.md + experience.md and sends as first user message via existing `send_text()`. Agent responds in character. General sessions unchanged. | Proven BMAD priming pattern. Uses existing tmux bridge infrastructure. No system prompt hacking — persona is conversation-level. Two creation paths: CLI for general, `create_agent()` for persona-backed. Grounded in existing `agent_lifecycle.create_agent()` mechanism. |
| 2026-02-17 | 4.1 Persona Assignment Flow | Two paths, same pipeline: system-initiated (`create_agent(persona_slug=)`) for production use, CLI-initiated (`--persona con`) for operator ad-hoc sessions. Both pass slug through hook payload → persona_id set at registration → skill injection via tmux bridge. No post-hoc reassignment — brain transplants excluded. | CLI flag is essentially free (same injection pipeline). Operator needs an escape hatch for debugging/testing persona sessions without going through the dashboard. Post-hoc assignment is semantically messy (mid-conversation identity injection) and unnecessary. |
| 2026-02-20 | 4.2 Dashboard Identity Display | Persona name as hero text, role as suffix (e.g., "Con — developer"). Technical details (UUID, session ID, pane IDs) preserved in agent info panel and project/activity summaries. Anonymous agents keep UUID hero. No colour coding, no avatars — name as text. | Simple and clean. Persona identity is meaningful; UUID is not. Technical details still accessible where needed. Visual embellishments deferred — not needed at this stage. |
| 2026-02-20 | 4.3 Workshop Mode — UI Implications | No distinct visual treatment in v1. Kanban hierarchy (work items above atomic agent activity) identified as a deferred dependency — build bottom-up: personas → org → then Kanban evolves from real operational data. | Premature to design the work-item Kanban layer without operational experience. The current atomic Kanban works for agent state. Higher-level work tracking will become clear once personas and org structure are running. |
| 2026-02-20 | 5.1 Handoff Design Hooks | Hybrid handoff: DB metadata (Handoff record with injection prompt) + filesystem content (agent-written markdown at `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`). Operator-initiated via dashboard button at context threshold. Agent-as-author writes the handoff file. Agent gains `previous_agent_id` self-ref FK for continuity chain. No auto-trigger in v1. File cleanup deferred to system management PRD. | Agent has the richest context — first-person handoffs beat reconstruction. File-native consumption (Read tool) is natural for agents. Manual trigger enables iterative prompt tuning with human-in-the-loop before automation. Two-phase bootstrap: DB prompt bootstraps immediately, file deepens understanding. |
| 2026-02-20 | 5.2 PM Layer Hooks | Deferred. Command model stays as-is. PM task decomposition design requires operational experience with personas first. | No concrete model for cross-agent task assignment yet. Bottom-up: personas → handoffs → then PM layer informed by real usage. |
| 2026-02-20 | 5.3 Multi-Org Readiness | Deferred. Personas are already org-independent (no org_id). No v1 conventions needed. | Existing design doesn't paint us into a corner. Design multi-org when the second org is on the horizon. |
| 2026-02-20 | 6.1 Sprint Structure | 14 atomic sprints in 5 phases, linear sequencing. Full roadmap at `docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md`. | Bottom-up build: models → filesystem → registration → agent identity → dashboard → handoff. Each sprint independently testable. |
| 2026-02-20 | 6.2 Migration Strategy | Phased — one migration per sprint as needed. All additive and non-breaking. | Matches atomic sprint approach. No risky multi-table migrations. |
| 2026-02-20 | 6.3 Test Strategy | Defined per sprint in roadmap acceptance criteria. Range from DB queries (models) to full E2E with running agents (handoff). | Matches the "verify against running app" lesson. Visual verification for UI sprints. |

---

*This document is the working artifact for the Agent Teams design workshop. Update it as decisions are made.*
