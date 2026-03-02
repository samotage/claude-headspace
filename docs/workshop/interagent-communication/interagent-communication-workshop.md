# Inter-Agent Communication — Design Workshop (Epic 9)

**Date:** 1 March 2026
**Status:** Active workshop. Section 0 resolved (4 decisions). **Section 1 fully resolved (5 decisions).** Section 0A seeded (7 decisions, pending workshop). **Section 2 fully resolved (3 decisions).** Sections 3–5 pending.
**Epic:** 9 — Inter-Agent Communication
**Inputs:**
- Organisation Workshop Sections 0–1 (resolved decisions on org structure, serialization, CLI)
- `docs/workshop/organisation-workshop.md` — Organisation workshop (on hold, Sections 2–9 blocked on this epic)
- `docs/workshop/agent-teams-workshop.md` — Phase 1 design decisions (Epic 8)
- `docs/conceptual/headspace-agent-teams-functional-outline.md` — Agent Teams vision
- `docs/workshop/erds/headspace-org-erd-full.md` — **Canonical data model** (all resolved outcomes stored here)
- Existing codebase: tmux bridge, hook receiver, SSE broadcaster, remote agent infrastructure

**Method:** Collaborative workshop between operator (Sam) and architect (Robbo). Same format as the Organisation Workshop — work through sections sequentially, resolve decisions with documented rationale.

**Prerequisite:** This workshop assumes Epic 8 Phase 1 (Personable Agents) is substantially built. Tmux bridge, hook receiver, SSE broadcaster, and remote agent API all exist and work. This workshop designs the channel-based communication layer that sits between agents and underpins the organisation mechanics designed in the Organisation Workshop.

**Relationship to Organisation Workshop:** This epic was extracted from the Organisation Workshop when Section 2 (Inter-Agent Communication) revealed that the communication primitive is channel-based group chat, not point-to-point messaging. The organisation mechanics (Sections 2–9 of the Organisation Workshop) build on top of the channel infrastructure designed here. The Organisation Workshop resumes after this epic delivers working channels.

---

## How to Use This Document

This is the **index document** for the workshop. Each section lives in its own file under `sections/` for context-efficient agent loading. Work through sections in order — each contains numbered decisions that may depend on earlier decisions. Dependency chains are explicit.

**Data model:** The canonical ERD is [`erds/headspace-org-erd-full.md`](../erds/headspace-org-erd-full.md). Embedded ERDs in section files are workshop working documents showing the design conversation at the time of resolution — not the source of truth.

---

## Workshop Log

