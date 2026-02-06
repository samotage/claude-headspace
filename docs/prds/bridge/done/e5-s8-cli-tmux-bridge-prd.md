---
validation:
  status: valid
  validated_at: '2026-02-06T11:04:52+11:00'
---

## Product Requirements Document (PRD) — CLI Launcher: tmux Bridge Alignment

**Project:** Claude Headspace
**Scope:** Replace the failed claudec mechanism in the CLI launcher with tmux pane detection, aligning the CLI with the server-side tmux bridge implemented in e5-s4
**Author:** samotage (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

The Claude Headspace CLI launcher (`claude-headspace start --bridge`) still uses the failed `claudec` (claude-commander) binary to wrap Claude Code sessions. The `claudec` approach — PTY wrapping with Unix domain socket injection — was proven non-functional because Claude Code's Ink TUI library rejects programmatic stdin as non-physical keystrokes.

PRD e5-s4 replaced the server-side transport with tmux send-keys, which is the only verified method for programmatic input to Claude Code. However, the CLI launcher was excluded from that PRD's scope ("Automated session creation/launch" was listed as out of scope). As a result, the `--bridge` flag still detects `claudec`, wraps the launch command with it, and produces the broken `Input Bridge: enabled (claudec detected)` output.

This PRD updates the CLI launcher to remove all claudec references and replace them with tmux pane detection. When `--bridge` is passed, the launcher detects whether it is running inside a tmux pane (via `$TMUX_PANE`), reports bridge availability, includes the tmux pane ID in session registration, and launches Claude Code directly (no wrapper). The server-side tmux bridge infrastructure is untouched — only the CLI and session registration API need changes.

---

## 1. Context & Purpose

### 1.1 Context

The e5-s1 Input Bridge PRD built the full dashboard respond pipeline: UI widget, API endpoint, state transitions, Turn audit records, and SSE broadcasting. The e5-s4 tmux Bridge PRD replaced the failed socket transport with tmux send-keys on the server side. Both are complete and working.

The CLI launcher (`src/claude_headspace/cli/launcher.py`) was created in e1-s11 and later gained claudec detection. It was never updated for the tmux bridge because e5-s4 assumed manual session launch inside tmux. In practice, users depend on the CLI and have shell aliases (`clhb = claude-headspace start --bridge`) as their primary entry point.

The result: the server side is ready for tmux input, but CLI-launched sessions either use the broken claudec wrapper (with `--bridge`) or have no bridge awareness at all (without `--bridge`). The tmux pane ID only reaches the server via hook backfill on the first hook event, rather than being available from session creation.

### 1.2 Target User

The same user as e5-s1 and e5-s4: someone running multiple Claude Code sessions via the Headspace dashboard who launches sessions using the `claude-headspace start` CLI and wants to respond to agent prompts from the dashboard.

### 1.3 Success Moment

The user runs `clhb` (alias for `claude-headspace start --bridge`) inside a tmux pane. The CLI outputs `Input Bridge: available (tmux pane %5)`, registers the session with the pane ID, and launches Claude Code directly. When the agent hits a permission prompt, the dashboard respond widget is immediately available — no waiting for hook backfill. The user clicks a quick-action button and the response is delivered via tmux send-keys.

---

## 2. Scope

### 2.1 In Scope

- Remove all claudec detection, wrapping, and references from the CLI launcher
- Repurpose the `--bridge` flag to enable tmux pane detection instead of claudec detection
- Detect tmux pane presence via the `$TMUX_PANE` environment variable when `--bridge` is passed
- Report tmux bridge status during CLI startup (available with pane ID, or unavailable)
- Always launch `claude` directly — no wrapper binary under any circumstance
- Include `tmux_pane_id` in the session registration payload (`POST /api/sessions`)
- Update the sessions API endpoint to accept and store `tmux_pane_id` on the Agent model
- Register the agent with the `CommanderAvailability` tracker at session creation time when pane ID is provided
- Warn (not block) when `--bridge` is passed outside a tmux session — monitoring still works, input bridge won't
- Update CLI help text and `--bridge` argument description to reference tmux instead of claudec

### 2.2 Out of Scope

- Server-side tmux bridge services (`tmux_bridge.py`, `commander_availability.py`) — complete, no changes
- Hook routes or hook script (`notify-headspace.sh`) — already send `$TMUX_PANE`, no changes
- Respond route (`respond.py`) or dashboard UI/JS — working, no changes
- Config changes — `tmux_bridge:` section already exists in `config.yaml`
- Automated tmux session creation (users still launch inside tmux manually)
- Removal of the `claudec` binary from the user's system
- Changes to the iTerm focus service (`iterm_focus.py`) — separate concern using `iterm_pane_id`

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Running `claude-headspace start --bridge` inside a tmux pane displays `Input Bridge: available (tmux pane %N)` and launches `claude` directly (not `claudec`)
2. Running `claude-headspace start --bridge` outside a tmux session displays `Input Bridge: unavailable (not in tmux session)` and still launches Claude Code successfully
3. Running `claude-headspace start` (without `--bridge`) launches Claude Code with no bridge detection output
4. Session registration includes `tmux_pane_id` when available, and the Agent record has the pane ID immediately after creation
5. The `CommanderAvailability` tracker begins monitoring the agent's tmux pane from session creation (not deferred to first hook event)
6. No references to `claudec`, `claude-commander`, or `detect_claudec` remain in the launcher code

### 3.2 Non-Functional Success Criteria

1. CLI startup time is not perceptibly affected — tmux pane detection is a simple environment variable read, faster than the previous `shutil.which("claudec")` call
2. The `--bridge` flag is preserved with the same short form, so existing user aliases (`clhb`) continue to work without modification

---

## 4. Functional Requirements (FRs)

### claudec Removal

**FR1:** The `detect_claudec()` function and all references to claudec are removed from the launcher. The `shutil` import is removed if no longer needed.

**FR2:** The `launch_claude()` function always constructs the command as `["claude"] + claude_args`. The `claudec_path` parameter is removed.

### tmux Pane Detection

**FR3:** A new function detects the tmux pane ID by reading the `$TMUX_PANE` environment variable. It returns the pane ID string (e.g., `%0`, `%5`) if set and non-empty, or `None` if not in a tmux session.

**FR4:** When the `--bridge` flag is passed, the CLI calls the tmux pane detection function and outputs one of:
- `Input Bridge: available (tmux pane %N)` — when `$TMUX_PANE` is set
- `Input Bridge: unavailable (not in tmux session)` — when `$TMUX_PANE` is not set (printed to stderr as a warning, launch continues)

**FR5:** When the `--bridge` flag is NOT passed, no bridge detection or output occurs. The CLI launches Claude Code with monitoring only.

### Session Registration

**FR6:** The `register_session()` function accepts an optional `tmux_pane_id` parameter and includes it in the registration payload when provided.

**FR7:** The `POST /api/sessions` endpoint accepts an optional `tmux_pane_id` field in the request body and stores it on the Agent model at creation time.

**FR8:** When the sessions endpoint receives a `tmux_pane_id`, it registers the agent with the `CommanderAvailability` service immediately, so availability monitoring begins from session creation rather than waiting for the first hook event.

### CLI Help Text

**FR9:** The `--bridge` flag's help text describes its purpose as enabling the tmux-based input bridge for dashboard responses. No references to claudec or commander remain in any help text or argument description.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The tmux pane detection is a simple `os.environ.get("TMUX_PANE")` call — no subprocess invocation, no filesystem access, no network call. Startup overhead is effectively zero.

**NFR2:** The session registration payload change is backward-compatible — the `tmux_pane_id` field is optional. Older CLI versions that don't send it continue to work (hook backfill remains as a fallback).

---

## 6. Technical Context (for implementer)

This section provides implementation-relevant context. These are not requirements — but they represent the current codebase state and patterns the implementer should follow.

### Files to Change

| File | Change Type |
|------|-------------|
| `src/claude_headspace/cli/launcher.py` | Remove claudec, add tmux detection, update register_session signature, update launch_claude signature, update cmd_start flow, update help text |
| `src/claude_headspace/routes/sessions.py` | Accept `tmux_pane_id` in POST payload, store on Agent, register with availability tracker |
| `tests/cli/test_launcher.py` | Remove claudec tests, add tmux detection tests, update registration and launch tests |
| `tests/routes/test_sessions.py` | Add tests for `tmux_pane_id` in registration |

### Current Launcher Flow (cmd_start, lines 370-435)

```
get_server_url() → validate_prerequisites() → get_project_info() →
get_iterm_pane_id() → uuid4() → register_session() →
[if --bridge: detect_claudec()] → setup_environment() →
SessionManager context → launch_claude()
```

### Target Launcher Flow

```
get_server_url() → validate_prerequisites() → get_project_info() →
get_iterm_pane_id() → [if --bridge: get_tmux_pane_id()] → uuid4() →
register_session(tmux_pane_id=...) → setup_environment() →
SessionManager context → launch_claude()
```

### Current Session Registration Payload

```json
{
  "session_uuid": "...",
  "project_path": "...",
  "working_directory": "...",
  "project_name": "...",
  "current_branch": "...",
  "iterm_pane_id": "..."
}
```

### Target Session Registration Payload

```json
{
  "session_uuid": "...",
  "project_path": "...",
  "working_directory": "...",
  "project_name": "...",
  "current_branch": "...",
  "iterm_pane_id": "...",
  "tmux_pane_id": "%5"
}
```

### Sessions Route Pattern (for tmux_pane_id storage)

Follow the existing `iterm_pane_id` pattern in `sessions.py`:
```python
# Existing pattern for iterm_pane_id:
iterm_pane_id = data.get("iterm_pane_id")
# ...
agent = Agent(
    session_uuid=session_uuid,
    project_id=project.id,
    iterm_pane_id=iterm_pane_id,
    # ADD: tmux_pane_id=tmux_pane_id,
)
```

### Availability Registration Pattern

Follow the existing pattern from `hooks.py` `_backfill_tmux_pane()`:
```python
# After agent creation, if tmux_pane_id is provided:
commander_availability = current_app.extensions.get("commander_availability")
if commander_availability and tmux_pane_id:
    commander_availability.register_agent(agent.id, tmux_pane_id)
```

### Existing Test Patterns

Launcher tests use `unittest.mock.patch` extensively:
- `@patch("claude_headspace.cli.launcher.subprocess.call")` for launch
- `@patch("claude_headspace.cli.launcher.requests.post")` for registration
- `@patch.dict(os.environ, {...})` for environment variable mocking

Sessions route tests use the Flask test client with `app` and `client` fixtures from conftest.

### What NOT to Change

- `bin/notify-headspace.sh` — already sends `$TMUX_PANE` in every hook payload
- `services/tmux_bridge.py` — stateless module, complete
- `services/commander_availability.py` — already uses tmux health checks
- `routes/respond.py` — already uses `agent.tmux_pane_id`
- `routes/hooks.py` — already backfills `tmux_pane_id` from hook payloads
- `config.yaml` — `tmux_bridge:` section already exists
- Dashboard UI/JS — no changes needed
