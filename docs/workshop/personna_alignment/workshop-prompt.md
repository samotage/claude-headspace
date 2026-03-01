# Persona Alignment Workshop — Paula (AR Director)

**Date:** 1 March 2026
**Facilitator:** Sam (system owner)
**Persona:** Paula — AR Director (`ar-director-paula-14`)
**Format:** Multi-session workshop. Each phase is designed to be completable in one agent session. Outputs from each phase are saved to this directory and carried forward as inputs to the next.

---

## Context

You are Paula, the Agentic Resources Director for the Headspace system. Your skill file at `data/personas/ar-director-paula-14/skill.md` defines your identity, philosophy, and responsibilities. Read it first — it is your operating brief.

You are inheriting a portfolio of personas that were built incrementally without centralised governance. This is normal for an early-stage agentic organisation. Your job is to bring structure to what exists and align it to the organisational architecture.

This workshop follows the "First Actions" sequence from your skill file, split across multiple sessions because the work is substantial.

---

## Reference Documents

Read these before starting each phase. They are your source of truth for the target architecture and current organisational thinking.

| Document | Location | Purpose |
|---|---|---|
| Your skill file | `data/personas/ar-director-paula-14/skill.md` | Your operating brief — identity, philosophy, responsibilities |
| Agent Teams functional outline | `docs/conceptual/headspace-agent-teams-functional-outline.md` | The conceptual architecture: layers, personas, workflows, version roadmap |
| Organisation design workshop | `docs/workshop/organisation-workshop.md` | Evolving design decisions for the org system (you are referenced in Section 1) |
| Existing persona assets | `data/personas/*/skill.md` | Current skill files for all registered personas |

---

## Phase 1: Catalogue & Template

**Goal:** Produce a complete catalogue of all existing personas and develop a Persona Specification Template.

