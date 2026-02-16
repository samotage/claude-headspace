All four research agents are complete. I've got the full picture now. Let me compile the alignment analysis.

---

## Alignment Analysis: Vision & Functional Outline vs. Actual Codebase

Sam, here's what I found. I'm going to walk through each major concept from your documents and map it to what's actually in the codebase today — what aligns cleanly, what needs extending, what's genuinely new, and where the documents make assumptions that don't match reality.

---

### CLEAN ALIGNMENTS (These Just Work)

**1. State Machine — Unchanged** ✅
The functional outline (§9.2) says the existing Task state machine is unaffected. Confirmed. The state machine is a pure stateless validator: `IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE`. Personas layer above this. No modifications needed for v1.

**2. Task & Turn Models — Unchanged** ✅
Task (5-state lifecycle with instruction, completion_summary, plan support) and Turn (actor, intent, text, summary, frustration_score) are exactly as described. The persona system sits above these — they're about execution mechanics, not identity.

**3. Context Window Data Exists** ✅
Agent already has `context_percent_used`, `context_remaining_tokens`, `context_updated_at`. This is the raw signal the handoff trigger (v2) needs. The data pipeline exists; you'd build detection logic on top.

**4. Priority Scoring Infrastructure** ✅
Agent has `priority_score`, `priority_reason`, `priority_updated_at` with a check constraint ensuring they're all-or-nothing. PriorityScoringService is already wired. Persona-aware scoring is an extension, not a rebuild.

**5. SSE/Broadcaster Pipeline** ✅
The card_refresh broadcast path is well-established: `build_card_state()` → broadcaster → SSE → `handleCardRefresh()` in JS → DOM update. Adding persona fields to the card state dict flows through the entire pipeline automatically.

**6. Agent.name Property — Easy Override** ✅
Currently returns `"ProjectName/session-uuid-prefix"`. This is a Python `@property` on the Agent model. With a `persona_id` FK, this becomes `persona.name` — trivial change, high visibility impact.

---

### NATURAL EXTENSIONS (Modify What Exists)

**7. Agent Model — Needs `persona_id` and `mode`**
The functional outline (§9.1) says Agent gains two fields:
- `persona_id` — FK to a Persona record (nullable for backward compat)
- `mode` — enum: `workshop` | `execution`

Current Agent has 17 fields. Adding two is straightforward. One Alembic migration. The nullable FK means existing agents without personas still work.

**8. Config.yaml — Needs `personas` and `pools` Sections**
Current config has ~18 top-level sections (server, logging, database, claude, etc.). The functional outline (§5.2, §5.4) defines `personas:` and `pools:` YAML blocks. These slot in as new top-level sections alongside existing ones. The config loader's `deep_merge()` handles this natively.

**9. Card State — Needs Persona Fields**
`build_card_state()` currently computes `hero_chars` and `hero_trail` from `session_uuid[:8]`. With personas, this becomes:
- `persona_name` — "Con", "Robbo", etc.
- `hero_chars` — first 2 chars of persona name (or keep UUID fallback for unassigned agents)
- Potentially `persona_role` — "execution", "workshop", etc. for visual indicators

Both the card_state computation AND the dashboard route's inline dict need to stay synchronised — the UI layer report confirms these are two parallel paths that must match.

**10. Session Correlator — Needs Persona Assignment**
The 6-strategy correlation cascade currently ends with "create new agent." With personas, step 6 becomes "create new agent **with persona assignment**." The correlator needs to know which persona is being assigned — this comes from config (operator selects) or from the CLI launcher (`claude-headspace start --persona con`).

**11. Agent Card Template — Identity Display**
Currently `_agent_card.html` line 17: `<span class="agent-hero">{{ agent.hero_chars }}</span>`. With personas, this becomes the persona name with appropriate styling. The Kanban view, priority view, and project view all use this same partial.

---

### GENUINELY NEW (Greenfield Work)

**12. Persona Model (Database)**
This is the big one. The functional outline describes persona identity in config (§5.2), but to support `Agent.persona_id` as a FK, you need a **Persona database table**. The outline doesn't explicitly call for this — it puts identity in config and skill files on disk. But the codebase pattern is relational: everything is FK'd through PostgreSQL.

**Decision needed:** Config-only personas (simpler, no migration, but no FK integrity) vs. Persona DB model (cleaner, supports queries like "which agents did Con run this week", but adds a model + migration + CRUD).

**13. Skill Files on Disk (`~/.headspace/personas/`)**
Entirely new infrastructure. Nothing in the codebase today touches `~/.headspace/`. You need:
- Directory creation/management
- `skill.md` and `experience.md` file I/O
- Loading skill files into agent context at spinup (how? via hook? via CLI wrapper?)
- The functional outline's experience log curation (v2) is future scope

