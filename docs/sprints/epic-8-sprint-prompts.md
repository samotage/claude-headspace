# Epic 8 Sprint Prompts for PRD Workshop

**Epic:** Epic 8 — Personable Agents
**Reference:** [`docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md`](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md)

---

## Context Documents

| Document                                                                                    | Purpose                                                                    |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md)       | Primary reference for sprint scope, deliverables, acceptance criteria      |
| [Agent Teams Workshop](../workshop/agent-teams-workshop.md)                                 | All 15 design decisions with rationale (authoritative for design choices)  |
| [ERD Full](../workshop/erds/headspace-org-erd-full.md)                                      | Entity relationship diagram (reference only — workshop decisions override) |
| [Platform Vision](../conceptual/headspace-platform-vision.md)                               | Long-term platform vision for agent teams                                 |
| [Functional Outline](../conceptual/headspace-agent-teams-functional-outline.md)             | Functional requirements outline for agent teams                           |
| [Overarching Roadmap](../roadmap/claude_headspace_v3.1_overarching_roadmap.md)              | Epic 8 goals, success criteria, dependencies                              |

---

## Sprint Prompts

### Epic 8 Sprint 1: Role + Persona Database Models

**PRD:** `docs/prds/persona/e8-s1-role-persona-models-prd.md`

> Create a PRD for the Role and Persona database models. This is Epic 8, Sprint 1. Reference Sprint 1 (E8-S1) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-1-role--persona-database-models-e8-s1) and design decisions 1.1, 1.2, 2.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Deliverables:**
>
> **Role Table:**
>
> - New `Role` SQLAlchemy model with integer PK
> - Fields: `id` (int PK), `name` (str, unique — e.g., "developer", "tester", "pm", "architect"), `description` (text), `created_at` (datetime)
> - Shared lookup table — referenced by both Persona ("I am a developer") and Position ("this seat needs a developer")
> - Alembic migration
>
> **Persona Table:**
>
> - New `Persona` SQLAlchemy model with integer PK
> - Fields: `id` (int PK), `slug` (str, unique — generated as `{role_name}-{persona_name}-{id}`), `name` (str), `description` (text), `status` (str — "active" | "archived"), `role_id` (int FK to Role), `created_at` (datetime)
> - Slug generated from role name + persona name + ID for filesystem path key (`data/personas/{slug}/`)
> - Status replaces boolean is_active for extensibility
> - Alembic migration
>
> **Model Registration:**
>
> - Both models registered with Flask-SQLAlchemy
> - Relationship defined: `Role.personas` ↔ `Persona.role`
>
> **Technical Decisions (all decided — see workshop):**
>
> - Integer PKs throughout (matches existing codebase: Agent, Command, Turn)
> - Slug format `{role_name}-{persona_name}-{id}` for natural filesystem sorting
> - Status field (`active|archived`) instead of boolean `is_active`
> - Role is a shared lookup, not org-scoped
> - No pool membership in v1
>
> **Data Model:**
>
> ```python
> class Role(db.Model):
>     id = Column(Integer, primary_key=True)
>     name = Column(String, unique=True, nullable=False)
>     description = Column(Text)
>     created_at = Column(DateTime, default=func.now())
>
> class Persona(db.Model):
>     id = Column(Integer, primary_key=True)
>     slug = Column(String, unique=True, nullable=False)
>     name = Column(String, nullable=False)
>     description = Column(Text)
>     status = Column(String, default="active")
>     role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
>     created_at = Column(DateTime, default=func.now())
> ```
>
> **Integration Points:**
>
> - New files: `src/claude_headspace/models/role.py`, `src/claude_headspace/models/persona.py`
> - Register in `src/claude_headspace/models/__init__.py`
> - Migration: `migrations/versions/xxx_add_role_persona_tables.py`
> - Existing models unaffected

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decisions 1.1, 1.2, 2.1)
- docs/workshop/erds/headspace-org-erd-full.md (reference only — workshop decisions override where they diverge)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 1 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 8 Sprint 2: Organisation Database Model

**PRD:** `docs/prds/persona/e8-s2-organisation-model-prd.md`

> Create a PRD for the Organisation database model. This is Epic 8, Sprint 2. Reference Sprint 2 (E8-S2) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-2-organisation-database-model-e8-s2) and design decision 1.3 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Deliverables:**
>
> **Organisation Table:**
>
> - New `Organisation` SQLAlchemy model with integer PK
> - Fields: `id` (int PK), `name` (str), `description` (text), `status` (str — "active" | "dormant" | "archived"), `created_at` (datetime)
> - Minimal table — exists to avoid a disruptive migration later when multi-org support arrives
> - Alembic migration
>
> **Seed Data:**
>
> - One Organisation record: name="Development", status="active"
> - Seed via migration data operation or application startup
>
> **Technical Decisions (all decided — see workshop):**
>
> - Minimal Organisation table in v1 — one small migration now avoids a disruptive one later
> - Three-state status: active, dormant, archived
> - No Organisation-level configuration in config.yaml (config.yaml is app config only)
>
> **Data Model:**
>
> ```python
> class Organisation(db.Model):
>     id = Column(Integer, primary_key=True)
>     name = Column(String, nullable=False)
>     description = Column(Text)
>     status = Column(String, default="active")
>     created_at = Column(DateTime, default=func.now())
> ```
>
> **Integration Points:**
>
> - New file: `src/claude_headspace/models/organisation.py`
> - Register in `src/claude_headspace/models/__init__.py`
> - Migration: `migrations/versions/xxx_add_organisation_table.py`
> - Existing models unaffected

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 1.3)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 2 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 8 Sprint 3: Position Database Model

