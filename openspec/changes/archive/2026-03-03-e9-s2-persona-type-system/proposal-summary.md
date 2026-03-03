# Proposal Summary: e9-s2-persona-type-system

## Architecture Decisions

1. **PersonaType as lookup table** — A fixed 4-row lookup table (2x2 matrix: agent/person x internal/external) rather than an enum column or polymorphic model. This enables future quadrant-specific logic without schema changes.

2. **NOT NULL FK with RESTRICT** — `persona_type_id` is NOT NULL with `ondelete="RESTRICT"` because PersonaType rows are infrastructure, not runtime entities. Every Persona must belong to exactly one quadrant.

3. **Model-level default=1** — New Persona records default to agent/internal (id=1) at the ORM level, providing backward compatibility with existing PersonaRegistration service without code changes.

4. **can_create_channel as property** — Channel creation capability is a Python model property, not a database column. This follows Workshop Decision 2.1 and allows the logic to evolve (per-persona overrides, role-based rules) without schema changes.

5. **Operator as person/internal Persona** — The operator (Sam) is modelled as a first-class Persona with persona_type = person/internal, not as a special case outside the Persona system. No Agent instances, no PositionAssignment, no filesystem assets.

## Implementation Approach

1. Create the PersonaType model file following existing Role model patterns (SQLAlchemy 2.0 Mapped annotations)
2. Modify Persona model to add FK column, relationship, can_create_channel property, and get_operator() classmethod
3. Register PersonaType in models/__init__.py
4. Create a single Alembic migration with 7 steps (create table, seed, add column nullable, backfill, alter NOT NULL, create operator Role, create operator Persona)
5. No changes to existing services, routes, CLI, or templates

## Files to Modify (organized by type)

### New Files
| File | Purpose |
|------|---------|
| `src/claude_headspace/models/persona_type.py` | PersonaType model — lookup table with type_key, subtype, unique constraint, relationship to Persona |
| `migrations/versions/{rev}_add_persona_type_system.py` | Alembic migration: create table, seed rows, add FK, backfill, create operator Role + Persona |

### Modified Files
| File | Change |
|------|--------|
| `src/claude_headspace/models/persona.py` | Add persona_type_id FK (NOT NULL, default=1, RESTRICT). Add persona_type relationship. Add PersonaType to TYPE_CHECKING. Add can_create_channel property. Add get_operator() classmethod. |
| `src/claude_headspace/models/__init__.py` | Import PersonaType. Add to __all__. Update module docstring. |

### Test Files (New)
| File | Purpose |
|------|---------|
| `tests/services/test_persona_type.py` or `tests/integration/test_persona_type.py` | PersonaType model tests, can_create_channel tests, get_operator tests, relationship tests |

## Acceptance Criteria

1. `persona_types` table has exactly 4 rows with deterministic IDs
2. `(type_key, subtype)` unique constraint prevents duplicate quadrants
3. Every Persona has non-null `persona_type_id` FK
4. All existing Persona records backfilled to agent/internal (id=1)
5. "operator" Role exists; "Sam" Persona exists with person/internal type
6. `persona.can_create_channel` returns True for internal, False for external
7. `Persona.get_operator()` returns the person/internal Persona
8. PersonaType importable from `claude_headspace.models`
9. Migration is reversible (downgrade drops column and table)
10. Existing PersonaRegistration flows work unchanged (default=1)

## Constraints and Gotchas

- **3-step nullable pattern required** — The migration must add `persona_type_id` as NULLABLE first, backfill, then alter to NOT NULL. Adding NOT NULL directly will fail on populated tables.
- **Raw SQL for operator Persona slug** — Since the migration uses raw SQL (not ORM), the after_insert event that auto-generates slugs does not fire. The slug must be manually set to `operator-sam-{id}` in the migration.
- **Idempotent inserts** — Both the operator Role and operator Persona inserts use `WHERE NOT EXISTS` to handle re-runs safely.
- **No service changes** — The `default=1` on the model column handles backward compatibility. Do NOT modify PersonaRegistration, CLI, or any existing service.
- **RESTRICT vs CASCADE** — This FK uses RESTRICT, unlike most other FKs in the codebase which use CASCADE or SET NULL. Do not change this to CASCADE.
- **PostgreSQL sequence reset** — After inserting rows with explicit IDs, the sequence may need resetting. Use `setval()` if further inserts need auto-increment to work correctly.

## Git Change History

- **Recent activity:** All recent commits are docs/workshop related (interagent communication workshop, ERDs, PRDs). No code changes to models/ directory.
- **No openspec history** for this subsystem — this is the first change in the channels subsystem.
- **Related archive:** `2026-02-20-e8-s1-role-persona-models` created the Persona and Role models this change extends.

## Q&A History

No clarifications needed. All design decisions are resolved in the Inter-Agent Communication Workshop (Section 1, Decision 1.1; Section 2, Decision 2.1).

## Dependencies

- **Persona model** (E8-S5, shipped) — Existing `personas` table to extend with FK
- **Role model** (E8-S5, shipped) — Existing `roles` table for operator Role creation
- **Alembic / Flask-Migrate** (infrastructure, shipped) — Migration framework
- **SQLAlchemy 2.0** (infrastructure, shipped) — Model definition patterns
- No external dependencies (no new pip packages, no API changes)

## Testing Strategy

1. **Unit tests** — PersonaType model instantiation, can_create_channel logic for all 4 quadrants, get_operator() with and without operator
2. **Integration tests** — Migration upgrade/downgrade, FK constraint enforcement, RESTRICT behavior, unique constraint, relationship loading
3. **Regression tests** — Existing persona registration creates agent/internal by default, all existing persona tests pass
4. **Migration tests** — Upgrade with existing data, downgrade preserves operator records, idempotent re-run

## OpenSpec References

- **Proposal:** `openspec/changes/e9-s2-persona-type-system/proposal.md`
- **Tasks:** `openspec/changes/e9-s2-persona-type-system/tasks.md`
- **Spec:** `openspec/changes/e9-s2-persona-type-system/specs/persona-type-system/spec.md`
- **PRD:** `docs/prds/channels/e9-s2-persona-type-system-prd.md`
- **Workshop reference:** `docs/workshop/interagent-communication/sections/section-1-channel-data-model.md` (Decision 1.1)
