# Proposal Summary: e8-s5-persona-filesystem-assets

## Architecture Decisions
- Stateless utility module (module-level functions, not a class) — matches `waypoint_editor.py` pattern
- Convention-based path: `data/personas/{slug}/` at project root — not configurable via config.yaml (workshop decision 1.2)
- No database dependency — all operations use slug strings only (NFR1)
- Read functions return `None` for missing files — not exceptions (NFR3)
- Idempotent operations — safe to call multiple times (NFR2)
- No Position/Agent model interaction — pure filesystem utilities

## Implementation Approach
- Single service module with ~10 module-level functions
- `pathlib.Path` for all path operations, `read_text(encoding="utf-8")` for file I/O
- `dataclass` for structured results (`AssetStatus`)
- Template strings embedded in module for skill.md and experience.md
- `project_root` parameter defaults to current working directory for flexibility

## Files to Create
- `src/claude_headspace/services/persona_assets.py` — Utility module with all persona asset functions
- `tests/services/test_persona_assets.py` — Unit tests using `tmp_path` fixture (no database needed)

## Files to Modify
- None — this is a new standalone module

## Acceptance Criteria
- Path resolution: `get_persona_dir("developer-con-1")` → `data/personas/developer-con-1/`
- Directory creation handles missing parents and existing directories
- skill.md template contains persona name, role, and 3 section scaffolding
- experience.md template contains persona header and append-only markers
- Combined create function seeds both files without overwriting existing ones
- Read functions return content string or None
- Existence check reports skill.md and experience.md presence independently
- All functions handle edge cases: empty slugs, missing directories

## Constraints and Gotchas
- `data/` directory may not exist initially — all creation functions must use `mkdir(parents=True, exist_ok=True)`
- Seeding must NOT overwrite existing files — check `path.exists()` before writing
- `project_root` parameter allows testing with `tmp_path` without mocking
- No service registration needed — these are pure utility functions, not Flask extensions
- The `data/personas/` directory is NOT gitignored by default — operator decides tracking

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/persona.py` (defines slug format: `{role}-{name}-{id}`)
- Services: `src/claude_headspace/services/waypoint_editor.py` (pattern reference), `src/claude_headspace/services/path_constants.py` (pattern reference)
- Tests: `tests/integration/test_role_persona_models.py`

### OpenSpec History
- e8-s1-role-persona-models: Created Role and Persona tables (merged 2026-02-20)
- e8-s2-organisation-model: Created Organisation table (merged)
- e8-s3-position-model: Created Position table with self-referential FKs (merged)
- e8-s4-agent-model-extensions: Extended Agent with persona_id, position_id, previous_agent_id (merged 2026-02-21)

### Implementation Patterns
- Module-level functions (not class-based) — matches `waypoint_editor.py`
- `pathlib.Path` for all path operations
- `read_text(encoding="utf-8")` for file reading
- `@dataclass` for structured results
- `tmp_path` pytest fixture for filesystem tests (no database)

## Q&A History
- No clarifications needed — PRD is clear, all design decisions resolved in workshop

## Dependencies
- No new packages needed
- No database migrations
- No config.yaml changes
- Only dependency: Python standard library (`pathlib`, `dataclasses`)

## Testing Strategy
- Pure unit tests using pytest `tmp_path` fixture — no database, no Flask app context
- Test each function independently
- Test idempotency (create twice, verify no overwrite)
- Test edge cases: missing directories, missing files, empty slugs
- Test template content: verify persona name and role appear in output

## OpenSpec References
- proposal.md: openspec/changes/e8-s5-persona-filesystem-assets/proposal.md
- tasks.md: openspec/changes/e8-s5-persona-filesystem-assets/tasks.md
- spec.md: openspec/changes/e8-s5-persona-filesystem-assets/specs/persona-filesystem-assets/spec.md