**PRD:** `docs/prds/persona/e8-s3-position-model-prd.md`

> Create a PRD for the Position database model with self-referential hierarchy. This is Epic 8, Sprint 3. Reference Sprint 3 (E8-S3) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-3-position-database-model-e8-s3) and the ERD at [headspace-org-erd-full.md](../workshop/erds/headspace-org-erd-full.md).
>
> **Dependencies:** E8-S1 (Role table), E8-S2 (Organisation table)
>
> **Deliverables:**
>
> **Position Table:**
>
> - New `Position` SQLAlchemy model with integer PK
> - Fields: `id` (int PK), `org_id` (int FK to Organisation), `role_id` (int FK to Role), `title` (str), `reports_to_id` (int FK to Position, self-ref, nullable), `escalates_to_id` (int FK to Position, self-ref, nullable), `level` (int — depth in hierarchy), `is_cross_cutting` (bool)
> - Self-referential hierarchy: `reports_to_id` and `escalates_to_id` both point to Position
> - Escalation path can differ from reporting path (e.g., Verner reports to Gavin but escalates architectural issues to Robbo)
> - Alembic migration
>
> **Relationships:**
>
> - `Position.role` → Role (what this seat needs)
> - `Position.organisation` → Organisation
> - `Position.reports_to` → Position (self-ref)
> - `Position.escalates_to` → Position (self-ref)
> - `Position.direct_reports` → list of Positions that report to this one
>
> **Technical Decisions (all decided):**
>
> - Position hierarchy is self-referential via `reports_to_id` and `escalates_to_id`
> - The operator (Sam) is not modelled as a Persona — top of hierarchy implicitly reports to operator
> - Role is shared lookup referenced by both Persona and Position — match on role_id to find personas that can fill a position
>
> **Data Model:**
>
> ```python
> class Position(db.Model):
>     id = Column(Integer, primary_key=True)
>     org_id = Column(Integer, ForeignKey("organisation.id"), nullable=False)
>     role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
>     title = Column(String, nullable=False)
>     reports_to_id = Column(Integer, ForeignKey("position.id"), nullable=True)
>     escalates_to_id = Column(Integer, ForeignKey("position.id"), nullable=True)
>     level = Column(Integer, default=0)
>     is_cross_cutting = Column(Boolean, default=False)
> ```
>
> **Integration Points:**
>
> - New file: `src/claude_headspace/models/position.py`
> - Register in `src/claude_headspace/models/__init__.py`
> - Migration: `migrations/versions/xxx_add_position_table.py`
> - References Role (E8-S1) and Organisation (E8-S2)

Review design decisions and guidance at:

- docs/workshop/erds/headspace-org-erd-full.md (Position entity)
- docs/workshop/agent-teams-workshop.md (Decision 2.1 — Role as shared lookup)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 3 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 8 Sprint 4: Agent Model Extensions

**PRD:** `docs/prds/persona/e8-s4-agent-model-extensions-prd.md`

> Create a PRD for extending the existing Agent model with persona, position, and predecessor foreign keys. This is Epic 8, Sprint 4. Reference Sprint 4 (E8-S4) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-4-agent-model-extensions-e8-s4) and design decisions 2.2, 2.3 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S1 (Persona table), E8-S3 (Position table)
>
> **Deliverables:**
>
> **Agent Model Extensions:**
>
> - Add `persona_id` (int FK to Persona, nullable) — which persona drives this agent
> - Add `position_id` (int FK to Position, nullable) — which org chart position this agent represents
> - Add `previous_agent_id` (int FK to Agent, self-ref, nullable) — predecessor in handoff continuity chain
> - All nullable for backward compatibility — existing agents unaffected
> - Alembic migration
>
> **Relationships:**
>
> - `Agent.persona` → Persona
> - `Agent.position` → Position
> - `Agent.previous_agent` → Agent (self-ref)
> - `Agent.successor_agents` → list of Agents with this agent as predecessor
> - `Persona.agents` → list of Agents driven by this persona
>
> **Design Notes:**
>
> - Agent serves as the join between Persona and Position — no separate PositionAssignment table
> - Multiple agents can share the same persona simultaneously (no availability constraint)
> - First agent in a continuity chain has `previous_agent_id = NULL`
>
> **Technical Decisions (all decided — see workshop):**
>
> - No PositionAssignment join table — Agent has both persona_id and position_id directly (decision 2.2)
> - No availability constraint — multiple agents can share the same persona (decision 2.3)
> - previous_agent_id self-ref FK for continuity chain (decision 5.1)
> - All new fields nullable for backward compatibility (decision 2.2)
>
> **Integration Points:**
>
> - Modify: `src/claude_headspace/models/agent.py` — add three nullable FK columns
> - Migration: `migrations/versions/xxx_add_agent_persona_position_predecessor.py`
> - All existing Agent queries and services must continue working unchanged

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decisions 2.2, 2.3, 5.1)
- docs/workshop/erds/headspace-org-erd-full.md (Agent extensions)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 4 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing Agent model for context:

