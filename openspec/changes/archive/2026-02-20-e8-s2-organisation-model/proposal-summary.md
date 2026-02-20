# Proposal Summary: e8-s2-organisation-model

## Architecture Decisions
- Minimal Organisation table in v1 — one small migration now avoids disruptive one later (Workshop 1.3)
- Three-state status: active, dormant, archived — lifecycle granularity beyond binary (ERD workshop)
- Integer PK — matches codebase convention
- No relationships defined in this sprint — Position (E8-S3) will add FK reference
- No unique constraint on name in v1 — only one org exists, add constraint when multi-org arrives
- No config.yaml involvement — org definitions are domain data, not app config

## Implementation Approach
- Create one new SQLAlchemy model following established Mapped/mapped_column patterns from Role, Persona, Agent models
- Single Alembic migration creating table + inserting seed data (Development org)
- Migration downgrade: delete seed data first, then drop table
- Register model in __init__.py following existing pattern

## Files to Modify
- **New:** `src/claude_headspace/models/organisation.py` — Organisation model
- **Modified:** `src/claude_headspace/models/__init__.py` — add import and `__all__` entry
- **New:** `migrations/versions/xxx_add_organisation_table.py` — table creation + seed data

## Acceptance Criteria
- Organisation table created with id (int PK), name (not null), description (nullable), status (not null, default "active"), created_at (UTC)
- Status accepts "active", "dormant", "archived"
- Seed data: one Organisation record (name="Development", status="active") present after migration
- Migration is additive and reversible — no impact on existing tables
- Model importable from `claude_headspace.models`

## Constraints and Gotchas
- No unique constraint on Organisation.name — intentional for v1
- Seed data must be inserted as a data operation in the migration (not model code)
- Downgrade must delete seed data BEFORE dropping the table
- No relationships in this sprint — E8-S3 Position will add FK
- No changes to existing models

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/role.py`, `src/claude_headspace/models/persona.py` (pattern reference)
- Migrations: `migrations/versions/0462474af024_add_role_and_persona_tables.py` (pattern reference)
- Tests: `tests/integration/test_role_persona_models.py` (pattern reference)

### OpenSpec History
- e8-s1-role-persona-models (2026-02-20) — Role and Persona models, similar pattern

### Implementation Patterns
- Model: db.Model → Mapped/mapped_column → DateTime(timezone=True) → __repr__
- Migration: op.create_table → op.bulk_insert (for seed) → reverse order in downgrade
- Test: integration tests with db_session fixture, factory pattern

## Q&A History
- No clarifications needed — PRD is fully specified

## Dependencies
- No new packages required
- No external services involved
- One database migration needed (additive + seed data)

## Testing Strategy
- Integration tests for Organisation model: creation, field defaults, status values
- Test seed data presence after migration
- Test not-null constraints on name and status
- Test migration reversibility
- Verify existing tests still pass

## OpenSpec References
- proposal.md: openspec/changes/e8-s2-organisation-model/proposal.md
- tasks.md: openspec/changes/e8-s2-organisation-model/tasks.md
- spec.md: openspec/changes/e8-s2-organisation-model/specs/organisation-model/spec.md
