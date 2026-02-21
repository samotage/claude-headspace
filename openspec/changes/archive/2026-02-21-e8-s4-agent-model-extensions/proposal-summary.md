# Proposal Summary: e8-s4-agent-model-extensions

## Architecture Decisions
- Agent gets direct `persona_id` and `position_id` FKs — no PositionAssignment join table (workshop decision 2.2)
- No unique constraint on `persona_id` — multiple agents can share same persona simultaneously (workshop decision 2.3)
- `previous_agent_id` self-referential FK for continuity chain — same `remote_side` pattern as Position's `reports_to_id`
- All three new columns nullable for full backward compatibility
- ON DELETE CASCADE on all three FKs

## Implementation Approach
- Extend existing Agent model with three nullable FK columns and four relationships
- Add `agents` backref to Persona model
- Single Alembic migration adding columns to existing `agents` table
- No changes to `__init__.py` (Agent and Persona already registered), Position model, or any services/routes

## Files to Modify
- `src/claude_headspace/models/agent.py` — Add 3 FK columns, 4 relationships, 2 TYPE_CHECKING imports
- `src/claude_headspace/models/persona.py` — Add `agents` relationship, Agent TYPE_CHECKING import

## Files to Create
- `migrations/versions/xxx_add_agent_persona_position_predecessor.py` — Migration adding 3 nullable columns with FK constraints
- `tests/integration/test_agent_model_extensions.py` — Integration tests for all new FKs, relationships, backrefs

## Acceptance Criteria
- Agent model has `persona_id`, `position_id`, `previous_agent_id` nullable FK columns
- Agent has `persona`, `position`, `previous_agent`, `successor_agents` relationships
- Persona has `agents` backref relationship
- Migration is additive and reversible
- Existing agents unaffected (all new fields NULL)
- All existing tests pass unchanged

## Constraints and Gotchas
- Self-referential FK on Agent requires `remote_side` and `foreign_keys` parameters — follow Position model pattern exactly
- Agent already has a TYPE_CHECKING block with Project and Command — add Persona and Position to it
- Persona already has a TYPE_CHECKING block with Role — add Agent to it
- Migration must depend on `a3b8c1d2e4f5` (Position table) which is the latest in the chain
- No `back_populates` on `position` relationship — Position doesn't need an `agents` backref per PRD scope

## Git Change History

### Related Files
- Models: `agent.py` (17 existing fields), `persona.py` (has `role` relationship), `position.py` (has self-ref FK pattern)
- Init: `__init__.py` (Agent and Persona already registered)
- Migrations: `0462474af024` (Role+Persona), `77a46a29dc5e` (Organisation), `a3b8c1d2e4f5` (Position)

### OpenSpec History
- e8-s1-role-persona-models: Created Role and Persona tables (merged)
- e8-s2-organisation-model: Created Organisation table (merged)
- e8-s3-position-model: Created Position table with self-referential FKs (merged)

### Implementation Patterns
- Model pattern: `Mapped[type]`, `mapped_column()`, `ForeignKey(ondelete="CASCADE")`, `relationship(back_populates=...)`
- Self-referential pattern: `remote_side="Model.id"`, `foreign_keys=[fk_column]`, `back_populates="reverse_name"`
- TYPE_CHECKING pattern: `if TYPE_CHECKING: from .model import Model`
- Integration test pattern: pytest fixtures for model instances, `db_session` fixture, `IntegrityError` for constraint tests

## Q&A History
- No clarifications needed — PRD is clear, all design decisions resolved in workshop

## Dependencies
- No new packages needed
- Database migration required (additive only)
- Depends on E8-S1 (Role+Persona), E8-S2 (Organisation), E8-S3 (Position) migrations being applied

## Testing Strategy
- Integration tests against real PostgreSQL (`claude_headspace_test` database)
- Test each FK column + relationship independently
- Test self-referential continuity chain (A → B → C)
- Test `Persona.agents` backref
- Test multiple agents sharing same persona (no uniqueness constraint)
- Test backward compatibility (all new fields NULL)
- Test FK integrity errors (referencing non-existent records)
- Run existing Agent-related tests to verify no regressions

## OpenSpec References
- proposal.md: openspec/changes/e8-s4-agent-model-extensions/proposal.md
- tasks.md: openspec/changes/e8-s4-agent-model-extensions/tasks.md
- spec.md: openspec/changes/e8-s4-agent-model-extensions/specs/agent-model-extensions/spec.md
