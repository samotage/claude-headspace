# Proposal: e8-s4-agent-model-extensions

## Summary

Extend the existing Agent model with three nullable foreign keys — `persona_id`, `position_id`, and `previous_agent_id` — connecting agents to the persona system, organisational structure, and handoff continuity chain. Add corresponding SQLAlchemy relationships on Agent and the `Persona.agents` backref. Single additive Alembic migration. No service, route, or UI changes.

## Motivation

Agents are currently anonymous (session UUIDs only). Sprints 1-3 created Role, Persona, Organisation, and Position tables but none connect to Agent. This sprint makes Agent the join point between identity (Persona), structure (Position), and continuity (predecessor chain), enabling downstream persona-aware features in S7-S14.

## Impact

### Files Modified

- `src/claude_headspace/models/agent.py` — Add three nullable FK columns (`persona_id`, `position_id`, `previous_agent_id`), relationships (`persona`, `position`, `previous_agent`, `successor_agents`), and TYPE_CHECKING imports for Persona and Position
- `src/claude_headspace/models/persona.py` — Add `agents` relationship with `back_populates="persona"`, and Agent TYPE_CHECKING import

### Files Created

- `migrations/versions/xxx_add_agent_persona_position_predecessor.py` — Single migration adding three nullable integer columns with FK constraints (all ON DELETE CASCADE)
- `tests/integration/test_agent_model_extensions.py` — Integration tests for new FK columns, relationships, backrefs, and constraints

### No Changes Required

- `src/claude_headspace/models/__init__.py` — Agent and Persona already registered
- `src/claude_headspace/models/position.py` — No backref from Position to Agent needed per PRD
- All existing services, routes, templates, and tests — nullable fields ensure backward compatibility

## Approach

1. Follow established model patterns: `Mapped[int | None]`, `mapped_column()`, `ForeignKey(ondelete="CASCADE")`, `relationship()` with `back_populates`
2. Self-referential FK (`previous_agent_id`) uses `remote_side` pattern matching Position's `reports_to_id` from E8-S3
3. No unique constraint on `persona_id` — multiple agents can share same persona (workshop decision 2.3)
4. Migration depends on `a3b8c1d2e4f5` (Position table) which transitively depends on Role/Persona and Organisation migrations

## Definition of Done

- [ ] Agent model has `persona_id`, `position_id`, `previous_agent_id` nullable FK columns
- [ ] Agent has `persona`, `position`, `previous_agent`, `successor_agents` relationships
- [ ] Persona has `agents` backref relationship
- [ ] Alembic migration adds three columns to existing `agents` table
- [ ] Migration is reversible (downgrade removes columns)
- [ ] Existing Agent data unaffected (all new fields default NULL)
- [ ] All existing tests continue to pass
- [ ] Integration tests verify FK relationships, backrefs, nullability, and self-referential chain
