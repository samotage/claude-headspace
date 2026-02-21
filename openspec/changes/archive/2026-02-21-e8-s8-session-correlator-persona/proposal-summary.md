# Proposal Summary: e8-s8-session-correlator-persona

## Architecture Decisions
- Persona assignment happens in `process_session_start()` (hook_receiver), NOT in SessionCorrelator — keeps persona logic in one place and avoids modifying the 6-strategy correlation cascade
- S7 stored persona_slug as transient `_pending_persona_slug` attribute; S8 replaces this with actual Persona DB lookup and `agent.persona_id` assignment
- Graceful degradation: unrecognised slugs log a warning but don't block agent registration (PRD FR5)
- `previous_agent_id` arrives as string from env vars/hook payload — convert to int before setting on Agent model
- No changes to `correlate_session()` or `_create_agent_for_session()` — the correlator's job is correlation only

## Implementation Approach
- Replace transient `_pending_persona_slug` storage in `process_session_start()` with: import Persona model → query by slug → if found, set `agent.persona_id` → log assignment
- Replace transient `_pending_previous_agent_id` storage with: convert string to int → set `agent.previous_agent_id`
- Wrap Persona lookup in try/except for DB error resilience
- The existing `db.session.commit()` later in `process_session_start()` will persist the persona_id and previous_agent_id along with other agent updates

## Files to Modify
- **MODIFIED** `src/claude_headspace/services/hook_receiver.py` — `process_session_start()` replaces transient attributes with actual DB assignment

## Acceptance Criteria
- `session-start` with `persona_slug="con"` sets `agent.persona_id` to matching Persona's ID
- `session-start` without `persona_slug` leaves `agent.persona_id = NULL`
- Unrecognised slug logs warning, creates agent without persona
- `agent.persona` relationship navigable after assignment
- `previous_agent_id` string converted to int and set on agent
- Existing tests pass unchanged
- Persona assignment logged at INFO with slug, persona ID, agent ID

## Constraints and Gotchas
- **S7's transient attributes must be replaced, not augmented**: The `_pending_persona_slug` and `_pending_previous_agent_id` attributes were temporary placeholders for S8. Remove them and replace with actual DB operations.
- **Persona import**: Use local import `from ..models.persona import Persona` inside the function to avoid circular imports (same pattern used in `agent_lifecycle.py`)
- **previous_agent_id is a string**: Comes from environment variable → hook payload → parameter. Must convert to int with error handling.
- **DB commit timing**: `process_session_start()` already updates agent fields (last_seen_at, ended_at, transcript_path, claude_session_id) and the changes are committed later in the hook processing flow. persona_id and previous_agent_id will be committed in the same transaction.
- **Thread safety**: Persona lookup is a read query within the existing request context — thread-safe by default via Flask-SQLAlchemy's scoped sessions.
- **No need to modify hooks.py or correlate_session()**: S7 already passes persona_slug and previous_agent_id to `process_session_start()`. S8 only needs to act on them inside that function.

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/hook_receiver.py`, `src/claude_headspace/services/session_correlator.py`
- Models: `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/agent.py`
- Tests: `tests/services/test_hook_receiver.py`, `tests/services/test_session_correlator.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) — created Role + Persona models
- `e8-s4-agent-model-extensions` (2026-02-20) — added Agent.persona_id FK, Agent.previous_agent_id
- `e8-s7-persona-aware-agent-creation` (2026-02-21) — hook payload carries persona_slug, transient _pending attributes

### Implementation Patterns
- Modules + tests only (no templates, static, config, or migration changes)
- Local model import pattern (avoid circular imports)
- Graceful degradation pattern: log warning, continue without blocking

## Q&A History
- No clarifications needed — PRD is clear and consistent with prior sprints

## Dependencies
- No new packages needed
- Consumes E8-S1 Persona model (slug lookup)
- Consumes E8-S4 Agent model extensions (persona_id FK, previous_agent_id column)
- Consumes E8-S7 hook payload persona_slug passthrough

## Testing Strategy
- **Unit tests** for `process_session_start()`: mock Persona.query, verify persona_id assignment, verify warning logging for unknown slug, verify no DB query when slug absent
- **Unit tests** for previous_agent_id: verify string-to-int conversion, verify assignment on agent record
- **Regression tests**: run existing hook_receiver and session_correlator tests

## OpenSpec References
- proposal.md: openspec/changes/e8-s8-session-correlator-persona/proposal.md
- tasks.md: openspec/changes/e8-s8-session-correlator-persona/tasks.md
- spec.md: openspec/changes/e8-s8-session-correlator-persona/specs/session-correlator-persona/spec.md
