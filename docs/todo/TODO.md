# Claude Headspace - TODO

## Agent Chat

### Review listening screen and question screen for deprecation

The `screen-listening` and `screen-question` views in the voice/chat interface (`static/voice/`) are currently unused — all agent interactions now route through the chat screen (`screen-chat`), which handles text input, inline question options, and a mic button.

These screens should be reviewed and potentially repurposed or removed when voice interactivity is implemented. This is a larger epic that requires integrating a conversational model for natural voice chat.

**Screens:**
- `screen-listening` — standalone voice dictation with transcript display and text fallback
- `screen-question` — dedicated structured question/option rendering

**What the chat screen already covers:**
- Text input (chat input bar)
- Voice input (chat mic button)
- Structured questions (inline bubble option buttons)
- Full transcript history

**What's needed for voice interactivity:**
- Integration with a speech-to-text/text-to-speech model for conversational chat
- Determine whether the listening/question screens have a role in the voice UX or should be removed entirely
- Scope and plan the full voice interaction epic

## Security

### Run vulnerability scanning against all projects with Opus 4.6

Run comprehensive vulnerability scanning across all projects using Claude Opus 4.6. Scope: all active projects in the portfolio. Goal: identify security vulnerabilities, dependency issues, and code-level risks.

## Research

### Investigate PageIndex Vectors RAG framework for RagLue

Research the PageIndex Vectors RAG framework as a potential replacement for LLM-driven embeddings in RagLue. This framework uses a hierarchy tree approach and claims 98.7% accuracy. Investigate: how it works, how it replaces traditional LLM-driven embeddings, what the hierarchy tree structure looks like, validation of the 98.7% accuracy claim, integration path for RagLue, and trade-offs vs current approach.

## Architecture

### Rationalise skills, discover capabilities, and review persona context loading

Multi-part architectural review:

1. **Rationalise skills** — Audit the full set of available skills/commands (OTL, BMAD, OPSX, etc.). Identify overlap, redundancy, and consolidation opportunities. Which skills are actually used vs theoretical?
2. **Discover ability** — Map what each skill can actually do vs what it claims. Document real capabilities and gaps.
3. **Review initial persona-based context load** — Examine how persona skill files and experience files are loaded into the initial prompt injection (via SkillInjector / tmux send-keys). Assess: How much context budget does this consume? Is the content effective? Are we front-loading too much?
4. **Architectural solution for assigning skills/commands to personas** — Design the mechanism for which skills and commands a persona has access to. Currently skills are globally available — need an architecture for persona-scoped skill assignment.

   **Problem (two distinct issues):**
   - **Capability awareness** — agents don't know what skills are available to them (budget pressure at 93% means skills get lost in noise). With 111 files competing for 2% of context, per-persona filtering to ~15-20 relevant commands dramatically improves signal-to-noise.
   - **Capability restriction** — agents CAN be coerced into running things outside their lane. Current guardrails are soft (prompt-level). A determined user can "twist an agent's arm" past prompt-level restrictions. Need hard enforcement.

   **Concrete use cases driving the design:**
   | Persona | Morning Briefing | Orchestration | Rationale |
   |---------|-----------------|---------------|-----------|
   | Jen (frontend) | No | No | Scoped to UI work only |
   | Judy (PM) | Yes | No | Needs strategic input, not build pipeline |
   | Ferret (research) | Yes | No | Runs briefings, no build access |
   | Con (dev) | No | Yes | Builds features, doesn't do briefings |

   **Architectural options (discussed 2026-02-28 with Robbo):**

   - **Option A: Skill whitelist in persona config** — Each persona gets an explicit `allowed_skills` list. The skill injection system reads this and only surfaces those skills to the agent. Anything not on the list doesn't exist in the agent's world. *Pros:* Simple, declarative, easy to audit, solves budget pressure. *Cons:* Requires injection-time filtering; doesn't hard-prevent arm-twisting if someone describes a skill inline.

   - **Option B: Platform-level enforcement** — Claude Headspace intercepts skill/command invocations (via `pre-tool-use` hooks or similar) and validates against the persona's allowed list BEFORE execution. Agent can be tricked into trying, but the platform blocks it. *Pros:* Hard enforcement regardless of prompt manipulation. *Cons:* More complex; requires hooking into the skill execution path; may not be feasible depending on how Claude Code dispatches skills.

   - **Option C: Layered defence (A + B)** — Awareness filtering (Option A) as first line to reduce noise. Platform enforcement (Option B) as backstop for hard restriction. *Pros:* Defence in depth. *Cons:* Build cost.

   **Recommendation:** Option A first (solves both budget pressure and basic scoping), Option C eventually (adds hard enforcement for security-sensitive personas like Jen who must not be arm-twisted). Option A is buildable within the existing persona system; Option B requires deeper integration with Claude Code's hook/tool lifecycle.

   **Open design questions:**
   - Where does the whitelist live? Persona DB record, persona skill.md frontmatter, or a separate config file?
   - Granularity: skill-level (`otl:util:project-review`), category-level (`otl:orch:*`), or both with glob support?
   - Are there "always allowed" skills every persona gets (e.g., basic utilities)?
   - How does this interact with Claude Code's own command discovery vs our tmux-based skill injection?
   - For Option B: can `pre-tool-use` hooks see enough context to identify which skill is being invoked and block it?

