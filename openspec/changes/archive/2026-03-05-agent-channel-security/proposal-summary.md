# Proposal Summary: Agent Channel Communication Security

## Architecture Decisions

1. **Security by capability removal, not addition.** No new tokens, secrets, or authentication mechanisms. The spoofable paths (HTTP header, env var) are removed entirely. Agents cannot exploit what does not exist.

2. **Two trust models, architecturally enforced.**
   - *Internal agents* (tmux-bound): identity from infrastructure. No direct posting. System observes output and routes completed work to channels.
   - *Remote agents* (token-bound): identity from validated session tokens. Direct posting via authenticated HTTP endpoints.

3. **CLI restriction via caller-context detection.** Mutating CLI commands detect whether the caller is an agent (via tmux pane resolution success) and reject the operation. Read-only commands remain accessible to all.

4. **System-mediated routing is already correct.** `ChannelDeliveryService.relay_agent_response()` already implements completion-only relay (COMPLETION and END_OF_COMMAND intents). This change confirms and hardens that path — no new relay logic needed.

5. **OpenSpec spec update, not replacement.** The existing `caller-identity` spec is modified to remove the env var override requirement. The spec itself is not removed or restructured.

## Implementation Approach

The implementation is primarily subtractive — removing code paths rather than adding new ones.

1. **channels_api.py**: Delete the `X-Headspace-Agent-ID` header block (lines 133-144) from `_resolve_caller()`. The function retains Bearer token validation (first priority) and session cookie fallback (second priority).

2. **caller_identity.py**: Delete the `HEADSPACE_AGENT_ID` env var block (lines 69-81) from `resolve_caller()`. The function retains tmux pane detection as the sole resolution strategy.

3. **CLI restriction**: Add a shared `_reject_if_agent_context()` guard in `cli_utils.py`. This attempts tmux pane-to-agent resolution — if it succeeds, the caller IS an agent and the command is rejected. If it fails (CallerResolutionError), the caller is a human operator and the command proceeds. Apply this guard to all mutating commands in `channel_cli.py`, `msg_cli.py`, and `persona_cli.py` (register only).

4. **Tests**: Update existing tests to remove coverage of deleted paths. Add new tests verifying rejected paths return appropriate errors.

## Files to Modify

### Routes
- `src/claude_headspace/routes/channels_api.py` — Remove X-Headspace-Agent-ID header acceptance from `_resolve_caller()`

### Services
- `src/claude_headspace/services/caller_identity.py` — Remove HEADSPACE_AGENT_ID env var override from `resolve_caller()`
- `src/claude_headspace/services/channel_delivery.py` — Audit only (no changes expected)

### CLI
- `src/claude_headspace/cli/cli_utils.py` — Add `_reject_if_agent_context()` guard
- `src/claude_headspace/cli/channel_cli.py` — Apply guard to mutating commands (create, add, leave, complete, transfer-chair, mute, unmute)
- `src/claude_headspace/cli/msg_cli.py` — Apply guard to `send` command
- `src/claude_headspace/cli/persona_cli.py` — Apply guard to `register` command

### Specs
- `openspec/specs/caller-identity/spec.md` — Remove env var override requirement, document tmux-only resolution

### Documentation
- `docs/architecture/channel-trust-models.md` — New file documenting the two trust models

### Tests
- `tests/services/test_caller_identity.py` — Update for removed env var strategy
- `tests/routes/test_channels_api.py` — Update for removed header path
- `tests/cli/test_msg_cli.py` — Add operator-only restriction tests
- `tests/cli/test_channel_cli.py` — Add operator-only restriction tests

## Acceptance Criteria

1. No internal agent can post a message to any channel by calling an HTTP endpoint with a spoofed X-Headspace-Agent-ID header
2. No internal agent can post a message to any channel by setting HEADSPACE_AGENT_ID env var and running `flask msg send`
3. No internal agent can use `flask channel create`, `flask channel add`, or other mutating CLI commands
4. Internal agent messages appear in channels only via system-mediated relay (COMPLETION/END_OF_COMMAND)
5. Remote agents can post to channels via valid Bearer token (no regression)
6. Dashboard operators can post to channels via session cookie (no regression)
7. Read-only CLI commands (list, show, members, history) remain accessible to agents
8. No new tokens, secrets, or authentication mechanisms are introduced

## Constraints and Gotchas

1. **CLI guard must not break operator usage.** The guard uses `CallerResolutionError` as the "not an agent" signal. If tmux is not installed or not running, `resolve_caller()` raises CallerResolutionError, which means the operator path works. However, if an operator happens to be running in a tmux pane that is bound to an agent, the guard would incorrectly reject them. This edge case is acceptable — operators should not share tmux panes with active agents.

2. **Existing tests for env var and header paths will fail.** These tests validate the exact paths being removed. They must be updated, not just deleted — replace them with tests that verify the paths are rejected.

3. **The `resolve_caller_persona()` wrapper still works.** It calls `resolve_caller()` internally. Since we only changed what `resolve_caller()` accepts, the wrapper's behavior changes automatically. No separate changes needed.

4. **ChannelDeliveryService is already correct.** The relay_agent_response method already checks `turn_intent not in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)` and returns False. No changes to this service.

5. **The `caller-identity` OpenSpec spec currently requires env var override.** This spec must be updated as part of this change to avoid a stale-spec situation.

## Git Change History

### Related OpenSpec History
- `e9-s4-channel-service-cli` (archived 2026-03-03) — established the caller-identity spec and CLI commands being modified
- `caller-identity` spec — currently documents the env var + tmux cascade being changed to tmux-only

### Recent Commits (related areas)
- `f679208` — voice app kebab menus (unrelated, no conflicts)
- `3324266` — channel chat UX improvements, agent auth header (introduced the X-Headspace-Agent-ID header path being removed)
- `4ddff90c` — handoff implementation (unrelated)

### Patterns Detected
- Flask blueprint + service delegation pattern (routes are thin wrappers)
- CLI commands use `resolve_caller_persona()` from `caller_identity.py`
- Service injection via `app.extensions["service_name"]`

## Q&A History

No clarification needed. PRD is clear and unambiguous.

## Dependencies

- No new packages required
- No database migrations required
- No API changes for external consumers (remote agent token path unchanged)
- No configuration changes required

## Testing Strategy

1. **Unit tests**: Update `test_caller_identity.py` to verify env var is ignored, tmux-only resolution works
2. **Route tests**: Update `test_channels_api.py` to verify header is ignored, Bearer token still works, session cookie still works
3. **CLI tests**: Update `test_msg_cli.py` and `test_channel_cli.py` to verify agent context rejection
4. **Regression tests**: Verify remote agent and operator paths remain functional
5. **Integration audit**: Verify `ChannelDeliveryService.relay_agent_response()` relay behavior via existing tests

## OpenSpec References

- Proposal: `openspec/changes/agent-channel-security/proposal.md`
- Tasks: `openspec/changes/agent-channel-security/tasks.md`
- Spec: `openspec/changes/agent-channel-security/specs/channel-auth/spec.md`
- Related spec (modified): `openspec/specs/caller-identity/spec.md`
