# Proposal Summary: e8-s3-position-model

## Architecture Decisions
- Dual self-referential FK pattern: `reports_to_id` for org chart tree + `escalates_to_id` for separate escalation paths
- ON DELETE CASCADE on all FKs (org_id, role_id, reports_to_id, escalates_to_id) — simple cleanup in v1
- Integer PK — matches codebase convention
- `remote_side` parameter on self-referential relationships to resolve SQLAlchemy FK ambiguity
- `back_populates` pattern for bidirectional relationships (same as Persona↔Role)
- No seed data — positions are created by the operator when registering personas
- No circular hierarchy validation — deferred to future sprints (application-level concern)

## Implementation Approach
- Create Position model following established Mapped/mapped_column patterns from Role, Persona, Organisation models
- Add `positions` relationship to Organisation and Role models using `back_populates` (ORM-only, no schema changes)
- Single Alembic migration creating Position table with all FKs
- Migration downgrade simply drops the table (no seed data to clean up)
- Use `TYPE_CHECKING` blocks for forward reference type hints on Organisation and Role

## Files to Modify
- **New:** `src/claude_headspace/models/position.py` — Position model with all fields, relationships, and self-referential hierarchy
- **Modified:** `src/claude_headspace/models/__init__.py` — add import and `__all__` entry
- **Modified:** `src/claude_headspace/models/organisation.py` — add `positions` relationship with `back_populates`
- **Modified:** `src/claude_headspace/models/role.py` — add `positions` relationship with `back_populates`
- **New:** `migrations/versions/xxx_add_position_table.py` — table creation with FKs

## Acceptance Criteria
- Position table created with id (int PK), org_id (FK→Organisation), role_id (FK→Role), title (not null), reports_to_id (self-ref FK, nullable), escalates_to_id (self-ref FK, nullable), level (int, default 0), is_cross_cutting (bool, default False), created_at (UTC)
- Self-referential reporting hierarchy works: Position.reports_to returns parent, Position.direct_reports returns children
- Self-referential escalation path works: Position.escalates_to can differ from reports_to
- Position.role and Position.organisation relationships resolve correctly
- Organisation.positions and Role.positions backref relationships work
- Migration is additive and reversible — no impact on existing tables
- Model importable from `claude_headspace.models`

## Constraints and Gotchas
- Self-referential FKs require `remote_side=[Position.id]` on relationship definitions to avoid ambiguity errors
- Two self-referential FKs on the same table need `foreign_keys` parameter on each relationship to disambiguate
- `back_populates` for direct_reports must match the `reports_to` relationship (not `escalates_to`)
- Organisation and Role need `TYPE_CHECKING` import for Position type hints
- ON DELETE CASCADE on self-referential FKs means deleting a parent cascades to all reports — intentional for v1
- No changes to existing table schemas — relationship additions are ORM-only (no migration changes to Organisation or Role tables)

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/role.py`, `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/organisation.py` (pattern reference + modification targets)
- Migrations: `migrations/versions/0462474af024_add_role_and_persona_tables.py`, `migrations/versions/77a46a29dc5e_add_organisation_table.py` (pattern reference)
- Tests: `tests/integration/test_role_persona_models.py`, `tests/integration/test_organisation_model.py` (pattern reference)

### OpenSpec History
- e8-s1-role-persona-models (2026-02-20) — Role and Persona models, similar pattern
- e8-s2-organisation-model (2026-02-20) — Organisation model, FK target for Position.org_id

### Implementation Patterns
- Model: db.Model → Mapped/mapped_column → DateTime(timezone=True) → relationship(back_populates) → __repr__
- Migration: op.create_table → ForeignKeyConstraint → reverse in downgrade
- Test: integration tests with db_session fixture, create parent records first (Organisation, Role) then Position

## Q&A History
- No clarifications needed — PRD is fully specified with all design decisions resolved in workshop

## Dependencies
- No new packages required
- No external services involved
- One database migration needed (additive, no seed data)
- Depends on E8-S1 (Role table) and E8-S2 (Organisation table) — both already merged

## Testing Strategy
- Integration tests for Position model: creation, field defaults, relationship navigation
- Test dual self-referential hierarchy: reports_to chain + escalation chain
- Test Organisation.positions and Role.positions backref relationships
- Test not-null constraints on title, org_id, role_id
- Test top-level positions (NULL reports_to_id and escalates_to_id)
- Test migration reversibility
- Verify existing tests still pass (no regressions from relationship additions)

## OpenSpec References
- proposal.md: openspec/changes/e8-s3-position-model/proposal.md
- tasks.md: openspec/changes/e8-s3-position-model/tasks.md
- spec.md: openspec/changes/e8-s3-position-model/specs/position-model/spec.md
