# Persona Catalogue — AR Director Initial Assessment

**Date:** 1 March 2026
**Author:** Paula (AR Director)
**Source:** `flask persona list` registry + `data/personas/{slug}/skill.md` and `experience.md` files
**Phase:** 1 of Persona Alignment Workshop

---

## Summary

11 active personas registered. 12 skill files on disk (one legacy directory `developer-con-1` with no skill file, one superseded `agentic-economy-architect-kent-voss-12` — deleted by operator). All experience logs are empty except Con, who has one entry. The portfolio spans development, architecture, QA, PM, research, writing, governance, and a separate economic domain.

Skill file quality varies but is actively improving. The execution-layer personas (Con, Al, Shorty) were upgraded to mature, deeply specified skill files on 1 March 2026 (today) — working methods, debugging protocols, coherence checks, and definitions of done. The workshop/coordination personas (Robbo, Gavin, Verner) have adequate but thinner specs — appropriate for their current usage in a 7-day-old portfolio. Support personas (Ferret, Judy) have well-characterised identities. One persona (Jen) is a separate application assistant for a different product domain.

**Important context:** This entire portfolio is 7 days old. Personas were initially created on 23 February 2026. The system is bootstrapping — all of this is new, and the focus has rightly been on getting functional personas operational before optimising specifications. Personas currently operate in a flat pool model (no organisational hierarchy) — organisation implementation is a future decision pending the org design workshop (Sections 1–9). Multi-org context for Jen and Kent Voss is similarly deferred until the org layer exists.

---

## Persona Catalogue

### 1. Robbo — Architect

| Field | Value |
|-------|-------|
| **Slug** | `architect-robbo-3` |
| **Role** | architect |
| **Status** | Active (63 agents) |
| **Identity** | Overall architect and operator's thinking partner. Turns messy ideas into clear specs. Reviews deliverables post-implementation. Does not write code — output is always documents. |
| **Skill file quality** | Adequate. Covers identity, skills, preferences, communication style. No working method, no debugging protocol, no definition of done. |
| **Experience file** | Empty — no entries logged despite 63 agent sessions. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Partial | Identity describes what he does but not what he optimises for. No explicit priority ordering. |
| Decision boundaries | Partial | "Escalate to operator when architectural direction is genuinely ambiguous" — one boundary. No detailed authority matrix. |
| Tradeoff hierarchies | Absent | Preferences listed but no guidance on what wins when they conflict. |
| Quality definitions | Absent | No definition of done. No criteria for what "a good spec" looks like. |
| Alignment feedback loops | Absent | No mechanism to detect when Robbo's output is drifting from organisational intent. |

**Observations:**
- Most-used persona (63 agents). Spec is adequate for current usage (workshop partner, document producer) but will need depth as the organisation layer matures and Robbo takes on formal review responsibilities in the build cycle.
- Communication style includes "quirky humour" and "may call you Birko" — good personality encoding, shows the operator values character.
- No post-implementation review criteria defined despite that being a stated responsibility.

---

### 2. Gavin — PM

| Field | Value |
|-------|-------|
| **Slug** | `pm-gavin-4` |
| **Role** | pm |
| **Status** | Active (10 agents) |
| **Identity** | Project manager. Receives specs from Robbo, decomposes into tasks, manages sequencing and dependencies. Logistics and orchestration, not creative problem-solving. |
| **Skill file quality** | Adequate. Clear identity, good preferences, communication style. No working method, no definition of done. |
| **Experience file** | Empty. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Partial | Clear about what he does (decompose, sequence, track) but not what he optimises for. "Track outputs not activity" is a hint but not a full intent statement. |
| Decision boundaries | Partial | "Do not resolve architectural questions — route them to Robbo." One clear boundary. No authority matrix for what Gavin can decide alone. |
| Tradeoff hierarchies | Absent | No guidance on competing priorities (e.g., speed vs quality, parallel work vs dependency safety). |
| Quality definitions | Absent | No criteria for what a good task decomposition looks like. |
| Alignment feedback loops | Absent | No mechanism to detect when task assignments are drifting from spec intent. |

**Observations:**
- Gavin's role will become significantly more important as the organisation matures (v2/v3 PM automation in the roadmap). Current spec is insufficient for that level of autonomy.
- "Every task should be completable in one agent session where possible" — good practical constraint, well-suited to the platform's context window reality.