- src/claude_headspace/models/agent.py

---

### Epic 8 Sprint 5: Persona Filesystem Assets

**PRD:** `docs/prds/persona/e8-s5-persona-filesystem-assets-prd.md`

> Create a PRD for the persona filesystem asset convention — the `data/personas/{slug}/` directory structure with skill.md and experience.md template files. This is Epic 8, Sprint 5. Reference Sprint 5 (E8-S5) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-5-persona-filesystem-assets-e8-s5) and design decisions 1.2, 3.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S1 (Persona model — slug format determines directory names)
>
> **Deliverables:**
>
> **Directory Convention:**
>
> - `data/` directory at project root for domain data
> - `data/personas/{slug}/` subdirectory per persona (e.g., `data/personas/developer-con-1/`)
> - Path derived from persona slug — not stored on model, not configurable
>
> **Template Files:**
>
> - `skill.md` — Core competencies, preferences, behavioural instructions. Stable, operator-curated. The "who you are and how you work" file
> - `experience.md` — Append-only log of learned experience. Evolves through agent self-improvement and periodic curation. The "what you've done and learned" file
>
> **Asset Utility Functions:**
>
> - Resolve persona slug → filesystem path
> - Read skill.md content given a persona slug
> - Read experience.md content given a persona slug
> - Check whether asset files exist for a given persona
> - Create persona directory with template files
>
> **Technical Decisions (all decided — see workshop):**
>
> - Convention-based `data/` directory at project root — not a configurable setting (decision 1.2)
> - Slug format `{role}-{name}-{id}` for natural filesystem sorting (decision 1.2)
> - Config.yaml is NOT involved — path is a project convention (decision 1.2)
> - Skill files are lightweight priming signals — no token budget management (decision 3.1)
> - Per-org skill extensions deferred to Phase 2+ (decision 3.1)
>
> **File Templates:**
>
> ```markdown
> <!-- data/personas/{slug}/skill.md -->
> # {Persona Name} — {Role Name}
>
> ## Core Identity
> [Who this persona is]
>
> ## Skills & Preferences
> [Key competencies and working style]
>
> ## Communication Style
> [How this persona communicates]
> ```
>
> ```markdown
> <!-- data/personas/{slug}/experience.md -->
> # Experience Log — {Persona Name}
>
> <!-- Append-only. New entries at top. Periodically curated. -->
> ```
>
> **Integration Points:**
>
> - New file: `src/claude_headspace/services/persona_assets.py` (or similar utility module)
> - Used by E8-S6 (registration creates directory + files)
> - Used by E8-S9 (skill injection reads files)
> - Used by E8-S14 (handoff writes to `data/personas/{slug}/handoffs/`)

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decisions 1.1, 1.2, 3.1)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 5 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 8 Sprint 6: Persona Registration

**PRD:** `docs/prds/persona/e8-s6-persona-registration-prd.md`

> Create a PRD for persona registration — a CLI command and/or API endpoint that creates a Persona DB record and filesystem assets in a single operation. This is Epic 8, Sprint 6. Reference Sprint 6 (E8-S6) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-6-persona-registration-e8-s6) and design decision 3.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S1 (Role + Persona models), E8-S5 (filesystem asset convention)
>
> **Deliverables:**
>
> **Registration Operation:**
>
> - Accepts: persona name, role name, optional description
> - Looks up or creates the Role record
> - Creates the Persona record with auto-generated slug
> - Creates filesystem directory at `data/personas/{slug}/`
> - Seeds skill.md and experience.md template files
> - Returns created persona (slug, id, filesystem path)
>
> **CLI Interface:**
>
> - Flask CLI command: `flask persona register --name Con --role developer --description "Backend Python developer"`
> - Agent-operable — agents can register personas via tools (no MCP context pollution)
>
> **API Interface (optional):**
>
> - REST endpoint for programmatic persona registration
> - Same operation as CLI, accessible via HTTP
>
> **Validation:**
>
> - Persona name required, role name required
> - Role created if it doesn't exist, reused if it does
> - Duplicate persona name + role handled gracefully (different IDs produce unique slugs)
>
> **Technical Decisions (all decided — see workshop):**
>
> - CLI is the preferred interface because agents can operate it via tools (decision 3.1)
> - Application manages directory creation on persona registration (decision 3.1)
> - Config.yaml not involved in persona definitions — domain data (decision 1.2)
>
> **Integration Points:**
>
> - Uses E8-S1 Role and Persona models
> - Uses E8-S5 asset utility functions for directory/file creation
> - New file: `src/claude_headspace/cli/persona.py` (or extend existing CLI)
> - Optional: `src/claude_headspace/routes/persona.py` for API endpoint

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decisions 1.2, 3.1)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 6 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 8 Sprint 7: Persona-Aware Agent Creation

