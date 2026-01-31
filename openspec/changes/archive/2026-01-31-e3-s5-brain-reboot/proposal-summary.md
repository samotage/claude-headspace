# Proposal Summary: e3-s5-brain-reboot

## Architecture Decisions
- BrainRebootService is a pure composition service — reads existing file artifacts, formats them into a single document. No LLM calls.
- StalenessService is a separate lightweight service computing freshness tiers from Agent.last_seen_at timestamps.
- In-memory caching of last generated brain reboot per project (dict keyed by project_id) — not persisted to database.
- Modal follows established waypoint editor pattern (overlay, dismiss behaviour, keyboard handling).
- Clipboard follows help.js pattern (navigator.clipboard.writeText with visual feedback).
- Export follows waypoint editor pattern (os.makedirs + file write to target project's docs/brain_reboot/).

## Implementation Approach
- Phase 1: Config defaults for brain_reboot section (staleness thresholds, export filename)
- Phase 2: StalenessService — classify projects into fresh/aging/stale based on Agent.last_seen_at
- Phase 3: BrainRebootService — compose waypoint + progress summary into formatted document
- Phase 4: API endpoints (POST generate, GET retrieve, POST export)
- Phase 5: Dashboard modal (HTML + JS with clipboard + export)
- Phase 6: Dashboard staleness integration (indicators, badges, Brain Reboot button)
- Phase 7: App registration and wiring

## Files to Modify
- **Services:**
  - NEW: `src/claude_headspace/services/brain_reboot.py` — BrainRebootService
  - NEW: `src/claude_headspace/services/staleness.py` — StalenessService
- **Routes:**
  - NEW: `src/claude_headspace/routes/brain_reboot.py` — brain_reboot_bp blueprint
- **Templates:**
  - NEW: `templates/partials/_brain_reboot_modal.html` — Modal template
  - MODIFIED: `templates/partials/_project_column.html` — Brain Reboot button + staleness indicators
  - MODIFIED: `templates/partials/_project_group.html` — Brain Reboot button + staleness indicators
  - MODIFIED: `templates/dashboard.html` — Include modal + JS
- **Static:**
  - NEW: `static/js/brain-reboot.js` — Modal + clipboard + export JS
- **Config/App:**
  - MODIFIED: `src/claude_headspace/config.py` — brain_reboot defaults
  - MODIFIED: `src/claude_headspace/app.py` — Register services + blueprint
  - MODIFIED: `src/claude_headspace/routes/dashboard.py` — Pass staleness data to templates
- **Tests:**
  - NEW: `tests/services/test_brain_reboot.py`
  - NEW: `tests/services/test_staleness.py`
  - NEW: `tests/routes/test_brain_reboot.py`

## Acceptance Criteria
1. BrainRebootService generates formatted document combining waypoint + progress summary
2. Missing artifact handling: waypoint-only, summary-only, both-missing all work gracefully
3. POST `/api/projects/<id>/brain-reboot` generates and returns brain reboot content
4. GET `/api/projects/<id>/brain-reboot` returns most recently generated content
5. Brain Reboot modal opens from dashboard with formatted content display
6. Copy to Clipboard copies full content with visual feedback
7. Export saves brain_reboot.md to target project's docs/brain_reboot/ directory
8. Export creates directory structure if missing
9. Modal dismissable via close button, backdrop click, escape key
10. StalenessService classifies projects into fresh/aging/stale tiers
11. Staleness thresholds configurable in config.yaml (defaults: fresh 0-3d, aging 4-7d, stale 8+d)
12. Dashboard shows staleness indicators per project (green/yellow/red)
13. Stale projects show "Needs Reboot" badge
14. Projects with no agent history show no staleness indicator
15. All tests pass with zero failures

## Constraints and Gotchas
- Brain reboot does NOT use LLM inference — pure file composition
- Waypoint file format: plain markdown at `docs/brain_reboot/waypoint.md` — no frontmatter
- Progress summary file format: YAML frontmatter + markdown body at `docs/brain_reboot/progress_summary.md`
- Staleness uses Agent.last_seen_at, NOT session-level inactivity_timeout (different time scales: days vs minutes)
- Agent model has composite index on (project_id, last_seen_at) — efficient for staleness queries
- Modal must use z-50 (same as waypoint editor) — avoid z-index conflicts
- FR20: Export overwrites existing brain_reboot.md (not versioned)
- FR10: GET endpoint returns in-memory cached last generation, not file on disk
- FR24: Projects with no agent history show no staleness indicator (unknown state)
- FR28: Staleness indicators update on dashboard refresh/SSE — pass staleness data from route

## Git Change History

### Related Files
- Services: `waypoint_editor.py`, `progress_summary.py`, `inference_service.py`
- Routes: `waypoint.py`, `progress_summary.py`, `dashboard.py`
- Models: `agent.py` (last_seen_at), `project.py` (name, path, agents)
- Templates: `_waypoint_editor.html`, `_project_column.html`, `_project_group.html`, `_doc_viewer_modal.html`
- Static: `help.js` (clipboard pattern), `progress-summary.js`
- Config: `config.py` (DEFAULTS dict)

### OpenSpec History
- e3-s4-git-analyzer (2026-01-31) — Added progress summary generation, git analyzer, progress summary service
- E2 waypoint editor — Established waypoint file patterns, modal UI, archive

### Implementation Patterns
- Service pattern: constructor(inference_service=None, app=None), sync methods, config via get_value()
- Route pattern: Blueprint with url_prefix, lazy db import, service from app.extensions
- Test pattern: MagicMock for services, tmp_path for filesystem, pytest fixtures
- Modal pattern: Fixed overlay z-50, JS state object, dismiss via close/backdrop/escape
- File I/O pattern: os.makedirs(exist_ok=True), read with Path.read_text(), write atomically

## Q&A History
- No clarifications needed — PRD is comprehensive with 28 FRs and 5 NFRs
- No conflicts detected with existing codebase

## Dependencies
- No new packages required
- Depends on existing: WaypointEditor (read waypoints), ProgressSummaryService (read summaries), Agent model (last_seen_at)
- No database migrations needed — uses existing Agent.last_seen_at field

## Testing Strategy
- **StalenessService tests:** All tier classifications (fresh/aging/stale/unknown), configurable thresholds, batch classification, edge cases (exact boundary values)
- **BrainRebootService tests:** Both artifacts present, waypoint-only, summary-only, both-missing, export success/failure, directory creation, overwrite, formatting
- **Route tests:** POST generate (success, project not found), GET retrieve (found, not found, project not found), POST export (success, failure, not found)
- **Integration:** Dashboard renders with staleness indicators, modal opens/closes, clipboard/export work

## OpenSpec References
- proposal.md: openspec/changes/e3-s5-brain-reboot/proposal.md
- tasks.md: openspec/changes/e3-s5-brain-reboot/tasks.md
- spec.md: openspec/changes/e3-s5-brain-reboot/specs/brain-reboot/spec.md