| Date | Session | Sections | Key Decisions |
|------|---------|----------|---------------|
| 2 Mar 2026 | Sam + Robbo | 0A (seeded) | Handoff continuity: filesystem-driven detection, summary-in-filename, synthetic injection primitive, operator-gated rehydration. 7 decisions seeded, pending formal workshop. |
| 2 Mar 2026 | Sam + Robbo | 0 (resolved) | Infrastructure audit: 7 communication paths mapped, per-pane parallel fan-out confirmed, completion-only relay rule, envelope format with persona+agent ID, channel behavioral primer as injectable asset, chair role in channels. Incorporated Paula's AR Director guidance: two-layer primer (base + intent), persona-based membership, chair capabilities (delivery priority deferred to v2). |
| 2 Mar 2026 | Sam + Robbo | 1.1 (resolved) | Channel model: 3 new tables (Channel, ChannelMembership, Message). PersonaType parent table introduced (2×2 matrix: agent/person × internal/external). Channels cross-project and optionally org-scoped. Membership persona-based with explicit PositionAssignment FK for org capacity. Operator participates as internal-person Persona. External persons/agents modelled for future cross-system collaboration (dragons acknowledged, scope held). |
| 2 Mar 2026 | Sam + Robbo | 1.2–1.4 (resolved) | Message model: 10-column table with metadata JSONB, attachment_path, bidirectional Turn/Command links (source_turn_id, source_command_id on Message; source_message_id on Turn). Messages immutable. Message types: 4-type enum (message, system, delegation, escalation). Membership model: explicit join/leave for all persona types, muted = delivery paused, one agent instance per active channel (partial unique index), no constraint on person-type personas. |
| 2 Mar 2026 | Sam + Robbo | 1.5 (resolved) | Relationship to existing models: channel messages enter the existing IntentDetector → CommandLifecycleManager pipeline. No special-case logic. Delegation type biases toward COMMAND intent but detector decides. No new Event types — Messages are their own audit trail. **Section 1 (Channel Data Model) fully resolved.** |
| 2 Mar 2026 | Sam + Robbo | 2.1 (resolved) | Channel lifecycle: 3 creation paths (CLI, dashboard, voice bridge — voice bridge is primary operator interface). Creation capability is a persona attribute (agents delegate check to persona via OOP method delegation). 4-state lifecycle: pending → active → complete → archived. Mid-conversation member addition creates new channel as overlay on existing 1:1 sessions — existing command/turn trees untouched. Context briefing: last 10 messages injected into new agent spin-up after persona injection. Channel is a Headspace-level construct; agents don't need to know they're in one. |
| 3 Mar 2026 | Sam + Robbo | 2.2 (resolved) | CLI Interface resolved. Standalone `flask channel` / `flask msg` namespaces (not nested under `flask org`), `flask channel complete` verb (matches state name, no translation layer). Caller identity via tmux pane detection + env var override. 10 channel commands, 2 message commands, conversational envelope format, one-agent-one-channel enforcement, capability checks, 7 actionable error messages, 7 architectural notes deferred to later sections. |
| 3 Mar 2026 | Sam + Robbo | 1.x (correction) | **Message.persona_id NULLABLE resolution.** PostgreSQL incompatibility (NOT NULL + SET NULL ondelete) resolved: Option A chosen — make persona_id nullable. Persona deletion sets message persona_id to NULL; agent record and audit trail remain intact. System messages naturally have NULL persona. Updated: Section 1.1, 1.2, 1.3, canonical ERD, migration checklist. |
| 3 Mar 2026 | Sam + Robbo | 2.3 (resolved) | API Endpoints resolved. Single `/api/channels` blueprint — REST endpoints for channels, members, messages. Same `ChannelService` backs CLI, API, voice bridge, and dashboard. Auth: existing dashboard session + session tokens (no new mechanism). SSE: two new event types (`channel_message`, `channel_update`) on existing stream with type filtering — no per-channel streams. Voice bridge: extend semantic picker for channel-name matching. Slug-based URLs. No channel-specific rate limiting in v1. **Section 2 (Channel Operations & CLI) fully resolved.** |

---

## The Foundational Insight

During the Organisation Workshop (Section 2), the operator's first real use case clarified the architecture:

> **Use case:** Sam, Robbo, and Paula need to sit down together and workshop persona alignment. Three participants, one conversation. Everyone sees everything. Any response while others are thinking is an interrupt.

This is a **group chat** — a well-solved problem (Slack, Discord, iMessage) with a well-understood data model. The communication primitive is not "Agent A sends a message to Agent B." It is:

**A message is posted to a channel, and all participants in that channel receive it.**

This means:
- **Channel** is the conversation container (N participants)
- **Message** belongs to a channel, from a sender (not sender→receiver)
- **Membership** determines who's in each channel
- **Delivery** fans out per member's connection type (tmux, SSE, API)
- **Point-to-point** is the degenerate case — a channel with two members
- **Interrupts** fall out naturally — a new message in the channel while others are mid-thought

Everything downstream — task delegation, escalation, reporting, org-aware routing — builds on channels. The channel is the nervous system; the organisation is the brain that decides which nerves to fire.

---

## Sections

### [Section 0: Existing Infrastructure Audit](sections/section-0-infrastructure-audit.md)
**Status:** Resolved (4 decisions: 0.1–0.4)

