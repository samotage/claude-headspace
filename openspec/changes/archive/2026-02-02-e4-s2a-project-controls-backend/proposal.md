## Why

Claude Headspace auto-discovers projects from the filesystem — any Claude Code session in any directory creates a project record automatically, polluting the dashboard with throwaway experiments and one-off sessions. There is no way to remove stale projects, no way to pause inference costs per project, and no control over which projects appear. This change adds explicit project lifecycle management (CRUD API), disables auto-discovery in favour of manual registration, and adds per-project inference pause/resume controls.

## What Changes

- New route: projects.py blueprint with CRUD endpoints (list, create, read, update, delete) and settings endpoints (get/put inference pause)
- New migration: Add description, inference_paused, inference_paused_at, inference_paused_reason columns to projects table
- Refactor: Disable auto-discovery in session_correlator.py and sessions.py; reject unregistered project sessions with clear error
- Enhancement: Add inference gating checks in summarisation_service.py and priority_scoring.py to skip inference for paused projects
- Enhancement: Broadcast SSE events for project CRUD and settings changes

## Impact

- Affected specs: project-controls (new capability)
- Affected code:
  - `src/claude_headspace/routes/projects.py` — **NEW** project CRUD and settings API endpoints
  - `migrations/versions/xxx_add_project_management_fields.py` — **NEW** Alembic migration
  - `src/claude_headspace/models/project.py` — add description, inference_paused, inference_paused_at, inference_paused_reason fields
  - `src/claude_headspace/app.py` — register projects_bp blueprint
  - `src/claude_headspace/services/session_correlator.py` — remove auto-create in _create_agent_for_session(), raise ValueError for unregistered projects
  - `src/claude_headspace/routes/sessions.py` — remove auto-create in create_session(), return 404 for unregistered projects
  - `src/claude_headspace/services/summarisation_service.py` — add inference pause check before summarise_turn(), summarise_task(), summarise_instruction()
  - `src/claude_headspace/services/priority_scoring.py` — filter out agents from paused projects in score_all_agents()
  - `tests/routes/test_projects.py` — **NEW** route tests for CRUD and settings
  - `tests/services/test_inference_gating.py` — **NEW** inference gating unit tests
  - `tests/services/test_session_correlator.py` — update tests for auto-discovery removal
  - `tests/routes/test_sessions.py` — update tests for auto-discovery removal
