# Getting Started

Welcome to Claude Headspace! This guide will help you get up and running quickly.

## What is Claude Headspace?

Claude Headspace is a dashboard for tracking Claude Code sessions across multiple projects. It shows you:

- Which projects have active Claude Code sessions
- What state each agent is in (working, waiting for input, idle)
- Quick access to focus on any session's terminal window

## Prerequisites

Before starting, make sure you have:

1. **Claude Headspace server running** - The Flask server must be running on the configured port (default: 5055)
2. **Claude Code installed** - The `claude` CLI must be available in your PATH
3. **Hooks installed** - Claude Code hooks must be configured to send events to the dashboard

## Starting a Monitored Session

There are two ways to start a Claude Code session that registers with the dashboard:

### Method 1: Wrapper Script (Recommended)

Use the `claude-headspace` wrapper script to launch Claude Code with automatic session registration:

```bash
claude-headspace start
```

You can also pass arguments through to Claude Code:

```bash
claude-headspace start -- "your prompt here"
```

The wrapper script:
- Checks that the Headspace server is reachable
- Registers the session with the dashboard
- Sets up environment variables for hook integration
- Launches Claude Code as a child process
- Cleans up the session when Claude Code exits

### Method 2: Hooks Only

If you prefer to run `claude` directly, you must first install the Claude Code hooks:

```bash
./bin/install-hooks.sh
```

This installs a notification script into `~/.claude/hooks/` and updates `~/.claude/settings.json` with hook configurations for these events:

- `session-start` - When Claude Code starts
- `session-end` - When Claude Code exits
- `user-prompt-submit` - When you submit a prompt
- `stop` - When Claude finishes a turn
- `notification` - When Claude sends a notification

After hooks are installed, any new `claude` session will automatically send lifecycle events to the Headspace dashboard.

**Important:** The hook script defaults to `http://localhost:5055`. If your server runs on a different port, set the `HEADSPACE_URL` environment variable:

```bash
export HEADSPACE_URL=http://localhost:5055
```

## Verifying Your Session Registered

After starting a session:

1. Open the dashboard at `http://localhost:5055`
2. Your session should appear as an agent card
3. The status badge will show the current state (ACTIVE or IDLE)

If your session doesn't appear, check the [Troubleshooting](troubleshooting) guide.

## Open the Dashboard

Navigate to `http://localhost:5055` in your browser to see all your active sessions.

## Understand Agent States

Each agent card shows its current state:

- **Working** (blue) - Claude is actively processing
- **Input Needed** (amber) - Claude is waiting for your response
- **Idle** (gray) - Claude has completed its task

## Focus on a Session

Click the "Headspace" button on any agent card to bring its iTerm window to the foreground.

## Next Steps

- [Dashboard Overview](dashboard) - Learn about all dashboard features
- [Set an Objective](objective) - Guide Claude's priorities
- [Configure Settings](configuration) - Customize your setup
