---
validation:
  status: valid
  validated_at: '2026-02-11T15:06:52+11:00'
---

## Product Requirements Document (PRD) — Agent Lifecycle Management

**Project:** Claude Headspace
**Scope:** Remote agent creation, graceful shutdown, and context window monitoring
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace is maturing into an orchestration system where agents are a first-class concept. Currently, creating and terminating Claude Code agents requires direct terminal access — opening tabs, running CLI commands, and manually closing sessions. This prevents effective remote operation, particularly from mobile devices via the voice/text bridge.

This PRD introduces agent lifecycle management: the ability to create new idle agents, gracefully shut down active agents, and monitor context window usage — all from the dashboard or voice/text bridge chat panel. This enables fully remote agent orchestration without needing physical access to the development machine.

Graceful shutdown ensures agents clean up properly by sending the `/exit` command through tmux, which fires all lifecycle hooks back to Claude Headspace, keeping dashboard state consistent and minimising reliance on the agent reaper for cleanup.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace already tracks agents, displays their status on a dashboard, and allows sending text input via the tmux bridge. However, the lifecycle endpoints — starting and stopping agents — are only accessible from the local terminal. The voice/text bridge (Epic 6, Sprints 1-3) established remote communication with agents, but cannot yet create or destroy them. Additionally, there is no visibility into an agent's context window usage, which is critical for managing agent quality — agents degrade as context fills up.

### 1.2 Target User

The primary user (developer/operator) who manages multiple Claude Code agents across projects, often remotely from a mobile device via the voice/text bridge chat panel.

### 1.3 Success Moment

The user is on their phone, sees an agent's context is at 85% used, kills it from the chat interface, and spins up a fresh agent for the same project — all without touching the development machine.

---

## 2. Scope

### 2.1 In Scope

- Create a new idle Claude Code agent for a registered project via API
- Gracefully shut down an active agent via API (sends `/exit` through tmux)
- Read an agent's context window usage (percentage used, tokens remaining) from the tmux pane statusline on demand
- Display context window usage on agent cards in the dashboard
- Expose create, kill, and context-check actions from the voice/text bridge chat panel
- Expose create, kill, and context-check actions from the dashboard UI
- New `agents` route blueprint

### 2.2 Out of Scope

- Creating agents with an initial prompt or instruction (future sprint)
- Agent orchestration or multi-agent coordination
- Bulk agent operations (kill all, create multiple)
- Context usage alerts or automatic actions (e.g., auto-restart when context is high)
- Agent-to-agent communication
- Non-tmux agent creation paths
- Periodic/automatic context usage polling (context refresh is on-demand only)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A user can create a new idle agent for any registered project from the dashboard
2. A user can create a new idle agent for any registered project from the voice/text bridge chat panel
3. A user can gracefully shut down any active agent from the dashboard
4. A user can gracefully shut down any active agent from the voice/text bridge chat panel
5. Context window usage (percentage used and tokens remaining) is visible on each agent card in the dashboard when requested
6. Context window usage can be queried for a specific agent from the voice/text bridge chat panel
7. Graceful shutdown fires all expected lifecycle hooks (session-end, stop) back to Claude Headspace
8. Dashboard state remains consistent after agent creation and shutdown (no orphaned cards, no stale state)
9. All operations work remotely via the voice/text bridge on a mobile device

### 3.2 Non-Functional Success Criteria

1. Agent creation completes within 10 seconds of the request
2. Graceful shutdown sends `/exit` and the agent begins terminating within 5 seconds
3. Context usage parsing returns results within 2 seconds
4. Failed operations return clear, actionable error messages (e.g., "Project not found", "Agent has no tmux pane")

---

## 4. Functional Requirements (FRs)

### Agent Creation

- **FR1:** The system shall accept a request to create a new agent for a specified project
- **FR2:** The system shall invoke the `claude-headspace` CLI to start a new Claude Code session in the project's working directory
- **FR3:** The new agent shall be registered with Claude Headspace and appear on the dashboard in idle state
- **FR4:** The system shall return the new agent's identifier upon successful creation
- **FR5:** If the specified project is not registered or its path is invalid, the system shall return an error

### Agent Shutdown

- **FR6:** The system shall accept a request to shut down a specific active agent
- **FR7:** The system shall send the `/exit` command to the agent's tmux pane via send-keys
- **FR8:** The system shall rely on Claude Code's existing hook lifecycle (session-end, stop) to update agent state in the dashboard
- **FR9:** If the agent has no tmux pane or the pane is not found, the system shall return an error indicating the agent cannot be gracefully shut down
- **FR10:** If the agent is already ended or not found, the system shall return an appropriate error

### Context Window Usage

- **FR11:** The system shall capture the agent's tmux pane content on demand and parse the context usage statusline (format: `[ctx: XX% used, XXXk remaining]`)
- **FR12:** The system shall return context usage as structured data: percentage used and tokens remaining
- **FR13:** If the statusline is not found in the pane content (e.g., agent not running, statusline not configured), the system shall return a clear indication that context data is unavailable
- **FR14:** Context usage shall be displayed on the agent card in the dashboard when requested by the user

### Dashboard UI

- **FR15:** The dashboard shall provide a control to create a new agent, with project selection
- **FR16:** Each agent card shall provide a control to shut down the agent
- **FR17:** Each agent card shall provide a control to check and display context window usage
- **FR18:** Context usage shall be displayed inline on the agent card (percentage and remaining tokens)

### Voice/Text Bridge

- **FR19:** The voice/text bridge shall support a command or intent to create a new agent for a named project
- **FR20:** The voice/text bridge shall support a command or intent to shut down a specific agent
- **FR21:** The voice/text bridge shall support a command or intent to check context usage for a specific agent or the currently-selected agent

---

## 5. Non-Functional Requirements (NFRs)

- **NFR1:** Agent creation shall be idempotent — requesting creation for a project that already has an active agent shall either return the existing agent or create an additional one (behaviour to be defined by implementation)
- **NFR2:** All API endpoints shall require the same authentication as existing voice bridge endpoints
- **NFR3:** Error responses shall be formatted consistently with existing voice bridge error patterns
- **NFR4:** All operations shall be logged at appropriate levels for debugging

---

## 6. UI Overview

### Dashboard

- **Project selector + "New Agent" button** — allows choosing a project and spinning up an agent
- **Agent card "Kill" control** — a button or action on each agent card to gracefully shut down the agent
- **Agent card "Context" indicator** — a visual display of context usage (e.g., progress bar or percentage badge) that appears when the user requests it, showing `XX% used · XXXk remaining`

### Voice/Text Bridge Chat Panel

- **Create command** — e.g., "start an agent for [project name]"
- **Kill command** — e.g., "kill [agent name/id]" or "shut down [agent]"
- **Context command** — e.g., "how much context is [agent] using?" or "check context for [agent]"
- Responses formatted consistently with existing voice bridge response patterns