---

### 3. Con — Backend

| Field | Value |
|-------|-------|
| **Slug** | `backend-con-5` |
| **Role** | backend |
| **Status** | Active (56 agents) |
| **Identity** | Backend systems specialist. Builds server-side logic, APIs, data models, migrations. Favours explicit, defensive code. Full-stack capable but backend-focused. |
| **Skill file quality** | **Mature.** Comprehensive: identity, skills, design principles, working method (5-step), debugging protocol (7-step), data coherence section, definition of done (7-item checklist), escalation paths, communication style. Best-in-class spec in the portfolio. |
| **Experience file** | **One entry** — TmuxWatchdog restart blindness fix (2026-02-27). Detailed, actionable, includes root cause and "if this breaks again" guidance. Demonstrates what a good experience entry looks like. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Present | Data integrity is clearly the north star. "The backend is the source of truth." State consistency, relational integrity, and downstream impact awareness are all encoded. |
| Decision boundaries | Present | Clear escalation paths (Gavin for unclear tasks, Gavin → Robbo for architectural ambiguity, coordinate with Al for cross-stack). Debugging protocol has an explicit "escalate after three failed hypotheses" threshold. |
| Tradeoff hierarchies | Partial | Design principles establish preferences (explicit > clever, constraints > validation) but no explicit guidance when principles conflict. |
| Quality definitions | Present | 7-item definition of done checklist. Clear and actionable. |
| Alignment feedback loops | Partial | "Downstream Impact Awareness" section asks three verification questions before shipping. Not a formal feedback loop but functionally serves as one. |

**Observations:**
- Gold standard for persona specification in this portfolio. Template development should draw heavily from this.
- The experience entry format is exactly right — problem, fix, future guidance.
- Legacy directory `developer-con-1` exists on disk (empty, no skill file). Previous incarnation before role-based slug convention.

---

### 4. Al — Frontend

| Field | Value |
|-------|-------|
| **Slug** | `frontend-al-6` |
| **Role** | frontend |
| **Status** | Active (41 agents) |
| **Identity** | Frontend expert. Builds UI, component architectures, interactive elements. Strong on accessibility and progressive enhancement. Full-stack capable but frontend-focused. |
| **Skill file quality** | **Mature.** Mirrors Con's structure: identity, skills, design principles, working method (5-step), debugging protocol (7-step), UI coherence section, definition of done (7-item checklist), escalation paths. |
| **Experience file** | Empty. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Present | UI coherence and truthful storytelling are the north star. "The Human Narrative Test" — look at the screen as a human, does it make sense? Strong intent encoding. |
| Decision boundaries | Present | Same escalation structure as Con. Debugging protocol has "escalate after three failed hypotheses." |
| Tradeoff hierarchies | Partial | Design principles establish ordering (accessibility > style > behaviour, semantic HTML > CSS > JS) but no guidance when principles conflict with deadlines or scope. |
| Quality definitions | Present | 7-item definition of done checklist. Includes visual verification requirement. |
| Alignment feedback loops | Partial | "Multi-Perspective Review" (the glance + the detail) serves as a pre-shipping feedback check. |

**Observations:**
- Very strong spec, clearly developed alongside Con's. The two execution personas share a structural template which is excellent for consistency.
- Al and Con both have Playwright-based visual verification baked in — this is a platform-aware design decision that should be preserved in the template.
- Empty experience file despite 41 agent sessions is a gap — not in the spec, but in the operational practice of experience capture.

---

### 5. Verner — QA Lead

| Field | Value |
|-------|-------|
| **Slug** | `qa-verner-7` |
| **Role** | qa |
| **Status** | Active (0 agents) |
| **Identity** | QA lead. Writes tests from specs, executes against implementations, resolves discrepancies pragmatically. Cross-cutting visibility across all domains. |
| **Skill file quality** | Adequate. Clear identity, good skills list, communication style. No working method, no definition of done, no debugging protocol. |
| **Experience file** | Empty. Never activated. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Partial | Pragmatic discrepancy resolution is implied but not explicitly stated as the optimisation target. "Test behaviour not implementation" is a design principle, not a full intent statement. |
| Decision boundaries | Partial | "Escalate architectural ambiguity to Robbo" and the three-way resolution model (test wrong → fix test; implementation wrong → send back; architecturally ambiguous → escalate). Good but incomplete. |
| Tradeoff hierarchies | Absent | No guidance on competing priorities (e.g., coverage breadth vs depth, speed of QA pass vs thoroughness). |
| Quality definitions | Absent | No definition of done. No criteria for what constitutes sufficient test coverage. |
| Alignment feedback loops | Absent | No mechanism to detect when QA standards are drifting. |

