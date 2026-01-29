---
validation:
  status: valid
  validated_at: '2026-01-29T11:18:50+11:00'
---

## Product Requirements Document (PRD) — AppleScript Integration

**Project:** Claude Headspace v3.1
**Scope:** macOS iTerm2 focus integration via AppleScript
**Author:** PRD Workshop
**Status:** Draft
**Epic:** 1
**Sprint:** 12

---

## Executive Summary

The AppleScript Integration subsystem enables users to instantly navigate from the Claude Headspace dashboard to the correct iTerm2 terminal session with a single click. When a user clicks an agent card's "Headspace" button or the "Recommended Next" panel, the system executes AppleScript to activate iTerm2, locate the specific terminal pane associated with that agent, and bring it to focus.

This capability transforms the dashboard from a passive monitoring tool into an active workflow accelerator. Without it, users must manually hunt through potentially dozens of iTerm tabs and panes to find the right session—breaking flow and wasting time. With click-to-focus, one click takes them exactly where they need to be.

Success is measured by: focus latency under 500ms, correct pane activation across all window states (minimized, different Spaces), graceful handling of permission errors with actionable guidance, and fallback to session path display when focus fails.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace monitors multiple concurrent Claude Code sessions across projects. The dashboard (Sprint 8) displays agent cards showing each session's state. Sprint 11's launcher script captures iTerm2 pane identifiers during session registration, storing them in the Agent model.

Sprint 12 connects these pieces: given an agent's pane ID, execute AppleScript to focus that specific pane in iTerm2. This is the final link in the chain from "see agent needs attention" to "work on that agent."

### 1.2 Target User

Developers managing multiple Claude Code sessions who see an agent requiring attention in the dashboard and want to immediately switch to that terminal—without manually navigating through iTerm windows, tabs, and panes.

### 1.3 Success Moment

The user sees an agent card showing "Input needed" (orange state). They click the "Headspace" button. Within half a second, iTerm2 comes to the foreground with the correct pane active, cursor ready for input. The user never had to remember which window or tab contained that session.

---

## 2. Scope

### 2.1 In Scope

- API endpoint that triggers iTerm2 focus for a specific agent
- AppleScript execution to activate iTerm2 and focus a specific pane by ID
- Permission error detection (macOS Automation privacy controls)
- Graceful handling when iTerm2 is not running
- Graceful handling when pane ID is missing, invalid, or stale
- Fallback response providing session/project path for manual navigation
- Focus across macOS Spaces/Desktops (switch to correct Space)
- Restore minimized iTerm windows before focusing
- Focus event logging for debugging
- Support for macOS Monterey (12.x), Ventura (13.x), Sonoma (14.x), Sequoia (15.x)
- Support for iTerm2 version 3.4 and later

### 2.2 Out of Scope

- WezTerm or other terminal emulator support (future epic)
- Linux or Windows support (macOS only in Epic 1)
- Dashboard UI changes (handled by Sprint 8b)
- Pane ID capture logic (handled by Sprint 11 launcher script)
- System notifications via AppleScript (separate feature)
- Sending text or commands to iTerm sessions (different capability)
- Auto-detection of installed terminal emulator (iTerm2 assumed)
- Terminal emulator selection UI
- API authentication (localhost only, per Epic 1 decisions)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| SC1 | API endpoint accepts agent ID and triggers focus | POST `/api/focus/<agent_id>` returns 200 on success |
| SC2 | Correct iTerm pane is activated | Pane matching stored `iterm_pane_id` receives focus |
| SC3 | Focus works when iTerm is on different Space | System switches to correct macOS Space/Desktop |
| SC4 | Focus restores minimized windows | Minimized iTerm window is restored and focused |
| SC5 | Permission errors return actionable message | Response includes guidance to grant Automation permission |
| SC6 | Missing pane ID returns fallback path | Response includes project/working directory path |
| SC7 | Invalid/stale pane ID handled gracefully | Error response with session path, no crash or hang |
| SC8 | iTerm not running returns appropriate error | Clear message indicating iTerm2 is not running |
| SC9 | Unknown agent returns 404 | Non-existent agent_id returns 404 status |
| SC10 | Focus attempts are logged | Event written to event log for each focus attempt |

