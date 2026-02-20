## Why

Claude Headspace agents are identified by anonymous session UUIDs with no persistent identity. Epic 8 introduces named personas as first-class entities. The Role and Persona database models are the foundation — a shared lookup table of agent specialisations and a registry of named identities that all downstream features (registration, skill injection, dashboard display, handoffs) depend on.

## What Changes

- Add `Role` SQLAlchemy model — agent specialisation lookup table (developer, tester, pm, architect)
- Add `Persona` SQLAlchemy model — named agent identity with slug, status, and role FK
- Add bidirectional relationship: `Role.personas` (one-to-many) and `Persona.role` (many-to-one)
- Add slug generation: `{role_name}-{persona_name}-{id}` format for filesystem path key
- Register both models in `models/__init__.py`
- Create single Alembic migration for both tables

## Impact

- Affected specs: None (new capability, no existing specs)
- Affected code:
  - **New:** `src/claude_headspace/models/role.py`
  - **New:** `src/claude_headspace/models/persona.py`
  - **Modified:** `src/claude_headspace/models/__init__.py` (imports + `__all__`)
  - **New:** `migrations/versions/xxx_add_role_persona_tables.py`
- No changes to existing models, services, routes, or templates
- Downstream consumers (future sprints): E8-S4 (Agent.persona_id FK), E8-S5 (slug → filesystem path), E8-S6 (registration)
