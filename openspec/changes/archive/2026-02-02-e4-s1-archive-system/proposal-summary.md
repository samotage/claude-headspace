# Proposal Summary: e4-s1-archive-system

## Architecture Decisions
- New centralized `ArchiveService` class registered in `app.extensions["archive_service"]`, following the established service pattern (similar to `ProgressSummaryService`, `BrainRebootService`)
- Atomic writes via `tempfile + os.replace` pattern (adopted from waypoint_editor.py's proven approach, replacing progress_summary.py's non-atomic `write_text()`)
- Archive service injected into consuming services via constructor (ProgressSummaryService, BrainRebootService) or passed as parameter (waypoint_editor standalone functions)
- Single archive directory per project at `{project_path}/docs/brain_reboot/archive/` (unchanged location)
- Second-precision UTC timestamps (`YYYY-MM-DD_HH-MM-SS`) replace date-only format with integer collision counters

## Implementation Approach
- Create `ArchiveService` as a standalone class that receives config at init time (retention policy settings)
- Service methods operate on filesystem paths (no database dependency) — consistent with how waypoint_editor and brain_reboot services work
- Cascading archive for brain_reboot export uses a shared UTC timestamp so all three artifacts in a cascade share the same timestamp
- Retention enforcement runs synchronously after each archive (not async) since it's a quick filesystem scan
- Best-effort error handling: each archive operation is wrapped in try/except, logged on failure, never blocks the primary operation or sibling archives

## Files to Modify

### New Files
- `src/claude_headspace/services/archive_service.py` — ArchiveService class
- `src/claude_headspace/routes/archive.py` — archive blueprint (list + retrieve endpoints)
- `tests/services/test_archive_service.py` — archive service unit tests
- `tests/routes/test_archive.py` — archive route tests

### Modified Files
- `src/claude_headspace/services/waypoint_editor.py` — remove `get_archive_filename()`, `get_archive_dir()`, archive block in `save_waypoint()`; add delegation to archive_service
- `src/claude_headspace/services/progress_summary.py` — remove `_archive_existing()`; inject archive_service; delegate in `_write_summary()`
- `src/claude_headspace/services/brain_reboot.py` — inject archive_service; add archive + cascade in `export()`
- `src/claude_headspace/app.py` — instantiate and register ArchiveService; register archive blueprint
- `src/claude_headspace/config.py` — add `archive` section to DEFAULTS dict
- `config.yaml` — add `archive` configuration section
- `tests/services/test_waypoint_editor.py` — update archive tests for delegation pattern
- `tests/services/test_progress_summary.py` — update archive tests for delegation pattern
- `tests/services/test_brain_reboot.py` — add archive/cascade tests for export

## Acceptance Criteria
- Saving a waypoint archives previous version as `waypoint_YYYY-MM-DD_HH-MM-SS.md`
- Generating progress_summary archives previous version as `progress_summary_YYYY-MM-DD_HH-MM-SS.md`
- Exporting brain_reboot archives previous brain_reboot AND cascades to archive waypoint + progress_summary
- Archive directory auto-created if missing
- `GET /api/projects/<id>/archives` returns grouped archive listing
- `GET /api/projects/<id>/archives/<artifact>/<timestamp>` returns specific archive content
- Retention policy configurable in config.yaml and enforced after each archive
- No counter-based collision filenames in codebase
- All inline archive code removed from waypoint_editor.py and progress_summary.py

## Constraints and Gotchas
- **Waypoint editor is standalone functions, not a class** — archive_service must be passed as a parameter to `save_waypoint()` or retrieved from Flask app context within the function. The other two services (ProgressSummaryService, BrainRebootService) accept it via constructor injection.
- **SaveResult dataclass** in waypoint_editor.py tracks `archived: bool` and `archive_path: str | None` — these fields must continue to be populated correctly after refactoring
- **Progress summary has non-atomic writes** — the new archive_service will use atomic writes for all archive operations, but the progress_summary's own content write (`_write_summary`) is non-atomic and out of scope to change
- **brain_reboot.md may not exist** when export is called (first-time export) — archive must handle this gracefully (skip if no previous file)
- **Cascade is best-effort** — if archiving waypoint fails, progress_summary archive should still proceed, and vice versa
- **FR5 specifies UTC timestamps** — ensure `datetime.now(timezone.utc)` is used, not local time
- **Retention enforcement should only clean up the artifact type that was just archived** (per FR8), not all types

## Git Change History

### Related Files
- Services:
  - `src/claude_headspace/services/waypoint_editor.py` — standalone functions with inline archive logic
  - `src/claude_headspace/services/progress_summary.py` — class with `_archive_existing()` method
  - `src/claude_headspace/services/brain_reboot.py` — class with `export()` method (no archiving)
- Routes:
  - `src/claude_headspace/routes/waypoint.py` — waypoint CRUD
  - `src/claude_headspace/routes/brain_reboot.py` — brain_reboot generate/export
  - `src/claude_headspace/routes/progress_summary.py` — progress_summary generate
- Models:
  - `src/claude_headspace/models/project.py` — Project model with `path` field
- Config:
  - `src/claude_headspace/config.py` — config loading with DEFAULTS + YAML + env
  - `config.yaml` — application configuration
- App:
  - `src/claude_headspace/app.py` — app factory with service registration
- Tests:
  - `tests/services/test_waypoint_editor.py` — includes TestGetArchiveFilename
  - `tests/services/test_progress_summary.py` — includes TestArchiveExisting
  - `tests/services/test_brain_reboot.py` — includes TestExport (no archive tests)

### OpenSpec History
- No prior archive-related OpenSpec changes
- Related changes: e3-s5-brain-reboot (brain reboot implementation), e2-s2-waypoint-editor (waypoint implementation)

### Implementation Patterns
- Service pattern: class with `__init__(self, app=None, **deps)`, registered in `app.extensions`
- Route pattern: Flask blueprint with `url_prefix`, services accessed via `current_app.extensions`
- Config pattern: defaults in `config.py` DEFAULTS dict, overridable via `config.yaml`
- Test pattern: unit tests with mocked dependencies in `tests/services/`, route tests with Flask test client in `tests/routes/`

## Q&A History
- No clarifications needed — PRD is clear and consistent with existing codebase patterns

## Dependencies
- No new packages required
- No external services/APIs involved
- No database migrations needed (archive is filesystem-only)

## Testing Strategy
- Unit tests for ArchiveService: archive operations, retention enforcement, listing, retrieval, error handling
- Route tests for archive endpoints: HTTP contract validation, status codes, response format
- Updated tests for waypoint_editor, progress_summary, brain_reboot to verify delegation to archive service
- Test cascading archive behavior (all three artifacts archived on brain_reboot export)
- Test best-effort error handling (individual failures don't block others)
- Test all three retention policies (keep_all, keep_last_n, time_based)

## OpenSpec References
- proposal.md: openspec/changes/e4-s1-archive-system/proposal.md
- tasks.md: openspec/changes/e4-s1-archive-system/tasks.md
- spec.md: openspec/changes/e4-s1-archive-system/specs/archive/spec.md
