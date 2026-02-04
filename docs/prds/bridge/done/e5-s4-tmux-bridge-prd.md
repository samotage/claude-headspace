---
validation:
  status: valid
  validated_at: '2026-02-04T22:00:00+11:00'
---

## Product Requirements Document (PRD) — tmux Bridge: Replace Commander Socket with tmux send-keys

**Project:** Claude Headspace
**Scope:** Replace the non-functional claude-commander socket bridge with a tmux-based input bridge using iTerm2 native tmux integration
**Author:** samotage (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

The Input Bridge (e5-s1) established the dashboard's ability to send responses to Claude Code sessions, but its transport mechanism — claude-commander's Unix domain socket injection — failed in practice. Claude Code's Ink-based TUI treats programmatic stdin (`\r`/`\n` via socket) differently from physical keyboard input, preventing prompt submission.

A proof of concept confirmed that `tmux send-keys` reliably triggers Ink's `onSubmit` handler, making it the only verified programmatic input method. iTerm2's native tmux integration (`tmux -CC`) preserves full terminal ergonomics (scrollback, copy/paste, Cmd+F, native tabs/splits) while enabling `send-keys` targeting from the Headspace Flask server.

This PRD replaces the commander socket transport layer with tmux subprocess calls. The existing dashboard respond UI, API contracts, SSE events, state machine transitions, and audit trail are all preserved — only the mechanism that delivers text to the Claude Code process changes.

---

## 1. Context & Purpose

### 1.1 Context

The e5-s1 Input Bridge built the full respond pipeline: dashboard UI with quick-action buttons and free-text input, API endpoint (`POST /api/respond/<agent_id>`), state transitions (AWAITING_INPUT -> PROCESSING), Turn audit records, and SSE broadcasting. All of this works correctly.

The single point of failure is the transport: `commander_service.py` sends JSON over Unix domain sockets to the `claudec` binary, which wraps Claude Code in a PTY. However, Claude Code's Ink library distinguishes between physical keypresses and programmatic input — socket-injected newlines do not trigger prompt submission. This is a fundamental incompatibility that cannot be fixed by the dashboard.

Community testing ([Claude Code Issue #15553](https://github.com/anthropics/claude-code/issues/15553)) and a local proof of concept (February 2026, Claude Code v2.1.29) confirmed that `tmux send-keys` is the exception — it sends keystrokes through tmux's PTY layer at a level Ink recognises as genuine keyboard input.

### 1.2 Target User

The same user as e5-s1: someone running multiple Claude Code sessions via the Headspace dashboard who wants to respond to agent prompts without context-switching to iTerm.

### 1.3 Success Moment

The user sees an amber "Input needed" card on the dashboard, taps a quick-action button, and the response is delivered to Claude Code via `tmux send-keys` — the agent resumes processing. The experience is identical to e5-s1's vision, but now it actually works.

---

## 2. Scope

### 2.1 In Scope

- New `tmux_bridge.py` service wrapping tmux CLI commands (`send-keys`, `list-panes`, `capture-pane`, `has-session`) as subprocess calls
- Replace `commander_service.py` socket-based send/health logic with tmux subprocess calls, preserving existing result types (`SendResult`, `HealthResult`)
- Replace `commander_availability.py` socket-probing with tmux pane existence checks
- Add `tmux_pane_id` field to Agent model (new Alembic migration)
- Update `bin/notify-headspace.sh` to extract and include `$TMUX_PANE` in hook payloads
- Update `hook_receiver.py` to extract and store pane ID on the Agent model
- Update hook routes to pass tmux pane ID through to the hook receiver
- Update `routes/respond.py` to target agents by tmux pane ID
- Update availability endpoint to use tmux-based checks
- Update `config.yaml` to replace `commander:` section with `tmux_bridge:` section
- Replace `CommanderErrorType` enum with tmux-specific error types
- Targeted tests for new service, updated routes, and updated services

### 2.2 Out of Scope

- Dashboard UI changes (respond widget, quick-action buttons, free-text input — all already working from e5-s1)
- Dashboard JavaScript changes (client-side code is unchanged)
- SSE/broadcaster layer changes
- Automated session creation/launch (users manually launch Claude Code in tmux sessions)
- Voice bridge phases 2-3 (voice capture, voice output)
- Auto-discovery of tmux sessions not launched via hooks
- Removal of the `claudec` binary or claude-commander references from documentation
- Changes to the iTerm focus service (`iterm_focus.py`) — it uses `iterm_pane_id`, a separate concern
- Mobile or remote access beyond local network

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User can respond to a permission prompt from the dashboard and the response is delivered to Claude Code via `tmux send-keys`, triggering prompt submission
2. Dual input works — user typing directly in the iTerm2 tmux session and dashboard respond coexist without interference
3. Hook scripts pass `$TMUX_PANE` and the pane ID is persisted on the Agent model as `tmux_pane_id`
4. Availability checks correctly detect whether a tmux pane exists and is running Claude Code
5. The API contract (`POST /api/respond/<agent_id>`) is unchanged — existing dashboard JS works without modification
6. SSE events for commander availability changes continue to fire when tmux pane status changes

### 3.2 Non-Functional Success Criteria

1. Response delivery from dashboard button click to Claude Code receipt within 500ms (subprocess overhead is minimal for local tmux)
2. No silent failures — every tmux subprocess error produces a visible, understandable message to the user
3. The `tmux_pane_id` field coexists with the existing `iterm_pane_id` field — the iTerm focus service is unaffected

---

## 4. Functional Requirements (FRs)

### tmux Bridge Service

**FR1:** The system can send literal text to a Claude Code session's tmux pane via `tmux send-keys -t <pane_id> -l "<text>"`. Pane IDs have the format `%N` (e.g., `%0`, `%5`, `%12`).

**FR2:** The system can send special keys (Enter, Escape, Up, Down, C-c, C-u) to a tmux pane via `tmux send-keys -t <pane_id> <key>`.

**FR3:** Text send and Enter send are separate operations with a configurable delay between them (default 100ms) to prevent race conditions.

**FR4:** The system can check whether a tmux pane exists and whether Claude Code is running in it, at two levels:
- **Pane exists:** `tmux list-panes -a -F '#{pane_id}' | grep -q '%N'` — the pane is still open in tmux.
- **Claude Code running:** Check `pane_current_command` (via `tmux list-panes -a -F '#{pane_id} #{pane_current_command}'`) for `claude` or `node` to verify Claude Code is actually running (not just an idle shell after Claude Code exited).
The health check reports both `available` (pane exists) and `running` (Claude Code process detected).

**FR5:** The system can capture the last N lines of a tmux pane's visible content via `tmux capture-pane` for readiness detection.

**FR6:** The system can list all tmux panes with metadata (pane ID, session name, current command, working directory).

### Error Types

**FR21:** The `CommanderErrorType` enum is replaced with a `TmuxBridgeErrorType` enum containing tmux-specific error types:
- `PANE_NOT_FOUND` — the tmux pane ID doesn't exist (pane was closed or session killed)
- `TMUX_NOT_INSTALLED` — the `tmux` binary is not found on `PATH`
- `SUBPROCESS_FAILED` — tmux subprocess returned a non-zero exit code
- `NO_PANE_ID` — agent has no `tmux_pane_id` set (replaces the socket-era `NO_SESSION_ID`)
- `TIMEOUT` — subprocess exceeded the configured timeout (preserved from commander)
- `SEND_FAILED` — text was sent but confirmation could not be verified (preserved from commander)
- `UNKNOWN` — catch-all for unexpected errors (preserved from commander)

**FR22:** The `SendResult` and `HealthResult` namedtuple shapes are preserved — same field names, same types — but their `error_type` field references `TmuxBridgeErrorType` instead of `CommanderErrorType`. This ensures the respond route's error-to-HTTP-status mapping logic requires only an enum name change, not a structural rewrite.

### Configuration

**FR23:** The `commander:` section in `config.yaml` is replaced with a `tmux_bridge:` section containing:
```yaml
tmux_bridge:
  health_check_interval: 30      # seconds between background health checks
  subprocess_timeout: 5          # seconds, timeout for tmux CLI calls
  text_enter_delay_ms: 100       # ms delay between text send and Enter send
  sequential_send_delay_ms: 150  # ms delay between rapid sequential sends
```
The `socket_timeout` and `socket_path_prefix` keys are removed as they have no tmux equivalent.

### Agent Model

**FR7:** The Agent model has a `tmux_pane_id` field (nullable string) that stores the tmux pane ID (format: `%0`, `%1`, etc.).

**FR8:** The `tmux_pane_id` field coexists alongside the existing `iterm_pane_id` field — they serve different purposes (tmux targeting vs iTerm focus).

### Hook Integration

**FR9:** The `bin/notify-headspace.sh` hook script extracts the `$TMUX_PANE` environment variable and includes it in **every** hook event payload (not just session-start), providing redundant pane ID discovery. The payload field name is `"tmux_pane"` (string, e.g., `"%5"`). Example payload:
```json
{"session_id": "abc123", "tmux_pane": "%5", "working_directory": "/path/to/project"}
```
The `bin/install-hooks.sh` script does NOT need changes — it installs the notify script; only the script itself is updated.

**FR10:** Hook routes (`routes/hooks.py`) extract the `tmux_pane` field from the payload via `data.get("tmux_pane")` and pass it through to the hook receiver service. Specifically:
- `hook_session_start()` extracts `tmux_pane` and passes it to `process_session_start()` as a new `tmux_pane_id` keyword argument.
- All other hook routes (session-end, stop, user-prompt-submit, notification, pre-tool-use, post-tool-use, permission-request) extract `tmux_pane` and pass it to their respective processor functions for late discovery (see FR11).

**FR11:** The pane ID is set on the first hook event that includes it (typically `session-start`) and is available for all subsequent operations on that agent. Specifically:
- `process_session_start()` accepts a new `tmux_pane_id: str | None = None` parameter. If provided, it stores the value on `agent.tmux_pane_id` and registers the agent with the availability tracker: `commander_availability.register_agent(agent.id, tmux_pane_id)`.
- For other hook processors (stop, user-prompt-submit, notification, etc.): if the payload contains `tmux_pane` and the agent's `tmux_pane_id` is not yet set, the route handler stores it on `agent.tmux_pane_id` (late discovery). This provides redundancy — the first event with the field populates it.

### Session End Cleanup

**FR24:** When the session-end hook fires:
- The availability tracker unregisters the agent (existing `unregister_agent()` behavior, preserved).
- The `tmux_pane_id` field on the Agent model is NOT cleared — it is preserved for audit/debugging purposes. The pane may still exist even after Claude Code exits.

### Respond Pipeline

**FR12:** The respond endpoint (`POST /api/respond/<agent_id>`) uses the agent's `tmux_pane_id` to target the correct tmux pane instead of deriving a socket path from `claude_session_id`. It reads config from `config["tmux_bridge"]` instead of `config["commander"]`.

**FR13:** The respond endpoint validates that the agent has a `tmux_pane_id` before attempting to send — agents without a pane ID receive a 400 error with `error_type: "no_pane_id"` (replacing the previous `"no_session_id"` check against `agent.claude_session_id`).

**FR14:** The existing validation flow is preserved: agent must exist, must be in AWAITING_INPUT state, must have a reachable tmux pane.

### Availability Tracking

**FR15:** The `CommanderAvailability` class's background daemon thread continues to run with the same lifecycle (start/stop, thread name `"commander-availability"`, daemon=True). The `_check_all_agents()` loop iterates registered agents and performs tmux pane existence checks instead of socket probes. The `_health_check_loop()` behavior, interval timing, and stop event handling are all preserved.

**FR16:** The internal mapping changes from `agent_id -> session_id` to `agent_id -> tmux_pane_id`. Method signatures change:
- `register_agent(agent_id: int, tmux_pane_id: str | None)` — internally maps `agent_id` to `tmux_pane_id` (previously mapped to `session_id`)
- `check_agent(agent_id: int, tmux_pane_id: str | None = None)` — accepts `tmux_pane_id` override (previously `session_id` override)
- `unregister_agent(agent_id: int)` — unchanged
- `is_available(agent_id: int)` — unchanged
Config is read from the `tmux_bridge:` section instead of `commander:`.

**FR17:** SSE broadcast of availability changes continues to work identically — the dashboard receives the same `commander_availability` event type with the same `{"agent_id": N, "available": true/false, "timestamp": "..."}` shape. The availability endpoint (`GET /api/respond/<agent_id>/availability`) preserves the `"commander_available"` response field name for backward compatibility with dashboard JS.

### Extension Registration

**FR25:** Two services are registered in `app.extensions`:
- `app.extensions["tmux_bridge"]` — the new `tmux_bridge.py` service (replaces `commander_service.py` module-level functions)
- `app.extensions["commander_availability"]` — the availability tracker class retains its existing extension key for backward compatibility. Dashboard JS, respond routes, and other services reference this key. Internally the class uses tmux pane checks instead of socket probes.

### Error Handling

**FR18:** If a tmux pane no longer exists (session killed, agent exited), the user sees a clear error indicating the session is unreachable, with `error_type: "pane_not_found"`.

**FR19:** If tmux is not installed or not running, the system reports this clearly with `error_type: "tmux_not_installed"` rather than failing with an opaque subprocess error.

**FR20:** If a response is sent but Claude Code has already moved past the prompt (race condition), the text is delivered anyway — `send-keys` is fire-and-forget, and state will self-correct on the next hook event.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Response delivery latency from user action to Claude Code receipt is under 500ms for local tmux subprocess calls.

**NFR2:** The tmux bridge service follows the existing service registration pattern and is accessible via `app.extensions["tmux_bridge"]`.

**NFR3:** The tmux bridge service is resilient to subprocess failures — errors are caught, logged, and surfaced to the user without crashing the server.

**NFR4:** All tmux subprocess calls use appropriate timeouts (default 5s via `subprocess_timeout` config) to prevent blocking the Flask request thread.

**NFR5:** The `tmux_pane_id` migration is additive (nullable field) and does not require data backfill.

---

## 6. UI Overview

No UI changes. The existing dashboard respond widget (quick-action buttons, free-text input, visual feedback) works without modification. The transport change is invisible to the user.

---

## 7. Technical Context (for implementer)

This section provides implementation-relevant context derived from the proof of concept and architecture documentation. These are not requirements — but they represent verified patterns that the implementer should follow.

### Reference Documents

- **Architecture doc:** `docs/architecture/tmux-bridge.md` — comprehensive technical reference
- **Current commander service:** `src/claude_headspace/services/commander_service.py` — to be replaced
- **Current availability checker:** `src/claude_headspace/services/commander_availability.py` — to be replaced
- **Respond route:** `src/claude_headspace/routes/respond.py` — internals rewired, API contract preserved
- **Hook receiver:** `src/claude_headspace/services/hook_receiver.py` — `process_session_start()` gains `tmux_pane_id` parameter
- **Hook routes:** `src/claude_headspace/routes/hooks.py` — all routes extract `tmux_pane` from payload
- **Hook script:** `bin/notify-headspace.sh` — adds `$TMUX_PANE` extraction to payload

### Core Implementation Pattern

The new `tmux_bridge.py` service wraps tmux CLI commands as subprocess calls:

```python
# Send literal text (does NOT interpret key names)
subprocess.run(["tmux", "send-keys", "-t", pane_id, "-l", text],
               check=True, timeout=5, capture_output=True)
# 100ms delay
time.sleep(0.1)
# Send Enter as a key (triggers Ink's onSubmit)
subprocess.run(["tmux", "send-keys", "-t", pane_id, "Enter"],
               check=True, timeout=5, capture_output=True)
```

**Critical:** Always use the `-l` flag for user text to prevent tmux from interpreting key names. Send `Enter` as a separate `send-keys` call without `-l`.

**Error handling:** Use `check=True` so non-zero exits raise `subprocess.CalledProcessError`. Catch this exception and map to appropriate `TmuxBridgeErrorType` values. Also catch `FileNotFoundError` (tmux not installed) and `subprocess.TimeoutExpired`.

### Replacement Mapping

| Current (commander) | New (tmux bridge) |
|---------------------|-------------------|
| `socket.connect("/tmp/claudec-{id}.sock")` | `subprocess.run(["tmux", "send-keys", ...])` |
| `{"action": "send", "text": "..."}` | `send-keys -t {pane_id} -l "text"` + `send-keys Enter` |
| `{"action": "status"}` | `tmux list-panes -a -F '#{pane_id} #{pane_current_command}'` |
| `{"action": "keys", "keys": "\x0d"}` | `tmux send-keys -t {pane_id} Enter` |
| Socket path derived from `claude_session_id` | Pane ID from `$TMUX_PANE` via hooks (direct target — `claude_session_id` is no longer needed for targeting) |
| `commander:` config section | `tmux_bridge:` config section |
| `CommanderErrorType` enum | `TmuxBridgeErrorType` enum |

### Pane ID Discovery via Hooks

Claude Code hooks fire in the shell environment where `$TMUX_PANE` is set. The hook script (`bin/notify-headspace.sh`) extracts this variable and includes it in every hook payload:

```bash
# In notify-headspace.sh — extract $TMUX_PANE alongside other fields
TMUX_PANE_ID="${TMUX_PANE:-}"

# Include in jq payload construction:
# + (if $tmux_pane != "" then {tmux_pane: $tmux_pane} else {} end)
```

All hook routes extract the field:
```python
tmux_pane = data.get("tmux_pane")
```

The hook receiver stores the pane ID on the Agent model's `tmux_pane_id` field on first discovery and registers with the availability tracker.

### Availability Detection

Replace socket-probing with tmux pane existence check:

```bash
# Check if specific pane is alive (preferred — uses pane ID directly)
tmux list-panes -a -F '#{pane_id}' | grep -q '%5'

# Check if Claude Code is running in the pane
tmux list-panes -a -F '#{pane_id} #{pane_current_command}' | grep '%5' | grep -q 'claude\|node'
```

### Readiness Detection (for future session launch)

Poll `capture-pane` for TUI indicators:

```python
READY_INDICATORS = [
    'Try "',          # Claude Code's suggestion prompt
    'Claude Code v',  # The banner
    'What can I',     # Initial greeting
]
```

**Do NOT** match on the string `claude` alone — it matches the shell command that was just typed.

### Verified Interaction Patterns

All patterns tested and confirmed working (February 2026, Claude Code v2.1.29):

| Pattern | Method | Result |
|---------|--------|--------|
| Submit text prompt | `-l "text"` + `Enter` | Prompt submitted, Claude responds |
| Reply to text-based questions | `-l "option 2"` + `Enter` | Claude processes text reply |
| AskUserQuestion picker — select default | `Enter` | Default option selected |
| AskUserQuestion picker — navigate | `Down` + `Enter` | Non-default option selected |
| Special characters (quotes, pipes, backticks) | `-l` flag handles all | Passed through correctly |
| Interrupt mid-processing | `Escape` | Claude interrupted, returns to prompt |
| Clear input line | `C-u` | Line cleared |
| Dual input (user + remote simultaneously) | Both paths | Both work in same session |

### Timing

- 100ms delay between text send and Enter send (prevents race conditions)
- 150ms between rapid sequential sends (tested reliable)

### What NOT to Change

- The respond route's API contract stays the same (`POST /api/respond/<agent_id>`)
- The dashboard JS that calls respond stays the same
- The SSE/broadcaster layer is untouched
- The iTerm focus service (`iterm_focus.py`) continues using `iterm_pane_id`
- The `app.extensions["commander_availability"]` key stays the same (backward compatibility)
- The availability endpoint response field `"commander_available"` stays the same

### Prerequisites

- tmux 3.x (`brew install tmux`) — tested with 3.6a
- iTerm2 (any 3.x version)
- Claude Code sessions must be launched inside tmux panes
- Recommended iTerm2 setting: General > tmux > "Automatically bury the tmux client session after connecting"

### Known Limitations

- All windows within a tmux session share dimensions — use one tmux session per agent
- Cannot mix tmux and non-tmux tabs within a single iTerm2 window
- Only one iTerm2 `-CC` client should be attached to a given tmux session at a time
- Sessions launched in plain iTerm2 tabs without tmux cannot be targeted by `send-keys`
- **Dual input verified safe:** Simultaneous input from user (typing directly) and dashboard (send-keys) does not cause corruption. Tested and confirmed February 2026.
- **Autocomplete/suggestion behavior:** Claude Code pre-fills suggestions in the input field. Sending text via `send-keys` overwrites the suggestion; sending Enter alone submits it. No special handling needed.
