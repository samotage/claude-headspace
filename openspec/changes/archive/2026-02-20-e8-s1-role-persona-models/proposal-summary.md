# Proposal Summary: e8-s1-role-persona-models

## Architecture Decisions
- Integer primary keys (not UUIDs) — matches existing codebase convention (Agent, Command, Turn all use int PKs)
- Slug format `{role}-{name}-{id}` — natural filesystem sorting by role then name, id guarantees uniqueness
- Status field as string (`active|archived`) not boolean `is_active` — extensible for future states
- Role is a shared lookup table, not org-scoped — org relationship comes through Position via Agent in later sprints
- No org_id on Persona — Persona is org-independent, org relationship through Position via Agent
- Skill file path derived from slug convention (`data/personas/{slug}/`) — not stored on model
- Persona definitions are domain data in the database, not app config (no config.yaml changes)

## Implementation Approach
- Create two new SQLAlchemy model files following the existing `Mapped`/`mapped_column` patterns established by Agent, Project, and other models
- Use `db.Model` inheritance, `DateTime(timezone=True)` with UTC defaults, `relationship()` with `back_populates`
- Slug generation as an `after_insert` event or helper method that sets the slug after the id is assigned
- Single Alembic migration creating both tables (Role first, then Persona with FK)
- Register models in `__init__.py` following existing import + `__all__` pattern

## Files to Modify
- **New:** `src/claude_headspace/models/role.py` — Role model
- **New:** `src/claude_headspace/models/persona.py` — Persona model
- **Modified:** `src/claude_headspace/models/__init__.py` — add imports and `__all__` entries for Role and Persona
- **New:** `migrations/versions/xxx_add_role_persona_tables.py` — single migration for both tables

## Acceptance Criteria
- Role table created with id (int PK), name (unique, not null), description (nullable), created_at (UTC)
- Persona table created with id (int PK), slug (unique, not null), name (not null), description (nullable), status (default "active"), role_id (FK to Role, not null), created_at (UTC)
- Slug generated as `{role_name}-{persona_name}-{id}` — all lowercase, hyphen-separated
- Bidirectional relationship: `Role.personas` (one-to-many list) and `Persona.role` (many-to-one)
- Migration is additive and reversible — no impact on existing tables
- Both models importable from `claude_headspace.models`

## Constraints and Gotchas
- Slug generation depends on the id, which is only available after flush/insert — implementation must handle the timing (e.g., `after_insert` event listener or explicit `db.session.flush()` before setting slug)
- Persona.name is NOT unique — uniqueness comes from the slug (role + name + id)
- Role.name IS unique at the database level
- The `__tablename__` should follow existing patterns: `roles` for Role, `personas` for Persona
- No service layer, routes, or UI changes — this is purely model + migration
- No changes to existing models (Agent, Command, Turn, etc.)

## Git Change History

### Related Files
- Models: None yet (new subsystem — persona)
- No existing persona-related code in the codebase

### OpenSpec History
- No previous OpenSpec changes for the persona subsystem

### Implementation Patterns
- Existing models follow: `db.Model` → `Mapped`/`mapped_column` → `relationship(back_populates=...)` → `DateTime(timezone=True)` → `__repr__`
- See `src/claude_headspace/models/agent.py` and `project.py` for reference patterns
- Agent model uses `TYPE_CHECKING` block for forward reference type hints

## Q&A History
- No clarifications needed — PRD is fully specified with all design decisions resolved in the Agent Teams Design Workshop

## Dependencies
- No new packages required
- No external services involved
- One database migration needed (additive)

## Testing Strategy
- Unit tests for Role model: creation, unique name constraint, field defaults
- Unit tests for Persona model: creation, slug generation, role FK, status default
- Test slug uniqueness enforcement at database level
- Test bidirectional relationships (Role.personas, Persona.role)
- Test migration reversibility (upgrade + downgrade)
- Verify existing tests still pass (no regressions)

## OpenSpec References
- proposal.md: openspec/changes/e8-s1-role-persona-models/proposal.md
- tasks.md: openspec/changes/e8-s1-role-persona-models/tasks.md
- spec.md: openspec/changes/e8-s1-role-persona-models/specs/persona-models/spec.md
