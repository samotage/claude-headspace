## Why

Persona creation currently requires manual coordination between the database (Role + Persona records) and the filesystem (directory + template files). There is no single operation that performs the full registration flow, making it error-prone and difficult for operators or agents to create personas reliably.

## What Changes

- **New service function:** `register_persona(name, role_name, description)` in `services/persona_registration.py` — orchestrates role lookup/create, persona insert, slug generation, and filesystem asset creation via E8-S5 utilities
- **New Flask CLI command:** `flask persona register --name <name> --role <role> [--description <desc>]` — thin wrapper around the service function
- **New REST API endpoint:** `POST /api/personas/register` — optional programmatic interface returning JSON (201 on success, 400/500 on error)
- Input validation: name and role required, non-empty; role lowercased on input
- Partial failure handling: if filesystem creation fails after DB insert, error is reported with persona ID for remediation (no rollback)
- Duplicate handling: same name+role creates a new persona with a unique slug (not an error)

## Impact

- Affected specs: persona-models, persona-filesystem-assets (consumed, not modified)
- Affected code:
  - NEW: `src/claude_headspace/services/persona_registration.py`
  - NEW: `src/claude_headspace/cli/persona_cli.py`
  - NEW: `src/claude_headspace/routes/personas.py`
  - MODIFIED: `src/claude_headspace/app.py` (register CLI group + blueprint)
  - Consumed: `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/role.py`, `src/claude_headspace/services/persona_assets.py`

## Definition of Done

- [ ] `flask persona register --name Con --role developer` creates Role, Persona, directory, and template files
- [ ] Re-running the same command creates a second persona with unique slug (e.g., developer-con-2)
- [ ] Existing role "developer" is reused (case-insensitive)
- [ ] Missing --name or --role produces clear error, no DB records created
- [ ] Output displays slug, database ID, and filesystem path
- [ ] API endpoint returns 201 JSON with same data
- [ ] Service function testable without CLI/HTTP context
- [ ] All unit and integration tests pass