**PRD:** `docs/prds/persona/e8-s7-persona-aware-agent-creation-prd.md`

> Create a PRD for persona-aware agent creation — extending `create_agent()` and the CLI with an optional persona parameter that carries through to the session-start hook payload. This is Epic 8, Sprint 7. Reference Sprint 7 (E8-S7) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-7-persona-aware-agent-creation-e8-s7) and design decisions 3.2, 4.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S6 (personas must exist), E8-S4 (Agent.persona_id FK)
>
> **Deliverables:**
>
> **Programmatic Path:**
>
> - `create_agent()` in `agent_lifecycle.py` gains optional `persona_slug` parameter
> - Persona slug included in session metadata passed to Claude Code session
> - Persona slug carried through to `session-start` hook payload
>
> **CLI Path:**
>
> - `claude-headspace start` gains optional `--persona <slug>` flag
> - Persona slug passed through launcher to session metadata
> - Session starts as vanilla Claude Code session (injection happens post-registration in S9)
>
> **Hook Payload Extension:**
>
> - `session-start` hook payload includes persona slug when present
> - No change when persona not specified (backward compatible)
>
> **Technical Decisions (all decided — see workshop):**
>
> - Two creation paths converge to the same pipeline (decision 4.1)
> - CLI flag for operator ad-hoc sessions, create_agent() for programmatic use (decision 4.1)
> - Vanilla session starts first; persona injection is separate (S9) (decision 3.2)
> - No post-hoc persona reassignment — "brain transplants" excluded (decision 4.1)
>
> **Integration Points:**
>
> - Modify: `src/claude_headspace/services/agent_lifecycle.py` — add persona_slug parameter
> - Modify: CLI launcher script (bin/) — add --persona flag
> - Modify: Hook notification script — include persona slug in payload when present
> - Validate slug against DB before session launch

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decisions 3.2, 4.1)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 7 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing agent lifecycle for context:

- src/claude_headspace/services/agent_lifecycle.py
- bin/ (launcher scripts)

---

### Epic 8 Sprint 8: SessionCorrelator Persona Assignment

**PRD:** `docs/prds/persona/e8-s8-session-correlator-persona-prd.md`

> Create a PRD for extending the SessionCorrelator and hook receiver to detect persona slug in the session-start hook payload and assign persona_id to the agent at registration. This is Epic 8, Sprint 8. Reference Sprint 8 (E8-S8) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-8-sessioncorrelator-persona-assignment-e8-s8) and design decision 4.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S7 (hook payload carries persona slug), E8-S4 (Agent.persona_id FK)
>
> **Deliverables:**
>
> **SessionCorrelator Extension:**
>
> - On `session-start` hook with persona slug in payload:
>   1. Look up Persona by slug
>   2. Set `agent.persona_id` on the newly created Agent record
>   3. Log the persona assignment
> - No persona slug: existing behaviour unchanged (anonymous agent)
>
> **Hook Receiver Extension:**
>
> - Extract persona slug from `session-start` hook payload
> - Pass to SessionCorrelator for persona lookup and assignment
> - Persona assignment at registration time — not retroactively
>
> **Error Handling:**
>
> - Persona slug in payload but not found in DB → log warning, create agent without persona (don't block registration)
>
> **Technical Decisions (all decided — see workshop):**
>
> - Persona assignment at registration time, not post-hoc (decision 4.1)
> - Anonymous agents remain anonymous — no change (decision 4.1)
>
> **Integration Points:**
>
> - Modify: `src/claude_headspace/services/session_correlator.py` — persona lookup and assignment
> - Modify: `src/claude_headspace/services/hook_receiver.py` — extract persona slug from payload
> - SessionCorrelator's existing 5-strategy cascade unaffected for non-persona sessions

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 4.1)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 8 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing services for context:

- src/claude_headspace/services/session_correlator.py
- src/claude_headspace/services/hook_receiver.py
- src/claude_headspace/services/hook_lifecycle_bridge.py

---

### Epic 8 Sprint 9: Skill File Injection via tmux Bridge

**PRD:** `docs/prds/persona/e8-s9-skill-file-injection-prd.md`

