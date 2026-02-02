## Why

Brain reboot artifacts (waypoint, progress_summary, brain_reboot) are overwritten in-place, losing previous context. Two of three artifacts have ad-hoc inline archiving with inconsistent patterns (date-only filenames, integer collision counters, different atomicity guarantees). Brain reboot has no archiving at all. This change consolidates all archive logic into a centralized service with second-precision timestamps, configurable retention policies, and retrieval API endpoints.

## What Changes

- New service: archive_service.py with centralized archive operations, atomic writes, retention enforcement, and cascading archive support
- New route: archive.py blueprint with list and retrieve endpoints for archived artifacts via REST API
- New config: archive section in config.yaml with retention policy settings
- Refactor: Remove inline archive code from waypoint_editor.py (get_archive_filename, archive block in save_waypoint)
- Refactor: Remove inline archive code from progress_summary.py (_archive_existing method)
- Enhancement: Add archive triggering to brain_reboot.py export() with cascading archive of waypoint and progress_summary
- New spec: Archive capability delta spec

## Impact

- Affected specs: waypoint, content-pipeline (brain_reboot, progress_summary)
- Affected code:
  - `src/claude_headspace/services/waypoint_editor.py` — remove `get_archive_filename()`, `get_archive_dir()`, archive block in `save_waypoint()`; add delegation to archive service
  - `src/claude_headspace/services/progress_summary.py` — remove `_archive_existing()` method; add delegation to archive service in `_write_summary()`
  - `src/claude_headspace/services/brain_reboot.py` — add archive triggering in `export()` with cascade
  - `src/claude_headspace/services/archive_service.py` — **NEW** centralized archive service
  - `src/claude_headspace/routes/archive.py` — **NEW** archive listing and retrieval endpoints
  - `src/claude_headspace/app.py` — register archive service and blueprint
  - `src/claude_headspace/config.py` — add archive defaults to DEFAULTS dict
  - `config.yaml` — add archive configuration section
  - `tests/services/test_archive_service.py` — **NEW** unit tests
  - `tests/routes/test_archive.py` — **NEW** route tests
  - `tests/services/test_waypoint_editor.py` — update archive-related tests
  - `tests/services/test_progress_summary.py` — update archive-related tests
  - `tests/services/test_brain_reboot.py` — add archive/cascade tests