Maps the 7 existing communication paths, confirms tmux bridge concurrent fan-out capacity (per-pane locks, no global lock), establishes the completion-only relay rule (only composed responses fan out — no PROGRESS turns), resolves envelope format (`[#channel-name] PersonaName (agent:ID):`), and designs the two-layer behavioral primer (base + channel intent). Incorporates Paula's AR Director guidance on persona-based membership, chair capabilities, and delivery priority deferral.

### [Section 0A: Handoff Continuity & Synthetic Injection](sections/section-0a-handoff-continuity.md)
**Status:** Seeded (7 decisions: 0A.1–0A.7, pending workshop)

Independent of Sections 1–5. Designs startup handoff detection, scannable filename format with summary-in-filename, synthetic injection delivery primitive, operator-gated rehydration, and on-demand handoff history CLI. Can be workshopped at any time.

### [Section 1: Channel Data Model](sections/section-1-channel-data-model.md)
**Status:** Fully resolved (5 decisions: 1.1–1.5)

The structural foundation. 3 new tables (Channel, ChannelMembership, Message) plus PersonaType parent table (2×2: agent/person × internal/external). Persona-based membership with mutable agent delivery target. Messages are immutable with bidirectional Turn/Command traceability. One agent instance per active channel (partial unique index). Messages enter existing IntentDetector → CommandLifecycleManager pipeline with no special-case logic.

### [Section 2: Channel Operations & CLI](sections/section-2-channel-operations.md)
**Status:** Fully resolved (3 decisions: 2.1–2.3)

Channel lifecycle (4-state: pending → active → complete → archived), creation paths, mid-conversation member addition. CLI interface: standalone `flask channel` / `flask msg` namespaces, caller identity via tmux pane detection, 10 channel commands, 2 message commands, conversational envelope format. API endpoints: single `/api/channels` blueprint, REST CRUD + members + messages. Auth via existing dashboard session + session tokens. SSE: two new event types on existing stream. Voice bridge: semantic picker extended for channel-name matching.

### [Section 3: Message Delivery & Fan-Out](sections/section-3-message-delivery.md)
**Status:** Pending (4 decisions: 3.1–3.4)

The delivery engine. Fan-out architecture, agent response capture & relay, delivery timing & agent state safety, operator delivery via SSE/dashboard.

### [Section 4: The Group Workshop Use Case](sections/section-4-group-workshop-use-case.md)
**Status:** Pending (3 decisions: 4.1–4.3)

End-to-end validation. Workshop channel setup, multi-agent conversation flow, workshop completion & output.

### [Section 5: Migration & Integration Checklist](sections/section-5-migration-checklist.md)
**Status:** Living document — populated as decisions resolve

Database migrations, new services, integration points with existing systems (tmux bridge, hook receiver, SSE broadcaster, remote agent API, voice bridge).

---

## Reference Documents

- **Canonical data model:** [`erds/headspace-org-erd-full.md`](../erds/headspace-org-erd-full.md)
- **AR Director guidance:** [`paula-channel-intent-guidance.md`](paula-channel-intent-guidance.md)
- **Organisation workshop (on hold):** [`organisation-workshop.md`](../organisation-workshop.md)
- **Agent Teams vision:** [`../conceptual/headspace-agent-teams-functional-outline.md`](../../conceptual/headspace-agent-teams-functional-outline.md)
- **Phase 1 design:** [`agent-teams-workshop.md`](../agent-teams-workshop.md)

---

## Relationship to Organisation Workshop

When this epic is complete, the Organisation Workshop (Sections 2–9) can resume. The channel infrastructure designed here becomes the foundation for:

- **Section 2 (Inter-Agent Communication)** → Superseded. Channels replace point-to-point messaging.
- **Section 3 (Task Model & Delegation)** → Tasks are communicated via channels. Delegation is posting to a channel.
- **Section 4 (Agent Interaction Patterns)** → Interaction patterns are channel conversation patterns.
- **Section 5+ (Lifecycle, Monitoring, etc.)** → Build on channel infrastructure.

The Organisation Workshop's resolved decisions (Sections 0–1) remain valid and do not depend on channels. The migration checklist from Section 1 can be implemented independently of this epic.
