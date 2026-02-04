# tmux Bridge: iTerm2 Native Integration for Claude Code Session Input

## Overview

The tmux bridge enables the Claude Headspace dashboard to send text input to running Claude Code sessions via `tmux send-keys`, while preserving full iTerm2 ergonomics through iTerm2's native tmux integration (`tmux -CC`).

This replaces the previous `claude-commander` approach (Unix domain socket injection via a Rust binary wrapper) which proved unreliable.

## Problem Statement

Claude Code uses the [Ink](https://github.com/vadimdemedes/ink) library (React for CLI) for its terminal UI. Ink treats programmatic stdin differently from physical keyboard input:

- **Physical Enter keypress** triggers `onSubmit` and the prompt is processed
- **Programmatic `\r` or `\n`** (from piped input, AppleScript, etc.) is treated as a newline character -- the prompt is NOT submitted

This means most naive approaches to injecting input fail: piping to stdin, VS Code `terminal.sendText()`, AppleScript `keystroke return`, and various escape sequences all fail to trigger prompt submission.

**`tmux send-keys` is the exception.** It sends keystrokes through tmux's PTY layer at a level that Ink recognises as genuine keyboard input. This was confirmed by community testing ([Claude Code Issue #15553](https://github.com/anthropics/claude-code/issues/15553)).

## Architecture

```
+-----------------------------------------------------------+
|  Claude Headspace (Flask)                                 |
|                                                           |
|  commander_service.py                                     |
|    subprocess.run(["tmux", "send-keys", "-t", pane_id,   |
|                    "-l", text])                            |
|    subprocess.run(["tmux", "send-keys", "-t", pane_id,   |
|                    "Enter"])                               |
|                                                           |
|  tmux_bridge.py (new service)                             |
|    - create_session(name, working_dir)                    |
|    - send_text(pane_id, text)                             |
|    - send_keys(pane_id, *keys)                            |
|    - capture_pane(pane_id, lines)                         |
|    - list_panes()                                         |
|    - get_pane_metadata(pane_id)                           |
+----------------------------+------------------------------+
                             |
                    tmux CLI (subprocess)
                             |
+----------------------------+------------------------------+
|  tmux server (persistence layer)                          |
|                                                           |
|  Session: agent-abc123  [%5: claude working on project-A] |
|  Session: agent-def456  [%8: claude working on project-B] |
+----------------------------+------------------------------+
                             |
              tmux -CC control protocol
                             |
+----------------------------+------------------------------+
|  iTerm2 (user's terminal)                                 |
|                                                           |
|  Native window/tab per tmux session                       |
|  Full scroll, copy, mouse, keyboard ergonomics            |
|  User can type directly into sessions                     |
+-----------------------------------------------------------+
```

The tmux server is the stable intermediary. Flask talks to it via CLI subprocess calls. iTerm2 talks to it via the `-CC` control protocol. Both see the same sessions, windows, and panes.

## How tmux -CC Works

iTerm2's native tmux integration uses "control mode" (`tmux -CC`). When a user runs `tmux -CC attach -t session-name` inside iTerm2:

1. tmux runs in control mode -- it sends structured output to iTerm2 instead of rendering its own UI
2. iTerm2 renders tmux panes as **native iTerm2 tabs/splits**
3. The tmux prefix key (`Ctrl-B`) is disabled -- all operations use native iTerm2 shortcuts
4. A "gateway" control window appears (can be auto-hidden via iTerm2 Settings > General > tmux > "Automatically bury the tmux client session after connecting")

### What the user gets

| Feature | Behaviour |
|---------|-----------|
| Scrollback | Native iTerm2 trackpad/mouse scrolling |
| Copy/paste | Cmd+C/V, mouse selection within pane boundaries |
| Search | Cmd+F within pane scrollback |
| New tab | Cmd+T creates a new tmux window (rendered as iTerm2 tab) |
| Split pane | Cmd+D / Cmd+Shift+D create tmux splits |
| Tab switching | Cmd+1/2/3 or Cmd+Option+arrows |
| Resize | Drag dividers, resize windows normally |

The user experience is indistinguishable from regular iTerm2, except that sessions persist if iTerm2 is closed and can be reattached with `tmux -CC attach`.

### Mapping

| tmux concept | iTerm2 concept |
|--------------|----------------|
| tmux session | A set of iTerm2 windows/tabs |
| tmux window  | An iTerm2 tab (or window, configurable) |
| tmux pane    | An iTerm2 split pane |

## Pane Targeting

tmux panes have globally unique IDs (format: `%0`, `%1`, `%2`, ...) that persist for the lifetime of the tmux server. These are the primary targeting mechanism.

### Discovering pane IDs

```bash
# List all panes across all sessions
tmux list-panes -a -F '#{pane_id} #{session_name} #{pane_current_command} #{pane_current_path}'

# Capture pane ID at creation time
PANE_ID=$(tmux new-session -d -s my-session -PF '#{pane_id}')
```

### The TMUX_PANE environment variable

Each pane's child process has access to `$TMUX_PANE`, which contains the pane ID. If Claude Code runs inside a tmux pane, its hooks can report this value to Headspace, enabling the dashboard to map agents to pane IDs.

### Pane metadata

```bash
tmux list-panes -t session-name -F '#{pane_id} #{pane_pid} #{pane_tty} #{pane_current_command} #{pane_current_path}'
```

Returns JSON-friendly metadata: pane ID, process PID, TTY device, current command, and working directory.

## Sending Input

### Text prompts

```bash
# Send literal text (does not interpret key names)
tmux send-keys -t %5 -l "Fix the bug in auth.py"
# Send Enter as a key (triggers Ink's onSubmit)
tmux send-keys -t %5 Enter
```

The `-l` (literal) flag is important -- without it, tmux interprets certain strings as key names. Always use `-l` for user text, then send `Enter` separately.

### Navigation keys

```bash
# Arrow keys for option picker navigation
tmux send-keys -t %5 Down
tmux send-keys -t %5 Up
tmux send-keys -t %5 Enter

# Escape to interrupt/cancel
tmux send-keys -t %5 Escape

# Ctrl-U to clear current input line
tmux send-keys -t %5 C-u

# Ctrl-C to send interrupt signal
tmux send-keys -t %5 C-c
```

### Timing

A small delay (100ms) between sending text and Enter prevents race conditions:

```python
subprocess.run(["tmux", "send-keys", "-t", pane_id, "-l", text])
time.sleep(0.1)
subprocess.run(["tmux", "send-keys", "-t", pane_id, "Enter"])
```

For rapid sequential sends, 150ms between operations was tested reliable.

## Reading Output

```bash
# Capture last N lines of pane content
tmux capture-pane -t %5 -p -S -50
```

This returns the visible terminal content as plain text, useful for:
- Detecting when Claude Code's TUI has loaded (look for `Claude Code v`)
- Checking if Claude is at the input prompt (`❯`)
- Reading Claude's responses
- Detecting question pickers (`Enter to select · ↑/↓ to navigate`)

## Verified Interaction Patterns

All patterns tested and confirmed working (February 2026, Claude Code v2.1.29):

| Pattern | Method | Result |
|---------|--------|--------|
| Submit text prompt | `-l "text"` + `Enter` | Prompt submitted, Claude responds |
| Reply to text-based questions | `-l "option 2"` + `Enter` | Claude processes text reply |
| AskUserQuestion picker -- select default | `Enter` | Default option selected |
| AskUserQuestion picker -- navigate | `Down` + `Enter` | Non-default option selected |
| Special characters (quotes, pipes, backticks) | `-l` flag handles all | Passed through correctly |
| Interrupt mid-processing | `Escape` | Claude interrupted, returns to prompt |
| Clear input line | `C-u` | Line cleared |
| Dual input (user + remote simultaneously) | Both paths | Both work in same session |
| Autocomplete suggestion overwrite | Any text overwrites suggestion | New text replaces suggestion |

### Autocomplete/suggestion behaviour

Claude Code pre-fills suggested prompts in the input field (greyed-out text). When sending via `send-keys`:
- **Typing any text** overwrites the suggestion with the new text
- **Pressing Enter alone** submits the suggestion as the next prompt
- No special handling needed -- just send text normally

## Session Lifecycle

### Creating a session for a Claude Code agent

```bash
# Create detached tmux session in the project directory
PANE_ID=$(tmux new-session -d -s "agent-${SESSION_ID}" -c /path/to/project -PF '#{pane_id}')

# Launch Claude Code in the pane
tmux send-keys -t "$PANE_ID" "claude" Enter
```

### User attaches to watch/interact

```bash
# In iTerm2 -- renders as native window with full ergonomics
tmux -CC attach -t "agent-${SESSION_ID}"
```

The user can type directly into this window at any time. Their input and remote `send-keys` input coexist in the same session.

### Detecting Claude Code readiness

Poll `capture-pane` for TUI indicators:

```python
READY_INDICATORS = [
    'Try "',          # Claude Code's suggestion prompt
    'Claude Code v',  # The banner
    'What can I',     # Initial greeting
]

while not ready:
    content = capture_pane(pane_id, lines=20)
    if any(indicator in content for indicator in READY_INDICATORS):
        time.sleep(1.5)  # Extra buffer for input field activation
        ready = True
    else:
        time.sleep(2)
```

Do NOT match on the string `claude` alone -- it matches the shell command that was just typed.

### Destroying a session

```bash
tmux kill-session -t "agent-${SESSION_ID}"
```

## Integration with Existing Headspace Services

### Replacing commander_service.py

The current `CommanderService` sends JSON over Unix domain sockets to claude-commander. The tmux bridge replaces this with subprocess calls:

| Current (commander) | New (tmux bridge) |
|---------------------|-------------------|
| `socket.connect("/tmp/claudec-{id}.sock")` | `subprocess.run(["tmux", "send-keys", ...])` |
| `{"action": "send", "text": "..."}` | `send-keys -t {pane_id} -l "text"` + `send-keys Enter` |
| `{"action": "status"}` | `tmux list-panes -t {session} -F ...` |
| `{"action": "keys", "keys": "\x0d"}` | `tmux send-keys -t {pane_id} Enter` |

### Pane ID discovery via hooks

Claude Code hooks fire in the shell environment where `$TMUX_PANE` is set. The hook payload can include this value:

```bash
# In the hook script (e.g., notify-headspace.sh)
curl -X POST http://localhost:5055/hook/session-start \
  -d "{\"session_id\": \"$SESSION_ID\", \"tmux_pane\": \"$TMUX_PANE\"}"
```

The hook receiver stores the pane ID on the Agent model, enabling the dashboard's respond button to target the correct pane.

### Commander availability

Replace socket-probing with tmux pane existence check:

```bash
tmux has-session -t "agent-${SESSION_ID}" 2>/dev/null
# Exit code 0 = session exists, 1 = not found
```

Or check if the pane is still running Claude Code:

```bash
tmux list-panes -t "agent-${SESSION_ID}" -F '#{pane_current_command}'
# Returns "claude" or "node" if Claude Code is running
```

## Known Limitations and Caveats

### Window size uniformity

All windows within a tmux session share the same dimensions. If the user resizes one tab, all tabs in that session resize. Mitigation: use one tmux session per agent rather than multiplexing agents into a single session.

### Cannot mix tmux and non-tmux tabs

Within a single iTerm2 window, you cannot have both tmux-managed tabs and regular tabs side by side. The user should keep tmux sessions in dedicated iTerm2 windows and use separate windows for non-tmux work.

### Gateway control window

Each `tmux -CC attach` spawns a control window. Enable **iTerm2 Settings > General > tmux > "Automatically bury the tmux client session after connecting"** to hide it automatically.

### Single -CC client per session

Only one iTerm2 instance should be attached to a given tmux session via `-CC` at a time. Multiple `-CC` clients to the same session causes confusion.

### tmux must be installed

Requires `brew install tmux`. Version 3.x recommended (tested with 3.6a).

### Opt-in workflow change

Users must launch Claude Code sessions within tmux (either via the Headspace dashboard which creates sessions, or manually via `tmux new-session`). Sessions launched in plain iTerm2 tabs without tmux cannot be targeted by `send-keys`.

## Prerequisites

- iTerm2 (any 3.x version)
- tmux 3.x (`brew install tmux`)
- iTerm2 setting: General > tmux > "Automatically bury the tmux client session after connecting" (recommended)

## Future Considerations

### Anthropic native IPC

[Claude Code Issue #15553](https://github.com/anthropics/claude-code/issues/15553) proposes native IPC mechanisms (environment variable, CLI flag, or socket). If Anthropic implements this, it would eliminate the need for tmux as an intermediary. The tmux bridge is designed to be replaceable -- the service interface (send text, send keys, check availability) is the same regardless of the underlying transport.

### iTerm2 Python API

iTerm2's Python API (`iterm2` package) offers `session.async_send_text()` which could potentially bypass tmux entirely. Whether this triggers Ink's `onSubmit` is untested. If it works, it would be a simpler integration for users who don't want tmux. This remains a candidate for future investigation.
