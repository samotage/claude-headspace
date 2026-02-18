# Commands: e3-s5-brain-reboot

## Phase 1: Configuration

- [x] 1. Add `brain_reboot` section to config.py DEFAULTS (staleness_threshold_days, aging_threshold_days, export_filename)

## Phase 2: Staleness Service

- [x] 2. Create `src/claude_headspace/services/staleness.py` with StalenessService class
- [x] 3. Implement `classify_project(project)` — returns freshness tier (fresh/aging/stale/unknown) based on most recent Agent.last_seen_at
- [x] 4. Implement `classify_projects(projects)` — batch classification for dashboard rendering
- [x] 5. Implement `get_last_activity(project)` — query most recent agent last_seen_at for a project
- [x] 6. Write unit tests for StalenessService (all tiers, unknown, edge cases, config thresholds)

## Phase 3: Brain Reboot Service

- [x] 7. Create `src/claude_headspace/services/brain_reboot.py` with BrainRebootService class
- [x] 8. Implement `generate(project)` — read waypoint + progress summary, compose formatted document
- [x] 9. Implement `_read_waypoint(project_path)` — read waypoint.md from docs/brain_reboot/
- [x] 10. Implement `_read_progress_summary(project_path)` — read progress_summary.md from docs/brain_reboot/
- [x] 11. Implement `_format_document(project_name, waypoint_content, summary_content)` — compose brain reboot markdown
- [x] 12. Implement missing artifact handling — waypoint-only, summary-only, both-missing cases
- [x] 13. Implement `export(project, content)` — save brain_reboot.md to target project directory
- [x] 14. Implement `get_last_generated(project_id)` — return cached/last generated content (in-memory)
- [x] 15. Write unit tests for BrainRebootService (generation, missing artifacts, export, formatting)

## Phase 4: API Endpoints

- [x] 16. Create `src/claude_headspace/routes/brain_reboot.py` with brain_reboot_bp blueprint
- [x] 17. Implement POST `/api/projects/<id>/brain-reboot` — generate brain reboot
- [x] 18. Implement GET `/api/projects/<id>/brain-reboot` — return last generated content
- [x] 19. Implement POST `/api/projects/<id>/brain-reboot/export` — export to filesystem
- [x] 20. Handle error responses: 404 (project not found), 500 (filesystem errors)
- [x] 21. Write unit tests for brain reboot API endpoints

## Phase 5: Dashboard Modal

- [x] 22. Create `templates/partials/_brain_reboot_modal.html` — modal following waypoint editor pattern
- [x] 23. Create `static/js/brain-reboot.js` — modal open/close, content loading, clipboard, export
- [x] 24. Implement clipboard functionality with visual feedback (following help.js pattern)
- [x] 25. Implement export button with success/error feedback
- [x] 26. Implement modal dismiss via close button, backdrop click, escape key

## Phase 6: Dashboard Staleness Integration

- [x] 27. Update `_project_column.html` — add Brain Reboot button and staleness indicators
- [x] 28. Update `_project_group.html` — add Brain Reboot button and staleness indicators
- [x] 29. Update dashboard route to compute and pass staleness data to templates
- [x] 30. Add staleness indicator styles (fresh=green, aging=amber, stale=red + "Needs Reboot" badge)

## Phase 7: App Registration & Wiring

- [x] 31. Register BrainRebootService and StalenessService in app.py (app.extensions)
- [x] 32. Register brain_reboot_bp blueprint in app.py
- [x] 33. Update `templates/dashboard.html` to include modal template and JS
- [x] 34. Run full test suite and verify no regressions
