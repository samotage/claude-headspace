## Why

Agents in Claude Headspace can read the system's source code, configuration, and API surface. The current channel communication implementation accepts agent identity as an unauthenticated claim via HTTP headers (`X-Headspace-Agent-ID`) and environment variables (`HEADSPACE_AGENT_ID`), enabling any agent to spoof messages as another persona. Security must be achieved by removing exploitable capabilities, not by adding secrets that agents can discover.

## What Changes

- **BREAKING** Remove `X-Headspace-Agent-ID` HTTP header acceptance from `channels_api.py::_resolve_caller()` — agent identity via HTTP must require a validated Bearer token
- **BREAKING** Remove `HEADSPACE_AGENT_ID` environment variable override from `caller_identity.py::resolve_caller()` — CLI caller identity must use only tmux pane-to-agent binding
- **BREAKING** Restrict agent-exploitable CLI commands (`flask msg send`, `flask channel create`, `flask channel add`, `flask channel leave`, `flask channel complete`, `flask channel transfer-chair`, `flask channel mute`, `flask channel unmute`) — agents running in tmux panes must not use these to bypass the system-mediated routing model
- Confirm and harden system-mediated routing via `ChannelDeliveryService.relay_agent_response()` as the sole path for internal agent messages (COMPLETION and END_OF_COMMAND intents only)
- Preserve Bearer token authentication for remote agents (no changes to SessionTokenService path)
- Preserve dashboard operator authentication via session cookie fallback (no changes to Persona.get_operator() path)
- Update `caller-identity` OpenSpec spec to remove the env var override requirement
- Document the two trust models (infrastructure identity for internal agents, validated tokens for remote agents)

## Impact

- Affected specs: `caller-identity` (env var requirement removed)
- Affected code:
  - `src/claude_headspace/routes/channels_api.py` (remove X-Headspace-Agent-ID header path)
  - `src/claude_headspace/services/caller_identity.py` (remove HEADSPACE_AGENT_ID env var override)
  - `src/claude_headspace/cli/msg_cli.py` (restrict `flask msg send` to operator contexts)
  - `src/claude_headspace/cli/channel_cli.py` (restrict mutating commands to operator contexts)
  - `src/claude_headspace/services/channel_delivery.py` (no changes expected — already correct)
  - `openspec/specs/caller-identity/spec.md` (update to reflect new resolution strategy)
  - `docs/architecture/channel-trust-models.md` (new — trust model documentation)
- Affected tests:
  - `tests/routes/test_channels_api.py` (update for removed header path)
  - `tests/services/test_caller_identity.py` (update for removed env var strategy)
  - `tests/cli/test_msg_cli.py` (update for restricted commands)
  - `tests/cli/test_channel_cli.py` (update for restricted commands)