### 3.2 Non-Functional Success Criteria

| # | Criterion | Target |
|---|-----------|--------|
| NFR1 | Focus latency | < 500ms from API call to iTerm window activation |
| NFR2 | No blocking on failure | API returns within 2 seconds even if AppleScript hangs |
| NFR3 | macOS version support | Works on Monterey (12.x), Ventura (13.x), Sonoma (14.x), Sequoia (15.x) |
| NFR4 | iTerm2 version support | Works on iTerm2 3.4.x and later |

---

## 4. Functional Requirements (FRs)

### API Endpoint

**FR1:** The application provides a `POST /api/focus/<agent_id>` endpoint that triggers focus for the specified agent's terminal session.

**FR2:** The endpoint accepts `agent_id` as a path parameter (integer, the database ID of the agent).

**FR3:** On successful focus, the endpoint returns HTTP 200 with response body:
```json
{
  "status": "ok",
  "agent_id": 42,
  "pane_id": "pty-12345"
}
```

**FR4:** On failure, the endpoint returns an appropriate HTTP status with response body:
```json
{
  "status": "error",
  "error_type": "permission_denied|pane_not_found|iterm_not_running|agent_not_found|unknown",
  "message": "Human-readable error message",
  "fallback_path": "/path/to/project (if available)"
}
```

**FR5:** The endpoint returns HTTP 404 when the specified `agent_id` does not exist in the database.

### Focus Behaviour

**FR6:** When focus is triggered, the system activates the iTerm2 application, bringing it to the foreground.

**FR7:** The system locates the specific pane matching the agent's stored `iterm_pane_id` across all iTerm2 windows and tabs.

**FR8:** The system activates the window and tab containing the target pane, and selects that pane as the active session.

**FR9:** When iTerm2 is on a different macOS Space/Desktop, the system switches to that Space as part of the focus operation.

**FR10:** When the iTerm2 window is minimized to the Dock, the system restores the window before focusing.

**FR11:** The focus operation has a timeout to prevent indefinite blocking if AppleScript hangs.

### Error Handling

**FR12:** When the agent exists but has no `iterm_pane_id` stored, the endpoint returns an error with `error_type: "pane_not_found"` and includes the agent's project path as `fallback_path`.

**FR13:** When the stored `iterm_pane_id` cannot be found in iTerm2 (stale/closed pane), the endpoint returns an error with `error_type: "pane_not_found"` and includes the fallback path.

**FR14:** When iTerm2 is not running, the endpoint returns an error with `error_type: "iterm_not_running"` and message suggesting to start iTerm2.

**FR15:** When macOS Automation permissions have not been granted, the endpoint returns an error with `error_type: "permission_denied"` and message guiding the user to System Settings → Privacy & Security → Automation.

**FR16:** For any other AppleScript execution failure, the endpoint returns an error with `error_type: "unknown"` and includes available diagnostic information.

### Fallback Behaviour

**FR17:** All error responses for existing agents include a `fallback_path` field containing the agent's working directory or project path.

**FR18:** The fallback path enables the dashboard to display "Session at: /path/to/project" so users can manually navigate if automatic focus fails.

### Event Logging

**FR19:** Each focus attempt (success or failure) is logged to the event system with event type `focus_attempted`.

**FR20:** The focus event payload includes: agent_id, pane_id (if available), outcome (success/failure), error_type (if failed), latency_ms.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The focus operation completes within 500ms under normal conditions (iTerm2 running, valid pane ID, permissions granted).

**NFR2:** The API endpoint returns within 2 seconds even if the underlying AppleScript execution hangs or times out.

