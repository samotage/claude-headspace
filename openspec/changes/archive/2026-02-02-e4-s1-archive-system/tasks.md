## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Configuration

- [x] 2.1.1 Add `archive` defaults to `DEFAULTS` dict in `config.py`
- [x] 2.1.2 Add `archive` section to `config.yaml`

### 2.2 Archive Service

- [x] 2.2.1 Create `src/claude_headspace/services/archive_service.py` with `ArchiveService` class
  - `archive_artifact(project_path, artifact_type, source_path)` — archive a single artifact with second-precision UTC timestamp
  - `archive_cascade(project_path)` — archive all three artifacts (for brain_reboot export)
  - `enforce_retention(project_path, artifact_type)` — apply configured retention policy
  - `list_archives(project_path, artifact_type=None)` — list archived versions grouped by type
  - `get_archive(project_path, artifact_type, timestamp)` — retrieve specific archived version content
  - Atomic writes via tempfile + os.replace (following waypoint_editor pattern)
  - Best-effort error handling per NFR2/NFR3 — log failures, don't block primary operations

### 2.3 Service Registration

- [x] 2.3.1 Register `ArchiveService` in `app.py` `create_app()` as `app.extensions["archive_service"]`

### 2.4 Refactor Waypoint Editor

- [x] 2.4.1 Remove `get_archive_filename()` function from `waypoint_editor.py`
- [x] 2.4.2 Remove `get_archive_dir()` function from `waypoint_editor.py` (if no longer needed elsewhere)
- [x] 2.4.3 Replace archive block in `save_waypoint()` with call to `archive_service.archive_artifact()`
- [x] 2.4.4 Pass archive_service to `save_waypoint()` or access via Flask app context

### 2.5 Refactor Progress Summary

- [x] 2.5.1 Remove `_archive_existing()` method from `ProgressSummaryService`
- [x] 2.5.2 Replace archive call in `_write_summary()` with delegation to `archive_service.archive_artifact()`
- [x] 2.5.3 Inject `ArchiveService` into `ProgressSummaryService` constructor

### 2.6 Add Brain Reboot Archiving

- [x] 2.6.1 Inject `ArchiveService` into `BrainRebootService` constructor
- [x] 2.6.2 In `export()`, archive previous `brain_reboot.md` before overwrite (if exists)
- [x] 2.6.3 In `export()`, call `archive_cascade()` to archive waypoint and progress_summary

### 2.7 Archive API Routes

- [x] 2.7.1 Create `src/claude_headspace/routes/archive.py` blueprint with:
  - `GET /api/projects/<id>/archives` — list all archives for project
  - `GET /api/projects/<id>/archives/<artifact>/<timestamp>` — retrieve specific archive content
- [x] 2.7.2 Register blueprint in `app.py`

## 3. Testing (Phase 3)

### 3.1 Archive Service Unit Tests

- [x] 3.1.1 Create `tests/services/test_archive_service.py`
  - Test archive_artifact creates correctly-named file with second-precision timestamp
  - Test archive_artifact creates archive directory if missing
  - Test archive_artifact uses atomic writes (tempfile + os.replace)
  - Test archive_cascade archives all three artifact types
  - Test archive_cascade is best-effort (one failure doesn't block others)
  - Test enforce_retention with keep_all (no deletions)
  - Test enforce_retention with keep_last_n (removes oldest)
  - Test enforce_retention with time_based (removes expired)
  - Test list_archives returns grouped results
  - Test list_archives returns empty when no archives exist
  - Test get_archive returns content for valid artifact/timestamp
  - Test get_archive returns None for nonexistent archive

### 3.2 Archive Route Tests

- [x] 3.2.1 Create `tests/routes/test_archive.py`
  - Test GET /api/projects/<id>/archives returns 200 with grouped list
  - Test GET /api/projects/<id>/archives returns empty list for no archives
  - Test GET /api/projects/<id>/archives/<artifact>/<timestamp> returns 200 with content
  - Test GET /api/projects/<id>/archives/<artifact>/<timestamp> returns 404 for missing
  - Test invalid artifact type returns 400
  - Test invalid timestamp format returns 400

### 3.3 Updated Existing Tests

- [x] 3.3.1 Update `tests/services/test_waypoint_editor.py` — remove `TestGetArchiveFilename`, update archive tests to verify delegation
- [x] 3.3.2 Update `tests/services/test_progress_summary.py` — remove `TestArchiveExisting`, update archive tests to verify delegation
- [x] 3.3.3 Update `tests/services/test_brain_reboot.py` — add tests for archive triggering and cascade in export

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
- [x] 4.4 No counter-based collision filenames remain in codebase
- [x] 4.5 `get_archive_filename()` fully removed
- [x] 4.6 `_archive_existing()` fully removed
