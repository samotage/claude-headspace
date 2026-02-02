# Input Bridge

Input Bridge lets you respond to Claude Code prompts directly from the Headspace dashboard — without switching to iTerm.

When a Claude Code agent is waiting for input (permission prompts, yes/no questions, numbered choices), the dashboard shows quick-action buttons and a free-text input field right on the agent card.

## How It Works

Input Bridge uses **claude-commander** (`claudec`), a lightweight Rust binary that wraps Claude Code in a pseudo-terminal (PTY) and exposes a Unix domain socket for text injection. Both keyboard input in iTerm and dashboard-injected input write to the same PTY, so the terminal remains fully interactive.

```
Dashboard button click
  → POST /api/respond/<agent_id>
  → Server writes to Unix socket: /tmp/claudec-<session_id>.sock
  → claudec writes to PTY master
  → Claude Code reads from PTY slave (same as keyboard input)
  → Agent resumes processing
```

## Installing claude-commander

`claudec` is a Rust binary available from GitHub.

### Install via Cargo (Rust toolchain)

If you have Rust installed:

```bash
cargo install claude-commander
```

### Install from GitHub Release

Download the pre-built binary for macOS:

```bash
# Download the latest release
curl -L https://github.com/sstraus/claude-commander/releases/latest/download/claudec-darwin-arm64 -o /usr/local/bin/claudec
chmod +x /usr/local/bin/claudec
```

### Verify Installation

```bash
claudec --version
```

You should see the version number (v0.1.0 or later).

## Launching Sessions with claudec

To enable Input Bridge for a session, launch Claude Code through the `claudec` wrapper:

```bash
claudec claude
```

This:
1. Creates a PTY pair for the Claude Code process
2. Opens a Unix socket at `/tmp/claudec-<session_id>.sock`
3. Launches Claude Code as a child process inside the PTY
4. Forwards all keyboard input to the PTY (transparent to the user)

The session registers with Headspace via the normal hooks. The Input Bridge becomes available once the commander socket is detected.

**Tip:** You can combine this with the Headspace wrapper:

```bash
claudec claude-headspace start
```

## Using the Respond Widget

When an agent is in the **Input Needed** (amber) state and the commander socket is reachable, the agent card shows a respond widget:

### Quick-Action Buttons

If the prompt contains numbered options (e.g., "1. Yes / 2. No / 3. Cancel"), the widget parses these and displays buttons for each option. Clicking a button sends just the number.

### Free-Text Input

A text field with a Send button is always available below the quick-action buttons. Type any response and press Send (or Enter).

### Feedback

- **Success:** The card briefly highlights green, a toast confirms "Response sent — Agent is now processing", and the widget fades out.
- **Error:** A toast appears with a specific message explaining what went wrong. The input text is preserved so you can retry.

## When the Widget Doesn't Appear

The respond widget only appears when **all** of these conditions are met:

1. The agent is in **AWAITING_INPUT** state
2. The agent has a `claude_session_id` (so the socket path can be derived)
3. The commander socket is reachable (health check passes)

If any condition is not met, the card displays the normal focus button to switch to iTerm instead. This is by design — the dashboard never shows a broken input widget.

## Availability Checking

Headspace checks commander socket availability:

- **On session start** — when an agent first registers
- **Periodically** — every 30 seconds (configurable via `commander.health_check_interval`)
- **On demand** — when an agent transitions to AWAITING_INPUT

Changes in availability are broadcast via SSE, so the widget appears or disappears in real-time without page refresh.

## Error Messages

| Error | Meaning | What to Do |
|-------|---------|------------|
| **Session unreachable** | Commander socket not found or process dead | Was the session started with `claudec`? Check if the Claude Code process is still running |
| **Agent not waiting for input** | Agent already moved past the prompt | The agent continued on its own — no action needed |
| **No session ID** | Agent has no `claude_session_id` | The session may not have registered properly. Restart with `claudec` |
| **Network error** | Cannot reach the Headspace server | Check if the Flask server is running |

## Configuration

Commander settings are in `config.yaml` under the `commander` section:

```yaml
commander:
  health_check_interval: 30        # Seconds between availability checks
  socket_timeout: 2                # Socket operation timeout in seconds
  socket_path_prefix: /tmp/claudec- # Must match claudec's convention
```

These can also be edited from the [Configuration](configuration) page.

## Audit Trail

Every response sent via the dashboard is recorded as a Turn entity (actor: USER, intent: ANSWER) in the database. This provides a complete audit trail of dashboard interactions alongside normal terminal interactions.

## Limitations

- **Input only** — the socket sends text to Claude Code but does not capture output (hooks already handle output awareness)
- **Local only** — Unix domain sockets work on the same machine; remote access is not supported
- **No authentication** — socket access relies on Unix file permissions
- **Startup delay** — there is a 2-5 second delay after launching `claudec` before the socket becomes available
