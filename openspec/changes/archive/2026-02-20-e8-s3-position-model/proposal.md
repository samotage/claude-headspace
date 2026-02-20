## Why

Claude Headspace needs a Position entity to model seats in an org chart — each defined by what role the seat needs, who it reports to, and who it escalates to. Position sits at the intersection of Role (E8-S1) and Organisation (E8-S2), and Agent (E8-S4) will reference Position via FK to complete the persona-to-org-chart mapping.

## What Changes

- Add `Position` SQLAlchemy model — org chart seat with dual self-referential hierarchy (reports_to + escalates_to), FK to Organisation and Role
- Add Alembic migration creating the Position table with foreign keys and self-referential FKs
- Add `positions` relationship to Organisation model (back_populates)
- Add `positions` relationship to Role model (back_populates)
- Register the model in `models/__init__.py`

## Impact

- Affected specs: None (new capability, no existing specs modified)
- Affected code:
  - **New:** `src/claude_headspace/models/position.py`
  - **Modified:** `src/claude_headspace/models/__init__.py` (import + `__all__`)
  - **Modified:** `src/claude_headspace/models/organisation.py` (add `positions` relationship)
  - **Modified:** `src/claude_headspace/models/role.py` (add `positions` relationship)
  - **New:** `migrations/versions/xxx_add_position_table.py`
- No changes to existing table schemas — relationship additions are ORM-only
- Downstream consumers (future sprints): E8-S4 (Agent.position_id FK)
