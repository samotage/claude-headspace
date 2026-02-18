---
validation:
  status: valid
  validated_at: '2026-01-29T11:22:52+11:00'
---

## Product Requirements Document (PRD) — Hook Receiver

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 13 — Claude Code Hooks Integration
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace currently monitors Claude Code sessions via a 2-second polling loop that infers agent state from terminal output. This approach has 0-2 second latency and 30-90% confidence. The Hook Receiver subsystem enables Claude Headspace to receive lifecycle events directly from Claude Code via hooks, providing instant (<100ms) state updates with 100% confidence.

This capability transforms the dashboard from "delayed inference" to "real-time truth" — users see agent state changes the moment they happen. The system implements a hybrid approach where hooks are the primary event source with polling as a fallback, ensuring reliability even when hooks aren't installed or are temporarily unavailable.

The Hook Receiver completes Epic 1's event-driven architecture by adding a high-confidence event source alongside existing polling, delivering the core differentiator: dual event sources for instant, certain state updates.

---

## 1. Context & Purpose

### 1.1 Context

Claude Code supports lifecycle hooks that fire on significant events (session start, prompt submit, turn complete, session end). These hooks can execute shell commands, enabling external systems to receive instant notifications of state changes.

Currently, Claude Headspace relies solely on polling the Claude Code jsonl files every 2 seconds and inferring state from content patterns. While functional, this approach:
- Has inherent latency (0-2 seconds)
- Requires inference (uncertain)
- Can miss fast state transitions between polls
- Consumes resources constantly

Hook events solve these problems by providing direct, instant, certain signals from Claude Code itself.

### 1.2 Target User

Developers using Claude Headspace to monitor multiple Claude Code sessions who want:
- Instant visibility into agent state changes
- Confidence that displayed states are accurate
- Reduced system resource usage
- A working system even without hook setup (graceful degradation)

### 1.3 Success Moment

The user submits a prompt to Claude Code and sees the dashboard update to "PROCESSING" within 100ms — not 2 seconds later. They know with certainty the state is accurate because it came directly from Claude Code, not from inference.

---

## 2. Scope

### 2.1 In Scope

- **Hook event reception** — Receive and process lifecycle events from Claude Code (session-start, session-end, stop, notification, user-prompt-submit)
- **Session correlation** — Match Claude Code sessions to tracked agents
- **State updates from hooks** — Update agent/command state based on hook events with high confidence
- **Hook configuration** — Enable/disable hooks, configure fallback behavior
- **Hybrid mode** — Use hooks as primary event source with polling fallback
- **Graceful degradation** — Continue functioning when hooks are unavailable
- **Hook notification script** — Provide script for Claude Code to call on hook events
- **Installation tooling** — Script to configure hooks on user's machine
- **Hook status display** — Show hook receiver health on Logging tab
- **Agent card freshness** — Display "last active" time on agent cards

### 2.2 Out of Scope

- Hook authentication (local-only deployment, trust localhost for Epic 1)
- WezTerm or other terminal support (iTerm2 only in Epic 1)
- Hook events triggering LLM inference (deferred to Epic 3)
- Multi-user hook isolation (single-user local deployment)
- Remote hook endpoints (localhost only)
- Turn intent detection from hook events (existing state machine handles this)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1:** Hook events received at endpoints update agent state within 100ms
2. **SC2:** State updates from hooks are recorded with high confidence (not inferred)
3. **SC3:** System gracefully degrades to frequent polling when hooks are silent for extended period
4. **SC4:** Installation script successfully configures hooks on a clean macOS installation
5. **SC5:** Hook receiver status is visible on the Logging tab
6. **SC6:** Agent cards display "last active" time showing data freshness

### 3.2 Non-Functional Success Criteria

1. **NFR1:** Hook endpoints respond within 50ms (excluding downstream processing)
2. **NFR2:** Hook script failures do not block or slow Claude Code sessions
3. **NFR3:** System remains functional when hooks are not installed
4. **NFR4:** Installation script uses absolute paths (not ~ or $HOME) for Claude Code compatibility