> Create a PRD for skill file injection — after an agent with a persona is registered and online, inject skill.md and experience.md content as the first user message via the tmux bridge, prompting the agent to respond in character. This is Epic 8, Sprint 9. Reference Sprint 9 (E8-S9) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-9-skill-file-injection-via-tmux-bridge-e8-s9) and design decision 3.2 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S8 (agent has persona_id after registration), E8-S5 (skill files exist on disk)
>
> **Deliverables:**
>
> **Injection Trigger:**
>
> - After SessionCorrelator assigns persona_id to a new agent:
>   1. Read `data/personas/{slug}/skill.md` content
>   2. Read `data/personas/{slug}/experience.md` content
>   3. Compose a priming message combining both (BMAD pattern)
>   4. Send via existing `tmux_bridge.send_text()` to the agent's tmux pane
> - Agent receives the priming message as its first user input
> - Agent responds in character (e.g., "Hi, I'm Con. Backend developer. What would you like me to work on?")
>
> **Priming Message Format:**
>
> - Structured message including persona identity, skills, and experience
> - Conversation-level user message — NOT system prompt injection (BMAD priming pattern)
>
> **Timing:**
>
> - Injection post-registration, after agent session is confirmed healthy
> - Must complete before operator interacts — no race condition
>
> **Edge Cases:**
>
> - Agent without persona → no injection (existing behaviour)
> - Missing skill file → warning logged, skip injection gracefully
>
> **Technical Decisions (all decided — see workshop):**
>
> - First-prompt injection via tmux bridge, not system prompt hacking (decision 3.2)
> - BMAD priming pattern — proven effective (decision 3.2)
> - Uses existing `tmux_bridge.send_text()` — no new transport mechanism (decision 3.2)
> - No token budget management for skill files — lightweight priming signals (decision 3.1)
>
> **Integration Points:**
>
> - Uses: `src/claude_headspace/services/tmux_bridge.py` (`send_text()`)
> - Uses: E8-S5 asset utility functions (read skill.md, experience.md)
> - Triggered from: hook receiver / session correlator flow after persona assignment (E8-S8)
> - New service or extension to hook_receiver for injection orchestration

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decisions 3.1, 3.2)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 9 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing services for context:

- src/claude_headspace/services/tmux_bridge.py
- src/claude_headspace/services/hook_receiver.py
- src/claude_headspace/services/session_correlator.py

---

### Epic 8 Sprint 10: Dashboard Card Persona Identity

**PRD:** `docs/prds/ui/e8-s10-card-persona-identity-prd.md`

> Create a PRD for updating the dashboard agent card to show persona name and role suffix instead of UUID hero, with backward compatibility for anonymous agents. This is Epic 8, Sprint 10. Reference Sprint 10 (E8-S10) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-10-dashboard-card-persona-identity-e8-s10) and design decision 4.2 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S8 (agents have persona_id — card needs persona data)
>
> **Deliverables:**
>
> **Card Hero Update:**
>
> - Agent with persona: hero text shows persona name (e.g., "Con"), role as suffix (e.g., "Con — developer")
> - Agent without persona: existing UUID-based hero (`hero_chars` + `hero_trail`) unchanged
>
> **CardState Extension:**
>
> - `card_state.py` computes persona name and role for card JSON when persona_id is set
> - SSE `card_refresh` events include persona identity data
> - Dashboard JavaScript renders persona name/role when present, UUID when absent
>
> **Technical Decisions (all decided — see workshop):**
>
> - Persona name as hero text, role as suffix (decision 4.2)
> - No colour coding per persona or role (decision 4.2)
> - No avatar or icon — name as text sufficient (decision 4.2)
> - Anonymous agents keep UUID hero — full backward compatibility (decision 4.2)
>
> **Integration Points:**
>
> - Modify: `src/claude_headspace/services/card_state.py` — add persona data to card JSON
> - Modify: `templates/partials/_agent_card.html` (or equivalent) — conditional persona/UUID display
> - Modify: `static/js/` dashboard JavaScript — render persona identity from SSE data
> - SSE `card_refresh` payload extended with persona fields

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 4.2)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 10 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing services and templates for context:

- src/claude_headspace/services/card_state.py
- templates/ (dashboard and agent card templates)
- static/js/ (dashboard JavaScript)

---

### Epic 8 Sprint 11: Agent Info Panel + Summary Persona Display

**PRD:** `docs/prds/ui/e8-s11-agent-info-persona-display-prd.md`

> Create a PRD for showing persona identity in the agent info/detail panel and in project/activity page agent summaries, while preserving technical details. This is Epic 8, Sprint 11. Reference Sprint 11 (E8-S11) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-11-agent-info-panel--summary-persona-display-e8-s11) and design decision 4.2 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S10 (card persona display — establishes the pattern)
>
> **Deliverables:**
>
> **Agent Info Panel:**
>
> - Persona section: name, role, status, slug
> - Technical details preserved: session UUID, claude_session_id, iterm_pane_id, tmux_pane_id, transcript_path
> - Persona section above technical details when present
> - No persona section for anonymous agents
>
> **Project Page Agent Summaries:**
>
> - Active and ended agents listed with persona name + role when available
> - UUID fallback for anonymous agents
>
> **Activity Page:**
>
> - Agent references show persona name + role when available
> - UUID fallback for anonymous agents
>
> **Technical Decisions (all decided — see workshop):**
>
> - Technical details preserved in info panel (decision 4.2)
> - Persona identity visible across all views where agents appear (decision 4.2)
>
> **Integration Points:**
>
> - Modify: agent info panel template (dashboard detail view)
> - Modify: project show page template — agent summaries
> - Modify: activity page template — agent references
> - All changes are template/view level — no service changes

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 4.2)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 11 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing templates for context:

