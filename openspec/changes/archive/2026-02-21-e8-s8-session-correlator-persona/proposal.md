## Why

Personas exist in the database (S1, S6) and the hook pipeline carries `persona_slug` through to `process_session_start()` (S7), but no code actually looks up the Persona record and sets `agent.persona_id`. Without this, personas are never connected to running agents, blocking downstream sprints (skill injection S9, dashboard identity S10).

## What Changes

- `process_session_start()` in `hook_receiver.py` replaces transient `_pending_persona_slug` storage with actual Persona lookup and `agent.persona_id` assignment
- `process_session_start()` sets `agent.previous_agent_id` when `previous_agent_id` is provided (integer conversion from string)
- Graceful degradation: unrecognised persona slug logs a warning and creates agent without persona (does not block registration)
- No changes to SessionCorrelator's 6-strategy correlation cascade
- Backward compatible: sessions without `persona_slug` are unchanged

## Impact

- Affected specs: session-correlator-persona (new capability)
- Affected code:
  - MODIFIED: `src/claude_headspace/services/hook_receiver.py` — `process_session_start()` gains Persona lookup + assignment logic, replaces transient attribute storage
- Affected tests:
  - MODIFIED: `tests/services/test_hook_receiver.py` — update existing S7 persona tests, add new tests for DB assignment, graceful degradation, previous_agent_id integer conversion

## Definition of Done

- [ ] `session-start` with `persona_slug="con"` results in `agent.persona_id` set to the matching Persona's ID
- [ ] `session-start` without `persona_slug` results in `agent.persona_id = NULL` (unchanged)
- [ ] `session-start` with unrecognised `persona_slug` results in agent created without persona + warning logged
- [ ] `agent.persona` relationship is navigable after assignment
- [ ] `previous_agent_id` string is converted to integer and set on `agent.previous_agent_id`
- [ ] Existing SessionCorrelator tests pass unchanged (no regressions)
- [ ] Persona assignment logged at INFO level with slug, persona ID, and agent ID