---

## 4. Functional Requirements (FRs)

### Hook Event Reception

**FR1:** System shall provide API endpoints to receive hook events from Claude Code:
- Session started
- Session ended
- Agent turn completed (stop)
- Notification received
- User prompt submitted

**FR2:** System shall provide an endpoint to query hook receiver status including last event times and current mode.

**FR3:** System shall validate incoming hook event payloads and reject malformed requests.

### Session Correlation

**FR4:** System shall correlate incoming Claude Code session identifiers to tracked agents.

**FR5:** System shall handle new sessions by creating agents when no correlation exists.

**FR6:** System shall handle multiple sessions in the same working directory appropriately.

### State Management

**FR7:** System shall update agent state based on hook events:
- Session start → Agent created/activated, idle state
- User prompt submit → Agent transitions to processing
- Stop (turn complete) → Agent transitions to idle
- Session end → Agent marked inactive

**FR8:** System shall record hook-originated state updates with high confidence indicator.

**FR9:** System shall emit events for downstream consumers (SSE, event log) when state changes.

### Hybrid Mode

**FR10:** System shall use hooks as the primary event source when available.

**FR11:** System shall use infrequent polling for reconciliation when hooks are active.

**FR12:** System shall detect when hooks become silent and increase polling frequency.

**FR13:** System shall return to infrequent polling when hook activity resumes.

### Hook Script & Installation

**FR14:** System shall provide a notification script that Claude Code hooks can execute.

**FR15:** Notification script shall send hook events to the application via HTTP.

**FR16:** Notification script shall fail silently without blocking Claude Code.

**FR17:** System shall provide an installation script that:
- Creates the notification script in the appropriate location
- Updates Claude Code settings with hook configuration
- Validates that paths are absolute
- Sets appropriate file permissions

**FR18:** System shall provide a settings template for Claude Code hook configuration.

### User Interface

**FR19:** Logging tab shall display hook receiver status:
- Whether hooks are enabled
- Last hook event timestamp
- Current mode (hooks active vs polling fallback)

**FR20:** Agent cards shall display "last active" time showing how recently the agent had activity.

**FR21:** "Last active" time shall update in real-time via SSE.

### Configuration

**FR22:** System shall support configuration options for:
- Enabling/disabling hook reception
- Polling interval when hooks are active
- Timeout before falling back to frequent polling

**FR23:** Configuration shall support environment variable overrides.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Hook endpoints shall respond within 50ms (p95) excluding downstream processing.

**NFR2:** Hook notification script shall timeout and exit cleanly if the application is unavailable.

**NFR3:** Hook notification script shall always exit with success status to avoid blocking Claude Code.

**NFR4:** Installation script shall validate paths are absolute before writing configuration.

**NFR5:** System shall log hook events for debugging and audit purposes.

**NFR6:** System shall handle concurrent hook events from multiple sessions.

---

## 6. UI Overview

### 6.1 Logging Tab — System Status Section

New section at the top of the Logging tab:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ SYSTEM STATUS                                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Hook Receiver: ● Enabled          Last Event: 3s ago                    │
│ Mode: Hooks active (reconciliation polling)                             │
└─────────────────────────────────────────────────────────────────────────┘
```

**States:**
- "● Enabled" (green) — Hooks configured and receiving events
- "○ Disabled" (grey) — Hooks not configured
- "● Fallback" (yellow) — Hooks silent, using frequent polling

### 6.2 Agent Card — Last Active Time

Addition to existing agent card:

```
│ 01  ● ACTIVE  #2e3fe060  up 32h 38m  active 3s ago       [Headspace]    │
                                       ▲
                                       └── Time since last activity
