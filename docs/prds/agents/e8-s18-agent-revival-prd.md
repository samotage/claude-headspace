## Product Requirements Document (PRD) — Agent Revival ("Seance")

**Project:** Claude Headspace
**Scope:** Dead agent context recovery and successor briefing
**Author:** Robbo (architect), workshopped with Sam
**Status:** Draft

---

## Executive Summary

When Claude Code agents die unexpectedly, all conversational context dies with them. Starting a fresh agent means repeating conversations, re-explaining decisions, and losing momentum. Agent Revival ("Seance") enables operators to spin up a new agent that self-briefs from its dead predecessor's conversation history stored in the database, turning a hard restart into a warm restart.

This feature introduces two new capabilities: (1) a CLI command that extracts a dead agent's conversation history from the database as structured markdown, and (2) a "revive" flow triggered from the dashboard UI that creates a successor agent, injects an instruction to self-brief via the CLI tool, and lets the new agent process its predecessor's context naturally.

The building blocks already exist: conversation history is stored in the database (agent -> commands -> turns), persona injection delivers instructions via tmux bridge, and the dashboard/VoiceBridge can create agents programmatically. This is a wiring job connecting existing infrastructure with a new CLI extraction tool and a thin orchestration layer.

---

## 1. Context & Purpose

### 1.1 Context

Agent death is a regular occurrence in Claude Headspace — agents crash, hit context limits, or are killed by system events like reloader restarts. The existing handoff system (E8-S14) addresses context continuity when agents are alive and can write their own handoff documents. But when an agent is already dead, there is no curator available to produce a contextual briefing. The operator must manually reconstruct context for the replacement, which is tedious and lossy.

The system already records the full conversational history in the database via hooks. Every user prompt and agent response is captured as Turn records, organised under Command records, linked to the Agent. This raw material is available — it just needs to be surfaced in a format a new agent can consume.

### 1.2 Target User

The operator (Sam) managing Claude Code agents via the dashboard or VoiceBridge. The operator notices a dead agent, wants to continue its work, and needs the replacement agent to understand what the predecessor was doing.

### 1.3 Success Moment

The operator clicks "Revive" on a dead agent's card. A new agent spins up with the same project and persona configuration. The new agent retrieves its predecessor's conversation history via the CLI, processes it, and says something like "I can see my predecessor was working on X, had completed Y, and was in the middle of Z. I'll pick up from here." The operator did not have to re-explain anything.

---

## 2. Scope

### 2.1 In Scope

- A CLI command (`claude-headspace transcript <agent-id>`) that queries the database (agent -> commands -> turns) and outputs the conversation as structured markdown
- The CLI output contains conversational content only: user prompts and agent responses, organised chronologically by command, with command instruction text as section headers and timestamps included
- A "Revive" API endpoint that orchestrates revival: creates a new agent with same project and persona config, links via `previous_agent_id`, injects a revival instruction
- Revival instruction injection via the persona injection mechanism (tmux bridge), telling the new agent to run the CLI command and self-brief
- For non-persona agents, the revival instruction is the sole injection (no preceding skill injection step)
- A "Revive" UI trigger on dead agent cards or the agent detail view in the dashboard
- Works for both persona-based and non-persona (anonymous) agents

### 2.2 Out of Scope

- Automatic revival (agent dies -> system auto-revives) — this is operator-initiated only
- Modifying the existing handoff flow — revival is complementary, not a replacement
- LLM-powered pre-summarisation of the transcript before injection — the new agent does its own processing in-context
- Reviving agents into a different project — the successor inherits the predecessor's project
- Changes to how agents die or how conversation is recorded in the database
- Filtering or limiting the CLI transcript output (e.g., last N commands, time ranges) — "give me everything" is sufficient for v1
- Cleanup of old transcript outputs or revival records

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Operator can trigger revival of a dead agent from the dashboard UI
2. A new agent is created with the same project and persona (if applicable) as the predecessor
3. The `previous_agent_id` chain links successor to predecessor for traceability
4. The CLI command outputs the predecessor's full conversation history as readable markdown
5. The new agent successfully retrieves and processes its predecessor's conversation history
6. The new agent demonstrates contextual awareness of what the predecessor was working on
7. Revival works for both persona-based and anonymous agents

### 3.2 Non-Functional Success Criteria

1. CLI transcript extraction completes within a reasonable time for agents with extensive history (hundreds of turns)
2. The revival flow does not require manual intervention beyond clicking the initial trigger
3. The structured markdown output is clean enough for an LLM to parse without confusion

---

## 4. Functional Requirements (FRs)

**FR1: CLI Transcript Command**

The system provides a CLI command `claude-headspace transcript <agent-id>` that accepts an agent database ID and outputs the agent's conversation history as structured markdown to stdout. The agent ID is the integer primary key from the Agent table.

**FR2: Transcript Markdown Format**

The CLI output is structured as follows:
- Each command appears as a markdown section with the command's instruction text as the heading
- Turns within each command are listed chronologically
- Each turn is prefixed with the actor label (`**User:**` or `**Agent:**`) followed by the turn text content
- Timestamps are included for each turn
- Commands are ordered chronologically (earliest first)
- Turns with empty or null text content are omitted

**FR3: Revive API Endpoint**

The system provides an API endpoint that accepts a dead agent's ID and initiates the revival flow. The endpoint validates that the agent exists and has ended (`ended_at` is not null) before proceeding.

**FR4: Successor Agent Creation**

The revival flow creates a new agent with:
- The same `project_id` as the predecessor
- The same `persona_id` as the predecessor (if the predecessor had a persona)
- `previous_agent_id` set to the predecessor's ID
Agent creation uses the existing `create_agent()` function in `agent_lifecycle.py`.

**FR5: Revival Instruction Injection**

After the successor agent is online and has completed skill injection (if persona-based), the system injects a revival instruction via the tmux bridge. The instruction tells the agent to run the CLI transcript command with the predecessor's agent ID and to use the output to understand the context of the predecessor's work.

**FR6: Non-Persona Agent Revival**

For agents without a persona, the revival instruction is injected as the first and only instruction after the agent comes online. No skill injection step precedes it.

**FR7: Revive UI Trigger**

The dashboard displays a "Revive" action on dead agent cards or in the agent detail view. The trigger is only visible for agents where `ended_at` is not null. Clicking the trigger calls the revive API endpoint.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: CLI Database Access**

The CLI transcript command requires Flask application context to access the database. It should use the existing Flask CLI infrastructure (Click commands within Flask context).

**NFR2: Graceful Handling of Missing Data**

If the predecessor agent has no commands or no turns, the CLI should output a message indicating no conversation history was found rather than failing silently or producing empty output.

---

## 6. UI Overview

**Dead Agent Card — Revive Action:**

Dead agents (those with `ended_at` set) display a "Revive" button or icon action. The button is visually distinct from other card actions (handoff, dismiss, etc.) and communicates the concept of continuing from a dead agent. Clicking it initiates the revival flow and provides feedback (e.g., "Reviving..." spinner or status message).

**Agent Detail View — Revive Action:**

If the agent detail view is open for a dead agent, the same revive action is available there, providing an alternative trigger point for operators who are inspecting a dead agent's details before deciding to revive.

**Successor Card — Predecessor Link:**

The successor agent's card or detail view indicates it was revived from a predecessor, showing the link in the continuity chain (via `previous_agent_id`). This is informational — the operator can see the lineage.
