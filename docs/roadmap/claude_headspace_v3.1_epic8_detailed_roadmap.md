# Epic 8 Detailed Roadmap: Personable Agents

**Project:** Claude Headspace v3.1
**Epic:** Epic 8 — Personable Agents
**Author:** Sam (workshopped with Claude)
**Status:** Roadmap — Baseline for PRD Generation
**Date:** 2026-02-20

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 8 implementation. It breaks Epic 8 into 18 sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem. This roadmap is designed to grow as new ideas emerge — additional sprints will be appended as they are scoped and workshopped.

**Epic 8 Goal:** Introduce named personas as first-class entities in Claude Headspace — persistent identities with skills and experience that drive Claude Code agents, replacing anonymous UUID-identified sessions with meaningful, recognisable team members.

**Epic 8 Value Proposition:**

- **Named Agent Identity** — Agents are driven by personas with names, roles, and accumulated experience, replacing anonymous UUID-based identification
- **Skill & Experience Assets** — Each persona has filesystem-based skill files (who they are) and experience logs (what they've learned), injected into agents at session startup via the proven BMAD priming pattern
- **Organisational Structure** — Minimal organisation and position models establish the hierarchy for future PM automation (Gavin v3) and multi-org support
- **Context Continuity via Handoff** — When an agent's context fills up, operator-initiated handoff produces a rich first-person handoff document that a successor agent consumes to continue work seamlessly
- **Dashboard Identity** — Agent cards show persona names and roles instead of cryptic UUIDs, making the dashboard immediately legible

**The Differentiator:** Until now, Claude Headspace agents are interchangeable and anonymous. An agent is a session UUID with no identity, no memory, and no continuity. Epic 8 transforms agents into recognisable team members — Con the backend developer, Robbo the architect, Verner the tester — each with persistent skills and accumulating experience. When one session ends, the persona's knowledge carries forward to the next. This is the foundation for the agent teams platform vision.

**Success Criteria:**

- Register a persona (Con, developer) → DB record created, skill.md + experience.md seeded at `data/personas/developer-con-1/`
- Launch agent with persona → `claude-headspace start --persona con` → agent starts, skill file injected, agent responds "Hi, I'm Con"
- Dashboard shows "Con — developer" on agent card instead of "4b6f8a"
- Agent reaches context threshold → handoff button appears → operator triggers → Con writes handoff document → new Con session picks up where the old one left off
- Anonymous agents (no persona) continue working exactly as before — full backward compatibility

**Architectural Foundation:** Builds on Epic 6's agent lifecycle management (E6-S4: `create_agent()`, tmux bridge, agent creation API), Epic 5's tmux bridge (E5-S4: `send_text()` for skill injection), and the existing hook receiver / session correlator infrastructure from Epic 1.

**Dependency:** Epics 1-6 must be complete before Epic 8 begins. Epic 7 (testing) is independent and not required.

**Design Source:** All architectural decisions resolved in the Agent Teams Design Workshop (`docs/workshop/agent-teams-workshop.md`) across sessions on 16-17 and 20 February 2026. ERD reference at `docs/workshop/erds/headspace-org-erd-full.md`. Conceptual vision at `docs/conceptual/headspace-platform-vision.md`. Functional outline at `docs/conceptual/headspace-agent-teams-functional-outline.md`.

---

## Epic 8 Story Mapping

| Story ID | Story Name                                              | Subsystem          | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------------------- | ------------------ | ------------- | ------ | -------- |
| E8-S1    | Role and Persona database models                        | `persona`          | persona/      | 1      | P1       |
| E8-S2    | Organisation database model                             | `persona`          | persona/      | 2      | P1       |
| E8-S3    | Position database model with hierarchy                  | `persona`          | persona/      | 3      | P1       |
| E8-S4    | Agent model extensions for persona and position         | `persona`          | persona/      | 4      | P1       |
| E8-S5    | Persona filesystem assets (skill.md, experience.md)     | `persona`          | persona/      | 5      | P1       |
| E8-S6    | Persona registration CLI/API                            | `persona`          | persona/      | 6      | P1       |
| E8-S7    | Persona-aware agent creation                            | `persona`          | persona/      | 7      | P1       |
| E8-S8    | SessionCorrelator persona assignment                    | `persona`          | persona/      | 8      | P1       |
| E8-S9    | Skill file injection via tmux bridge                    | `persona`          | persona/      | 9      | P1       |
| E8-S10   | Dashboard card persona identity                         | `persona`          | ui/           | 10     | P1       |
| E8-S11   | Agent info panel and summary persona display            | `persona`          | ui/           | 11     | P1       |
| E8-S12   | Handoff database model                                  | `persona`          | persona/      | 12     | P1       |
| E8-S13   | Handoff trigger UI (context threshold + button)         | `persona`          | ui/           | 13     | P1       |
| E8-S14   | Handoff execution (agent-written document + successor)  | `persona`          | persona/      | 14     | P1       |
| E8-S15   | Persona list & CRUD UI                                  | `persona`          | persona/      | 15     | P1       |
| E8-S16   | Persona detail page & skill editor                      | `persona`          | persona/      | 16     | P1       |
| E8-S17   | Persona-aware agent creation UI & CLI discovery         | `persona`          | persona/      | 17     | P1       |
| E8-S18   | Agent revival ("Seance") — dead agent context recovery  | `agents`           | agents/       | 18     | P1       |

---

## Sprint Breakdown

### Sprint 1: Role + Persona Database Models (E8-S1)

**Goal:** Create the Role and Persona database tables with Alembic migrations, establishing the foundation for named agent identity.

**Duration:** 1 week
**Dependencies:** None within Epic 8 (foundational sprint)

**Deliverables:**

**Role Table:**

- New `Role` SQLAlchemy model with integer PK
- Fields: `id` (int PK), `name` (str, unique — e.g., "developer", "tester", "pm", "architect"), `description` (text), `created_at` (datetime)
- Shared lookup table — referenced by both Persona ("I am a developer") and Position ("this seat needs a developer")
- Alembic migration

**Persona Table:**

- New `Persona` SQLAlchemy model with integer PK
- Fields: `id` (int PK), `slug` (str, unique — generated as `{role_name}-{persona_name}-{id}`), `name` (str), `description` (text), `status` (str — "active" | "archived"), `role_id` (int FK to Role), `created_at` (datetime)
- Slug is generated from the persona's role and name, used as the filesystem path key (`data/personas/{slug}/`)
- Status replaces a simple boolean is_active for extensibility
- Alembic migration

**Model Registration:**

- Both models registered with Flask-SQLAlchemy
- Accessible via standard query patterns
- Relationship defined: `Role.personas` ↔ `Persona.role`

**Subsystem Requiring PRD:**

1. `persona` — Role and Persona database models, migrations, relationships

**PRD Location:** `docs/prds/persona/e8-s1-role-persona-models-prd.md`

**Stories:**

- E8-S1: Role and Persona database models with migrations and relationships

**Technical Decisions Made:**

- Integer PKs throughout (matches existing codebase: Agent, Command, Turn all use int PKs) — **decided** (workshop 2.1)
- Slug format `{role_name}-{persona_name}-{id}` for natural filesystem sorting — **decided** (workshop 1.2, 2.1)
- Status field (`active|archived`) instead of boolean `is_active` — **decided** (workshop 2.1)
- Role is a shared lookup, not org-scoped — **decided** (workshop 2.1)
- No pool membership in v1 — **decided** (workshop 2.1)

**Data Model:**

```python
class Role(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # developer, tester, pm, architect
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())

class Persona(db.Model):
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)  # generated: developer-con-1
    name = Column(String, nullable=False)                # Con
    description = Column(Text)
    status = Column(String, default="active")            # active | archived
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
```

**Risks:**

- Migration conflicts with concurrent development (mitigated: Epic 8 is sequential, no parallel sprints)
- Slug uniqueness edge cases (mitigated: generated from role + name + id, id guarantees uniqueness)

**Acceptance Criteria:**

- [ ] Role table exists in database after migration
- [ ] Persona table exists in database after migration
- [ ] Can create a Role record (e.g., name="developer")
- [ ] Can create a Persona record with role_id FK (e.g., name="Con", role="developer")
- [ ] Persona slug auto-generated as `{role_name}-{persona_name}-{id}` (e.g., "developer-con-1")
- [ ] Slug is unique — duplicate names with same role produce different slugs via id
- [ ] Persona.role relationship navigable in both directions
- [ ] Existing Agent, Command, Turn tables unaffected

---

### Sprint 2: Organisation Database Model (E8-S2)

**Goal:** Create a minimal Organisation table to establish the organisational grouping concept for future multi-org support.

**Duration:** 0.5-1 week
**Dependencies:** None within Epic 8 (independent of S1, but sequenced for logical build order)

**Deliverables:**

**Organisation Table:**

- New `Organisation` SQLAlchemy model with integer PK
- Fields: `id` (int PK), `name` (str), `description` (text), `status` (str — "active" | "dormant" | "archived"), `created_at` (datetime)
- Minimal table — exists to avoid a disruptive migration later when multi-org support arrives
- Alembic migration

**Seed Data:**

- One Organisation record created: the dev org (name="Development", status="active")
- Seed can be via migration data operation or application startup

**Subsystem Requiring PRD:**

2. `persona` — Organisation database model and seed data

**PRD Location:** `docs/prds/persona/e8-s2-organisation-model-prd.md`

**Stories:**

- E8-S2: Organisation database model with minimal schema and dev org seed

**Technical Decisions Made:**

- Minimal Organisation table in v1 — one small migration now avoids a disruptive one later — **decided** (workshop 1.3)
- Three-state status: active, dormant, archived — **decided** (ERD)
- No Organisation-level configuration in config.yaml — **decided** (workshop 1.2 — config.yaml is app config only)

**Data Model:**

```python
class Organisation(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active")  # active | dormant | archived
    created_at = Column(DateTime, default=func.now())
```

**Risks:**

- Minimal table may need extension later (mitigated: that's the point — small migration now, extend when needed)

**Acceptance Criteria:**

- [ ] Organisation table exists in database after migration
- [ ] Can create an Organisation record
- [ ] Dev org seed data present (name="Development", status="active")
- [ ] Existing tables unaffected

---

### Sprint 3: Position Database Model (E8-S3)

**Goal:** Create the Position table that models seats in an org chart with self-referential hierarchy (reports-to, escalates-to).

**Duration:** 1 week
**Dependencies:** E8-S1 (Role table — Position references Role), E8-S2 (Organisation table — Position references Organisation)

**Deliverables:**

**Position Table:**

- New `Position` SQLAlchemy model with integer PK
- Fields: `id` (int PK), `org_id` (int FK to Organisation), `role_id` (int FK to Role), `title` (str), `reports_to_id` (int FK to Position, self-ref, nullable), `escalates_to_id` (int FK to Position, self-ref, nullable), `level` (int — depth in hierarchy), `is_cross_cutting` (bool)
- Self-referential hierarchy via `reports_to_id` and `escalates_to_id`
- Escalation path can differ from reporting path (e.g., Verner reports to Gavin but escalates architectural issues to Robbo)
- Alembic migration

**Relationships:**

- `Position.role` → Role (what this seat needs)
- `Position.organisation` → Organisation
- `Position.reports_to` → Position (self-ref)
- `Position.escalates_to` → Position (self-ref)
- `Position.direct_reports` → list of Positions that report to this one

**Subsystem Requiring PRD:**

3. `persona` — Position database model with self-referential hierarchy

**PRD Location:** `docs/prds/persona/e8-s3-position-model-prd.md`

**Stories:**

- E8-S3: Position database model with org chart hierarchy

**Technical Decisions Made:**

- Position hierarchy is self-referential — `reports_to_id` and `escalates_to_id` both point to Position — **decided** (ERD)
- Escalation path can differ from reporting path — **decided** (ERD)
- The operator (Sam) is not modelled as a Persona — top of every hierarchy implicitly reports to the operator — **decided** (ERD)
- Role is shared lookup referenced by both Persona and Position — matching on role_id finds personas that can fill a position — **decided** (workshop 2.1)

**Data Model:**

```python
class Position(db.Model):
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisation.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
    title = Column(String, nullable=False)
    reports_to_id = Column(Integer, ForeignKey("position.id"), nullable=True)
    escalates_to_id = Column(Integer, ForeignKey("position.id"), nullable=True)
    level = Column(Integer, default=0)  # depth in hierarchy
    is_cross_cutting = Column(Boolean, default=False)
```

**Risks:**

- Self-referential FK complexity in SQLAlchemy (mitigated: well-documented pattern, use `remote_side` parameter)
- Circular hierarchy (mitigated: level field provides depth sanity check, application-level validation)

**Acceptance Criteria:**

- [ ] Position table exists in database after migration
- [ ] Can create Position records with org_id and role_id FKs
- [ ] Can set reports_to_id to another Position (self-referential)
- [ ] Can set escalates_to_id to a different Position than reports_to_id
- [ ] Position.role and Position.organisation relationships navigable
- [ ] Position.direct_reports returns subordinate positions
- [ ] Top-level positions have reports_to_id = NULL
- [ ] Existing tables unaffected

---

### Sprint 4: Agent Model Extensions (E8-S4)

**Goal:** Extend the existing Agent model with three new nullable foreign keys linking agents to personas, positions, and predecessor agents for continuity chains.

**Duration:** 0.5-1 week
**Dependencies:** E8-S1 (Persona table), E8-S3 (Position table)

**Deliverables:**

**Agent Model Extensions:**

- Add `persona_id` (int FK to Persona, nullable) — which persona drives this agent
- Add `position_id` (int FK to Position, nullable) — which org chart position this agent represents
- Add `previous_agent_id` (int FK to Agent, self-ref, nullable) — predecessor in a handoff continuity chain
- All nullable for backward compatibility — existing agents remain unaffected
- Alembic migration

**Relationships:**

- `Agent.persona` → Persona
- `Agent.position` → Position
- `Agent.previous_agent` → Agent (self-ref)
- `Agent.successor_agents` → list of Agents that have this agent as predecessor
- `Persona.agents` → list of Agents driven by this persona

**Design Notes:**

- Agent serves as the join between Persona and Position — when an agent has both FKs set, that persona is filling that position
- No separate PositionAssignment join table — Agent IS the assignment record
- Multiple agents can share the same persona simultaneously (no availability constraint — workshop 2.3)
- First agent in a continuity chain has `previous_agent_id = NULL`

**Subsystem Requiring PRD:**

4. `persona` — Agent model extensions with persona, position, and predecessor FKs

**PRD Location:** `docs/prds/persona/e8-s4-agent-model-extensions-prd.md`

**Stories:**

- E8-S4: Agent model extensions for persona, position, and continuity chain

**Technical Decisions Made:**

- No PositionAssignment join table — Agent has both persona_id and position_id directly — **decided** (workshop 2.2)
- No availability constraint — multiple agents can share the same persona — **decided** (workshop 2.3)
- previous_agent_id self-ref FK for continuity chain (not from/to on Handoff) — **decided** (workshop 5.1, ERD)
- All new fields nullable for backward compatibility — **decided** (workshop 2.2)

**Data Model Changes (existing Agent table):**

```python
class Agent(db.Model):
    # ... existing 17 fields unchanged ...

    # NEW fields
    persona_id = Column(Integer, ForeignKey("persona.id"), nullable=True)
    position_id = Column(Integer, ForeignKey("position.id"), nullable=True)
    previous_agent_id = Column(Integer, ForeignKey("agent.id"), nullable=True)
```

**Risks:**

- Migration on existing Agent table with data (mitigated: all fields nullable, no data transformation needed)
- Self-referential FK on Agent (mitigated: same pattern as Position.reports_to_id, use `remote_side`)

**Acceptance Criteria:**

- [ ] Migration adds three nullable columns to Agent table
- [ ] Existing Agent records unaffected (all new fields NULL)
- [ ] Can create Agent with persona_id set → Agent.persona navigable
- [ ] Can create Agent with position_id set → Agent.position navigable
- [ ] Can set previous_agent_id to link agents in a chain
- [ ] Persona.agents returns all agents driven by that persona
- [ ] Multiple agents can reference the same persona_id simultaneously
- [ ] All existing Agent queries and services continue working unchanged

---

### Sprint 5: Persona Filesystem Assets (E8-S5)

**Goal:** Establish the `data/personas/{slug}/` directory convention and template file structure for persona skill files and experience logs.

**Duration:** 0.5-1 week
**Dependencies:** E8-S1 (Persona model — slug format determines directory names)

**Deliverables:**

**Directory Convention:**

- `data/` directory at project root as the convention-based location for domain data
- `data/personas/{slug}/` subdirectory per persona (e.g., `data/personas/developer-con-1/`)
- Directory path derived from persona slug — not stored on the model, not configurable in config.yaml

**Template Files:**

- `skill.md` — Core competencies, preferences, behavioural instructions. Stable, operator-curated. The "who you are and how you work" file. Seeded with a minimal template on persona registration.
- `experience.md` — Append-only log of learned experience from completed work. Evolves through agent self-improvement and periodic curation. The "what you've done and learned" file. Seeded empty or with a header.

**Asset Utility:**

- Utility functions for resolving persona slug → filesystem path
- Functions for reading skill.md and experience.md content given a persona slug
- Functions for checking whether asset files exist for a given persona

**Subsystem Requiring PRD:**

5. `persona` — Filesystem asset convention, template files, path resolution utilities

**PRD Location:** `docs/prds/persona/e8-s5-persona-filesystem-assets-prd.md`

**Stories:**

- E8-S5: Persona filesystem asset structure with skill.md and experience.md

**Technical Decisions Made:**

- Convention-based `data/` directory at project root — not a configurable setting — **decided** (workshop 1.2)
- Slug format `{role}-{name}-{id}` for natural filesystem sorting by role then name — **decided** (workshop 1.2)
- Config.yaml is NOT involved — path is a project convention — **decided** (workshop 1.2)
- Skill files are lightweight priming signals, not knowledge dumps — no token budget management — **decided** (workshop 3.1)
- Per-org skill extensions deferred to Phase 2+ — **decided** (workshop 3.1)

**File Templates:**

```markdown
<!-- data/personas/{slug}/skill.md -->
# {Persona Name} — {Role Name}

## Core Identity
[Who this persona is — 1-2 sentences]

## Skills & Preferences
[Key competencies and working style]

## Communication Style
[How this persona communicates]
```

```markdown
<!-- data/personas/{slug}/experience.md -->
# Experience Log — {Persona Name}

<!-- Append-only. New entries added at the top. -->
<!-- Periodically curated to remove outdated learnings. -->
```

**Risks:**

- `data/` directory not in .gitignore and could be committed with persona-specific content (mitigated: operator decides what to track in git — skill files are intentionally version-controllable)
- Filesystem permissions on `data/` directory (mitigated: standard user-writable directory, same as project root)

**Acceptance Criteria:**

- [ ] `data/personas/` directory structure can be created programmatically
- [ ] Given a persona slug, can resolve to the correct filesystem path
- [ ] skill.md template seeded with persona name and role
- [ ] experience.md template seeded with header
- [ ] Utility functions for reading skill/experience content work correctly
- [ ] Path resolution handles edge cases (persona not yet created on disk, missing files)

---

### Sprint 6: Persona Registration (E8-S6)

**Goal:** Create a CLI command and/or API endpoint that registers a new persona end-to-end: creates the DB record (Role lookup + Persona insert) and the filesystem assets (directory + template files) in a single operation.

**Duration:** 1 week
**Dependencies:** E8-S1 (Role + Persona models), E8-S5 (filesystem asset convention)

**Deliverables:**

**Registration Operation:**

- Accepts: persona name, role name, optional description
- Looks up or creates the Role record
- Creates the Persona record with auto-generated slug
- Creates the filesystem directory at `data/personas/{slug}/`
- Seeds skill.md and experience.md template files
- Returns the created persona (slug, id, filesystem path)

**CLI Interface:**

- Command accessible via the application CLI (Flask CLI or standalone script)
- Agent-operable — agents can register personas via tools (no MCP context pollution)
- Example: `flask persona register --name Con --role developer --description "Backend Python developer"`

**API Interface (optional):**

- REST endpoint for programmatic persona registration
- Same operation as CLI, accessible via HTTP

**Validation:**

- Persona name required
- Role name required (creates Role if it doesn't exist)
- Duplicate persona name + role combination handled gracefully (different IDs produce unique slugs)

**Subsystem Requiring PRD:**

6. `persona` — Persona registration CLI/API with end-to-end creation flow

**PRD Location:** `docs/prds/persona/e8-s6-persona-registration-prd.md`

**Stories:**

- E8-S6: Persona registration CLI and API with DB + filesystem creation

**Technical Decisions Made:**

- CLI is the preferred interface because agents can operate it via tools — **decided** (workshop 3.1)
- Application manages directory creation on persona registration — **decided** (workshop 3.1)
- Config.yaml not involved in persona definitions — they are domain data — **decided** (workshop 1.2)

**Risks:**

- Partial creation failure (DB succeeds, filesystem fails or vice versa) — mitigated: create DB record first, then filesystem; if filesystem fails, provide clear error and rollback guidance
- Role name normalisation (mitigated: lowercase, stripped, consistent formatting)

**Acceptance Criteria:**

- [ ] CLI command registers a persona end-to-end (DB + filesystem)
- [ ] Role record created if it doesn't exist; reused if it does
- [ ] Persona slug auto-generated correctly (`{role}-{name}-{id}`)
- [ ] Filesystem directory created at `data/personas/{slug}/`
- [ ] skill.md seeded with persona name and role
- [ ] experience.md seeded with header
- [ ] Duplicate registrations produce unique slugs (different IDs)
- [ ] Clear error messages for missing required fields
- [ ] Registration operation is idempotent-safe (re-running doesn't corrupt existing data)

---

### Sprint 7: Persona-Aware Agent Creation (E8-S7)

**Goal:** Extend agent creation to accept an optional persona, both through the programmatic `create_agent()` path and the CLI `claude-headspace start --persona` flag, so that persona identity can be carried through to session registration.

**Duration:** 1 week
**Dependencies:** E8-S6 (persona registration — personas must exist to reference), E8-S4 (Agent persona_id FK)

**Deliverables:**

**Programmatic Path:**

- `create_agent()` (in `agent_lifecycle.py`) gains an optional `persona_slug` parameter
- When provided, persona slug is included in the session metadata passed to the Claude Code session
- Persona slug carried through to the `session-start` hook payload

**CLI Path:**

- `claude-headspace start` gains an optional `--persona <slug>` flag
- When provided, persona slug is passed through the launcher to the session metadata
- Session starts as a vanilla Claude Code session (persona injection happens post-registration in S9)

**Hook Payload Extension:**

- `session-start` hook payload includes persona slug when present
- No change to hook payload when persona is not specified (backward compatible)

**Subsystem Requiring PRD:**

7. `persona` — Persona-aware agent creation via create_agent() and CLI --persona flag

**PRD Location:** `docs/prds/persona/e8-s7-persona-aware-agent-creation-prd.md`

**Stories:**

- E8-S7: Persona-aware agent creation with CLI flag and programmatic parameter

**Technical Decisions Made:**

- Two creation paths converge to the same pipeline — **decided** (workshop 4.1)
- CLI flag for operator ad-hoc sessions, create_agent() for programmatic/dashboard use — **decided** (workshop 4.1)
- Vanilla Claude Code session starts first; persona injection is a separate step (S9) — **decided** (workshop 3.2)
- No post-hoc persona reassignment — "brain transplants" excluded — **decided** (workshop 4.1)

**Risks:**

- Persona slug typo in CLI flag (mitigated: validate slug against DB before proceeding, clear error if not found)
- Hook payload backward compatibility (mitigated: persona slug is an optional field, absence means anonymous agent)

**Acceptance Criteria:**

- [ ] `create_agent(persona_slug="con")` creates an agent session with persona metadata
- [ ] `claude-headspace start --persona con` starts a session with persona metadata
- [ ] `claude-headspace start` (no flag) continues working as before — anonymous agent
- [ ] Persona slug appears in the session-start hook payload when specified
- [ ] Invalid persona slug (not in DB) produces a clear error before session launch
- [ ] Hook payload without persona slug is fully backward compatible

---

### Sprint 8: SessionCorrelator Persona Assignment (E8-S8)

**Goal:** Extend the hook receiver and SessionCorrelator to detect persona slug in the session-start hook payload, look up the Persona record, and set `agent.persona_id` at registration time.

**Duration:** 0.5-1 week
**Dependencies:** E8-S7 (hook payload carries persona slug), E8-S4 (Agent.persona_id FK)

**Deliverables:**

**SessionCorrelator Extension:**

- When processing a `session-start` hook with persona slug in the payload:
  1. Look up Persona by slug
  2. Set `agent.persona_id` on the newly created Agent record
  3. Log the persona assignment
- When no persona slug is present: existing behaviour unchanged (anonymous agent)

**Hook Receiver Extension:**

- Extract persona slug from `session-start` hook payload
- Pass to SessionCorrelator for persona lookup and assignment
- Persona assignment happens at registration time — not retroactively

**Subsystem Requiring PRD:**

8. `persona` — SessionCorrelator persona assignment from hook payload

**PRD Location:** `docs/prds/persona/e8-s8-session-correlator-persona-prd.md`

**Stories:**

- E8-S8: SessionCorrelator persona assignment at agent registration

**Technical Decisions Made:**

- Persona assignment at registration time — not post-hoc — **decided** (workshop 4.1)
- Anonymous agents (no persona slug in payload) remain anonymous — no change — **decided** (workshop 4.1)

**Risks:**

- Persona slug in payload but not found in DB (mitigated: log warning, create agent without persona — don't block registration)
- Race condition between persona creation and agent creation (mitigated: personas are pre-registered via S6)

**Acceptance Criteria:**

- [ ] session-start hook with persona slug → Agent created with persona_id set
- [ ] session-start hook without persona slug → Agent created with persona_id NULL (existing behaviour)
- [ ] Agent.persona relationship navigable after assignment
- [ ] Persona slug not found in DB → agent created without persona, warning logged
- [ ] SessionCorrelator's existing 6-strategy cascade unaffected for non-persona sessions
- [ ] Events logged for persona assignment

---

### Sprint 9: Skill File Injection via tmux Bridge (E8-S9)

**Goal:** After an agent with a persona is registered and online, inject the persona's skill.md and experience.md content as the first user message via the existing tmux bridge, prompting the agent to respond in character.

**Duration:** 1 week
**Dependencies:** E8-S8 (agent has persona_id after registration), E8-S5 (skill files exist on disk)

**Deliverables:**

**Injection Trigger:**

- After SessionCorrelator assigns persona_id to a new agent:
  1. Read `data/personas/{slug}/skill.md` content
  2. Read `data/personas/{slug}/experience.md` content
  3. Compose a priming message combining both (BMAD pattern)
  4. Send via existing `tmux_bridge.send_text()` to the agent's tmux pane
- Agent receives the priming message as its first user input
- Agent responds in character (e.g., "Hi, I'm Con. Backend developer. What would you like me to work on?")

**Priming Message Format:**

- Structured message that includes persona identity, skills, and experience
- Format designed for the agent to absorb and respond to naturally
- Not a system prompt injection — it's a conversation-level user message (BMAD priming pattern)

**Timing:**

- Injection happens post-registration, after the agent session is confirmed healthy and communicating
- Must not race with operator's first command — injection should complete before the operator interacts

**Subsystem Requiring PRD:**

9. `persona` — Skill file injection via tmux bridge with BMAD priming pattern

**PRD Location:** `docs/prds/persona/e8-s9-skill-file-injection-prd.md`

**Stories:**

- E8-S9: Skill file injection via tmux bridge post-registration

**Technical Decisions Made:**

- First-prompt injection via tmux bridge, not system prompt hacking — **decided** (workshop 3.2)
- BMAD priming pattern (proven effective) — **decided** (workshop 3.2)
- Uses existing `tmux_bridge.send_text()` — no new transport mechanism — **decided** (workshop 3.2)
- General sessions (no persona) are not affected — injection only for persona-backed agents — **decided** (workshop 3.2)
- No token budget management for skill files — they're lightweight priming signals — **decided** (workshop 3.1)

**Risks:**

- Agent may not respond in character if skill file content is poorly structured (mitigated: iterate on skill.md templates, this is a prompt engineering refinement)
- tmux pane not ready when injection fires (mitigated: injection waits for session-start hook confirmation — agent is online)
- Skill file missing on disk (mitigated: check file exists before reading, log warning if missing, skip injection gracefully)

**Acceptance Criteria:**

- [ ] Agent with persona launches → skill.md + experience.md content sent as first message via tmux bridge
- [ ] Agent responds in character (acknowledges identity, role, readiness)
- [ ] Agent without persona launches → no injection occurs (existing behaviour)
- [ ] Missing skill file handled gracefully (warning logged, agent starts without persona priming)
- [ ] Injection uses existing `send_text()` — no new tmux infrastructure
- [ ] Operator can send commands after injection completes — no race condition

---

### Sprint 10: Dashboard Card Persona Identity (E8-S10)

**Goal:** Replace the UUID-based hero display on agent cards with persona name and role suffix when a persona is associated, while preserving the existing UUID display for anonymous agents.

**Duration:** 1 week
**Dependencies:** E8-S8 (agents have persona_id set — card needs persona data)

**Deliverables:**

**Card Hero Update:**

- When agent has persona: hero text shows persona name (e.g., "Con")
- Role shown as suffix (e.g., "Con — developer")
- When agent has no persona: existing UUID-based hero display (`hero_chars` + `hero_trail`) unchanged

**CardState Extension:**

- `card_state.py` computes persona name and role for card JSON when persona_id is set
- SSE `card_refresh` events include persona identity data
- Dashboard JavaScript renders persona name/role when present, UUID when absent

**Backward Compatibility:**

- Anonymous agents (no persona) display exactly as they do today
- No visual changes to cards without personas

**Subsystem Requiring PRD:**

10. `persona` — Dashboard card persona identity display (UI)

**PRD Location:** `docs/prds/ui/e8-s10-card-persona-identity-prd.md`

**Stories:**

- E8-S10: Dashboard card persona name and role display

**Technical Decisions Made:**

- Persona name as hero text, role as suffix — **decided** (workshop 4.2)
- No colour coding per persona or role — not needed at this stage — **decided** (workshop 4.2)
- No avatar or icon — name as text is sufficient — **decided** (workshop 4.2)
- Anonymous agents keep UUID hero — full backward compatibility — **decided** (workshop 4.2)

**Risks:**

- Long persona names may overflow card layout (mitigated: CSS truncation, names are short by convention — "Con", "Robbo", "Gavin")
- SSE card_refresh payload size increase (mitigated: two additional string fields — negligible)

**Acceptance Criteria:**

- [ ] Agent card with persona shows "Con — developer" instead of UUID hero
- [ ] Agent card without persona shows UUID hero as before
- [ ] Persona identity updates via SSE card_refresh events
- [ ] Multiple agents with same persona display correctly (both show "Con — developer")
- [ ] Card layout handles persona name + role suffix without visual overflow
- [ ] Dashboard renders correctly with mix of persona and anonymous agents

---

### Sprint 11: Agent Info Panel + Summary Persona Display (E8-S11)

**Goal:** Show persona identity in the agent info/detail panel and in project/activity page agent summaries, while preserving technical details (UUID, session ID, pane IDs) in the info panel.

**Duration:** 1 week
**Dependencies:** E8-S10 (card persona display — establishes the pattern)

**Deliverables:**

**Agent Info Panel:**

- Persona section: name, role, status, slug
- Technical details preserved: session UUID, claude_session_id, iterm_pane_id, tmux_pane_id, transcript_path
- Persona section appears above technical details when persona is present
- No persona section for anonymous agents

**Project Page Agent Summaries:**

- Active and ended agents listed with persona name + role when available
- UUID fallback for anonymous agents

**Activity Page:**

- Agent references in activity views show persona name + role when available
- UUID fallback for anonymous agents

**Subsystem Requiring PRD:**

11. `persona` — Agent info panel and summary persona display (UI)

**PRD Location:** `docs/prds/ui/e8-s11-agent-info-persona-display-prd.md`

**Stories:**

- E8-S11: Agent info panel and project/activity page persona display

**Technical Decisions Made:**

- Technical details (UUID, session ID, pane IDs) preserved in info panel — **decided** (workshop 4.2)
- Persona identity visible across all views where agents appear — **decided** (workshop 4.2)

**Risks:**

- Multiple views to update (mitigated: systematic — info panel, project page, activity page; each is a discrete template change)

**Acceptance Criteria:**

- [ ] Agent info panel shows persona name, role, and status when persona is associated
- [ ] Agent info panel preserves all technical details (UUID, session IDs, pane IDs)
- [ ] Project page agent summaries show persona name + role
- [ ] Activity page agent references show persona name + role
- [ ] Anonymous agents show UUID-based identity across all views (unchanged)
- [ ] Ended agents with personas retain persona identity in historical views

---

### Sprint 12: Handoff Database Model (E8-S12)

**Goal:** Create the Handoff table that stores metadata and injection prompts for agent context handoffs, linking to the outgoing agent and referencing the filesystem-based handoff document.

**Duration:** 0.5-1 week
**Dependencies:** E8-S4 (Agent.previous_agent_id — handoff chain depends on agent continuity)

**Deliverables:**

**Handoff Table:**

- New `Handoff` SQLAlchemy model with integer PK
- Fields: `id` (int PK), `agent_id` (int FK to Agent — the outgoing agent that produced this handoff), `reason` (str — "context_limit" | "shift_end" | "task_boundary"), `file_path` (str — path to handoff document on disk), `injection_prompt` (text — the full prompt sent to the successor agent via tmux bridge), `created_at` (datetime)
- Alembic migration

**Design Notes:**

- Handoff belongs to the outgoing agent (the one that wrote it)
- The incoming agent finds the handoff by: follow `previous_agent_id` → find predecessor's Handoff record → read `file_path` (for system queries) OR receive `injection_prompt` directly via tmux bridge (for agent consumption)
- `injection_prompt` IS the orchestration message sent to the successor — e.g., "Continuing work from Agent 4b6f8a2c. Read `data/personas/developer-con-1/handoffs/20260220T143025-4b6f8a2c.md` to pick up context."
- `file_path` points to the detailed handoff document that the successor reads with its own tools

**Relationships:**

- `Handoff.agent` → Agent (outgoing)
- `Agent.handoff` → Handoff (one-to-one — one agent produces at most one handoff)

**Subsystem Requiring PRD:**

12. `persona` — Handoff database model with injection prompt and file path

**PRD Location:** `docs/prds/persona/e8-s12-handoff-model-prd.md`

**Stories:**

- E8-S12: Handoff database model for agent context continuity

**Technical Decisions Made:**

- Hybrid handoff storage: DB metadata + filesystem content — **decided** (workshop 5.1)
- DB stores the injection prompt (sent directly to successor) — **decided** (workshop 5.1)
- Filesystem stores the detailed handoff document (read by successor via tools) — **decided** (workshop 5.1)
- Handoff belongs to outgoing agent; successor finds it via previous_agent_id chain — **decided** (workshop 5.1, ERD)
- Integer PK, consistent with codebase — **decided** (workshop)

**Data Model:**

```python
class Handoff(db.Model):
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agent.id"), nullable=False)
    reason = Column(String, nullable=False)  # context_limit | shift_end | task_boundary
    file_path = Column(String)  # path to handoff document on disk
    injection_prompt = Column(Text)  # full prompt sent to successor via tmux bridge
    created_at = Column(DateTime, default=func.now())
```

**Risks:**

- One-to-one relationship enforcement (mitigated: application-level check — if agent already has a handoff, reject or overwrite)

**Acceptance Criteria:**

- [ ] Handoff table exists in database after migration
- [ ] Can create Handoff record with agent_id, reason, file_path, injection_prompt
- [ ] Handoff.agent relationship navigable
- [ ] Agent.handoff relationship returns the handoff record (if exists)
- [ ] Existing tables unaffected

---

### Sprint 13: Handoff Trigger UI (E8-S13)

**Goal:** Add context threshold monitoring to agent cards and display a handoff button when an agent's context usage reaches a configurable threshold, enabling operator-initiated handoffs.

**Duration:** 1 week
**Dependencies:** E8-S12 (Handoff model), E8-S10 (card persona identity — handoff button appears on persona cards)

**Deliverables:**

**Context Threshold Monitoring:**

- Monitor `context_percent_used` on each agent (already tracked by E6-S4 context monitoring)
- Compare against configurable threshold (e.g., 80% — configurable for testing)
- When threshold exceeded, flag agent as "handoff eligible"

**Handoff Button on Agent Card:**

- New UI control on the agent card: "Handoff" button
- Button appears only when:
  - Agent has a persona (anonymous agents don't handoff)
  - Context usage exceeds the configured threshold
- Button triggers the handoff flow (E8-S14)
- Visual indicator that context is approaching limit (e.g., context bar changes colour)

**Configuration:**

- Handoff threshold configurable (for testing: wind down to 10% to trigger easily)
- Configuration in appropriate config section

**Subsystem Requiring PRD:**

13. `persona` — Handoff trigger UI with context threshold and dashboard button

**PRD Location:** `docs/prds/ui/e8-s13-handoff-trigger-ui-prd.md`

**Stories:**

- E8-S13: Handoff trigger UI with context threshold monitoring and card button

**Technical Decisions Made:**

- Operator-initiated handoff only — no auto-trigger in v1 — **decided** (workshop 5.1)
- Manual trigger allows compaction to work naturally — operator judges whether handoff is needed — **decided** (workshop 5.1)
- Manual trigger doubles as debugging mechanism — wind down threshold, fire handoff, inspect output, refine prompt — **decided** (workshop 5.1)
- Configurable threshold for testing — **decided** (workshop 5.1)

**Risks:**

- Context usage data not always available (mitigated: button only appears when context data exists — relies on E6-S4 context monitoring)
- Operator doesn't notice button (mitigated: visual indicator on context bar when threshold exceeded)

**Acceptance Criteria:**

- [ ] Handoff button appears on persona agent cards when context exceeds threshold
- [ ] Handoff button does not appear on anonymous agent cards
- [ ] Handoff button does not appear when context is below threshold
- [ ] Threshold is configurable (can be set to 10% for testing)
- [ ] Context bar visual indicator changes when threshold exceeded
- [ ] Button click triggers the handoff flow (wired to E8-S14)
- [ ] Button state updates via SSE as context usage changes

---

### Sprint 14: Handoff Execution (E8-S14)

**Goal:** Implement the full handoff cycle: operator triggers → Headspace prompts outgoing agent to write handoff document → DB record created → outgoing session ends → successor agent spins up with same persona → injection prompt sent → successor reads handoff file and continues work.

**Duration:** 2 weeks
**Dependencies:** E8-S13 (trigger UI), E8-S12 (Handoff model), E8-S9 (skill injection — successor needs the same priming), E8-S7 (persona-aware agent creation — successor is created with same persona)

**Deliverables:**

**Handoff Orchestration Flow:**

1. Operator clicks handoff button (from S13)
2. Headspace sends handoff instruction to outgoing agent via tmux bridge: "Write your handoff document to `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`"
3. Agent writes the handoff file using its Write tool (agent-as-author — it has the richest context about what it was doing)
4. Agent confirms completion in conversation
5. Headspace detects confirmation via existing hook/turn processing
6. Headspace creates Handoff DB record with:
   - `agent_id` → outgoing agent
   - `reason` → from trigger context
   - `file_path` → the handoff document path
   - `injection_prompt` → composed prompt for successor (includes handoff file path and task context)
7. Outgoing agent session ends (graceful shutdown via `/exit`)
8. New agent spins up with same persona (via `create_agent(persona_slug=...)`)
9. New agent's `previous_agent_id` set to outgoing agent's ID
10. After registration + skill injection (S9): Headspace sends `injection_prompt` from Handoff record via tmux bridge
11. Successor agent reads the handoff file with its own tools → continues work

**Handoff Document Location:**

- Path: `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`
- ISO datetime format in filename (e.g., `20260220T143025`)
- Agent 8-digit identifier for uniqueness
- Directory created if it doesn't exist

**Handoff Document Content (agent-written):**

The outgoing agent writes first-person context:
- What it was working on
- Current progress and state
- Key decisions made and why
- Blockers encountered
- Files modified
- Next steps and what remains
- Any context the successor needs

**Injection Prompt (DB-stored, sent to successor):**

The orchestration message sent directly via tmux bridge:
- References the predecessor agent
- Points to the handoff file path
- Provides task context
- Successor receives this without needing tools — it's a conversation message

**File Lifecycle:**

- Handoff files accumulate in `data/personas/{slug}/handoffs/`
- No cleanup in v1 — small text files, deferred to future system management PRD

**Subsystem Requiring PRD:**

14. `persona` — Handoff execution with agent-written document and successor bootstrap

**PRD Location:** `docs/prds/persona/e8-s14-handoff-execution-prd.md`

**Stories:**

- E8-S14: Handoff execution — full cycle from trigger to successor continuation

**Technical Decisions Made:**

- Agent-as-author — outgoing agent writes its own handoff document (richest context) — **decided** (workshop 5.1)
- File-native consumption — successor reads handoff file via Read tool (natural for agents) — **decided** (workshop 5.1)
- Two-phase bootstrap — DB injection prompt bootstraps immediately, file deepens understanding — **decided** (workshop 5.1)
- Handoff files under persona tree — consistent with skill.md/experience.md asset pattern — **decided** (workshop 5.1)
- Operator-initiated — manual trigger provides human-in-the-loop for prompt tuning and quality control — **decided** (workshop 5.1)
- Handoff file naming: ISO datetime + agent 8-digit ID — **decided** (workshop 5.1)
- No file cleanup in v1 — deferred to system management PRD — **decided** (workshop 5.1)

**Risks:**

- Agent may not comply with handoff prompt correctly (mitigated: manual trigger enables iterative prompt tuning; human-in-the-loop reviews handoff quality before committing)
- Context headroom — agent needs enough remaining context to write a thorough handoff (mitigated: threshold tuning; operator triggers early enough to leave room)
- Race condition between handoff write and session end (mitigated: Headspace waits for agent confirmation before proceeding)
- Handoff file missing after agent claims completion (mitigated: verify file exists before creating DB record)

**Acceptance Criteria:**

- [ ] Operator clicks handoff → outgoing agent receives handoff instruction via tmux
- [ ] Outgoing agent writes handoff document to correct filesystem path
- [ ] Handoff document contains meaningful first-person context (progress, decisions, next steps)
- [ ] Handoff DB record created with correct agent_id, reason, file_path, injection_prompt
- [ ] Outgoing agent session ends gracefully
- [ ] Successor agent spins up with same persona
- [ ] Successor agent's previous_agent_id links to outgoing agent
- [ ] Successor receives skill injection (S9) followed by handoff injection prompt
- [ ] Successor reads handoff file and demonstrates context continuity
- [ ] Full handoff cycle completes without manual intervention (after initial trigger)
- [ ] Handoff files accumulate at `data/personas/{slug}/handoffs/` without issues

---

### Sprint 15: Persona List & CRUD UI (E8-S15)

**Goal:** Deliver the persona management UI: a Personas tab in the main navigation, a list page showing all registered personas, and full CRUD operations (create, edit, archive/delete) via modal forms with role management inline.

**Duration:** 1 week
**Dependencies:** E8-S6 (persona registration — backend CRUD exists), E8-S10 (card persona identity — establishes UI patterns)
**Status:** Complete (23 Feb 2026)

**Deliverables:**

- Personas tab in main navigation (top-level, alongside Projects/Config/Help)
- Persona list page (`/personas`) with table: name, role, status, linked agent count, created date
- Create persona modal: name (required), role (select existing or create new), description (optional)
- Edit persona modal for name, description, and status updates
- Archive and delete actions with confirmation dialogs
- Toast notifications for CRUD outcomes
- API endpoints powering the UI

**PRD Location:** `docs/prds/persona/done/e8-s15-persona-list-crud-prd.md`

---

### Sprint 16: Persona Detail Page & Skill Editor (E8-S16)

**Goal:** Add the persona detail page with a markdown skill file editor, experience log viewer, and linked agent display — completing the per-persona management experience.

**Duration:** 1 week
**Dependencies:** E8-S15 (persona list — provides navigation to detail page), E8-S5 (filesystem assets — skill.md and experience.md exist on disk)
**Status:** Complete (23 Feb 2026)

**Deliverables:**

- Persona detail page (`/personas/<slug>`) with full profile
- Skill file editor with markdown editing and preview modes (following waypoint editor pattern)
- Experience log viewer (read-only, rendered markdown)
- Linked agents list showing agents currently assigned to this persona
- API endpoints for skill file read/write, experience file read, persona asset status
- Back navigation to persona list

**PRD Location:** `docs/prds/persona/done/e8-s16-persona-detail-skill-editor-prd.md`

---

### Sprint 17: Persona-Aware Agent Creation UI & CLI Discovery (E8-S17)

**Goal:** Integrate persona selection into the agent creation workflow from the dashboard and enhance the CLI with persona discovery and short-name matching.

**Duration:** 1 week
**Dependencies:** E8-S15 (persona list UI), E8-S7 (persona-aware agent creation backend)
**Status:** Complete (23 Feb 2026)

**Deliverables:**

- Persona selector in dashboard agent creation flow (dropdown, grouped by role, active only)
- Persona quick-info display during selection (role, description preview)
- Agent creation API accepting optional `persona_slug` parameter
- CLI `flask persona list` for persona discovery
- CLI short-name matching for `--persona` flag (e.g., `--persona con` resolves to `developer-con-1`)
- Disambiguation prompt when short-name matches multiple personas

**PRD Location:** `docs/prds/persona/done/e8-s17-persona-agent-creation-prd.md`

---

### Sprint 18: Agent Revival — "Seance" (E8-S18)

**Goal:** Enable operators to revive dead agents by spinning up a successor that self-briefs from the predecessor's conversation history stored in the database. Where handoff (S14) requires a living agent to curate context, revival reconstructs context from the raw conversational record — a "seance" for dead agents.

**Duration:** 1-2 weeks
**Dependencies:** E8-S9 (skill injection — persona agents need priming before revival instruction), E8-S7 (persona-aware agent creation — successor created with same persona), E8-S4 (Agent.previous_agent_id for continuity chain)

**Deliverables:**

**CLI Transcript Command:**

- New `claude-headspace transcript <agent-id>` CLI command
- Queries database: Agent → Commands → Turns
- Outputs structured markdown: commands as section headers, turns as `**User:**` / `**Agent:**` blocks with timestamps
- Conversational content only — no metadata (frustration scores, command states, turn summaries)
- Uses Flask CLI infrastructure (Click commands within Flask context)
- Handles edge cases: no commands, no turns, empty turn text

**Revive API Endpoint:**

- REST endpoint triggered by dashboard UI
- Validates agent exists and is dead (`ended_at IS NOT NULL`)
- Creates successor agent with same project and persona config
- Sets `previous_agent_id` to link continuity chain
- Orchestrates revival instruction injection after agent comes online

**Revival Instruction Injection:**

- Delivered via tmux bridge (same mechanism as persona injection)
- For persona agents: injected after skill injection completes
- For non-persona agents: injected as the sole first instruction
- Instruction tells the new agent to run `claude-headspace transcript <predecessor-id>` and self-brief

**Revive UI Trigger:**

- "Revive" button/action on dead agent cards and agent detail view
- Only visible for agents where `ended_at IS NOT NULL`
- Provides feedback during revival flow (spinner/status)
- Successor card shows predecessor link in continuity chain

**Subsystem Requiring PRD:**

18. `agents` — Agent revival CLI, API endpoint, injection, and UI trigger

**PRD Location:** `docs/prds/agents/e8-s18-agent-revival-prd.md`

**Stories:**

- E8-S18: Agent revival — CLI transcript extraction, revive API, injection, and dashboard trigger

**Technical Decisions Made:**

- Agent self-briefs from CLI output — no pre-summarisation by the system — **decided** (PRD workshop)
- CLI outputs conversational content only — no metadata — **decided** (PRD workshop)
- Agent database ID as the identifier — **decided** (PRD workshop)
- Reuses persona injection mechanism (tmux bridge) — **decided** (PRD workshop)
- Works for both persona and anonymous agents — **decided** (PRD workshop)
- Complementary to handoff (S14), not a replacement — **decided** (PRD workshop)
- Always allow revival regardless of conversation length — **decided** (PRD workshop)

**Risks:**

- Long conversation histories may exceed the new agent's context window (mitigated: agent processes what it can; operator can start a second revival if needed)
- CLI command requires Flask app context for DB access (mitigated: use existing Flask CLI infrastructure)
- Revival instruction timing — must arrive after skill injection for persona agents (mitigated: same sequencing pattern as handoff injection in S14)

**Acceptance Criteria:**

- [ ] `claude-headspace transcript <agent-id>` outputs structured markdown of conversation history
- [ ] CLI handles edge cases (no commands, no turns, invalid agent ID)
- [ ] Revive endpoint validates agent is dead before proceeding
- [ ] Successor agent created with same project and persona as predecessor
- [ ] `previous_agent_id` links successor to predecessor
- [ ] Revival instruction injected after skill injection (persona agents) or as first instruction (anonymous agents)
- [ ] New agent retrieves and processes predecessor's conversation history
- [ ] Dashboard shows "Revive" action on dead agent cards
- [ ] Revive action not visible on active agents
- [ ] Revival works for both persona-based and anonymous agents

---

## Sprint Dependencies & Sequencing

```
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
   │                       └──▶ E8-S8 (SessionCorrelator Assignment) ◄── E8-S4
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

E8-S6 (Registration) + E8-S10 (Card Identity)
   │
   └──▶ E8-S15 (Persona List & CRUD UI) ◄── E8-S6, E8-S10
           │
           └──▶ E8-S16 (Persona Detail & Skill Editor) ◄── E8-S5
                   │
                   └──▶ E8-S17 (Persona-Aware Agent Creation UI) ◄── E8-S7

E8-S9 (Skill Injection) + E8-S7 (Persona-Aware Agent Creation) + E8-S4 (Agent Extensions)
   │
   └──▶ E8-S18 (Agent Revival / "Seance") ◄── E8-S9, E8-S7, E8-S4
```

**Critical Path:** E8-S1 → E8-S5 → E8-S6 → E8-S7 → E8-S8 → E8-S9 → E8-S14/S18

**Linear Build Order (implementation sequence):**

```
S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11 → S12 → S13 → S14 → S15 → S16 → S17 → S18
```

All sprints are built sequentially. Each sprint builds on the foundation of previous sprints.

---

## Cross-Epic Dependencies

```
Epic 1 (Core Foundation)
   │
   ├── Hook Receiver ──────────────────────────────────┐
   ├── SessionCorrelator ──────────────────────────────┤
   ├── State Machine ──────────────────────────────────┤
   └── Dashboard + SSE ────────────────────────────────┤
                                                        │
Epic 5 (Voice Bridge & Project Enhancement)             │
   │                                                    │
   └── E5-S4 (tmux Bridge / send_text) ────────────────┤
                                                        │
Epic 6 (Voice Bridge & Agent Chat)                      │
   │                                                    │
   └── E6-S4 (Agent Lifecycle / create_agent) ─────────┤
                                                        │
                                                        ▼
                                                 Epic 8 (Personable Agents)
                                                        │
                                                        ├── E8-S1–S6: Data + Registration
                                                        ├── E8-S7–S9: Agent Identity + Injection
                                                        ├── E8-S10–S11: Dashboard Display
                                                        └── E8-S12–S14: Handoff System
```

**Key dependencies from completed epics:**

- **Hook Receiver + SessionCorrelator (E1):** Extended in S8 for persona assignment at registration
- **tmux Bridge / send_text (E5-S4):** Used in S9 for skill injection and S14 for handoff prompting
- **create_agent (E6-S4):** Extended in S7 for persona-aware agent creation
- **Dashboard + SSE + CardState (E1):** Extended in S10-S11 for persona identity display
- **Context monitoring (E6-S4):** Used in S13 for handoff threshold detection

All dependencies are on completed epics (E1-E6). Epic 7 (testing) is independent.

---

## Acceptance Test Cases

### Test Case 1: Persona Registration

**Setup:** Application running, database clean of persona data.

**Success:**

- ✅ `flask persona register --name Con --role developer --description "Backend Python developer"` succeeds
- ✅ Role record "developer" exists in database
- ✅ Persona record exists with slug "developer-con-1"
- ✅ Directory `data/personas/developer-con-1/` exists
- ✅ `skill.md` seeded with template content
- ✅ `experience.md` seeded with header

### Test Case 2: Persona-Aware Agent Launch (CLI)

**Setup:** Persona "Con" registered. Server running.

**Success:**

- ✅ `claude-headspace start --persona con` launches a tmux session
- ✅ session-start hook fires with persona slug in payload
- ✅ Agent record created with persona_id set to Con's persona
- ✅ skill.md + experience.md content injected as first message via tmux bridge
- ✅ Agent responds in character ("Hi, I'm Con...")
- ✅ Dashboard card shows "Con — developer" instead of UUID

### Test Case 3: Anonymous Agent Launch (Backward Compat)

**Setup:** Server running. No persona specified.

**Success:**

- ✅ `claude-headspace start` launches normally
- ✅ Agent record created with persona_id = NULL
- ✅ No skill injection occurs
- ✅ Dashboard card shows UUID hero as before
- ✅ All existing functionality unchanged

### Test Case 4: Dashboard Identity Display

**Setup:** Two agents running — one with persona (Con), one anonymous.

**Success:**

- ✅ Con's card shows "Con — developer" as hero
- ✅ Anonymous agent card shows UUID hero
- ✅ Con's info panel shows persona details AND technical details (UUID, session ID, pane IDs)
- ✅ Project page shows Con's persona identity in agent summaries
- ✅ Activity page shows Con's persona identity

### Test Case 5: Handoff Cycle

**Setup:** Con agent running with context at threshold. Persona registered. Server running.

**Success:**

- ✅ Context exceeds threshold → handoff button appears on Con's card
- ✅ Operator clicks handoff → outgoing Con receives handoff instruction
- ✅ Con writes handoff document to `data/personas/developer-con-1/handoffs/20260220T143025-00000042.md`
- ✅ Handoff DB record created with injection prompt
- ✅ Outgoing Con session ends gracefully
- ✅ New Con agent spins up automatically
- ✅ New agent's previous_agent_id links to outgoing agent
- ✅ Skill injection + handoff injection prompt sent to new Con
- ✅ New Con reads handoff file and demonstrates context continuity
- ✅ Dashboard updates throughout: old card disappears, new card appears with "Con — developer"

### Test Case 6: End-to-End Epic 8 Flow

**Setup:** Fresh Epic 8 deployment. No personas registered.

**Success:**

- ✅ Register personas: Con (developer), Robbo (architect), Verner (tester)
- ✅ Create dev org and positions
- ✅ Launch Con with persona → responds in character
- ✅ Launch Robbo with persona → responds in character
- ✅ Dashboard shows "Con — developer" and "Robbo — architect"
- ✅ Launch anonymous agent → shows UUID hero (backward compat)
- ✅ Con reaches context threshold → handoff button appears
- ✅ Trigger handoff → new Con picks up seamlessly
- ✅ All persona agents and anonymous agents coexist on dashboard
- ✅ Project and activity pages show persona identities correctly

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order:

### Phase 1: Data Foundation (Sprints 1-4)

1. **persona-role-models** (`docs/prds/persona/e8-s1-role-persona-models-prd.md`) — Role and Persona database models with migrations
2. **organisation-model** (`docs/prds/persona/e8-s2-organisation-model-prd.md`) — Organisation database model with dev org seed
3. **position-model** (`docs/prds/persona/e8-s3-position-model-prd.md`) — Position database model with self-referential hierarchy
4. **agent-extensions** (`docs/prds/persona/e8-s4-agent-model-extensions-prd.md`) — Agent model extensions with persona_id, position_id, previous_agent_id

**Checkpoint:** All new tables exist. Agent can reference Persona and Position. Continuity chain enabled.

---

### Phase 2: Filesystem + Registration (Sprints 5-6)

5. **filesystem-assets** (`docs/prds/persona/e8-s5-persona-filesystem-assets-prd.md`) — Persona directory convention, skill.md/experience.md templates, path utilities
6. **persona-registration** (`docs/prds/persona/e8-s6-persona-registration-prd.md`) — CLI/API for end-to-end persona registration (DB + filesystem)

**Checkpoint:** Can register a persona. DB record + filesystem assets created in one operation.

---

### Phase 3: Agent Identity (Sprints 7-9)

7. **persona-agent-creation** (`docs/prds/persona/e8-s7-persona-aware-agent-creation-prd.md`) — create_agent() persona parameter, CLI --persona flag, hook payload
8. **session-correlator-persona** (`docs/prds/persona/e8-s8-session-correlator-persona-prd.md`) — SessionCorrelator persona assignment from hook payload
9. **skill-injection** (`docs/prds/persona/e8-s9-skill-file-injection-prd.md`) — Skill file injection via tmux bridge with BMAD priming

**Checkpoint:** Can launch an agent with a persona. Agent receives identity, responds in character.

---

### Phase 4: Dashboard Display (Sprints 10-11)

10. **card-persona-identity** (`docs/prds/ui/e8-s10-card-persona-identity-prd.md`) — Dashboard card hero with persona name + role suffix
11. **info-panel-persona** (`docs/prds/ui/e8-s11-agent-info-persona-display-prd.md`) — Agent info panel and project/activity page persona display

**Checkpoint:** Dashboard shows persona names. Full visual identity working.

---

### Phase 5: Handoff System (Sprints 12-14)

12. **handoff-model** (`docs/prds/persona/e8-s12-handoff-model-prd.md`) — Handoff database model with injection prompt and file path
13. **handoff-trigger-ui** (`docs/prds/ui/e8-s13-handoff-trigger-ui-prd.md`) — Context threshold monitoring and handoff button on agent card
14. **handoff-execution** (`docs/prds/persona/e8-s14-handoff-execution-prd.md`) — Full handoff cycle: agent-written document, DB record, successor bootstrap

**Checkpoint:** Full handoff cycle works. Persona context carries across agent sessions.

---

### Phase 5b: Persona Management UI (Sprints 15-17) [COMPLETE]

15. **persona-list-crud** (`docs/prds/persona/done/e8-s15-persona-list-crud-prd.md`) — Personas tab, list page, create/edit/archive/delete modals, role management
16. **persona-detail-skill-editor** (`docs/prds/persona/done/e8-s16-persona-detail-skill-editor-prd.md`) — Persona detail page, skill file markdown editor, experience log viewer, linked agents
17. **persona-agent-creation-ui** (`docs/prds/persona/done/e8-s17-persona-agent-creation-prd.md`) — Persona selector in agent creation flow, CLI persona discovery, short-name matching

**Checkpoint:** Full persona management UI. Create, edit, inspect, and assign personas entirely from the dashboard.

---

### Phase 6: Agent Revival (Sprint 18)

18. **agent-revival** (`docs/prds/agents/e8-s18-agent-revival-prd.md`) — CLI transcript extraction, revive API, injection, and dashboard trigger for dead agent context recovery

**Checkpoint:** Dead agents can be revived. Successor agents self-brief from predecessor conversation history.

---

## Deferred Items

The following items were identified during the workshop but explicitly deferred:

### Kanban Hierarchy (Deferred — Build Bottom-Up)

The current Kanban tracks agent state at the atomic level (command/turn, minutes-to-hours). Workshop mode and persona-driven work introduces work-item progress across multi-day, multi-session horizons. A two-level Kanban hierarchy (work items above atomic activity) will emerge from operational experience with personas and org structure. Not designed in v1.

**Status:** Deferred — revisit after personas and org are operational

### PM Layer / Cross-Agent Task Assignment (Deferred — v3)

Gavin's PM automation requires a concrete understanding of cross-agent task decomposition. The Command model stays as-is. A higher-level WorkItem or Assignment model is a v3 concern.

**Status:** Deferred — requires operational persona experience

### Multi-Org Conventions (Deferred — Phase 2+)

Personas are org-independent by design (no org_id on Persona). Multi-org naming and structure conventions will be designed when the second org is on the horizon.

**Status:** Deferred — current design doesn't paint into a corner

### Handoff File Cleanup (Deferred — System Management PRD)

Handoff files accumulate under `data/personas/{slug}/handoffs/`. Cleanup is part of a future system management PRD covering DB trimming, temp file cleanup, and housekeeping.

**Status:** Deferred — files are small, not urgent

### Auto-Handoff Trigger (Deferred — Post v1 Tuning)

Automatic handoff based on context threshold. Requires reliable handoff prompt compliance first. Manual trigger enables iterative tuning.

**Status:** Deferred — add after handoff prompt is proven reliable

---

## Design Source Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Agent Teams Workshop | `docs/workshop/agent-teams-workshop.md` | 15 design decisions resolved across 6 sessions (Feb 16-20, 2026) |
| ERD (Full) | `docs/workshop/erds/headspace-org-erd-full.md` | Entity relationship diagram — reference only (workshop decisions take precedence) |
| ERD (Simplified) | `docs/workshop/erds/headspace-org-erd-simplified.md` | Simplified entity view |
| Platform Vision | `docs/conceptual/headspace-platform-vision.md` | Long-term platform vision for agent teams |
| Functional Outline | `docs/conceptual/headspace-agent-teams-functional-outline.md` | Functional requirements outline for agent teams |
| Workshop Alignment Analysis | `docs/workshop/agent-teams-alignment-analysis.md` | Codebase grounding analysis |

**Note:** Where ERD documents diverge from workshop decisions, the workshop decisions (recorded in `agent-teams-workshop.md`) take precedence. The ERDs include reference material from external review that was not adopted (UUIDs, PositionAssignment table, org-scoped roles). See workshop decision log for authoritative resolutions.

---

## Document History

| Version | Date       | Author | Changes                                                |
| ------- | ---------- | ------ | ------------------------------------------------------ |
| 1.0     | 2026-02-20 | Sam    | Initial detailed roadmap for Epic 8 (14 sprints)       |

---

**End of Epic 8 Detailed Roadmap**
