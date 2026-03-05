## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Remove unauthenticated HTTP identity assertion (FR1)

- [ ] 2.1.1 Remove the `X-Headspace-Agent-ID` header check from `channels_api.py::_resolve_caller()` — delete lines 133-144 that accept raw agent ID without token validation
- [ ] 2.1.2 Verify the Bearer token path and session cookie fallback remain intact and unchanged

### 2.2 Remove environment-variable identity override (FR2)

- [ ] 2.2.1 Remove the `HEADSPACE_AGENT_ID` env var override (Strategy 1) from `caller_identity.py::resolve_caller()` — delete lines 69-81
- [ ] 2.2.2 Update function docstring to reflect tmux-only resolution strategy
- [ ] 2.2.3 Remove `os` import if no longer needed

### 2.3 Audit and restrict agent-exploitable CLI commands (FR3)

- [ ] 2.3.1 Add an operator-context guard to mutating CLI commands — `flask msg send`, `flask channel create`, `flask channel add`, `flask channel leave`, `flask channel complete`, `flask channel transfer-chair`, `flask channel mute`, `flask channel unmute`
- [ ] 2.3.2 Implement the guard as a shared decorator or utility in `cli_utils.py` that detects whether the caller is in an agent tmux context and rejects the command if so (tmux pane-to-agent binding means the caller IS an agent, and agents must not use CLI to bypass system-mediated routing)
- [ ] 2.3.3 Allow read-only CLI commands to remain accessible (`flask channel list`, `flask channel show`, `flask channel members`, `flask msg history`)
- [ ] 2.3.4 Allow `flask persona list` and `flask persona handoffs` to remain accessible (read-only)
- [ ] 2.3.5 Restrict `flask persona register` to operator-only contexts (persona creation should not be agent-initiated)

### 2.4 Confirm system-mediated routing (FR4, FR5)

- [ ] 2.4.1 Audit `ChannelDeliveryService.relay_agent_response()` to confirm it only relays COMPLETION and END_OF_COMMAND intents (already implemented — verify no regressions)
- [ ] 2.4.2 Audit the hook_receiver call site that invokes relay_agent_response to confirm the relay path is correct

### 2.5 Preserve remote agent token auth (FR6)

- [ ] 2.5.1 Verify Bearer token validation path in `channels_api.py::_resolve_caller()` is unchanged
- [ ] 2.5.2 Run existing remote agent channel tests to confirm no regression

### 2.6 Preserve operator dashboard auth (FR7)

- [ ] 2.6.1 Verify session cookie fallback via `Persona.get_operator()` is unchanged
- [ ] 2.6.2 Run existing dashboard channel tests to confirm no regression

### 2.7 Update OpenSpec caller-identity spec (FR2 impact)

- [ ] 2.7.1 Update `openspec/specs/caller-identity/spec.md` to remove the env var override requirement and document tmux-only resolution

### 2.8 Document trust models (FR8)

- [ ] 2.8.1 Create `docs/architecture/channel-trust-models.md` documenting internal agent (infrastructure identity) and remote agent (validated token) trust models

## 3. Testing (Phase 3)

- [ ] 3.1 Update `tests/services/test_caller_identity.py` — remove/update tests for env var strategy, ensure tmux-only resolution is tested
- [ ] 3.2 Update `tests/routes/test_channels_api.py` — remove/update tests for X-Headspace-Agent-ID header, add tests verifying the header is rejected
- [ ] 3.3 Update `tests/cli/test_msg_cli.py` — add tests for operator-only restriction on `flask msg send`
- [ ] 3.4 Update `tests/cli/test_channel_cli.py` — add tests for operator-only restriction on mutating commands
- [ ] 3.5 Add test: internal agent cannot post to channel via HTTP with spoofed header
- [ ] 3.6 Add test: internal agent cannot post to channel via CLI `flask msg send`
- [ ] 3.7 Add test: remote agent CAN post to channel via valid Bearer token (no regression)
- [ ] 3.8 Add test: operator CAN post to channel via session cookie (no regression)
- [ ] 3.9 Add test: system-mediated relay only fires on COMPLETION/END_OF_COMMAND intents

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: confirm dashboard chat still works for operator
- [ ] 4.4 Manual verification: confirm system-mediated relay still delivers agent messages to channels
