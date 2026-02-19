# Agent-Driven Testing

Agent-driven tests exercise the full production loop end-to-end: a real Claude Code session runs in tmux, fires real hooks into a test Flask server, and Playwright verifies that the dashboard reflects every state change in the browser DOM. Nothing is mocked.

## What It Tests

The loop under test:

```
Voice Chat UI (Playwright)
    │  send command
    ▼
Claude Code (real CLI in tmux)
    │  processes command
    ▼
Lifecycle Hooks (real hook scripts)
    │  session-start, user-prompt, stop, etc.
    ▼
Flask Test Server (real app, test database)
    │  state transitions, SSE broadcast
    ▼
Browser DOM (Playwright)
    │  agent card, chat bubbles, state badges
    ▼
Database Assertions (SQLAlchemy)
    └─ Command state, Turn records, Agent registration
```

Every layer is real. The test database is created and dropped automatically per session.

## Prerequisites

Before running agent-driven tests, ensure you have:

- **tmux** — sessions run inside tmux panes (`brew install tmux`)
- **Claude CLI** — `claude` must be in your PATH
- **Playwright** — `pip install pytest-playwright && playwright install chromium`
- **PostgreSQL** — running locally (the test creates/drops its own `_test` database)
- **Hooks installed** — `bin/install-hooks.sh` must have been run
- **OPENROUTER_API_KEY** — set in `.env` (required for LLM-powered summarisation during the session)

## Running the Tests

```bash
pytest tests/agent_driven/ -v -s
```

The `-s` flag is recommended so you can see real-time progress output (ready gate polling, tmux session names, teardown status).

To run a specific test:

```bash
pytest tests/agent_driven/test_simple_command.py -v -s
```

Tests are marked with `@pytest.mark.agent_driven` so you can also use:

```bash
pytest -m agent_driven -v -s
```

## How It Works

### The `claude_session` Fixture

The core fixture in `tests/agent_driven/conftest.py` manages the full lifecycle:

1. **Create tmux session** — a new tmux session is created with a unique name (`headspace-test-<uuid>`), with environment variables pointing hooks to the test server
2. **Launch Claude CLI** — `claude --model haiku` is sent into the tmux pane via `tmux send-keys` (uses Haiku for cost control)
3. **Ready gate** — polls the test database for up to 45 seconds waiting for a `session-start` hook to create an Agent record. If the gate times out, the tmux pane content is captured for diagnostics and the test fails
4. **Yield** — provides `agent_id` and `session_name` to the test
5. **Conditional teardown:**
   - **On success:** kills the tmux session and truncates all database tables
   - **On failure:** preserves the tmux session and database state so you can investigate

### The Test Flow

`test_simple_command_roundtrip` walks through the full loop:

1. **Navigate** — Playwright opens the voice chat page on the test server
2. **Wait for agent card** — the agent card for the launched Claude session must appear (proves session-start hook worked and SSE broadcast reached the browser)
3. **Select agent** — clicks the agent card to enter the chat screen
4. **Send command** — types a deterministic command (e.g., "create a file") into the chat input
5. **Wait for response** — waits up to 60 seconds for an agent response bubble (`.chat-bubble.agent[data-turn-id]`) to appear in the DOM
6. **Database assertions** — verifies that a Command record exists with state `COMPLETE` or `AWAITING_INPUT`

Screenshots are captured at each step and saved to `tests/agent_driven/screenshots/`.

## Debugging Failures

### Preserved tmux sessions

When a test fails, the tmux session is **not killed**. You can inspect it:

```bash
# List preserved sessions
tmux list-sessions | grep headspace-test

# Attach to investigate
tmux attach-session -t headspace-test-<id>

# Clean up when done
tmux kill-session -t headspace-test-<id>
```

### Screenshots

Each test step captures a screenshot to `tests/agent_driven/screenshots/`. Check these to see exactly what Playwright saw at each stage — they're numbered sequentially (01, 02, 03, etc.).

### Database state

On failure, database tables are also preserved. Connect to the test database to inspect:

```bash
psql claude_headspace_test

-- Check registered agents
SELECT id, session_uuid, started_at, ended_at FROM agent;

-- Check command states
SELECT id, agent_id, state, instruction FROM command;

-- Check turns
SELECT id, command_id, actor, intent, text FROM turn ORDER BY id;
```

### Common failure modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Ready gate timeout | Hooks not installed or not pointing to test server | Run `bin/install-hooks.sh`, check `CLAUDE_HEADSPACE_URL` env var |
| Agent card never appears | SSE connection not established | Check test server logs, verify Playwright navigated to correct URL |
| Response bubble timeout | Claude CLI crashed or prompt was ambiguous | Check tmux pane content, try a simpler prompt |
| Database assertion fails | State machine transition issue | Check Event records for the hook sequence |

## Writing New Tests

New tests use the same fixture infrastructure. Here's the pattern:

```python
import pytest
from pathlib import Path
from playwright.sync_api import expect
from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"

@pytest.mark.agent_driven
def test_my_scenario(claude_session, page, e2e_server, e2e_app):
    """Describe what this test verifies."""
    agent_id = claude_session["agent_id"]

    # Navigate to voice chat
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)

    # Wait for agent, select it
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()

    # Send your command
    va.send_chat_message("your deterministic command here")

    # Assert on browser state, database state, etc.
    # ...
```

Key considerations:

- **Use deterministic commands** — avoid prompts that produce unpredictable output
- **Use generous timeouts** — real Claude Code sessions take time to process
- **Capture screenshots** — use `va.capture("step_name")` at each significant step for debugging
- **Check database state** — use `e2e_app.app_context()` to query the test database for assertions

## Related Topics

- [Voice Bridge](voice-bridge) — the voice chat UI that agent-driven tests exercise
- [Getting Started](getting-started) — setting up Claude Headspace and installing hooks
- [Troubleshooting](troubleshooting) — common issues and solutions