**14. Workshop Mode Lifecycle**
The outline says workshop mode is "collaborative, iterative, document-producing." But the current system's entire lifecycle is hook-driven: Claude Code fires hooks → Flask processes them. A workshop session with Robbo would presumably still fire hooks (it's still Claude Code), but the *semantics* differ:
- No code expected
- Output is documents, not implementations
- Different summarisation prompts? Different priority scoring?

The state machine stays the same (the outline confirms this), but the *interpretation* of states changes. PROCESSING for a workshop persona means "thinking and writing docs," not "writing code."

**15. Pool-Based Persona Selection**
The outline's §5.5 describes: identify skill domain → filter pool → select available persona. Nothing like this exists today. Agents are created reactively (a Claude Code session starts → hook fires → agent appears). Pool selection implies *proactive* assignment: operator says "I need a backend task done" → system picks Con from the backend pool → launches a session.

This is a fundamentally different flow from the current hook-driven reactive model. In v1 where operator-is-Gavin, the operator manually picks — but the system still needs to track availability (which personas have active agents).

**16. Persona Availability Tracking**
The outline (§5.5) says "a persona can only be active in one agent at a time." The codebase currently has no concept of this. You need:
- Query: "Is Con currently assigned to an active agent?"
- Constraint: Prevent two active agents with the same persona
- Release: When agent ends/is reaped, persona returns to pool

This is straightforward with a Persona DB model + FK, but it's new logic.

---

### DISCREPANCIES & ASSUMPTIONS TO RESOLVE

**17. Config Location Mismatch**
The functional outline puts persona config in `~/.headspace/config.yaml`. But Headspace uses a **project-level** `config.yaml` (symlinked from `otl_support`). These are different files in different locations.

Options:
- **a)** Add persona/pool config to existing project-level config.yaml (simpler, but ties persona definitions to one project)
- **b)** Create `~/.headspace/config.yaml` as a new global config layer (matches the outline, but adds a second config system)
- **c)** Persona definitions in project config, skill files at `~/.headspace/` (hybrid — identity is project-scoped, experience is global)

The platform vision (§4.1) says personas exist independently of any organisation. That argues for option (b) or (c).

**18. Organisation Model — v1 or Not?**
The platform vision introduces Organisations as first-class entities. The functional outline's dev org is implicit. Do we add an `Organisation` DB model in v1?

My read: **No.** In v1, there's one org (dev). Hard-code it. The Organisation model is Phase 2 work (when Marketing org needs to coexist). Building it now is premature abstraction — but we should *design* the Persona model so it can gain an `org_id` FK later without breaking changes.

**19. How Do Skill Files Get Loaded?**
The functional outline says agents spin up "with persona identity + skill file loaded into context." But *how*? Currently, Claude Code sessions start independently — Headspace learns about them via hooks. The skill file needs to be in the Claude Code context *at launch*. This means either:
- The CLI launcher (`claude-headspace start`) injects skill file content into the session's system prompt (via CLAUDE.md or similar mechanism)
- Or Claude Code's own memory/settings mechanism is leveraged

This is a critical implementation detail the outline doesn't address.

**20. Handoff Orchestration (v2, but design-relevant)**
The outline's handoff (§6.4) says: outgoing session ends → new session spins up with same persona. Currently, session spinup is *manual* (operator runs `claude-headspace start`). Automated respawn requires new orchestration — possibly triggered by the CLI wrapper detecting context threshold, or by Headspace itself detecting it and spawning a new tmux session.

Not v1, but the design of how personas map to sessions needs to not preclude this.

---

### THE BOTTOM LINE

**What's surprisingly well-aligned:** The core domain model (Agent → Task → Turn), state machine, SSE pipeline, card state computation, priority scoring, and context monitoring are all solid foundations. The persona system genuinely layers on top without breaking existing abstractions.

**What's the biggest new work:** Persona model + availability tracking, skill file infrastructure, and pool selection logic. These are genuinely new subsystems.

**What needs the most design thought:** The boundary between config-driven persona identity and database-driven persona state. And how skill files get loaded into agent context at launch.

---

Sam, that's the full grounding pass. Want to start workshopping from here? I'd suggest we tackle the design decisions (DB model vs config-only, config location, skill file loading) first, because those shape every sprint that follows.

That last agent was the config/services one — its findings were already incorporated into the alignment analysis I just presented. All four research streams are fully digested.

Over to you, Sam — where do you want to dig in first?

Yes — I pulled its full output via TaskOutput while we were waiting, and all of its findings are baked into the alignment analysis I gave you. The config loader's `deep_merge()`, the SessionCorrelator's 6-strategy cascade, the state machine's transition map, TaskLifecycleManager's `process_turn()` flow, the reaper's liveness checks, card_state's `build_card_state()` — all mapped against your concept docs.

The 20 alignment points I walked through cover everything those four agents surfaced.