### Skill/command budget and persona visibility (investigated 2026-02-28)

Investigation into skill visibility regression after Claude Code 2.1.50 → 2.1.62 upgrade. Key findings:

- **`disable-model-invocation: true`** in SKILL.md frontmatter prevents the skill from appearing in the system-reminder listing. The model cannot discover it exists — only explicit `/skill-name` invocation works. This was the root cause for the morning-briefing skill (now fixed by removing the flag).
- **Budget constants are unchanged** between versions: 2% of context window, hard-capped at 16,000 characters. All 110 commands always included (code never filters commands). At ~135 chars/entry × 111 items = ~15,000 chars, we're at **93% budget utilisation**. Adding more commands will force names-only mode (no descriptions).
- **Context pressure increased** between versions: system prompt grew ~29K chars, auto-memory feature (2.1.59) adds content at session start, persona injection adds ~4K+ chars of guardrails/skill/experience. Combined effect reduces effective model attention to the command listing.
- **Per-persona command filtering** is the recommended structural fix — not every persona needs all 53 BMAD commands or 22 orchestration commands. Filtering to ~15-20 relevant commands per persona would improve signal-to-noise and reduce budget pressure.
- **Relevant GitHub issues**: #28660 (O(n) skill injection per tool call), #16160 (lazy loading proposal), #27280 (help dialog truncation at 2% budget), #24991 (Opus 4.6 quality regression).

### Migrate commands to skills

Migrate existing Claude Code commands (.claude/commands/) to the newer skills format. Assess which commands should become skills, plan the migration path, and execute the transition. Consider backward compatibility, discoverability, and how this interacts with the persona skill assignment architecture above.

## Persona & Organisation

### Persona workshop series — group review and spec work

**BLOCKED — awaiting inter-agent communication (group chat).** Sam confirmed (2 March 2026) that the back-and-forth-between-sessions model is not sustainable for this volume of work. Group chat must be operational before this workshop series runs.

**Format:** Group sessions with Sam, Robbo, Paula (+ Shorty for infrastructure items). Paula facilitates.

**Inputs:**
- `docs/workshop/personna_alignment/01-persona-catalogue.md` — 11 personas catalogued with intent-encoding assessments
- `data/templates/persona-spec-template.md` — Persona Specification Template (v1.0)
- `docs/workshop/personna_alignment/03-ar-status-report.md` — AR Status Report with gap analysis, intent audit, and 12-item roadmap
- `data/briefs/personal-assistant-pip-brief.md` — Pip (personal assistant) brief for architectural review

**Workshop backlog (priority order per AR Status Report + new items):**

#### Spec upgrades (spec-depth inversion — highest leverage)

1. **Robbo** — Gates the entire build cycle. 63 agents. Weakest intent encoding at his responsibility level. Add: domain intent, definition of done for specs, review criteria, tradeoff hierarchies.
2. **Gavin** — PM automation on the roadmap requires deeper spec before granting autonomy. Add: domain intent, authority matrix, tradeoff hierarchies, quality definitions.
3. **Verner** — QA gatekeeper, never activated (0 agents). Must reach execution-persona spec quality before activation. Preserve three-way resolution model.

#### New persona creation

4. **Pip** (Personal Assistant) — Sam's PA. Calendar + email management via Google Workspace. Read-heavy, write-light autonomy. Requires: Robbo architectural review of brief, Shorty connector/credential evaluation, then Paula drafts skill file. See brief at `data/briefs/personal-assistant-pip-brief.md`.
5. **Leon** (Ops) — Operator confirmed needed. No ops capability currently exists. Exception triage, severity classification, auto-remediation boundaries.
6. **Mark** (Full-stack generalist) — Medium priority. Gap felt on cross-stack tasks. Assess whether workload warrants a dedicated persona.
7. **May** (Database) — Low priority. Currently absorbed by Con. Assess whether schema complexity warrants a specialist.

#### Support persona upgrades

8. **Ferret** — Add domain intent (what makes research "good enough"), tradeoff guidance (breadth vs depth), definition of done.
9. **Judy** — Add domain intent beyond editorial quality, strategic alignment (writing the right things, not just writing well).

#### Execution persona refinements (minor)

10. **Con, Al, Shorty** — Add explicit tradeoff hierarchies under pressure, formalise alignment feedback loops. Minor gaps — refinement, not restructuring.

#### Architecture decisions (Robbo's domain, reviewed in session)

11. **Formalise Support Layer** (Ferret, Judy) and **Systems sublayer** (Shorty) in the functional outline.
12. **Template rollout** — Confirm spec template as the standard for all future persona creation and review.
13. **Credential storage architecture** — Cross-cutting platform capability. Not just for Pip — future projects and personas will need credential management. Robbo scopes, Shorty evaluates infrastructure.
14. **Persona-scoped skill/command assignment** — Ties into the architecture TODO above (skill whitelist / platform enforcement). Review in context of the full persona portfolio.
