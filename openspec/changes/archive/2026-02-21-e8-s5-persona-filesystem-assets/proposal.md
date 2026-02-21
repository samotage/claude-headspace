# Proposal: e8-s5-persona-filesystem-assets

## Why

Personas need filesystem assets (skill.md, experience.md) to define their behaviour and accumulate experience. Downstream sprints (registration E8-S6, injection E8-S9, handoff E8-S14) need a consistent utility interface to create, read, and check these files. Currently no filesystem convention or utility module exists.

## What Changes

- New service module `src/claude_headspace/services/persona_assets.py` with utility functions for:
  - Path resolution: slug → `data/personas/{slug}/` directory
  - Directory creation with parent directories
  - Template seeding for skill.md and experience.md
  - Combined create-and-seed operation
  - Read functions for both file types
  - Existence checking for asset files
- New unit tests at `tests/services/test_persona_assets.py`

## Summary

Create a stateless utility service module that manages persona filesystem assets using the `data/personas/{slug}/` convention. All functions operate on slug strings only — no database dependency. Follows existing `waypoint_editor.py` patterns: `pathlib.Path`, `read_text(encoding="utf-8")`, dataclass results, graceful absence handling.

## Impact

### Files Created

- `src/claude_headspace/services/persona_assets.py` — Utility module with path resolution, directory creation, template seeding, file reading, and existence checking functions
- `tests/services/test_persona_assets.py` — Unit tests covering all utility functions, edge cases, and idempotency

### No Changes Required

- No database models modified (pure filesystem operations)
- No existing services modified
- No routes, templates, or static files changed
- No migrations needed
- No config.yaml changes

## Approach

1. Follow `waypoint_editor.py` patterns: module-level functions (not a class), `pathlib.Path`, `dataclass` results
2. Path resolution is convention-based: project root / `data/personas/{slug}/`
3. Template seeding accepts persona name and role name as parameters
4. Read functions return `None` for missing files (not exceptions)
5. All operations are idempotent — safe to call multiple times

## Definition of Done

- [ ] `persona_assets.py` module exists with all 7 utility functions (FR2-FR8 + FR6 combined)
- [ ] Path resolution returns correct `data/personas/{slug}/` path
- [ ] Directory creation handles missing parents and existing directories
- [ ] skill.md template contains persona name, role, and section scaffolding
- [ ] experience.md template contains persona header and append-only markers
- [ ] Combined create function seeds both files without overwriting existing ones
- [ ] Read functions return content or None for missing files
- [ ] Existence check reports skill.md and experience.md presence independently
- [ ] All functions handle edge cases: empty slugs, missing directories
- [ ] Unit tests cover all functions with edge cases
- [ ] No database dependency — all operations use slug strings only
