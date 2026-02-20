---
validation:
  status: valid
  validated_at: '2026-02-20T15:58:47+11:00'
---

## Product Requirements Document (PRD) — Skill File Injection via tmux Bridge

**Project:** Claude Headspace v3.1
**Epic:** Epic 8 — Personable Agents
**Sprint:** E8-S9
**Scope:** Inject persona skill and experience content into newly registered persona-backed agents as first user message via tmux bridge
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Skill file injection is the mechanism that transforms persona identity from database metadata into observable agent behaviour. After a persona-backed agent is registered (E8-S8 assigns `persona_id`) and confirmed healthy, Claude Headspace reads the persona's `skill.md` and `experience.md` files from disk and sends a composed priming message as the agent's first user input via the existing tmux bridge.

The agent absorbs the priming content and responds in character — e.g., "Hi, I'm Con. Backend developer. What would you like me to work on?" This is the moment the persona system becomes tangible: the operator sees agents that know who they are.

The injection uses the proven BMAD priming pattern (conversation-level user message, not system prompt manipulation) and the existing `tmux_bridge.send_text()` transport. Agents without personas are unaffected — no injection occurs, preserving full backward compatibility.

---

## 1. Context & Purpose

### 1.1 Context

Epic 8 introduces named personas as first-class entities in Claude Headspace. Prior sprints establish the data foundation (S1-S4), filesystem assets (S5), registration (S6), persona-aware agent creation (S7), and SessionCorrelator persona assignment (S8). At the end of S8, a persona-backed agent exists in the database with `persona_id` set and skill files on disk — but the agent itself has no awareness of its identity.

S9 bridges this gap: it reads the persona's skill and experience content and delivers it to the agent as its first user message, prompting the agent to operate in character for the remainder of its session.

### 1.2 Target User

The operator (Sam) launching persona-backed agents via `claude-headspace start --persona <slug>` or programmatically via `create_agent(persona_slug=...)`. The operator expects agents to immediately behave as the named persona after launch.

### 1.3 Success Moment

The operator launches a persona-backed agent. Within seconds of registration, the agent receives its skill and experience content, processes it, and responds with a character-appropriate greeting. The operator sees "Hi, I'm Con. Backend developer. What would you like me to work on?" in the terminal — confirmation that the persona is active and the agent is ready for work.

---

## 2. Scope

### 2.1 In Scope

- Injection trigger: after persona assignment, verify agent health and deliver priming message
- Skill file reading: load persona's `skill.md` and `experience.md` content from disk
- Priming message composition: structured message combining persona identity, skills, and experience
- Delivery of priming message as the agent's first user input via tmux bridge
- Health verification: confirm tmux pane exists and Claude Code is running before injection
- Idempotency: track that injection has occurred to prevent re-injection on duplicate events or server restart
- Graceful handling of missing skill files (warning logged, injection skipped)
- Graceful handling of agents without personas (no injection, existing behaviour preserved)
- Timing: injection completes before operator interacts with the agent

### 2.2 Out of Scope

- System prompt injection or CLAUDE.md manipulation (workshop decision 3.2 — conversation-level priming only)
- Token budget management for skill files (workshop decision 3.1 — lightweight priming signals, no limits)
- New transport mechanisms (uses existing tmux bridge infrastructure)
- Skill file authoring, editing, or template creation (E8-S5 responsibility)
- Re-injection or mid-session identity updates (workshop decision 4.1 — no brain transplants)
- Per-organisation skill extensions (deferred to Phase 2+)
- Handoff injection to successor agents (E8-S14 responsibility)
- Special hook receiver filtering for priming messages (priming flows through as a normal user prompt)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Agent launched with persona receives skill.md + experience.md content as its first user message via tmux bridge
2. Agent responds in character after receiving the priming message (acknowledges identity, role, readiness)
3. Agent launched without persona experiences no injection — existing behaviour fully preserved
4. Missing skill file on disk produces a warning log and the agent starts without persona priming (degraded but functional)
5. Injection is a one-time operation per agent session — duplicate session-start events or server restarts do not re-inject
6. Injection only fires after the agent's tmux pane is confirmed healthy (pane exists, Claude Code process running)
7. Injection completes before the operator's first command reaches the agent — no race condition

### 3.2 Non-Functional Success Criteria

1. Injection adds no more than 5 seconds to the agent startup flow (health check + send)
2. Injection failure (tmux send fails, pane disappears) does not crash the server or block other agents
3. All injection attempts (success, skip, failure) are logged with agent ID and persona slug for debugging

---

## 4. Functional Requirements (FRs)

**FR1: Injection Trigger**
After an agent is registered with a persona_id, the system triggers skill file injection for that agent. The trigger fires once per agent session, post-registration.

**FR2: Agent Health Verification**
Before attempting injection, the system verifies that the agent's tmux pane exists and that a Claude Code process is running in it. If the health check fails, injection is retried or skipped with a warning.

**FR3: Skill File Loading**
The system reads the persona's `skill.md` and `experience.md` content from disk using the persona's slug to resolve the filesystem path.

