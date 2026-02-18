# Commands: e3-s4-git-analyzer

## Phase 1: Git Analyzer Service

- [x] 1. Create `src/claude_headspace/services/git_analyzer.py` with GitAnalyzer class and GitAnalysisResult dataclass
- [x] 2. Implement `_run_git_log()` — subprocess wrapper for read-only git log commands with error handling
- [x] 3. Implement `_parse_git_log()` — parse structured git log output into commit objects
- [x] 4. Implement `analyze()` with `since_last` scope — extract commits since previous generation timestamp
- [x] 5. Implement `analyze()` with `last_n` scope — extract most recent N commits
- [x] 6. Implement `analyze()` with `time_based` scope — extract commits within last N days
- [x] 7. Implement maximum commit cap — truncate to most recent when cap exceeded
- [x] 8. Handle edge cases: non-git repos, empty repos, detached HEAD, shallow clones, permission errors
- [x] 9. Write unit tests for GitAnalyzer (all scopes, cap enforcement, edge cases, parsing)

## Phase 2: Progress Summary Service

- [x] 10. Create `src/claude_headspace/services/progress_summary.py` with ProgressSummaryService class
- [x] 11. Implement `_build_prompt()` — construct prompt from GitAnalysisResult with project context
- [x] 12. Implement `_write_summary()` — write progress_summary.md with metadata header to target project
- [x] 13. Implement `_archive_existing()` — archive current file with date-stamp, handle same-day suffix
- [x] 14. Implement `_ensure_directory()` — create docs/brain_reboot/ and archive/ if missing
- [x] 15. Implement `generate()` — main entry: validate project, analyze git, build prompt, call inference, write file
- [x] 16. Implement `get_current_summary()` — read and return current progress_summary.md content
- [x] 17. Implement concurrent generation guard — threading.Lock with set of in-progress project IDs
- [x] 18. Handle error cases: inference failure, file write failure, no commits in scope
- [x] 19. Write unit tests for ProgressSummaryService (prompt building, file output, archiving, guard, errors)

## Phase 3: API Endpoints

- [x] 20. Create `src/claude_headspace/routes/progress_summary.py` with progress_summary_bp blueprint
- [x] 21. Implement POST `/api/projects/<id>/progress-summary` — trigger generation with optional scope override
- [x] 22. Implement GET `/api/projects/<id>/progress-summary` — return current summary content
- [x] 23. Handle error responses: 404 (project not found), 422 (not a git repo), 409 (generation in progress), 503 (inference unavailable)
- [x] 24. Write unit tests for progress summary API endpoints

## Phase 4: Configuration

- [x] 25. Add `progress_summary` section to config defaults in `config.py` (default_scope, last_n_count, time_based_days, max_commits)
- [x] 26. Add configuration reading in ProgressSummaryService constructor

## Phase 5: Dashboard Integration

- [x] 27. Add "Generate Progress Summary" button to project panel template
- [x] 28. Add summary display area to project panel template
- [x] 29. Add JavaScript for button click handler, in-progress indicator, and summary rendering
- [x] 30. Add generation-in-progress and error state UI handling

## Phase 6: App Registration & Wiring

- [x] 31. Register ProgressSummaryService in app.py (app.extensions)
- [x] 32. Register progress_summary_bp blueprint in app.py
- [x] 33. Run full test suite and verify no regressions