**Observations:**
- Never activated (0 agents). Spec is intentionally held back — Verner's role is more aligned with the organisational layer being built now.
- Spec quality is below Con/Al standard. Given QA's gatekeeper role in the build cycle, Verner needs a spec upgrade before activation.
- The three-way resolution model (test wrong / implementation wrong / spec ambiguous) is architecturally sound — preserve this in any rework.

---

### 6. Judy — Tech Writer

| Field | Value |
|-------|-------|
| **Slug** | `tech-writer-judy-8` |
| **Role** | tech-writer |
| **Status** | Active (9 agents) |
| **Identity** | Technical writer. Translates complex technical concepts into clear, engaging content for general audiences. Owns all written output: blog posts, docs, READMEs, release notes, email copy. Resourceful — works from any brief quality. |
| **Skill file quality** | Good. Strong identity, clear skills, well-defined communication style with calibratable sass level. References external writing law (`.claude/rules/writing.mdc`). No working method or definition of done. |
| **Experience file** | Empty. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Partial | "Owns all written output aimed at external audiences" defines scope but not what she optimises for. No explicit quality hierarchy (accuracy vs engagement vs speed). |
| Decision boundaries | Partial | "Currently operates with QA review from the operator; earns more autonomy over time" — autonomy gradient is explicit, which is good. "Takes the lead on audience-facing editorial decisions" — authority in her domain. |
| Tradeoff hierarchies | Absent | No guidance on competing demands (e.g., speed vs polish, broad coverage vs deep analysis). |
| Quality definitions | Partial | Writing law file (`.claude/rules/writing.mdc`) serves as a quality gate for output. No broader definition of done. |
| Alignment feedback loops | Absent | No mechanism to assess whether written output is achieving its purpose. |

**Observations:**
- The sass calibration (0-100, default 75) is a sophisticated personality encoding. Good design pattern.
- External writing law reference is architecturally clean — separates persona identity from editorial standards.
- Judy is a support persona, not part of the core build cycle. Her spec is appropriate for her role.

---

### 7. Shorty — Tech Architect

| Field | Value |
|-------|-------|
| **Slug** | `tech-arch-shorty-9` |
| **Role** | tech-arch |
| **Status** | Active (19 agents) |
| **Identity** | Technical architect and systems generalist. Knows how systems work under the hood — stack traces, protocols, infrastructure, CI/CD. Hands-on: writes scripts, configs, Dockerfiles, infrastructure code. Where Robbo designs what to build, Shorty understands how the underlying systems make it happen. |
| **Skill file quality** | **Mature.** Same comprehensive structure as Con/Al: identity, skills, design principles, working method (5-step), debugging protocol (7-step), system coherence section, definition of done (6-item checklist), escalation paths. |
| **Experience file** | Empty (just the template header, no entries). |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Present | "Infrastructure is a stack of agreements. Every layer assumes things about the layers above and below it. Shorty's job is to make sure those assumptions hold." Clear intent encoding. |
| Decision boundaries | Present | Escalation paths defined. Working method includes blast radius assessment before any change. |
| Tradeoff hierarchies | Partial | "Prefers the simplest infrastructure that solves the problem" — one clear preference. No explicit priority ordering when simplicity conflicts with other concerns. |
| Quality definitions | Present | 6-item definition of done checklist. Includes the "Would This Survive a Restart" test — excellent systems-specific quality gate. |
| Alignment feedback loops | Partial | Configuration consistency checks and infrastructure-application agreement verification serve as functional feedback loops. |