**NFR3:** The focus functionality works on macOS Monterey (12.x), Ventura (13.x), Sonoma (14.x), and Sequoia (15.x).

**NFR4:** The focus functionality works with iTerm2 version 3.4.x and later.

**NFR5:** AppleScript execution failures do not crash the Flask application or leave zombie processes.

**NFR6:** The focus service is stateless and handles concurrent requests safely.

---

## 6. Integration Points

### 6.1 Sprint 11 (Launcher Script) - Upstream

Sprint 11 captures the iTerm2 pane ID during session registration and stores it in:
- `Agent.iterm_pane_id` (database model)
- `RegisteredSession.iterm_pane_id` (in-memory registry)

This PRD consumes that pane ID to perform focus operations.

### 6.2 Sprint 8b (Dashboard Interactivity) - Downstream

Sprint 8b's PRD specifies the dashboard integration (FR21-FR25):
- "Headspace" button click triggers `POST /api/focus/<agent_id>`
- Success: brief visual highlight on agent card
- Failure: toast notification with error message

The error response format in this PRD (FR4) aligns with Sprint 8b's expected error types:
- `permission_denied` → "Grant iTerm automation permission in System Preferences"
- `pane_not_found` / `agent_not_found` → "Session ended - cannot focus terminal"
- `iterm_not_running` / `unknown` → "Could not focus terminal - check if iTerm is running"

### 6.3 Event System (Sprint 5) - Logging

Focus events are written to the event log using the event system established in Sprint 5, enabling debugging and audit trail for focus operations.

---

## 7. Tech Context (Implementation Guidance)

This section provides technical context for implementers. These are not requirements but guidance on patterns and constraints.

### 7.1 AppleScript Execution

macOS provides the `osascript` command for executing AppleScript. iTerm2 exposes an AppleScript dictionary for window, tab, and session manipulation. Key operations:
- `activate` brings iTerm2 to foreground
- Session/pane identification via TTY name or session ID
- Window and tab traversal to locate target pane

### 7.2 Pane ID Format

Sprint 11 captures pane IDs in a format like `pty-12345` or iTerm's session GUID. The AppleScript must match this identifier against iTerm2's session objects.

### 7.3 Permission Detection

When macOS Automation permissions are not granted, AppleScript execution fails with a specific error. This error should be detected and mapped to the `permission_denied` error type.

### 7.4 Timeout Handling

AppleScript can hang if iTerm2 is unresponsive. Implementation should use subprocess timeout or similar mechanism to ensure the API returns within the NFR2 target (2 seconds).

### 7.5 File Locations (Suggested)

| File | Purpose |
|------|---------|
| `src/claude_headspace/services/iterm_focus.py` | AppleScript execution service |
| `src/claude_headspace/routes/focus.py` | API endpoint |
| `tests/services/test_iterm_focus.py` | Unit tests for focus service |
| `tests/routes/test_focus.py` | Integration tests for API endpoint |

---

## 8. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| **Sprint 11: Launcher Script** | Hard | Provides `iterm_pane_id` in Agent model |
| **Sprint 8b: Dashboard Interactivity** | Soft | Consumes this API; can be developed in parallel |
| **Sprint 5: Event System** | Soft | For logging focus events; can stub if not ready |
| **Sprint 3: Domain Models** | Hard | Agent model must exist |
| macOS with iTerm2 installed | Runtime | Required for actual focus operations |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| macOS privacy controls block AppleScript | High | Detect permission errors, return actionable guidance |
| iTerm2 pane IDs change between sessions | Medium | Handle stale IDs gracefully, provide fallback path |
| AppleScript execution is slow or hangs | Medium | Implement timeout, ensure API returns within 2 seconds |
| Different iTerm2 versions have different AppleScript APIs | Low | Test on multiple versions, document supported versions |
| Users don't grant Automation permissions | Medium | Clear error message with exact System Settings path |

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial draft |
