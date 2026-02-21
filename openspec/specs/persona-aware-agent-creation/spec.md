# persona-aware-agent-creation Specification

## Purpose
TBD - created by archiving change e8-s7-persona-aware-agent-creation. Update Purpose after archive.
## Requirements
### Requirement: Programmatic agent creation with persona

The `create_agent()` function SHALL accept an optional `persona_slug` string parameter and an optional `previous_agent_id` integer parameter. When `persona_slug` is provided, the function SHALL validate it against the Persona table (slug exists with status "active") before launching a session. When valid, the persona slug SHALL be included in the CLI command arguments passed to the tmux session. When `previous_agent_id` is provided, it SHALL be passed through session metadata.

#### Scenario: Valid persona slug provided
- **WHEN** `create_agent(project_id=X, persona_slug="developer-con-1")` is called and persona "developer-con-1" exists with status "active"
- **THEN** the tmux session is launched with persona slug in the CLI arguments and environment

#### Scenario: Invalid persona slug provided
- **WHEN** `create_agent(project_id=X, persona_slug="nonexistent")` is called and no active persona with that slug exists
- **THEN** `CreateResult(success=False)` is returned with an error message naming the slug and suggesting registration, and no session is launched

#### Scenario: No persona specified (backward compatible)
- **WHEN** `create_agent(project_id=X)` is called without persona_slug
- **THEN** behaviour is identical to the current implementation — anonymous agent creation

### Requirement: CLI persona flag

The `claude-headspace start` command SHALL accept an optional `--persona <slug>` argument. When provided, the CLI SHALL validate the slug against the database. If valid, the slug SHALL be set as environment variable `CLAUDE_HEADSPACE_PERSONA_SLUG` for hook script inheritance. If invalid, the CLI SHALL print an error and exit without launching Claude Code.

#### Scenario: CLI with valid persona
- **WHEN** `claude-headspace start --persona developer-con-1` is executed and persona exists
- **THEN** session launches with `CLAUDE_HEADSPACE_PERSONA_SLUG=developer-con-1` in the environment

#### Scenario: CLI with invalid persona
- **WHEN** `claude-headspace start --persona nonexistent` is executed and persona does not exist
- **THEN** an error message is printed and the process exits with non-zero exit code without launching Claude Code

#### Scenario: CLI without persona (backward compatible)
- **WHEN** `claude-headspace start` is executed without --persona
- **THEN** behaviour is identical to the current implementation

### Requirement: Hook payload extension

The hook notification script (`notify-headspace.sh`) SHALL read `CLAUDE_HEADSPACE_PERSONA_SLUG` and `CLAUDE_HEADSPACE_PREVIOUS_AGENT_ID` from the environment. When either value is present, it SHALL be included in the JSON payload as `persona_slug` and `previous_agent_id` respectively. When absent, the corresponding field SHALL be omitted from the payload.

#### Scenario: Persona slug in environment
- **WHEN** `CLAUDE_HEADSPACE_PERSONA_SLUG=developer-con-1` is set in the session environment
- **THEN** the hook payload includes `"persona_slug": "developer-con-1"`

#### Scenario: No persona slug in environment
- **WHEN** `CLAUDE_HEADSPACE_PERSONA_SLUG` is not set
- **THEN** the hook payload does not include a `persona_slug` field

### Requirement: Hook route extraction

The `/hook/session-start` route handler SHALL extract `persona_slug` and `previous_agent_id` from the incoming payload when present and pass them to `process_session_start()`. S7 owns this extraction — S8 consumes these values as inputs.

#### Scenario: Payload contains persona_slug and previous_agent_id
- **WHEN** session-start payload includes `persona_slug` and `previous_agent_id`
- **THEN** both values are extracted and passed to `process_session_start()`

#### Scenario: Payload without persona fields
- **WHEN** session-start payload does not include `persona_slug` or `previous_agent_id`
- **THEN** `process_session_start()` is called with None for both parameters (backward compatible)

### Requirement: Hook receiver passthrough

`process_session_start()` SHALL accept optional `persona_slug` and `previous_agent_id` parameters and make them available for Sprint 8's SessionCorrelator to consume when setting `agent.persona_id` and `agent.previous_agent_id`.

#### Scenario: Persona slug passed to process_session_start
- **WHEN** `process_session_start()` is called with `persona_slug="developer-con-1"`
- **THEN** the persona slug is stored or passed through for S8 consumption

### Requirement: Backward compatibility

All existing agent creation flows SHALL continue to work unchanged. Omitting persona parameters SHALL produce identical behaviour to the current implementation. No existing tests SHALL break.

#### Scenario: Existing anonymous agent creation
- **WHEN** any current agent creation flow is executed without persona parameters
- **THEN** behaviour is identical to the pre-S7 implementation

