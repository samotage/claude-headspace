## Why

Claude Headspace needs an Organisation entity to support future multi-org capability. Position records (E8-S3) will reference Organisation via FK, so the table must exist first. A minimal table now avoids a disruptive migration later when downstream tables already contain data.

## What Changes

- Add `Organisation` SQLAlchemy model — minimal organisational grouping with three-state status (active, dormant, archived)
- Add Alembic migration creating the Organisation table with seed data (one "Development" organisation)
- Register the model in `models/__init__.py`

## Impact

- Affected specs: None (new capability, no existing specs)
- Affected code:
  - **New:** `src/claude_headspace/models/organisation.py`
  - **Modified:** `src/claude_headspace/models/__init__.py` (import + `__all__`)
  - **New:** `migrations/versions/xxx_add_organisation_table.py`
- No changes to existing models, services, routes, or templates
- Downstream consumers (future sprints): E8-S3 (Position.org_id FK), E8-S4 (Agent → Position → Organisation chain)
