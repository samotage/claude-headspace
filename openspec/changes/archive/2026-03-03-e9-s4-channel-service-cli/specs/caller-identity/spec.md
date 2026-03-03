## ADDED Requirements

### Requirement: Caller Identity Resolution (FR18)
A `resolve_caller()` function SHALL resolve the calling agent using a two-strategy cascade: (1) `HEADSPACE_AGENT_ID` env var override (takes precedence when set), (2) tmux `display-message` pane detection. If neither resolves, raise `CallerResolutionError`.

#### Scenario: Env var override
- **WHEN** `HEADSPACE_AGENT_ID` is set to a valid agent ID
- **THEN** the corresponding active Agent is returned

#### Scenario: Invalid env var
- **WHEN** `HEADSPACE_AGENT_ID` is set to an invalid or non-existent ID
- **THEN** fallback to tmux detection is attempted

#### Scenario: Tmux pane detection
- **WHEN** `HEADSPACE_AGENT_ID` is not set
- **AND** tmux `display-message -p '#{pane_id}'` returns a valid pane ID
- **AND** an active Agent has that `tmux_pane_id`
- **THEN** the Agent is returned

#### Scenario: No resolution
- **WHEN** neither strategy resolves an agent
- **THEN** `CallerResolutionError` is raised with message: "Error: Cannot identify calling agent. Are you running in a Headspace-managed session?"

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
