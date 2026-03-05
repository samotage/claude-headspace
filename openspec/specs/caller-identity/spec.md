# caller-identity Specification

## Purpose
Provides infrastructure-verified agent identity resolution for CLI commands, using tmux pane detection as the sole resolution strategy. This ensures agent identity cannot be spoofed via environment variables or other user-controllable inputs.

## Requirements
### Requirement: Caller Identity Resolution (FR18)
A `resolve_caller()` function SHALL resolve the calling agent using tmux pane detection only: tmux `display-message` pane ID -> Agent lookup. If resolution fails, raise `CallerResolutionError`.

The `HEADSPACE_AGENT_ID` env var override was **removed** in the `agent-channel-security` change as a security hardening measure — it was a spoofable identity assertion.

#### Scenario: Tmux pane detection
- **WHEN** tmux `display-message -p '#{pane_id}'` returns a valid pane ID
- **AND** an active Agent has that `tmux_pane_id`
- **THEN** the Agent is returned

#### Scenario: No resolution
- **WHEN** tmux pane detection fails to resolve an agent
- **THEN** `CallerResolutionError` is raised with message: "Error: Cannot identify calling agent. Are you running in a Headspace-managed session?"

#### Scenario: Env var ignored
- **WHEN** `HEADSPACE_AGENT_ID` env var is set
- **THEN** it is ignored — only tmux pane detection is used

---

### Requirement: CallerResolutionError
`CallerResolutionError` SHALL be a standalone exception (not a `ChannelError` subclass) because caller identity resolution is shared infrastructure, not channel-specific logic.

#### Scenario: Independent exception
- **WHEN** `CallerResolutionError` is imported
- **THEN** it is NOT a subclass of `ChannelError`
- **AND** it IS a subclass of `Exception`

---

### Requirement: Module Location
The caller identity module SHALL be at `src/claude_headspace/services/caller_identity.py`, importable by CLI commands and future API routes.

#### Scenario: Import path
- **WHEN** `from claude_headspace.services.caller_identity import resolve_caller, CallerResolutionError` is executed
- **THEN** both are available

