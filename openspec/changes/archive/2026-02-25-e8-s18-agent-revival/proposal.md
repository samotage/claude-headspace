## Why

When Claude Code agents die unexpectedly, all conversational context dies with them. The operator must manually reconstruct context for a replacement agent, which is tedious and lossy. The database already records the full conversation history (Agent -> Commands -> Turns) but there is no mechanism to surface it for a successor agent.

Agent Revival ("Seance") enables operators to spin up a replacement agent that self-briefs from its dead predecessor's conversation history, turning a hard restart into a warm restart.

## What Changes

- **New CLI command** `claude-headspace transcript <agent-id>` that queries Agent -> Commands -> Turns and outputs structured markdown to stdout
- **New revival service** (`revival_service.py`) that orchestrates the revival flow: validates the dead agent, creates a successor via `create_agent()`, and schedules revival instruction injection
- **New API endpoint** `POST /api/agents/<agent-id>/revive` that triggers the revival flow from the dashboard
- **Revival instruction injection** via tmux bridge after the successor agent's session-start hook fires (post-skill-injection for persona agents, immediately for anonymous agents)
- **New hook_receiver integration** to detect revival-pending agents at session_start and inject the revival instruction
- **Dashboard UI** additions: "Revive" button on dead agent cards and predecessor link on successor cards

## Impact

- Affected specs: Agent lifecycle, CLI commands, dashboard UI, hook receiver
- Affected code:
  - `src/claude_headspace/cli/launcher.py` (new `transcript` subcommand)
  - `src/claude_headspace/services/revival_service.py` (new)
  - `src/claude_headspace/routes/agents.py` (new revive endpoint)
  - `src/claude_headspace/services/hook_receiver.py` (revival injection at session_start)
  - `templates/partials/` (revive button on agent cards)
  - `static/js/` (revive button click handler)
  - `tests/services/test_revival_service.py` (new)
  - `tests/routes/test_agents.py` (revive endpoint tests)
  - `tests/cli/test_transcript_cli.py` (new)
- Related existing files:
  - `src/claude_headspace/models/agent.py` (has `previous_agent_id`, `persona_id`, `ended_at`)
  - `src/claude_headspace/models/command.py` (queried for transcript)
  - `src/claude_headspace/models/turn.py` (queried for transcript)
  - `src/claude_headspace/services/agent_lifecycle.py` (has `create_agent()` with `previous_agent_id` support)
  - `src/claude_headspace/services/skill_injector.py` (persona injection pattern to follow)
  - `src/claude_headspace/services/tmux_bridge.py` (used for revival instruction delivery)
- Recent related commits:
  - `0b75617f` — orphan cleanup safety guards for agent lifecycle
  - `37f2cabb` — DB-level prompt_injected_at for skill injection idempotency
  - `b3e52b7c` — agent creation with persona end-to-end
  - `64bcbebb` — CASCADE->SET NULL on nullable FKs
