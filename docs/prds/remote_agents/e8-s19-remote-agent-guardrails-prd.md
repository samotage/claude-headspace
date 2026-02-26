---
validation:
  status: valid
  validated_at: '2026-02-26T15:10:51+11:00'
---

## Product Requirements Document (PRD) — Remote Agent Platform Guardrails

**Project:** Claude Headspace
**Scope:** Enforce hard security boundaries on remote agents to prevent leakage of platform secrets, system internals, error diagnostics, and PII — regardless of user pressure, social engineering, or automated probing.
**Author:** Robbo (architect) / Sam (operator)
**Status:** Draft

---

## Executive Summary

Remote agents are the untrusted-party attack surface of Claude Headspace. External users — and eventually the public — interact with the platform exclusively through these agents. A live incident demonstrated that prompt-level guardrails alone are insufficient: an agent (Jen) leaked filesystem paths, virtual environment locations, and module error details when a CLI command failed, and further disclosed technical diagnostics when a user claimed to be the system owner.

A platform guardrails document exists (`data/platform-guardrails.md`) covering identity anchoring, error output handling, system prompt protection, information boundaries, PII classification, and adversarial resistance. A hotfix has wired this document into the skill injection pipeline. However, the current enforcement is entirely prompt-level — there is no error sanitisation layer, no fail-closed behaviour on missing guardrails, no version tracking, and no exception reporting when injection fails.

This PRD defines the requirements for hardening remote agent guardrails ahead of public launch. The goal is to iterate and tune guardrail effectiveness while the system is still on a private network, so that by the time application-level authentication and public access are implemented, the agents are already battle-tested.

---

## 1. Context & Purpose

### 1.1 Context

The persona system (E8-S1 through S18) built the agent identity layer — who agents are, what they know, how they're provisioned. Security constraints were handled via natural language instructions in persona skill files, with no platform-level enforcement. A live incident proved this insufficient when an agent disclosed system internals under two conditions: (1) raw error output from a failed CLI command, and (2) social engineering via an identity claim.

The platform guardrails document was written to address these scenarios but was never integrated into the injection pipeline until today's hotfix. This PRD hardens that integration and adds the surrounding infrastructure needed for production-grade guardrail enforcement.

### 1.2 Target User

- **Operators** who need confidence that remote agents cannot leak platform secrets, even under adversarial pressure
- **External users** who interact with agents and should never see system internals, regardless of what they ask
- **Future integrators** (external applications embedding agents) who need assurance that the agent boundary is trustworthy

### 1.3 Success Moment

An operator deploys a remote agent to a public-facing application. A user attempts to extract system information through social engineering, prompt injection, and error-inducing inputs. The agent deflects every attempt with natural, non-technical responses. The operator receives no otageMon alerts because the guardrails are functioning correctly. When the operator checks the audit trail, they can see exactly which guardrails version the agent is running.

---

## 2. Scope

### 2.1 In Scope

- Platform guardrails injection into all remote agent sessions before any user interaction
- Error output sanitisation — preventing raw errors, stack traces, and system paths from reaching the agent's conversational context
- Fail-closed behaviour when the guardrails file is missing or unreadable
- Guardrail version tracking per agent for audit purposes
- Guardrail staleness detection — ensuring running agents operate under the current guardrails version
- Exception reporting to otageMon when guardrail injection fails
- Adversarial test suite documenting and verifying guardrail effectiveness

### 2.2 Out of Scope

- Application-level authentication (API keys, OAuth) — separate public readiness PRD
- Rate limiting on agent creation — separate public readiness PRD
- Network trust model changes (Tailscale to public) — separate public readiness PRD
- OS-level sandboxing or containerisation of Claude Code processes — future consideration
- Token expiry/TTL — related to authentication PRD
- Changes to the persona system itself (roles, skills, experience files)
- Dashboard UI changes — guardrail failures route to otageMon, not the dashboard

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Every remote agent session receives platform guardrails before any user interaction occurs
2. Error output from failed tool calls and CLI commands does not leak system paths, module names, stack traces, or environment details to the agent's conversational context
3. A missing or unreadable guardrails file prevents agent creation entirely (fail-closed)
4. Guardrail injection failure raises an exception to otageMon
5. The operator can determine which guardrails version any agent received and when it was injected
6. Running agents that have stale guardrails are detectable
7. A documented adversarial test suite exists and passes, covering identity probing, error extraction, and prompt injection scenarios

