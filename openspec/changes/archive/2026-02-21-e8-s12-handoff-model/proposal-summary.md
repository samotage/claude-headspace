# Proposal Summary: e8-s12-handoff-model

## Architecture Decisions
- New `Handoff` model follows hybrid storage design (workshop decision 5.1): DB stores orchestration metadata + injection prompt, filesystem stores detailed handoff document
- Handoff belongs to the outgoing agent (the one that produced the handoff), not the successor
- One-to-one relationship: Agent has at most one Handoff (application-level enforcement, not DB constraint)
- ON DELETE CASCADE: deleting an Agent cascades to its Handoff record
- Integer PK consistent with codebase convention (not UUID)
- No service layer, no UI, no routes — purely data model and migration

## Implementation Approach
- Create new model file `src/claude_headspace/models/handoff.py` following Persona model pattern
- Add `handoff` relationship to Agent model with `uselist=False` and `back_populates`
- Register in `models/__init__.py`
- Create additive Alembic migration
- Integration tests following existing `test_role_persona_models.py` pattern

## Files to Modify
- **Models:** `src/claude_headspace/models/handoff.py` (NEW) — Handoff model
- **Models:** `src/claude_headspace/models/agent.py` — add handoff relationship
- **Models:** `src/claude_headspace/models/__init__.py` — register Handoff
- **Migration:** `migrations/versions/xxxx_add_handoff_table.py` (NEW) — Alembic migration
- **Tests:** `tests/integration/test_handoff_model.py` (NEW) — integration tests

## Acceptance Criteria
- Handoff table exists after migration
- Handoff record can be created with agent_id, reason, file_path, injection_prompt
- Handoff.agent navigates to the outgoing Agent
- Agent.handoff returns Handoff or None
- Multiple handoffs can reference different agents
- Existing tables unaffected
- Migration is additive
- Model follows SQLAlchemy 2.0+ Mapped conventions
- All existing tests pass

## Constraints and Gotchas
- **Table name:** Use `handoffs` (plural) consistent with `agents`, `personas`, `positions`, `roles`
- **Agent model TYPE_CHECKING:** Add `Handoff` to the `TYPE_CHECKING` block in agent.py
- **Relationship back_populates:** Handoff.agent back_populates="handoff" on Agent; Agent.handoff back_populates="agent" on Handoff
- **uselist=False:** Agent.handoff must use `uselist=False` for one-to-one
- **No reason enum at DB level:** PRD explicitly says application-level validation only
- **No one-to-one constraint at DB level:** PRD explicitly says application-level check is sufficient
- **Migration must be applied immediately** per orchestration Migration Protocol (flask db upgrade + restart)
- **created_at default:** Use `server_default=func.now()` or `default=lambda: datetime.now(timezone.utc)` — follow codebase convention

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/persona.py`, `agent.py`, `__init__.py`
- Migrations: `migrations/versions/0462474af024_add_role_and_persona_tables.py`, `b5c9d3e6f7a8_add_agent_persona_position_predecessor.py`
- Tests: `tests/integration/test_role_persona_models.py`, `tests/integration/test_persona_registration.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) — Role and Persona DB models
- `e8-s5-persona-filesystem-assets` (2026-02-21) — Persona filesystem assets
- `e8-s6-persona-registration` (2026-02-21) — Persona registration service
- `e8-s7-persona-aware-agent-creation` (2026-02-21) — Agent creation with persona
- `e8-s8-session-correlator-persona` (2026-02-21) — Session correlator persona support

### Implementation Patterns
- Model → Migration → Registration → Integration Tests
- Persona model provides the reference pattern for model structure
- Agent model shows how to add relationships with TYPE_CHECKING imports

## Q&A History
- No clarifications needed — PRD is comprehensive with clear technical context

## Dependencies
- No new packages
- Depends on Agent model (agents table must exist)
- Depends on E8-S4 (previous_agent_id FK on Agent — already implemented)

## Testing Strategy
- Integration tests (real PostgreSQL, factory-boy pattern from test_role_persona_models.py)
- Test CRUD operations on Handoff model
- Test Handoff.agent and Agent.handoff relationships
- Test cascade delete behaviour
- Regression: existing tests pass without modification

## OpenSpec References
- proposal.md: openspec/changes/e8-s12-handoff-model/proposal.md
- tasks.md: openspec/changes/e8-s12-handoff-model/tasks.md
- spec.md: openspec/changes/e8-s12-handoff-model/specs/handoff-model/spec.md
