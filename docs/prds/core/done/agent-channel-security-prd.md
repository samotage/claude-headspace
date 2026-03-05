---
validation:
  status: valid
  validated_at: '2026-03-05T09:36:34+11:00'
---

## Product Requirements Document (PRD) — Agent Channel Communication Security

**Project:** Claude Headspace
**Scope:** Tamper-proof agent channel communication via architectural constraints
**Author:** Robbo (Architect) + Sam (Operator)
**Status:** Draft

---

## Executive Summary

Agents in Claude Headspace have full visibility of the system's source code, configuration, database connections, and API surface. Traditional security measures — tokens, session secrets, API authentication — are ineffective because any secret the system knows, an agent can discover. The current channel communication implementation contains multiple authentication paths that accept agent identity as a claim (HTTP header, environment variable), enabling agents to spoof messages as other personas.

This PRD specifies requirements for making agent channel communication architecturally tamper-proof. Rather than adding authentication layers that agents can read and circumvent, the approach removes the capability for agents to post messages directly. Internal agent output reaches channels exclusively through system-mediated routing based on infrastructure identity (tmux pane binding). Remote agents, which lack infrastructure access, continue to authenticate via validated session tokens — the one case where traditional auth is appropriate.

The result is a system where misbehaviour is not prevented by rules agents might break, but by the absence of mechanisms they could exploit. The skill file is a suggestion; the architecture is the law.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace manages multiple AI agents that communicate through channels — named conversation containers with memberships, messages, and delivery mechanisms. The current implementation provides three authentication paths for posting messages to channels:

1. **Bearer token** — validated via SessionTokenService (sound)
2. **X-Headspace-Agent-ID HTTP header** — accepts raw agent ID with no token validation (spoofable)
3. **HEADSPACE_AGENT_ID environment variable** — accepts raw agent ID from shell environment (spoofable)

Additionally, CLI commands (`flask msg send`, `flask channel create`, etc.) provide agent-accessible mechanisms for channel manipulation that bypass the intended communication model.

Agents are not black-box clients. They can read source code, inspect configuration, enumerate API endpoints, discover other agents' session data, and craft HTTP requests. Any security model that relies on agents not knowing something — or choosing not to exploit what they know — is fundamentally broken.

### 1.2 Target User

System operators who manage multi-agent teams and need to trust that channel message attribution is accurate — that a message from "Melanie" genuinely originated from Melanie's agent session, not from another agent claiming her identity.

### 1.3 Success Moment

An operator reads a channel conversation and can trust every message attribution without reservation, because the architecture makes spoofing impossible — not merely prohibited.

---

## 2. Scope

### 2.1 In Scope

- Elimination of unauthenticated identity assertion from internal agents via HTTP endpoints
- Elimination of environment-variable-based identity override in CLI caller resolution
- Full audit of all CLI commands for agent-exploitable capabilities, with restriction of commands that allow agents to modify channel state, post messages, or manipulate personas/memberships
- Confirmation and hardening of system-mediated routing as the sole path for internal agent messages into channels (COMPLETION and END_OF_COMMAND turn intents only — no mid-processing output)
- Preservation of Bearer token authentication for remote agents (validated session tokens remain the correct model for agents without infrastructure identity)
- Preservation of dashboard operator authentication via session cookie
- Documentation of the two trust models: infrastructure identity (internal agents) and validated tokens (remote agents)

### 2.2 Out of Scope

- Redesign of the channel model (channels, memberships, message schema are sound)
- Per-persona/channel rate limiting (useful but separate concern)
- Content inspection or moderation of agent messages
- Voice bridge changes (operator-first model is unaffected)
- Remote agent channel creation or membership management (separate feature)
- Information discovery mitigation (agents reading other agents' data is made inert by this work, not addressed separately)
- Process sandboxing or filesystem isolation for agents (future consideration — architecturally distinct problem)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. No internal agent can post a message to any channel by calling an HTTP endpoint with a spoofed or unvalidated identity assertion
2. No internal agent can post a message to any channel by setting an environment variable or calling a CLI command
3. Internal agent messages appear in channels only when the system routes them via the existing relay mechanism, triggered by COMPLETION or END_OF_COMMAND turn intents
4. Remote agents can post to channels via validated Bearer token authentication (no regression)
5. Dashboard operators can post to channels via session cookie authentication (no regression)
6. All CLI commands that modify channel state, post messages, or manipulate personas/memberships are restricted to operator-initiated contexts only
7. The two trust models (infrastructure identity for internal agents, validated tokens for remote agents) are documented and enforced at the architectural level

### 3.2 Non-Functional Success Criteria

1. No new authentication mechanisms, tokens, or secrets are introduced — security is achieved by removing capabilities, not adding layers
2. Existing channel functionality (create, list, history, membership management) remains fully operational for authorised callers (operators and remote agents with valid tokens)

---

## 4. Functional Requirements (FRs)

**FR1: Remove unauthenticated HTTP identity assertion**
The system must not accept agent identity claims via HTTP headers that lack cryptographic validation. Any HTTP-based agent identity must be backed by a validated session token. Unauthenticated identity headers (e.g., raw agent ID without token) must be rejected or ignored.

**FR2: Remove environment-variable identity override**
CLI caller identity resolution must not accept agent identity from environment variables. The sole identity source for CLI callers in an agent context must be infrastructure-derived (tmux pane-to-agent binding).

**FR3: Audit and restrict agent-exploitable CLI commands**
All Flask CLI commands must be audited for capabilities that an agent with shell access could exploit. Commands that allow posting messages, creating/modifying channels, managing memberships, or registering/modifying personas must be restricted to operator-initiated contexts. The specific restriction mechanism is an implementation decision, but the requirement is that an agent running in a tmux pane cannot use CLI commands to perform actions outside its authorised communication path.

**FR4: System-mediated routing is the sole internal agent channel path**
Internal agent messages must reach channels exclusively through system-mediated routing. The system observes agent output (via the existing hook/lifecycle infrastructure), determines whether the output should be routed to a channel (based on the agent's active channel membership), and posts the message on the agent's behalf. The agent does not choose, initiate, or control the routing.

**FR5: Route only completed output**
System-mediated routing must only relay agent output that represents completed work — specifically, turns with COMPLETION or END_OF_COMMAND intents. Mid-processing output (progress updates, thinking, tool use) must not be routed to channels. Channels are for outcomes, not stream of consciousness.

**FR6: Preserve remote agent token authentication**
Remote agents (those without tmux pane infrastructure identity) must continue to authenticate via validated Bearer tokens issued by SessionTokenService. This path is architecturally sound and must not be degraded by changes to internal agent authentication.

**FR7: Preserve operator dashboard authentication**
Dashboard operators must continue to authenticate via session cookies. Operator access to all channel functionality (posting, creating, managing) must be unaffected.

**FR8: Document trust models**
The two distinct trust models must be documented as part of the system architecture:
- **Internal agents:** Identity from infrastructure (tmux pane binding). No direct posting capability. System routes output to channels.
- **Remote agents:** Identity from validated session tokens. Direct posting via authenticated HTTP endpoints. Token validation is required and sufficient.

---

## 5. UI Overview

No user-facing UI changes. Channel chat interfaces continue to display messages as before. The change is invisible to users — messages appear the same way, but their provenance is architecturally guaranteed rather than trust-based.