**FR4: Graceful Missing File Handling**
If `skill.md` does not exist on disk, the system logs a warning and skips injection entirely — the agent starts without persona priming. If `experience.md` does not exist, the system proceeds with `skill.md` content only (experience is optional for new personas).

**FR5: Priming Message Composition**
The system composes a structured priming message that includes the persona's identity, skills, and experience content. The message format prompts the agent to absorb the identity and respond in character.

**FR6: Message Delivery**
The system sends the composed priming message to the agent's tmux pane as a user input message. The agent receives it as its first user prompt and processes it naturally.

**FR7: Idempotency**
The system tracks whether injection has been performed for each agent session. If injection has already occurred (e.g., due to duplicate session-start hooks or server restart), subsequent triggers are no-ops.

**FR8: Backward Compatibility**
Agents without a persona_id receive no injection. The existing anonymous agent startup flow is completely unaffected.

**FR9: Timing Guarantee**
Injection completes (message delivered and confirmed) before the operator is able to send commands to the agent. The operator's first interaction with a persona-backed agent is always after the agent has received its priming.

**FR10: Injection Logging**
Every injection attempt is logged with: agent ID, persona slug, outcome (success, skipped, failed), and reason for skip/failure. This enables debugging of persona priming issues.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Latency**
The injection process (health check + file read + message send) completes within 5 seconds under normal conditions.

**NFR2: Fault Isolation**
Injection failures are contained — a failed injection does not prevent the agent from starting, does not affect other agents, and does not crash the server process.

**NFR3: Thread Safety**
The injection mechanism is safe for concurrent use — multiple agents registering simultaneously do not interfere with each other's injection.

---

## 6. Technical Context

This section preserves implementation-relevant decisions and integration points from the workshop and codebase analysis. These are not requirements — they are context for the implementation phase.

### 6.1 Design Decisions (from Agent Teams Workshop)

| Decision | Resolution | Source |
|----------|-----------|--------|
| Injection mechanism | First-prompt injection via tmux bridge, not system prompt hacking | Workshop 3.2 |
| Priming pattern | BMAD priming pattern — conversation-level user message, proven effective | Workshop 3.2 |
| Transport | Existing `tmux_bridge.send_text()` — no new transport mechanism | Workshop 3.2 |
| Token management | No token budget management for skill files — lightweight priming signals | Workshop 3.1 |
| Scope | General sessions (no persona) are not affected — injection only for persona-backed agents | Workshop 3.2 |

### 6.2 Codebase Integration Points

- **Trigger source:** `process_session_start()` in `hook_receiver.py` — after SessionCorrelator assigns `persona_id` (E8-S8). Injection fires post-registration.
- **Transport:** `tmux_bridge.send_text(pane_id, text)` — battle-tested, includes ghost text detection, Enter verification, per-pane locking.
- **Health check:** `tmux_bridge.check_health(pane_id)` — three-level check (EXISTS, COMMAND, PROCESS_TREE). Use COMMAND level minimum.
- **File reading:** E8-S5 asset utility functions for resolving persona slug to filesystem path and reading `skill.md` / `experience.md` content.
- **Hook receiver passthrough:** The injected priming message flows through the normal hook receiver path. When Claude Code receives the tmux input, it fires `user_prompt_submit` → hook receiver processes it as a normal COMMAND turn. No special filtering required.
- **Respond pending / skill expansion filters:** The priming message is sent via `send_text()`, which is the same path used by the voice bridge respond flow. The `respond_pending` mechanism in hook_receiver may need coordination so the priming message is not suppressed. Alternatively, if the priming is sent before the hook receiver is aware of the agent, this coordination may be unnecessary — implementation should verify.
- **team_content_detector:** The `is_skill_expansion()` filter detects and suppresses skill file content in `process_user_prompt_submit`. The priming message content (skill.md + experience.md) could trigger this filter. Implementation should verify whether the priming arrives before or after the filter is active for the agent.

### 6.3 Dependencies

| Sprint | Dependency | What It Provides |
|--------|-----------|-----------------|
| E8-S5 | Persona filesystem assets | Asset utility functions for reading skill.md and experience.md by persona slug |
| E8-S8 | SessionCorrelator persona assignment | `agent.persona_id` set at registration time, providing the trigger signal |
| E8-S4 | Agent model extensions | `persona_id` FK on Agent model |
| E5-S4 | tmux bridge | `send_text()` function for delivering the priming message |

### 6.4 Priming Message Format Reference

The priming message follows the BMAD priming pattern — a structured conversation-level message that the agent absorbs naturally. The message combines `skill.md` content (who the persona is, how they work) with `experience.md` content (what they've learned from past sessions). The exact format is an implementation detail to be iterated on, but should prompt the agent to acknowledge its identity and signal readiness.

---

## Document History

| Version | Date       | Author | Changes                                    |
|---------|------------|--------|--------------------------------------------|
| 1.0     | 2026-02-20 | Sam    | Initial PRD from workshop (E8-S9)          |