- templates/ (dashboard, project show, activity page templates)

---

### Epic 8 Sprint 12: Handoff Database Model

**PRD:** `docs/prds/persona/e8-s12-handoff-model-prd.md`

> Create a PRD for the Handoff database model — storing metadata, file path reference, and injection prompt for agent context handoffs. This is Epic 8, Sprint 12. Reference Sprint 12 (E8-S12) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-12-handoff-database-model-e8-s12) and design decision 5.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S4 (Agent.previous_agent_id — handoff chain depends on agent continuity)
>
> **Deliverables:**
>
> **Handoff Table:**
>
> - New `Handoff` SQLAlchemy model with integer PK
> - Fields: `id` (int PK), `agent_id` (int FK to Agent — outgoing agent), `reason` (str — "context_limit" | "shift_end" | "task_boundary"), `file_path` (str — path to handoff document on disk), `injection_prompt` (text — full prompt sent to successor via tmux bridge), `created_at` (datetime)
> - Alembic migration
>
> **Design Notes:**
>
> - Handoff belongs to outgoing agent (the one that wrote it)
> - `injection_prompt` IS the orchestration message sent to successor — e.g., "Continuing from Agent 4b6f8a2c. Read `data/personas/developer-con-1/handoffs/20260220T143025-4b6f8a2c.md` to pick up context."
> - Incoming agent finds handoff via `previous_agent_id` chain (for queries) OR receives injection_prompt directly via tmux bridge (for agent consumption)
>
> **Relationships:**
>
> - `Handoff.agent` → Agent (outgoing)
> - `Agent.handoff` → Handoff (one-to-one)
>
> **Technical Decisions (all decided — see workshop):**
>
> - Hybrid handoff: DB metadata + filesystem content (decision 5.1)
> - DB stores the injection prompt sent directly to successor (decision 5.1)
> - Filesystem stores the detailed handoff document read by successor via tools (decision 5.1)
> - Handoff belongs to outgoing agent; successor finds via previous_agent_id chain (decision 5.1)
>
> **Data Model:**
>
> ```python
> class Handoff(db.Model):
>     id = Column(Integer, primary_key=True)
>     agent_id = Column(Integer, ForeignKey("agent.id"), nullable=False)
>     reason = Column(String, nullable=False)
>     file_path = Column(String)
>     injection_prompt = Column(Text)
>     created_at = Column(DateTime, default=func.now())
> ```
>
> **Integration Points:**
>
> - New file: `src/claude_headspace/models/handoff.py`
> - Register in `src/claude_headspace/models/__init__.py`
> - Migration: `migrations/versions/xxx_add_handoff_table.py`
> - Used by E8-S14 (handoff execution creates records)

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 5.1)
- docs/workshop/erds/headspace-org-erd-full.md (Handoff entity)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 12 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 8 Sprint 13: Handoff Trigger UI

**PRD:** `docs/prds/ui/e8-s13-handoff-trigger-ui-prd.md`

> Create a PRD for the handoff trigger UI — context threshold monitoring on agent cards and a handoff button that appears when context exceeds a configurable threshold. This is Epic 8, Sprint 13. Reference Sprint 13 (E8-S13) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-13-handoff-trigger-ui-e8-s13) and design decision 5.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S12 (Handoff model), E8-S10 (card persona identity — button appears on persona cards)
>
> **Deliverables:**
>
> **Context Threshold Monitoring:**
>
> - Monitor `context_percent_used` on each agent (already tracked by E6-S4 context monitoring)
> - Compare against configurable threshold (e.g., 80%)
> - Flag agent as "handoff eligible" when threshold exceeded
>
> **Handoff Button on Agent Card:**
>
> - "Handoff" button appears only when:
>   - Agent has a persona (anonymous agents don't handoff)
>   - Context usage exceeds configured threshold
> - Button triggers handoff flow (E8-S14)
> - Visual indicator that context is approaching limit (e.g., context bar colour change)
>
> **Configuration:**
>
> - Handoff threshold configurable (wind down to 10% for testing/debugging)
>
> **Technical Decisions (all decided — see workshop):**
>
> - Operator-initiated handoff only — no auto-trigger in v1 (decision 5.1)
> - Manual trigger allows compaction to work naturally (decision 5.1)
> - Manual trigger doubles as debugging mechanism — wind down threshold, fire, inspect (decision 5.1)
>
> **Integration Points:**
>
> - Uses: E6-S4 context monitoring (`context_percent_used` on Agent)
> - Modify: agent card template — conditional handoff button
> - Modify: card_state.py — include handoff eligibility in card JSON
> - Modify: dashboard JavaScript — handle handoff button click
> - Button click triggers API call to handoff execution endpoint (E8-S14)

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 5.1)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 13 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing context monitoring for reference:

