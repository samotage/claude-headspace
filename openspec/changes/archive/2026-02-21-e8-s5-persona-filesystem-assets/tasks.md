# Tasks: e8-s5-persona-filesystem-assets

## Phase 1: Preparation
- [x] 1.1 Read PRD and understand requirements (10 FRs, 3 NFRs, utility module)
- [x] 1.2 Read existing pattern references (`waypoint_editor.py`, `path_constants.py`)
- [x] 1.3 Identify conventions: pathlib.Path, UTF-8 encoding, dataclass results, module-level functions

## Phase 2: Implementation

### Task 2.1: Create persona_assets.py service module
**File:** `src/claude_headspace/services/persona_assets.py`
- [x] Define module constants: `PERSONAS_DIR = "data/personas"`, `SKILL_FILENAME = "skill.md"`, `EXPERIENCE_FILENAME = "experience.md"`
- [x] Define `AssetStatus` dataclass: `skill_exists: bool`, `experience_exists: bool`, `directory_exists: bool`
- [x] Implement `get_persona_dir(slug: str, project_root: Path | None = None) -> Path` — resolve slug to directory path (FR2)
- [x] Implement `create_persona_dir(slug: str, project_root: Path | None = None) -> Path` — create directory with parents (FR3)
- [x] Implement `seed_skill_file(slug: str, persona_name: str, role_name: str, project_root: Path | None = None) -> Path` — create skill.md template, skip if exists (FR4)
- [x] Implement `seed_experience_file(slug: str, persona_name: str, project_root: Path | None = None) -> Path` — create experience.md template, skip if exists (FR5)
- [x] Implement `create_persona_assets(slug: str, persona_name: str, role_name: str, project_root: Path | None = None) -> Path` — combined create dir + seed both files (FR6)
- [x] Implement `read_skill_file(slug: str, project_root: Path | None = None) -> str | None` — return content or None (FR7)
- [x] Implement `read_experience_file(slug: str, project_root: Path | None = None) -> str | None` — return content or None (FR8)
- [x] Implement `check_assets(slug: str, project_root: Path | None = None) -> AssetStatus` — report file existence (FR9)

### Task 2.2: Write unit tests
**File:** `tests/services/test_persona_assets.py`
- [x] Test `get_persona_dir` returns correct path for valid slug
- [x] Test `get_persona_dir` with custom project_root
- [x] Test `create_persona_dir` creates directory structure including parents
- [x] Test `create_persona_dir` is idempotent (no error if exists)
- [x] Test `seed_skill_file` creates file with correct template content (name, role, sections)
- [x] Test `seed_skill_file` does not overwrite existing file
- [x] Test `seed_experience_file` creates file with correct template content (name, append-only markers)
- [x] Test `seed_experience_file` does not overwrite existing file
- [x] Test `create_persona_assets` creates directory and both files in one call
- [x] Test `create_persona_assets` is idempotent — existing files not overwritten
- [x] Test `read_skill_file` returns content when file exists
- [x] Test `read_skill_file` returns None when file missing
- [x] Test `read_experience_file` returns content when file exists
- [x] Test `read_experience_file` returns None when file missing
- [x] Test `check_assets` reports both files present
- [x] Test `check_assets` reports partial presence (skill only, experience only)
- [x] Test `check_assets` reports no files present
- [x] Test edge case: empty slug string

## Phase 3: Testing
- [ ] 3.1 Run unit tests for persona_assets module
- [ ] 3.2 Verify no regressions in existing tests

## Phase 4: Verification
- [ ] 4.1 Verify all 10 FRs are satisfied
- [ ] 4.2 Verify NFRs: no DB dependency, idempotent operations, graceful failure handling
- [ ] 4.3 Verify existing tests pass unchanged