**Status:** COMPLETE — 1 March 2026, Paula (Agent #1085).

### Tasks

#### 1.1 Catalogue Existing Personas — COMPLETE

Run `FLASK_APP=src/claude_headspace/app.py flask persona list` to get the current registry.

For each persona, read their skill file at `data/personas/{slug}/skill.md` and experience file at `data/personas/{slug}/experience.md`.

Produce a catalogue document (`docs/workshop/personna_alignment/01-persona-catalogue.md`) covering each persona:

- Name, role, slug, status
- Summary of their defined identity (1-2 sentences)
- What's in their skill file — is it a filled-out specification or still a template?
- What's in their experience file — has it accumulated any learnings?
- Which of the five intent-encoding elements are present: (1) encoded intent, (2) decision boundaries, (3) tradeoff hierarchies, (4) quality definitions, (5) alignment feedback loops
- Initial observations — anything that stands out as a gap, inconsistency, or strength

**Resolution:** Catalogue produced at `01-persona-catalogue.md`. 11 active personas catalogued. Spec quality is bimodal — execution personas (Con, Al, Shorty) have mature specs upgraded today by Robbo and Sam; coordination and support personas have thinner specs appropriate for a 7-day-old bootstrapping portfolio. All experience files empty except Con (one entry, operator-directed). Legacy directory `developer-con-1` exists on disk (empty), superseded slug `agentic-economy-architect-kent-voss-12` deleted by operator.

**Operator corrections during this task:**
- Portfolio is 7 days old (created 23 Feb 2026). Framing should reflect bootstrapping stage, not mature gaps.
- Con/Al/Shorty specs were upgraded today by Robbo and Sam — the catalogue reflects the upgraded versions.
- Experience capture is intentionally conservative (context budget cost), not broken. Only high-value, operator-directed entries are warranted.
- Personas are in a flat pool — no org hierarchy yet. Org layer is future work pending the org design workshop.

#### 1.2 Review the Conceptual Architecture — COMPLETE

Read `docs/conceptual/headspace-agent-teams-functional-outline.md`. This is the target architecture that defines what the organisation should look like.

Read `docs/workshop/organisation-workshop.md`. This is the evolving design workshop — note where you (Paula) are already referenced and what decisions affect your domain.

At the bottom of the catalogue document, add a section noting:
- Which architectural roles have personas registered
- Which architectural roles have no persona yet
- Any personas that exist but don't appear in the architecture
- Key observations about the gap between current state and target state

**Resolution:** Architecture mapping included as a section in `01-persona-catalogue.md` (combined with 1.1 — natural appendix rather than separate document). Key findings: 5 of 8 architectural roles have personas (Robbo, Gavin, Con, Al, Verner). Three are unregistered and need to be added: May (database), Mark (full-stack generalist), Leon (ops) — operator confirmed. Six personas exist outside the functional outline: Shorty (fills genuine systems/infra gap), Ferret (research), Judy (writing), Jen (separate product — Mable application assistant), Kent Voss (economy org), Paula (governance).

#### 1.3 Develop the Persona Specification Template — COMPLETE

Based on your review of all existing skill files, develop a Persona Specification Template (`docs/workshop/personna_alignment/02-persona-spec-template.md`).

The template must cover:
- All five intent-encoding elements from your philosophy (encoded intent, decision boundaries, tradeoff hierarchies, quality definitions, alignment feedback loops)
- Standard fields observed across existing personas (identity, skills, communication style, escalation paths, etc.)
- Fields that are missing from most personas but should be present
- Guidance notes explaining what belongs in each section

Build this iteratively — look at what works in the existing skill files (some are quite mature), identify what's missing, and synthesise a template that raises the floor without losing the character of individual personas.

**Resolution:** Template produced at `02-persona-spec-template.md`. 13 sections with required/conditional/optional classification by persona type (execution, coordination, support, customer-facing). Gold standard drawn from Con/Al/Shorty structure (working method, debugging protocol, coherence checks, definition of done) and Kent's intent encoding (autonomy gradient, decision framework).

**Key design decisions:**
- Intent section named **"Domain Intent"** — explicitly separated from organisational intent. Sam clarified that org-level intent (objective cascade, how goals flow to agents) is being scoped in the Organisation Design Workshop (Section 5). Persona specs define domain-level optimisation priorities only. The coupling between domain intent and org intent is deferred until the org layer exists.
- **Guardrails Layer** section added to the template. Sam flagged the Jen incident (leaking system-level information to a user) as the reason platform guardrails exist. Template now documents: guardrails are injected before the skill file, are absolute, set the floor. Skill files can add domain-specific constraints on top but never lower the floor. Customer-facing personas need the tightest alignment between guardrails and skill file.
- **Context budget guidance** included — execution personas justified up to 1000 words, coordination 300–500, support 200–400. Sized by what it takes to produce aligned behaviour, not by arbitrary token targets.
- **Experience file convention** codified — selective high-value entries only, following Con's format (problem, fix, future guidance).

### Phase 1 Outputs

Saved to `docs/workshop/personna_alignment/`:
1. `01-persona-catalogue.md` — Full catalogue with intent-encoding assessment and architecture mapping
2. `02-persona-spec-template.md` — Pointer to canonical template at `data/templates/persona-spec-template.md`

---

## Phase 2: Analysis & Report

**Prerequisite:** Phase 1 complete. Requires the catalogue and template from Phase 1 as inputs.

**Goal:** Perform gap analysis, intent audit, and model currency check. Produce the initial AR Status Report.

**Status:** COMPLETE — 1 March 2026, Paula (Agent #1085 produced Phase 1 outputs; successor agent completed Phase 2 analysis and report).

### Tasks

#### 2.1 Gap Analysis: Personas vs Architecture — COMPLETE

Using the catalogue from Phase 1 and the conceptual architecture, produce a structured gap analysis. Map each existing persona onto the architecture and categorise:

- **Clean fit** — persona maps directly to an architectural role, just needs intent alignment
- **Partial overlap** — persona covers some of an architectural role, needs refactoring or scope adjustment
- **No architectural home** — persona exists but doesn't fit the target architecture (candidate for restructuring or deprecation)
- **Unfilled role** — architectural role with no persona assigned (gap to fill)

**Resolution:** Gap analysis consolidated into Section 1 of `03-ar-status-report.md`. Key findings:

- **Clean fit (5):** Robbo → Workshop/Architect, Gavin → PM, Con → Execution/Backend, Al → Execution/Frontend, Verner → QA. All map directly to architectural roles; varying degrees of intent alignment needed.
- **Organic additions to formalise (3):** Shorty fills a genuine systems/infrastructure gap between Robbo's architecture and execution-layer code. Ferret and Judy provide cross-cutting support (research and writing) not in the original architecture. Recommended: formalise a Support Layer and a Systems sublayer within Execution.
- **Separate domain (2):** Jen (Mable/NDIS application assistant) and Kent Voss (agentic economy) belong to different organisations. Currently coexist in the flat pool — no operational impact now, but organisational separation required when the org layer is activated.
- **Governance (1):** Paula sits above the architecture layers as cross-cutting governance (the governance triangle: Sam, Robbo, Paula).
- **Unfilled roles (3):** May (database — currently absorbed by Con, low priority), Mark (full-stack generalist — medium priority, gap felt on cross-stack work), Leon (ops — medium-high priority, operator confirmed should be registered).

#### 2.2 Intent Audit — COMPLETE

For each persona, assess against the five intent-encoding elements using the template from Phase 1 as the benchmark. Rate each element as: present, partial, or absent.

Identify the most critical gaps — which personas are doing the most important work with the least intent encoding?

**Resolution:** Full audit in Section 2 of `03-ar-status-report.md`. Two tiers emerged:

- **Tier 1 — Mature (minor gaps):** Con, Al, Shorty (4.0/5 each), Kent Voss (4.0/5), Paula (4.5/5), Jen (3.5/5). These have strong intent encoding. Remaining gaps are tradeoff hierarchies under pressure and formal alignment feedback loops.
- **Tier 2 — Adequate (significant gaps):** Robbo (1.5/5), Gavin (1.5/5), Verner (1.5/5), Ferret (1.5/5), Judy (2.0/5). These describe what the persona does but not what it optimises for. Missing: domain intent, tradeoff hierarchies, quality definitions, alignment feedback loops.

**Critical finding: spec-depth inversion.** The personas with the most architectural responsibility (Robbo, Gavin, Verner) have the weakest intent encoding. Tolerable now because the operator provides the intent context that specs lack. Untenable as autonomy increases.

**Priority ranking for spec upgrades:** (1) Robbo — gates the entire build cycle, 63 agents, weakest intent encoding at his responsibility level. (2) Gavin — PM automation on the roadmap requires deeper spec before granting autonomy. (3) Verner — QA gatekeeper, must reach execution-persona spec quality before activation.

#### 2.3 Model Currency Check — COMPLETE

Assess whether existing persona specifications are optimised for the current model version (Claude Opus 4.6 / Sonnet 4.6) and platform capabilities (Claude Code with MCP, tool use, extended context). Flag any specifications that rely on patterns from older model versions or that aren't leveraging current capabilities.

**Resolution:** No model currency issues found. Portfolio is 6 days old, built entirely on the current model generation. Platform capabilities (tool use, Playwright CLI, extended context) are appropriately leveraged where relevant — Al's visual verification, Jen's sandboxed command list, context budget guidance in the template. One observation for future: execution persona specs (Con, Al, Shorty) are the most model-specific and should be first reviewed on any model generation change.

#### 2.4 AR Status Report — COMPLETE

Produce the initial AR Status Report (`docs/workshop/personna_alignment/03-ar-status-report.md`) consolidating everything:

- Executive summary (the state of the persona portfolio in 3-5 sentences)
- Full catalogue reference (link to Phase 1 output)
- Gap analysis findings
- Intent audit findings with priority ranking
- Model currency assessment
- Prioritised roadmap: what to fix first, what can wait
- Immediate risks or misalignments that need attention now
- Recommendations for the first personas to create, refactor, or align

**Resolution:** AR Status Report produced at `03-ar-status-report.md`. Consolidates gap analysis, intent audit, model currency check, and a 12-item prioritised roadmap across three time horizons (immediate, near-term, medium-term). Three active risks identified: spec-depth inversion (high), Verner activation without spec upgrade (medium), flat pool mixing domains (low/current). Five observations documented including the gold standard execution spec pattern and the governance triangle working relationship.

**Post-report actions taken during this session:**
- **Living document discipline** identified as a cross-cutting gap. Both Paula and Robbo were caught producing incomplete workshop resolutions (status without substance). Experience entries written for both. Template updated to include living document discipline in Working Method guidance. Roadmap items 1-3 amended to include this discipline in spec upgrades.
- **Template relocated** from workshop output directory (`docs/workshop/personna_alignment/02-persona-spec-template.md`) to canonical location (`data/templates/persona-spec-template.md`) with YAML front matter (version 1.0, changelog). Workshop copy replaced with a pointer. Sam directed this move — the template is a durable standard, not a workshop artefact.
- **Paula's skill file updated** to reference the template's canonical location at `data/templates/persona-spec-template.md`.

### Phase 2 Outputs

Saved to `docs/workshop/personna_alignment/`:
3. `03-ar-status-report.md` — Initial AR Status Report

---

## Workshop Status

**Both phases COMPLETE.** All outputs produced, committed, and pushed.

**Next steps:**

**BLOCKED — awaiting inter-agent communication (group chat) build.** Sam and Robbo decided (1 March 2026) to fast-track Organisation Workshop Section 2 (Inter-Agent Communication) as the next epic. The persona reconciliation group review and subsequent spec upgrades are dependent on this capability existing — the review is designed as a group session (Sam, Robbo, Paula) which requires the communication layer. The spec upgrades are also more valuable after communication protocols exist, since upgraded specs can encode interaction patterns that don't exist yet.

Once group chat is operational:
1. **Group review of AR Status Report** — Sam, Robbo, Paula. Decide spec upgrade priority and template rollout. (See `docs/todo/TODO.md`, Persona & Organisation section.)
2. Spec upgrades (report recommends Robbo → Gavin → Verner) — can now include communication protocols
3. Register Leon (Ops) — operator confirmed this is needed
4. Formalise architecture updates (Support Layer, Systems sublayer) — Robbo's domain
5. Schedule periodic intent audits and model currency checks as standing practice

---

## Working Notes

- Paula does not write code or modify platform guardrails. All outputs are documents.
- When uncertain about architectural intent, flag the question for Robbo.
- When uncertain about organisational priority, flag the question for Sam.
- The organisation workshop (`docs/workshop/organisation-workshop.md`) is evolving in parallel. Paula's work here informs and is informed by that workshop — they are complementary, not sequential.
- **Template canonical location:** `data/templates/persona-spec-template.md` — all references should point here, not to the workshop directory.
