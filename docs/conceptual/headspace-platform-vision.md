# Claude Headspace — Agentic Workforce Platform Vision

**Date:** 16 February 2026
**Author:** Sam Sabey / OtageLabs
**Status:** Vision Document — Frames the strategic direction for all Headspace org modules
**Relationship:** This document sits above individual BMAD root artefacts. Each organisation module (Development, Marketing, Production, etc.) has its own BMAD root artefact that implements a subset of this vision.

---

## 1. Vision Statement

Claude Headspace evolves from a developer tool managing Claude Code sessions into a general-purpose agentic workforce platform. The platform supports the definition of personas (named identities with skills), the organisation of those personas into hierarchical teams, and the execution of workflows that match the operational patterns of different business functions.

The operator runs multiple organisations — each with its own structure, workflow patterns, and objectives — all managed through a single Headspace instance. Personas are modelled as people: they have identities, skills that grow over time, and can work across multiple organisations, just as real consultants and contractors do.

---

## 2. Core Abstraction: Real-World Organisational Modelling

The platform models the real world. This is a deliberate design choice — modelling real-world organisational patterns produces better software outcomes because the abstractions are intuitive, well-understood, and battle-tested by centuries of human organisational practice.

### 2.1 Personas (People)

The atomic unit. A persona is a named identity with persistent, evolving skills.

- Personas exist independently of any organisation
- A persona can work in multiple organisations (just as a contractor or consultant does)
- Skills grow through work — learned experience accumulates over time
- A persona has a core identity (stable) and a skill file (evolving)

### 2.2 Roles (Functions)

The function a persona performs within an organisation. Roles are organisation-scoped — the same persona may play different roles in different orgs.

Known role types (extensible):
- **Workshop** — collaborative thinking partner, produces documents not code
- **PM** — decomposes plans into tasks, manages sequencing and assignment
- **Execution** — builds things (code, content, assets, reports)
- **QA** — validates deliverables against specifications
- **Ops** — monitors runtime, triages issues, drives remediation
- **Strategy** — (future) defines objectives, evaluates performance, adjusts direction

### 2.3 Organisations (Teams & Hierarchies)

A structured grouping of personas into a hierarchy with defined workflows, escalation paths, and operational patterns.

- An organisation is a loadable, swappable configuration
- Each org defines: which personas, what roles, what hierarchy, what workflow pattern
- Multiple orgs can run concurrently
- Personas can be shared across orgs (subject to availability/concurrency limits)

### 2.4 Workflow Patterns

Different organisations operate with different workflow patterns. The platform must support multiple patterns, not impose a single one.

| Pattern | Description | Example Org |
|---------|-------------|-------------|
| **Pipeline** | Linear progression through stages: spec → build → test → review → ship | Development |
| **Iterative Loop** | Produce → deploy → measure → adjust → produce again. Short cycles, feedback-driven. | Marketing & Sales |
| **Continuous Production** | Ongoing automated workflows producing recurring outputs. Monitor, optimise, scale. | Production (Services as Software, Agentic Arbitrage) |
| **Engagement** | Client-facing delivery with discovery, proposal, execution, handover phases. | Consulting / Delivery |

---

## 3. Organisation Instances

### 3.1 Development Organisation

**Status:** BMAD root artefact complete — ready for epic decomposition.

**Purpose:** Builds software. Takes messy ideas through specification, decomposition, implementation, testing, review, and deployment.

**Workflow pattern:** Pipeline.

**Team:** Robbo (architect/workshop), Gavin (PM), Con (backend), Al (frontend), May (database), Mark (full-stack), Verner (QA), Leon (ops).

**Reference:** `headspace-agent-teams-functional-outline.md`

### 3.2 Marketing & Sales Organisation

**Status:** Not yet defined — next candidate for workshop.

**Purpose:** Produces content, runs campaigns, measures performance, iterates. Drives revenue through messaging, blog posts, social media, SEO, email campaigns, landing pages.

**Workflow pattern:** Iterative Loop.

**Likely roles needed:**
- Workshop partner (could be Robbo, or a marketing-domain specialist)
- Content strategist / campaign manager (the "Gavin" equivalent — plans what to produce and when)
- Copywriter(s) — produces written content
- Designer — visual assets, landing page layouts
- SEO / analytics specialist — measures performance, feeds data back into the loop
- Ops equivalent — monitors campaign metrics, flags underperformance, triggers adjustments

**Key difference from dev org:** The feedback loop is continuous and data-driven. Campaign performance metrics feed directly back into what the team produces next. There's no single "ship it" moment — it's ongoing optimisation toward an objective.

**Open questions:**
- Which personas from the dev org work here too? (Robbo for strategy? Al for landing pages? Leon for monitoring?)
- What new personas are needed?
- What does the "measure" step look like technically? (Analytics ingestion, LLM analysis of performance data)
- How does content review/approval work? (Similar to QA, or different?)

