---
validation:
  status: valid
  validated_at: '2026-02-02T21:39:24+11:00'
---

## Product Requirements Document (PRD) — Input Bridge: Remote Session Interaction via claude-commander

**Project:** Claude Headspace
**Scope:** Dashboard-to-terminal input path for responding to Claude Code sessions remotely
**Author:** samotage (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Code frequently blocks on permission prompts that require physical terminal interaction. The Headspace dashboard already detects these prompts — displaying amber "Input needed" cards, broadcasting via SSE, and sending macOS notifications — but provides no return path. The user sees the problem but must context-switch to iTerm to respond.

Input Bridge closes this loop by allowing users to send text responses to Claude Code sessions directly from the Headspace dashboard. It uses claude-commander (claudec), a Rust binary that wraps Claude Code in a pseudo-terminal and exposes a Unix domain socket for programmatic text injection. Both terminal keyboard input and dashboard-injected input write to the same PTY, so the terminal remains fully interactive for desk use while the dashboard provides a second input channel for remote use.

This is Phase 1 of the broader Voice Bridge vision. The commander service built here becomes the session-targeting mechanism for future voice input (Phase 2) and voice output (Phase 3), replacing the previously considered tmux approach with socket injection.

---

## 1. Context & Purpose

### 1.1 Context

Managing multiple concurrent Claude Code sessions across projects means frequent context-switching to respond to permission prompts. This is disruptive when:

- Multiple agents are running and several need simple "yes" responses
- The user is away from the desk (phone, couch, walking)
- The user is in flow on a different task and an agent needs a one-word answer

The Headspace dashboard already has complete detection infrastructure (PermissionRequest hooks, AWAITING_INPUT state, SSE broadcast, amber card state, macOS notifications). Only the response path is missing.

### 1.2 Target User

The primary user is someone running multiple Claude Code sessions simultaneously via the Headspace dashboard, who wants to respond to agent prompts without leaving their current context.

### 1.3 Success Moment

The user sees an amber "Input needed" card on the dashboard, reads the permission question, taps a quick-action button ("1" / "Yes"), sees confirmation that the response was sent, and the agent resumes — all without switching to iTerm.

---

## 2. Scope

### 2.1 In Scope

- Users can send text responses to Claude Code sessions from the Headspace dashboard
- Quick-action buttons for numbered permission choices (parsed from question text)
- Free-text input for arbitrary responses
- Visual feedback on send success/failure
- Graceful degradation when no commander socket is available
- Audit trail — responses recorded as Turn entities
- Commander socket health checking and availability detection
- SSE event when commander availability changes for an agent
- Documentation for launching sessions with the `claudec` wrapper

### 2.2 Out of Scope

- Voice input/output (Voice Bridge Phase 2-3)
- Mobile-optimized PWA view
- Auto-approval rules or smart permission handling
- Output capture via socket (hooks already handle output awareness)
- Multi-user authentication
- Remote access beyond local network
- Raw key sequence UI (service may support it, dashboard does not expose it)
- Auto-detection/scanning of socket files on the filesystem
- Modifications to claude-commander itself

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User can respond to a permission prompt from the dashboard without switching to iTerm
2. iTerm terminal remains fully interactive — keyboard input works simultaneously with dashboard input
3. Quick-action buttons appear for numbered permission choices when the pattern is detectable in the question text
4. Free-text input is available for arbitrary responses
5. Visual feedback confirms the response was sent (or shows a clear error)
6. Dashboard degrades gracefully when commander socket is unavailable — no respond UI shown, focus button still works
7. Responses are recorded as Turn entities in the audit trail

### 3.2 Non-Functional Success Criteria

1. Response delivery from button click to Claude Code receipt within 500ms under normal conditions
2. No silent failures — every error scenario produces a visible, understandable message to the user
3. Commander service availability is checked and broadcast so the UI reflects current state without page refresh

---

## 4. Functional Requirements (FRs)

### Commander Communication

**FR1:** The system can send text followed by a newline (simulating "type and press Enter") to a Claude Code session's commander socket.

**FR2:** The system can check whether a commander socket is available and healthy for a given agent.

**FR3:** The system derives the commander socket path from the agent's session identifier using the claude-commander naming convention.

### Response Endpoint

**FR4:** The dashboard can submit a text response targeted at a specific agent via an API endpoint.

**FR5:** Submitting a response creates a Turn record (actor: USER, intent: ANSWER) with the response text for audit trail purposes.

**FR6:** Submitting a response triggers the appropriate state transition (AWAITING_INPUT to PROCESSING) via the existing state machine.

**FR7:** The API validates that the target agent exists, is in AWAITING_INPUT state, and has a reachable commander socket before attempting to send.

### Dashboard Input UI

**FR8:** When an agent is in AWAITING_INPUT state AND a commander socket is available, the agent card displays an input widget.

**FR9:** The input widget parses numbered options from the question text when the pattern is detectable (e.g., "1. Yes / 2. No / 3. Cancel") and displays quick-action buttons for each option.

**FR10:** When no numbered pattern is detected, or in addition to quick-action buttons, a free-text input field with a send button is available.

**FR11:** After sending a response, the UI provides visual confirmation of success (e.g., highlight animation) or displays an error message on failure (e.g., toast notification).

**FR12:** When no commander socket is available for an agent, the input widget is not shown — the card displays only the existing focus button and question text.

### Commander Availability

**FR13:** Commander socket availability is checked when an agent session starts and periodically thereafter.

**FR14:** Changes in commander availability are broadcast via SSE so the dashboard can show or hide the input widget without page refresh.

### Error Handling

**FR15:** If the commander socket exists but the process has died, the user sees a clear error message indicating the session is unreachable.

**FR16:** If a response is sent but Claude Code has already moved past the prompt (race condition), the system handles this gracefully — the text is delivered (socket is input-only, no prompt awareness) and the state transition reflects reality on the next hook event.

**FR17:** If an agent is in AWAITING_INPUT but has no `claude_session_id` (socket path cannot be derived), the input widget is not shown.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Response delivery latency from user action to Claude Code receipt is under 500ms for local Unix socket communication.

**NFR2:** The commander service follows the existing service registration pattern and is accessible via the application extensions registry.

**NFR3:** The commander service is resilient to socket connection failures — errors are caught, logged, and surfaced to the user without crashing the server.

**NFR4:** The input widget does not degrade the existing dashboard experience — agents without commander sockets behave exactly as they do today.

---

## 6. UI Overview

### Agent Card — AWAITING_INPUT State with Commander Available

The existing agent card in AWAITING_INPUT state (amber state bar, "Input needed" label, question text on line 04) is extended with an input region:

- **Quick-action buttons:** When the question text contains numbered options (e.g., "1. Yes 2. Allow all 3. No"), display a horizontal row of buttons labeled with each option. Clicking a button sends the option number.
- **Free-text input:** A text field with a send button, always available alongside or below quick-action buttons. Supports typing an arbitrary response and submitting.
- **Send feedback:** On success, brief visual confirmation (consistent with existing focus success feedback). On error, toast-style error message (consistent with existing focus error feedback).

### Agent Card — AWAITING_INPUT State without Commander

Identical to current behavior: amber state bar, question text displayed, focus button to switch to iTerm. No input widget shown.

### Agent Card — Other States

No change. Input widget only appears during AWAITING_INPUT with commander available.

---

## 7. Technical Context (for implementer)

This section provides implementation-relevant context. These are not requirements — the implementer may choose different approaches that satisfy the functional requirements above.

### claude-commander (claudec)

- **Repository:** https://github.com/sstraus/claude-commander
- **Version:** v0.1.0 (released January 30, 2026)
- **Binary:** ~600KB Rust binary using portable-pty crate (from wezterm)
- **Mechanism:** Wraps Claude Code in a PTY pair. Socket input and keyboard input both write to the PTY master. Claude Code on the PTY slave cannot distinguish the two sources.
- **Socket path convention:** `/tmp/claudec-<SESSION_ID>.sock`
- **Socket protocol:** Newline-delimited JSON over Unix domain socket

```json
// Send text + press Enter
{"action": "send", "text": "1"}
// Response: {"status": "sent"}

// Health check
{"action": "status"}
// Response: {"running": true, "socket": "/tmp/claudec-xxx.sock", "pid": 12345}
```

- **Limitations:** Input-only socket (no output capture), ~2-5 second startup delay before socket is available, no authentication beyond Unix file permissions, session detection relies on Claude Code banner string.
- **Risk posture:** Very new project, single developer. The socket protocol is simple enough that if the project is abandoned, the mechanism (~200 lines of Rust) could be forked or replaced. If Anthropic adds native IPC support, claude-commander can be swapped out.

### Existing Infrastructure to Leverage

- **Permission detection:** `hook_receiver.py` → `_handle_awaiting_input()` → Turn(AGENT/QUESTION) → SSE broadcast
- **State machine:** `(AWAITING_INPUT, USER, ANSWER) → PROCESSING` transition already defined
- **iTerm focus pattern:** `iterm_focus.py` + `routes/focus.py` + `focus-api.js` — service + route + client pattern to follow
- **Session correlation:** `claude_session_id` on Agent model maps to socket path
- **SSE broadcasting:** `broadcaster.py` handles real-time event distribution to dashboard clients

### Connection to Voice Bridge

This is Phase 1 of the Voice Bridge roadmap:

1. **Phase 1 — Input Bridge (this PRD):** Dashboard buttons/text → commander service → Unix socket → Claude Code
2. **Phase 2 — Voice Capture:** Web Speech API → transcription → commander service (same path)
3. **Phase 3 — Voice Output:** Summarisation service → TTS → hands-free loop

The commander service built here replaces tmux as the session input mechanism for the Voice Bridge vision (see `docs/ideas/VOICE_BRIDGE_OUTLINE_PROMPT.md`).