**Observations:**
- Third mature spec in the portfolio, following the Con/Al template. Excellent systems-specific adaptations (restart survival test, configuration consistency checks).
- Role distinction from Robbo is clearly articulated ("Robbo designs what to build, Shorty understands how the systems make it happen") — important for avoiding overlap.
- Not in the original functional outline. Organic addition that fills a genuine gap between architecture (Robbo) and execution (Con/Al).

---

### 8. Ferret — Researcher

| Field | Value |
|-------|-------|
| **Slug** | `researcher-ferret-10` |
| **Role** | researcher |
| **Status** | Active (9 agents) |
| **Identity** | Research and intelligence specialist. Goes out into the internet, digs through noise, brings back actionable findings. Hunts technical solutions, scouts products, sniffs out opportunities. Anyone on the team can dispatch him. |
| **Skill file quality** | Good. Strong identity with distinctive voice. Clear skills including BS detection and source quality intuition. Communication style well-defined. No working method, no definition of done. |
| **Experience file** | Empty. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Partial | "Finds relevant products, services, libraries, and platforms that solve a stated need" — functional description but not an intent hierarchy. Does not define what "useful research" optimises for. |
| Decision boundaries | Partial | "Knows when to stop — recognises when a trail has gone cold and says so rather than padding results." This is a boundary but informally expressed. No authority matrix. |
| Tradeoff hierarchies | Absent | No guidance on breadth vs depth, speed vs thoroughness, or how to prioritise between multiple research threads. |
| Quality definitions | Absent | No definition of done. No criteria for what constitutes sufficient research. |
| Alignment feedback loops | Absent | No mechanism to assess whether research output was actually useful to the requesting agent. |

**Observations:**
- Not in the original functional outline. Organic addition filling the research gap.
- "Anyone on the team can dispatch him" — unique dispatch model, different from hierarchy-based delegation. Worth preserving.
- "Experienced BS detection" with specific examples is good defensive encoding.
- Strong personality voice ("keen nose," "breathless when onto something good") — demonstrates the operator values character differentiation.

---

### 9. Jen — Assistant

| Field | Value |
|-------|-------|
| **Slug** | `assistant-jen-11` |
| **Role** | assistant |
| **Status** | Active (34 agents) |
| **Identity** | Application assistant for Mable (NDIS support worker job application platform). Helps non-technical support workers apply for jobs on their iPhones. NOT a developer tool. |
| **Skill file quality** | **Comprehensive but domain-specific.** Extremely detailed: conversation flow (10-step), allowed commands (sandboxed to `maybelle` CLI), forbidden actions (7 hard constraints), edge cases table, availability negotiation protocol. This is effectively a full application specification, not a team persona. |
| **Experience file** | Empty. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Present | Clear: help the support worker apply for jobs. Every design decision serves this single purpose. |
| Decision boundaries | Present | Extremely well-defined. 7 forbidden actions. Sandboxed command list. Explicit approval requirement before submission. |
| Tradeoff hierarchies | Partial | Worker satisfaction > efficiency is implied. Edge cases table provides specific tradeoff guidance per scenario. |
| Quality definitions | Partial | Implicit in the conversation flow — quality means the worker is happy and the application is submitted with approval. No formal checklist. |
| Alignment feedback loops | Absent | No mechanism to assess whether Jen's applications are actually effective for workers. |

**Observations:**
- **Fundamentally different from all other personas.** Jen is a customer-facing application assistant, not a development team member. She operates in a completely separate domain (NDIS support work) with her own tool sandbox.
- Highest intent-encoding in the portfolio despite not following the team persona pattern — because her spec was designed as an application specification with explicit constraints, which is exactly what intent engineering looks like in practice.
- The platform guardrails document is injected as part of her skill injection — she's the public-facing persona that needs the strongest safety rails.
- 34 agent sessions — second-most-used persona after Robbo. This is a production application.
- Does not fit the Headspace development team architecture. Belongs to a separate organisation (or a separate product entirely).

---

### 10. Kent Voss — Agentic Economy Architect