```

**Format:**
- "active Xs ago" — seconds (< 60s)
- "active Xm ago" — minutes (< 60m)
- "active Xh ago" — hours (≥ 60m)

---

## 7. Technical Context

*This section provides implementation guidance for engineers. These are not requirements but rather decisions and patterns to follow.*

### 7.1 Hook Event to State Mapping

| Hook Event | Current State | New State | Notes |
|------------|---------------|-----------|-------|
| SessionStart | — | idle | Create agent if not exists |
| UserPromptSubmit | idle | processing | Start task turn |
| Stop | processing | idle | Complete task turn |
| Notification | any | (no change) | Update timestamp only |
| SessionEnd | any | ended | Mark agent inactive |

### 7.2 Session Correlation Strategy

Claude Code's `$CLAUDE_SESSION_ID` differs from terminal pane IDs. Correlation uses working directory matching:
1. Check if Claude session ID has been seen before (cache lookup)
2. Match by working directory to existing agents
3. Create new agent if no match found

### 7.3 Hybrid Mode Intervals

- **Hooks active:** Polling every 60 seconds (reconciliation only)
- **Hooks silent:** After 300 seconds of silence, revert to 2-second polling
- **Hooks resume:** Return to 60-second polling

### 7.4 Hook Script Behavior

- Connect timeout: 1 second
- Maximum request time: 2 seconds
- Exit status: Always 0 (success) to avoid blocking Claude Code
- Uses environment variables: `$CLAUDE_SESSION_ID`, `$CLAUDE_WORKING_DIRECTORY`

### 7.5 Configuration Defaults

```yaml
hooks:
  enabled: true
  polling_interval_with_hooks: 60  # seconds
  fallback_timeout: 300  # seconds before reverting to fast polling
```

### 7.6 File Locations

- Hook script: `~/.claude/hooks/notify-headspace.sh`
- Claude Code settings: `~/.claude/settings.json`
- Settings template: `docs/claude-code-hooks-settings.json`

---

## 8. Dependencies

### 8.1 Sprint Dependencies

- **Sprint 5 (Event System):** Event writer, event schemas, background process — **Complete**
- **Sprint 6 (State Machine):** Command state transitions — **Required** (not yet implemented)
- **Sprint 8 (Dashboard UI):** Agent cards, Logging tab — **Required** (not yet implemented)

### 8.2 External Dependencies

- Claude Code hooks feature (available in current Claude Code versions)
- macOS with bash shell (for hook script)

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users don't install hooks | Medium | Graceful degradation to polling; clear value proposition in docs |
| Hook events arrive out of order | Low | State machine validates transitions; reject invalid |
| Multiple sessions in same directory | Low | Last-matched wins; document limitation |
| Installation script fails | Medium | Clear error messages; manual installation fallback documented |
| Hook endpoint unavailable | Low | Silent failures in hook script; polling continues |

---

## 10. Acceptance Tests

### AT1: Hook Event Reception
- POST to `/hook/session-start` → agent created with idle state
- POST to `/hook/user-prompt-submit` → agent transitions to processing
- POST to `/hook/stop` → agent transitions to idle
- POST to `/hook/session-end` → agent marked inactive
- GET `/hook/status` → returns last event times and mode

### AT2: Session Correlation
- Same Claude session ID maps to same agent on repeated events
- New session in known directory correlates to existing agent
- New session in unknown directory creates new agent

### AT3: Hybrid Mode
- Hooks active → polling interval is 60 seconds
- Hooks silent >300s → polling interval reverts to 2 seconds
- Hooks resume → polling interval returns to 60 seconds

### AT4: Installation
- `bin/install-hooks.sh` creates `~/.claude/hooks/notify-headspace.sh`
- Script is executable
- `~/.claude/settings.json` updated with hook configuration
- Paths in settings are absolute (not ~ or $HOME)

### AT5: UI Updates
- Logging tab shows hook receiver status
- Agent cards show "last active" time
- "Last active" updates in real-time via SSE

### AT6: End-to-End
- Start Claude Code with hooks installed
- SessionStart hook fires → agent appears in dashboard
- Send prompt → UserPromptSubmit fires → state shows processing
- Claude responds → Stop fires → state shows idle
- Exit Claude → SessionEnd fires → agent marked inactive

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial draft from workshop |
