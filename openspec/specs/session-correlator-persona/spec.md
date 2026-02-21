# session-correlator-persona Specification

## Purpose
TBD - created by archiving change e8-s8-session-correlator-persona. Update Purpose after archive.
## Requirements
### Requirement: Persona assignment during session start

When `process_session_start()` receives a non-empty `persona_slug` parameter, it SHALL look up the Persona record by slug using the existing database session. When found, it SHALL set `agent.persona_id` to the Persona's database ID. The assignment SHALL occur before the agent record is committed.

#### Scenario: Valid persona slug provided
- **WHEN** `process_session_start()` is called with `persona_slug="developer-con-1"` and a Persona with slug "developer-con-1" exists in the database
- **THEN** `agent.persona_id` is set to the Persona's ID and `agent.persona.name` is navigable

#### Scenario: Unknown persona slug provided
- **WHEN** `process_session_start()` is called with `persona_slug="nonexistent"` and no Persona with that slug exists
- **THEN** the agent is created with `persona_id = NULL`, a warning is logged containing the unrecognised slug, and no error is returned to the hook caller

#### Scenario: No persona slug provided
- **WHEN** `process_session_start()` is called without `persona_slug` (None or empty)
- **THEN** no Persona lookup occurs and `agent.persona_id` remains NULL — identical to pre-S8 behaviour

#### Scenario: Database error during Persona lookup
- **WHEN** a database error occurs during the Persona slug lookup
- **THEN** the error is logged, the agent is created without persona, and registration is not blocked

### Requirement: Previous agent ID assignment

When `process_session_start()` receives a non-empty `previous_agent_id` parameter, it SHALL convert the string value to an integer and set `agent.previous_agent_id` on the Agent record.

#### Scenario: Previous agent ID provided
- **WHEN** `process_session_start()` is called with `previous_agent_id="42"`
- **THEN** `agent.previous_agent_id` is set to integer 42

#### Scenario: No previous agent ID
- **WHEN** `process_session_start()` is called without `previous_agent_id`
- **THEN** `agent.previous_agent_id` remains NULL

### Requirement: Persona assignment logging

When a persona is successfully assigned to an agent, the system SHALL log at INFO level with: persona slug, persona database ID, and agent database ID.

#### Scenario: Successful assignment logged
- **WHEN** persona "developer-con-1" (id=5) is assigned to agent 42
- **THEN** an INFO log contains the persona slug, persona ID 5, and agent ID 42

### Requirement: Backward compatibility

All existing hook receiver and session correlator tests SHALL continue to pass without modification. Sessions without persona_slug SHALL be processed identically to pre-S8 implementation.

#### Scenario: Existing anonymous agent creation unchanged
- **WHEN** a session-start hook fires without `persona_slug` in the payload
- **THEN** agent creation follows the existing logic with `persona_id = NULL` and no Persona database queries are made

