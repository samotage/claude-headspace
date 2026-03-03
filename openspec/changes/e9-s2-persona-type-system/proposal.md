## Why

The channel infrastructure (Epic 9, Sprints 3-8) requires every Persona to be classified into one of four quadrants (agent/person x internal/external) to determine delivery mechanism, trust boundaries, visibility scope, and channel creation capability. Currently, all personas are implicitly AI agents with no type distinction, and the operator (Sam) cannot be represented as a first-class Persona. Without a type system, every channel operation would need ad-hoc identity checks scattered across the service layer.

## What Changes

- **New model:** `PersonaType` lookup table (`persona_types`) with 4 seeded rows: agent/internal, agent/external, person/internal, person/external
- **Schema change:** `persona_type_id` NOT NULL FK added to `personas` table (ondelete RESTRICT, default=1)
- **Data migration:** All existing Persona records backfilled with `persona_type_id = 1` (agent/internal)
- **New data:** "operator" Role created; "Sam" Persona created with persona_type = person/internal
- **New model method:** `can_create_channel` property on Persona (returns True for internal personas, False for external)
- **New class method:** `Persona.get_operator()` returns the person/internal operator Persona
- **Model registration:** PersonaType added to `models/__init__.py`
- **Relationship wiring:** Bidirectional PersonaType <-> Persona relationships

## Impact

- Affected specs: Persona model, models package init
- Affected code:
  - `src/claude_headspace/models/persona_type.py` (new file)
  - `src/claude_headspace/models/persona.py` (add FK, relationship, can_create_channel, get_operator)
  - `src/claude_headspace/models/__init__.py` (register PersonaType)
  - `migrations/versions/{rev}_add_persona_type_system.py` (new migration)
- No breaking changes to existing PersonaRegistration service or CLI flows (model default=1 handles backward compatibility)
- No API endpoints, CLI commands, or admin UI for PersonaType CRUD (immutable lookup table)
