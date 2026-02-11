# Input Bridge

Input Bridge lets you respond to Claude Code prompts directly from the Headspace dashboard — without switching to iTerm.

When a Claude Code agent is waiting for input (permission prompts, yes/no questions, numbered choices), the dashboard shows quick-action buttons and a free-text input field right on the agent card.

## How It Works

Input Bridge uses **tmux send-keys** to inject text into the terminal pane where Claude Code is running. The dashboard sends your response to the Flask backend, which writes it to the correct tmux pane.

```
Dashboard button click
  → POST /api/respond/<agent_id>
  → Server calls tmux send-keys on the agent's pane
  → Text appears in the terminal as if typed
  → Claude Code reads the input and resumes processing
```

## Prerequisites

- **tmux** must be installed (`brew install tmux`)
- Bridge mode is now the **default** when using the `claude-headspace` CLI — tmux is auto-detected; if not installed, a warning is shown and the session continues without bridge
- The agent's `tmux_pane_id` must be set (registered via hooks at session start)

## Disabling the Bridge

To run without the Input Bridge (plain session, no dashboard respond):

```bash
claude-headspace start --no-bridge
```

Or set in `config.yaml`:
```yaml
cli:
  default_bridge: false
```

## Using the Respond Widget

When an agent is in the **Input Needed** (amber) state and its tmux pane is reachable, the agent card shows a respond widget:

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
2. The agent has a `tmux_pane_id` set
3. The tmux pane is reachable (health check passes)

If any condition is not met, the card displays the normal focus button to switch to iTerm instead. This is by design — the dashboard never shows a broken input widget.

## Availability Checking

Headspace checks tmux pane availability:

- **On session start** — when an agent first registers via hooks
- **Periodically** — every 30 seconds (configurable via `tmux_bridge.health_check_interval`)
- **On demand** — when an agent transitions to AWAITING_INPUT

Changes in availability are broadcast via SSE, so the widget appears or disappears in real-time without page refresh.

## Error Messages

| Error | Meaning | What to Do |
|-------|---------|------------|
| **Session unreachable** | Tmux pane not found or process dead | Check if the Claude Code process is still running in tmux |
| **Agent not waiting for input** | Agent already moved past the prompt | The agent continued on its own — no action needed |
| **No pane ID** | Agent has no `tmux_pane_id` | The session may not have registered properly via hooks |
| **Network error** | Cannot reach the Headspace server | Check if the Flask server is running |

## Configuration

Tmux bridge settings are in `config.yaml` under the `tmux_bridge` section:

```yaml
tmux_bridge:
  health_check_interval: 30      # Seconds between availability checks
  subprocess_timeout: 5           # Subprocess timeout (seconds)
  text_enter_delay_ms: 100        # Delay between sending text and Enter key (ms)
```

These can also be edited from the [Configuration](configuration) page.

## Audit Trail

Every response sent via the dashboard is recorded as a Turn entity (actor: USER, intent: ANSWER) in the database. This provides a complete audit trail of dashboard interactions alongside normal terminal interactions.

## Known Behaviors

### Claude Code Chat Buttons Remain Interactive

When Claude Code uses `AskUserQuestion` to present options, the Headspace dashboard correctly removes its response buttons after a selection is made. However, the buttons rendered in the **Claude Code chat history** (in the terminal) remain interactive and can be re-clicked at any time.

This is native Claude Code behavior that Headspace cannot control. Re-clicking an old button sends a new user message into the conversation, and Claude responds to it as a fresh input. This can be a useful feature — for example, re-selecting a different option to explore alternatives — but be aware that each click generates a new turn that flows through the hook pipeline and is tracked by Headspace.

## Limitations

- **Input only** — tmux send-keys delivers text but does not capture output (hooks handle output awareness)
- **Local only** — tmux works on the same machine; remote access is not supported
- **No authentication** — tmux pane access relies on Unix user permissions