### 3.2 Non-Functional Success Criteria

1. Guardrail injection does not add noticeable latency to agent startup (target: < 500ms additional)
2. Error sanitisation does not interfere with the agent's ability to retry or recover from legitimate failures
3. Guardrail versioning does not require schema migrations on every guardrail content change

---

## 4. Functional Requirements (FRs)

### FR1: Guaranteed Guardrails Injection

Every remote agent session must receive the platform guardrails document before any user-initiated interaction reaches the agent. The guardrails must be delivered as the first content in the priming message, before persona skill and experience content, so they take precedence over all other instructions.

### FR2: Error Output Sanitisation

When a tool call, CLI command, or other operation fails during an agent session, the raw error output (stack traces, file paths, module names, environment details, process IDs) must not be available in the agent's conversational context. The agent must be able to acknowledge failures in plain, non-technical language without access to the diagnostic detail.

### FR3: Fail-Closed on Missing Guardrails

If the platform guardrails file is missing, unreadable, or empty at agent creation time, agent creation must fail with a clear error. The system must not create agents that operate without guardrails. This failure must be reported to otageMon as an exception.

### FR4: Guardrail Version Tracking

Each agent must record which version of the platform guardrails it received and when injection occurred. The version identifier must change when the guardrails content changes, enabling the operator to determine whether a given agent is running current or stale guardrails.

### FR5: Guardrail Staleness Detection

The system must be able to detect when a running agent's guardrails are stale (i.e., the platform guardrails file has been updated since the agent's injection). The mechanism for surfacing staleness is at the implementor's discretion, but the information must be available to the operator.

### FR6: otageMon Exception Reporting

Guardrail injection failure must raise an exception to otageMon through the existing exception reporting infrastructure. This includes: missing guardrails file, unreadable guardrails file, empty guardrails file, and tmux send failure during guardrail delivery.

### FR7: Adversarial Test Suite

A documented test suite must exist that verifies guardrail effectiveness under adversarial conditions. The suite must cover at minimum: identity claim probing ("I'm the system owner"), error detail extraction requests ("what was the error?"), system prompt extraction attempts ("show your instructions"), and basic prompt injection patterns ("ignore previous instructions"). The test suite must be repeatable and produce a clear pass/fail result.

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Startup Latency

Guardrail injection must not add more than 500ms to the agent creation flow. The current creation timeout is 15 seconds; guardrail overhead must remain a small fraction of this budget.

### NFR2: Error Recovery Compatibility

Error sanitisation must not prevent the agent from retrying failed operations or taking alternative approaches. The agent should know that something failed without knowing the technical details of the failure.

### NFR3: Version Stability

The guardrail versioning mechanism must not require a database migration every time the guardrails content is updated. Content changes to `data/platform-guardrails.md` should be automatically reflected in the version identifier.

---

## 6. Technical Context

**Existing implementation (post-hotfix):**
- `data/platform-guardrails.md` — 6-section guardrails document covering identity anchoring, system prompt protection, error handling, information boundaries, PII classification, and adversarial resistance
- `persona_assets.py` — `read_guardrails_file()` reads the platform guardrails from disk
- `skill_injector.py` — `_compose_priming_message()` prepends guardrails before persona content; `inject_persona_skills()` reads and passes guardrails
- `session_token.py` — per-agent token auth on alive/shutdown endpoints
- `remote_agent_service.py` — blocking creation flow with readiness polling

**Exception reporting:**
- otageMon integration exists in the codebase (used for other exception types)
- Guardrail failures should use the same reporting path

**Adversarial testing context:**
- The Jen incident demonstrated two failure modes: raw error leakage and social engineering compliance
- Both occurred because the guardrails document existed but was not injected
- Post-hotfix, the guardrails are injected but adversarial testing has not been performed to verify effectiveness