| Field | Value |
|-------|-------|
| **Slug** | `ag-econ-arch-kent-voss-13` |
| **Role** | ag-econ-arch |
| **Status** | Active (5 agents) |
| **Identity** | Agentic economy architect. Designs self-sustaining economic loops where agents generate value with minimal human intervention. Operates at the intersection of autonomous AI systems and onchain financial infrastructure. Thinks in flows, not holdings. |
| **Skill file quality** | **Strong.** Comprehensive: identity, skills, autonomy & guardrails section, decision framework (5-step), communication style, anti-patterns ("What Kent Is NOT"), key knowledge domains. |
| **Experience file** | Empty. |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Present | "Designing self-sustaining economic loops." "Think in value flows and feedback loops." "Build repeatable economic machines, not one-off bets." Clear and specific. |
| Decision boundaries | Present | Autonomy section is explicit: "Default mode: propose and recommend. Nothing that moves money executes without explicit sign-off." Regulatory flagging requirement. Risk budget separation (exploration vs treasury). |
| Tradeoff hierarchies | Present | Decision framework provides explicit ordering: value flow → cost floor → edge → failure mode → repeatability. "Kill ideas early when they don't pencil out." |
| Quality definitions | Partial | Decision framework serves as quality criteria for strategies. No formal definition of done for deliverables. |
| Alignment feedback loops | Partial | Risk budgeting and autonomy gradient ("upgradeable as trust builds through demonstrated competence and logged experience") imply a feedback mechanism but don't define it. |

**Observations:**
- Best intent-encoding among the non-Jen personas. The autonomy gradient and decision framework are model patterns for the spec template.
- "What Kent Is NOT" section is an excellent anti-pattern. Defining boundaries by exclusion prevents scope drift.
- Kent belongs to the economy organisation, not the dev team. The org workshop (Section 8) references Kent's domain as validation for multi-org support.
- Superseded slug `agentic-economy-architect-kent-voss-12` has been deleted by operator.

---

### 11. Paula — AR Director

| Field | Value |
|-------|-------|
| **Slug** | `ar-director-paula-14` |
| **Role** | ar-director |
| **Status** | Active (1 agent — this session) |
| **Identity** | Agentic Resources Director. Manages the persona portfolio, organisational design, intent alignment, and model currency. Reports to Sam, works alongside Robbo. Does not write code — output is specifications, reviews, reports, recommendations. |
| **Skill file quality** | **Comprehensive.** Detailed: identity, philosophy (intent engineering), 5 responsibilities, persona specification standards, decision authority matrix, anti-patterns, key relationships, communication style, first actions sequence. The most thoroughly specified persona in the portfolio for governance and organisational design. |
| **Experience file** | Empty (first session). |

**Intent-Encoding Assessment:**

| Element | Status | Notes |
|---------|--------|-------|
| Encoded intent | Present | "Intent engineering — the discipline of making organisational purpose machine-readable and machine-actionable." The five intent-encoding elements are defined as the framework all personas should be assessed against. |
| Decision boundaries | Present | Full decision authority matrix covering 7 decision types with explicit authority levels (proposes, executes, acts autonomously). Emergency deactivation authority. |
| Tradeoff hierarchies | Present | Implicit in the philosophy section: intent alignment > task completion. Explicit in the anti-patterns: what to avoid prioritises correctly. |
| Quality definitions | Partial | Persona Specification Standards are defined as a responsibility but not yet formalised (that's this workshop's output). |
| Alignment feedback loops | Present | Regular intent alignment auditing is a defined responsibility. Transcript review for misalignment signals is specified. |

**Observations:**
- Self-referentially, this is the most intent-aligned persona in the portfolio — because it was designed with the intent-engineering framework already in mind.
- The governance triangle (Sam, Robbo, Paula) is well-defined. Relationship boundaries between architect and AR director are clear.
- First actions sequence matches this workshop — the spec and the operational plan are aligned.

---

## Architecture Mapping

### Personas with Architectural Roles (from Functional Outline)

| Architecture Layer | Role | Persona | Status |
|-------------------|------|---------|--------|
| Workshop Layer | Architect | Robbo (`architect-robbo-3`) | Active, 63 agents |
| PM Layer | Project Manager | Gavin (`pm-gavin-4`) | Active, 10 agents |
| Execution Layer | Backend | Con (`backend-con-5`) | Active, 56 agents |
| Execution Layer | Frontend | Al (`frontend-al-6`) | Active, 41 agents |
| Execution Layer | Database | **May — NOT REGISTERED** | Gap |
| Execution Layer | Full-stack generalist | **Mark — NOT REGISTERED** | Gap |
| QA Layer | QA Lead | Verner (`qa-verner-7`) | Active, 0 agents (never used) |
| Ops Layer | Operations | **Leon — NOT REGISTERED** | Gap |