- src/claude_headspace/services/agent_lifecycle.py (context capture)
- src/claude_headspace/services/card_state.py

---

### Epic 8 Sprint 14: Handoff Execution

**PRD:** `docs/prds/persona/e8-s14-handoff-execution-prd.md`

> Create a PRD for the full handoff execution cycle: operator triggers → outgoing agent writes handoff document → DB record created → session ends → successor spins up → injection prompt sent → successor reads handoff file and continues. This is Epic 8, Sprint 14. Reference Sprint 14 (E8-S14) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-14-handoff-execution-e8-s14) and design decision 5.1 in the [Agent Teams Workshop](../workshop/agent-teams-workshop.md).
>
> **Dependencies:** E8-S13 (trigger UI), E8-S12 (Handoff model), E8-S9 (skill injection — successor needs priming), E8-S7 (persona-aware agent creation — successor created with same persona)
>
> **Deliverables:**
>
> **Handoff Orchestration Flow:**
>
> 1. Operator clicks handoff button (from S13)
> 2. Headspace sends handoff instruction to outgoing agent via tmux bridge: "Write your handoff document to `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`"
> 3. Agent writes handoff file using its Write tool (agent-as-author — richest context)
> 4. Agent confirms completion in conversation
> 5. Headspace detects confirmation via existing hook/turn processing
> 6. Headspace creates Handoff DB record (agent_id, reason, file_path, injection_prompt)
> 7. Outgoing agent session ends (graceful shutdown via `/exit`)
> 8. New agent spins up with same persona (via `create_agent(persona_slug=...)`)
> 9. New agent's `previous_agent_id` set to outgoing agent's ID
> 10. After skill injection (S9): Headspace sends `injection_prompt` from Handoff record via tmux bridge
> 11. Successor reads handoff file with own tools → continues work
>
> **Handoff Document Location:**
>
> - Path: `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`
> - ISO datetime format in filename (e.g., `20260220T143025`)
> - Agent 8-digit identifier for uniqueness
> - Directory created if it doesn't exist
>
> **Handoff Document Content (agent-written, first-person):**
>
> - What was being worked on
> - Current progress / state
> - Key decisions made and why
> - Blockers encountered
> - Files modified
> - Next steps / what remains
>
> **Injection Prompt (DB-stored, sent to successor):**
>
> - References predecessor agent
> - Points to handoff file path
> - Provides task context
> - Successor receives without tools — direct conversation message
>
> **File Lifecycle:**
>
> - Handoff files accumulate in `data/personas/{slug}/handoffs/`
> - No cleanup in v1 — deferred to system management PRD
>
> **Technical Decisions (all decided — see workshop):**
>
> - Agent-as-author — outgoing agent writes its own handoff document (decision 5.1)
> - File-native consumption — successor reads via Read tool (decision 5.1)
> - Two-phase bootstrap — DB prompt bootstraps immediately, file deepens understanding (decision 5.1)
> - Handoff files under persona tree — consistent with skill/experience asset pattern (decision 5.1)
> - Operator-initiated — human-in-the-loop for prompt tuning (decision 5.1)
> - Handoff file naming: ISO datetime + agent 8-digit ID (decision 5.1)
>
> **Integration Points:**
>
> - New service: `src/claude_headspace/services/handoff_service.py` (orchestration logic)
> - Uses: `src/claude_headspace/services/tmux_bridge.py` (send handoff instruction + injection prompt)
> - Uses: `src/claude_headspace/services/agent_lifecycle.py` (graceful shutdown + create_agent)
> - Uses: E8-S9 skill injection (successor gets skill priming before handoff prompt)
> - Uses: E8-S12 Handoff model (create DB record)
> - New API endpoint: handoff trigger (called by S13 button)

Review design decisions and guidance at:

- docs/workshop/agent-teams-workshop.md (Decision 5.1 — full handoff mechanism design)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 14 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing services for context:

- src/claude_headspace/services/tmux_bridge.py
- src/claude_headspace/services/agent_lifecycle.py
- src/claude_headspace/services/hook_receiver.py

---

### Epic 8 Sprint 18: Agent Revival ("Seance")

**PRD:** `docs/prds/agents/e8-s18-agent-revival-prd.md`