### 3.3 Production Organisation (Services as Software / Agentic Arbitrage)

**Status:** Conceptual — informed by agentic arbitrage research.

**Purpose:** Runs ongoing automated workflows that produce recurring revenue. Agents performing services as software — automated reports, data processing, monitoring, client deliverables.

**Workflow pattern:** Continuous Production.

**Likely roles needed:**
- Operations manager — oversees running services
- Quality monitor — validates output quality on ongoing basis
- Optimiser — improves efficiency, reduces costs, increases margins
- Client liaison — (if client-facing) manages relationships and requirements

**Key difference from dev org:** This org doesn't build and ship — it runs and maintains. The objective is uptime, quality, and margin, not feature delivery. Closer to a factory floor than a dev shop.

### 3.4 Consulting / Delivery Organisation

**Status:** Conceptual.

**Purpose:** Client-facing project delivery. Discovery, scoping, proposal, execution, handover.

**Workflow pattern:** Engagement.

**Likely roles needed:**
- Account manager / client liaison
- Technical lead (could be Robbo)
- Execution team (drawn from dev org personas)
- QA / delivery assurance

**Key difference from dev org:** External stakeholders, different communication patterns, proposal/scoping phases that don't exist in internal dev work.

---

## 4. Platform Architecture Implications

### 4.1 Persona Registry

A central registry of all personas, independent of any org. Each persona has:
- Identity (name, core description)
- Skill file(s) — potentially org-specific skill extensions
- Availability status (which org/agent they're currently assigned to)
- Experience log (cross-org — learnings accumulate regardless of where the work happened)

### 4.2 Organisation Definitions

Each org is a configuration that references personas from the registry and defines:
- Hierarchy (who reports to whom, escalation paths)
- Workflow pattern (pipeline, loop, continuous, engagement)
- Roles (which personas play which roles in this org)
- Pools (skill-domain groupings within this org)
- Modes (workshop, execution — as defined in the dev org spec)

### 4.3 Cross-Org Persona Sharing

A persona working in the dev org's backend pool might also be available in the production org's maintenance pool. Concurrency constraints still apply — a persona can only be active in one agent at a time, regardless of which org spawned it.

This creates natural resource contention, which is realistic. If Con is busy fixing a production issue for Leon, he's not available for Gavin's sprint tasks. The operator (or a future meta-PM) manages this prioritisation.

### 4.4 Org-Specific Skill Extensions

A persona's core skill file is global, but orgs can extend it. Con's global skill file says "backend systems specialist." The dev org extension might add "familiar with RAGlue codebase." The production org extension might add "experienced with Solarcam API error patterns."

### 4.5 Workflow Engine

The platform needs a workflow engine that supports different patterns. The dev org's pipeline is one workflow definition. The marketing org's iterative loop is another. Both run on the same engine but with different step definitions, transition rules, and feedback mechanisms.

This may connect to the FlowRun subsystem (Flow + Steps model) already in the RAGlue stack — potentially a shared infrastructure component.

---

## 5. Strategic Direction

### Phase 1: Development Organisation (Current)
Build the persona system, workshop mode, and team execution for software development. This is the BMAD root artefact already prepared. All foundational infrastructure (persona registry, org definitions, skill files, modes) gets built here because the dev org is the first customer.

### Phase 2: Marketing & Sales Organisation
Stand up the second org instance. This validates that the abstractions are general-purpose, not dev-specific. The iterative loop workflow pattern forces the workflow engine to support non-linear patterns. OtageLabs website refresh, content production, and campaign execution are the immediate use cases.

### Phase 3: Production Organisation
Stand up automated service delivery. Agentic arbitrage loops, recurring report generation, services as software. This validates the continuous production workflow pattern and the ops/monitoring patterns at scale.

### Phase 4: Multi-Org Orchestration
Cross-org resource management, priority balancing, and meta-level oversight. The operator manages a portfolio of organisations, each running semi-autonomously, with shared personas moving between them based on priority.

---

## 6. Relationship to BMAD Root Artefacts

This vision document frames the strategic direction. Each organisation module has its own BMAD root artefact that implements a subset of this vision:

| Organisation | BMAD Root Artefact | Status |
|-------------|-------------------|--------|
| Development | `headspace-agent-teams-functional-outline.md` | Ready for epic decomposition |
| Marketing & Sales | TBD | Next candidate for workshop |
| Production | TBD | Conceptual |
| Consulting / Delivery | TBD | Conceptual |

The Development org BMAD artefact should be built with awareness that the persona system, org definitions, and workflow engine it creates will be reused by subsequent orgs. Build for the dev org's needs first, but don't make decisions that paint future orgs into a corner.

---

*This document is the strategic frame for all Headspace organisation modules. Individual BMAD root artefacts implement specific orgs within this vision.*