### Personas Without Architectural Home

These personas exist in the registry but are not defined in the Agent Teams functional outline:

| Persona | Role | Assessment |
|---------|------|------------|
| **Shorty** | tech-arch | Fills a genuine gap between Robbo (architecture) and execution. Systems/infra layer not in the original outline but clearly needed. Candidate for formalisation in the architecture. |
| **Ferret** | researcher | Research function not in the original outline. Cross-cutting support role. Useful but architecturally unplaced. |
| **Judy** | tech-writer | Content/documentation function not in the original outline. Support role. Architecturally unplaced. |
| **Jen** | assistant | Completely separate domain (NDIS job applications). Not a development team member. Belongs to a different organisation. |
| **Kent Voss** | ag-econ-arch | Economy organisation architect. Referenced in the functional outline as multi-org validation (Section 8). Belongs to a separate organisation. |
| **Paula** | ar-director | Governance/AR function. Added after the functional outline was written. Cross-cutting governance role that sits above the architecture layers. |

### Unregistered Architectural Roles

Three personas defined in the functional outline have no registered persona:

1. **May (Database)** — Database administrator. Schema design, migration safety, query optimisation. Pools: database, backend. **The database specialisation is currently absorbed by Con**, who covers "Database migrations and schema design" in his skill file. The question is whether a separate persona is warranted or whether Con's current scope is sufficient.

2. **Mark (Full-stack generalist)** — Cross-cutting integration work. Pools: backend, frontend, integration. **No current persona covers the generalist/integration role.** When cross-stack work arises, it's assigned to Con or Al depending on the dominant domain.

3. **Leon (Ops)** — Operations lead. Monitors deployed projects, triages exceptions, drives auto-remediation. Pools: ops + cross-cutting. **No ops capability exists in the current portfolio.** This is a v5 roadmap item per the functional outline, but the operator has indicated Leon should be registered.

### Key Observations: Current State vs Target State

1. **The core build cycle is 60% staffed.** Workshop (Robbo) and Execution (Con, Al) are strong. PM (Gavin) is adequate but needs spec upgrades. QA (Verner) exists but is dormant. Three execution roles and the ops role are missing.

2. **Organic growth has produced useful personas not in the architecture.** Shorty, Ferret, and Judy fill real gaps. The architecture should evolve to accommodate them rather than treating them as anomalies.

3. **Two personas operate in separate domains.** Jen (Mable application assistant) and Kent Voss (agentic economy) are not dev team members. They currently exist in the same flat persona pool. Organisational separation is a future concern — when the org layer is implemented, they're natural candidates for separate org contexts. For now, the pool model is correct.

4. **Spec quality is bimodal.** The execution personas (Con, Al, Shorty) have mature, deeply specified skill files. Everyone else has adequate-to-thin specs. The gap is largest for the personas with the most architectural responsibility (Robbo, Gavin, Verner).

5. **Experience capture is intentionally conservative.** Only Con has a single experience entry, created when the operator explicitly instructed him to remember something. This is deliberate — experience entries consume context on every agent session, so over-populating them bloats the context window and degrades agent performance. The right model is selective, high-value entries (as Con's TmuxWatchdog entry demonstrates), not automatic logging. The current approach is correct for a bootstrapping phase.

6. **Spec maturity follows usage patterns, not architectural importance.** The most-used execution personas (Con, Al, Shorty) were upgraded first — today — because they're the ones doing the most work and generating the most observable behaviour. The coordination personas (Robbo, Gavin, Verner) have thinner specs, which is appropriate for a 7-day-old portfolio that's still bootstrapping. As the organisation layer matures and these personas take on more autonomous coordination, their specs will need to grow accordingly. The functional outline's v2/v3 PM automation milestones are the natural trigger for upgrading Gavin's spec depth.

---

*This catalogue is Phase 1, Task 1.1 + 1.2 output. It serves as input to the Persona Specification Template (Task 1.3) and the Phase 2 analysis.*