> Create a PRD for dead agent revival ("Seance") — enabling operators to revive dead agents by spinning up a successor that self-briefs from the predecessor's conversation history. This is Epic 8, Sprint 18. Reference Sprint 18 (E8-S18) in the [Epic 8 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md#sprint-18-agent-revival--seance-e8-s18).
>
> **Dependencies:** E8-S9 (skill injection), E8-S7 (persona-aware agent creation), E8-S4 (Agent.previous_agent_id)
>
> **Deliverables:**
>
> **CLI Transcript Command:**
>
> - New `claude-headspace transcript <agent-id>` CLI command
> - Queries database: Agent -> Commands -> Turns
> - Outputs structured markdown: commands as section headers (instruction text), turns as `**User:**` / `**Agent:**` blocks with timestamps
> - Conversational content only — no metadata (frustration scores, command states, turn summaries)
> - Uses Flask CLI infrastructure (Click commands within Flask context)
> - Handles edge cases: no commands, no turns, empty turn text, invalid agent ID
>
> **Revive API Endpoint:**
>
> - REST endpoint triggered by dashboard UI
> - Validates agent exists and is dead (`ended_at IS NOT NULL`)
> - Creates successor with same project and persona config via `create_agent()`
> - Sets `previous_agent_id` for continuity chain
> - Orchestrates revival instruction injection after agent comes online
>
> **Revival Instruction Injection:**
>
> - Delivered via tmux bridge (reuses persona injection mechanism)
> - For persona agents: injected after skill injection completes (same sequencing as handoff)
> - For non-persona agents: injected as sole first instruction
> - Instruction tells new agent to run `claude-headspace transcript <predecessor-id>` and self-brief
>
> **Revive UI Trigger:**
>
> - "Revive" button/action on dead agent cards and agent detail view
> - Only visible for agents where `ended_at IS NOT NULL`
> - Provides feedback during revival (spinner/status)
> - Successor card shows predecessor link via `previous_agent_id`
>
> **Technical Decisions (all decided — PRD workshop):**
>
> - Agent self-briefs from CLI output — no pre-summarisation
> - CLI outputs conversational content only — no metadata
> - Agent database ID as identifier for CLI command
> - Reuses persona injection mechanism (tmux bridge)
> - Works for both persona and anonymous agents
> - Complementary to handoff (S14), not a replacement
> - Always allow revival regardless of conversation length
>
> **Integration Points:**
>
> - New CLI command: `src/claude_headspace/cli/` (transcript extraction)
> - New route: `src/claude_headspace/routes/agents.py` (revive endpoint)
> - New service or extension: revival orchestration logic
> - Uses: `src/claude_headspace/services/agent_lifecycle.py` (`create_agent()`)
> - Uses: `src/claude_headspace/services/tmux_bridge.py` (`send_text()`)
> - Uses: `src/claude_headspace/services/skill_injector.py` (injection sequencing)
> - Modify: dashboard templates/JS (revive button on dead agent cards)

Review the PRD at:

- docs/prds/agents/e8-s15-agent-revival-prd.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic8_detailed_roadmap.md (Sprint 15 section)
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

Existing services for context:

- src/claude_headspace/services/agent_lifecycle.py
- src/claude_headspace/services/skill_injector.py
- src/claude_headspace/services/handoff_executor.py (pattern reference)
- src/claude_headspace/services/tmux_bridge.py
- src/claude_headspace/models/agent.py
- src/claude_headspace/models/command.py
- src/claude_headspace/models/turn.py

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
[Epics 1-6 Complete]
       │
       ▼
   E8-S1 (Role + Persona Models)
       │
       ├──▶ E8-S2 (Organisation Model)
       │       │
       │       └──▶ E8-S3 (Position Model)
       │               │
       │               └──▶ E8-S4 (Agent Extensions) ◄── E8-S1
       │
       ├──▶ E8-S5 (Filesystem Assets)
       │       │
       │       └──▶ E8-S6 (Registration) ◄── E8-S1
       │               │
       │               └──▶ E8-S7 (Persona-Aware Agent Creation) ◄── E8-S4
       │                       │
       │                       └──▶ E8-S8 (SessionCorrelator) ◄── E8-S4
       │                               │
       │                               └──▶ E8-S9 (Skill Injection) ◄── E8-S5
       │
       └──▶ E8-S10 (Card Identity) ◄── E8-S8
               │
               └──▶ E8-S11 (Info Panel + Summaries)

   E8-S4 (Agent Extensions)
       │
       └──▶ E8-S12 (Handoff Model)
               │
               └──▶ E8-S13 (Handoff Trigger UI) ◄── E8-S10
                       │
                       └──▶ E8-S14 (Handoff Execution) ◄── E8-S9, E8-S7, E8-S12

   E8-S9 (Skill Injection) + E8-S7 (Persona-Aware Agent Creation) + E8-S4 (Agent Extensions)
       │
       └──▶ E8-S18 (Agent Revival / "Seance") ◄── E8-S9, E8-S7, E8-S4
                               │
                               └──▶ [Epic 8 Complete]
```

**Linear Build Order:** S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11 → S12 → S13 → S14 → S15 → S16 → S17 → S18

**Note:** All sprints built sequentially. Each sprint builds on the foundation of previous sprints.
