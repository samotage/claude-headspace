# Proposal: e3-s4-git-analyzer

## Summary

Add a git analyzer service and progress summary generator that extracts commit history from target project repositories and produces LLM-powered narrative summaries, written as markdown files to each project's `docs/brain_reboot/` directory.

## Motivation

Claude Headspace tracks real-time agent activity but lacks a historical view. Developers returning to a project have no concise summary of what has been accomplished — only raw git logs. This sprint provides the "what's been done" half of the brain reboot system (E3-S5 combines this with waypoint). The git analyzer extracts structured commit data and the progress summary generator produces human-readable narratives via the E3-S1 inference service.

## Impact

### Files Modified

**Services (New):**
- `src/claude_headspace/services/git_analyzer.py` — Git commit extraction with scope modes (since_last, last_n, time_based), structured analysis results
- `src/claude_headspace/services/progress_summary.py` — Progress summary generator: prompt building, file output, archiving, concurrent generation guard

**Routes (New):**
- `src/claude_headspace/routes/progress_summary.py` — New blueprint: POST/GET `/api/projects/<id>/progress-summary`

**App Wiring:**
- `src/claude_headspace/app.py` — Register ProgressSummaryService and progress_summary blueprint

**Templates (Modified):**
- `templates/partials/_project_panel.html` — Add "Generate Progress Summary" button and summary display area (or relevant dashboard template)

**Configuration:**
- `config.yaml` — Add `progress_summary` section with scope defaults and commit cap

### Integration Points

- **E3-S1 InferenceService:** Uses `infer(level="project", purpose="progress_summary", project_id=project.id, ...)` for narrative generation
- **Project model:** Uses `project.path` to access target repo filesystem and run git commands
- **SSE Broadcaster:** Could broadcast generation progress/completion events (optional enhancement)

### Recent Changes (from E3-S3)

- Agent model extended with priority fields (no conflict)
- PriorityScoringService registered in app.py (pattern to follow for service registration)
- Priority blueprint registered (pattern to follow for blueprint registration)

## Approach

### Architecture

1. **GitAnalyzer** — Standalone utility class (no Flask dependencies):
   - `analyze(repo_path, scope, ...)` — Main entry point returning structured `GitAnalysisResult`
   - `_get_commits_since_last(...)` — Scope mode: since last generation
   - `_get_commits_last_n(...)` — Scope mode: last N commits
   - `_get_commits_time_based(...)` — Scope mode: last N days
   - Uses `subprocess.run` with `git log` commands (read-only)

2. **ProgressSummaryService** — Flask-aware service:
   - `generate(project, scope=None)` — Main entry: analyze git, build prompt, call inference, write file
   - `_build_prompt(analysis_result)` — Construct prompt from structured git data
   - `_write_summary(project_path, content, metadata)` — Write progress_summary.md with archiving
   - `_archive_existing(project_path)` — Archive current file before overwrite
   - `get_current_summary(project)` — Read current progress_summary.md
   - Concurrent generation guard via set of in-progress project IDs with threading.Lock

3. **Progress summary routes** — Blueprint with POST (trigger) and GET (read) endpoints

4. **Dashboard integration** — Button and display area in project panel

### File Output Pattern

```
{project.path}/docs/brain_reboot/
  progress_summary.md              (current, with metadata header)
  archive/
    progress_summary_2026-01-28.md
    progress_summary_2026-01-28_2.md  (numeric suffix for same-day)
```

## Definition of Done

- [ ] GitAnalyzer extracts commits with all three scope modes (since_last, last_n, time_based)
- [ ] Maximum commit cap enforced
- [ ] ProgressSummaryService generates narrative via E3-S1 inference
- [ ] progress_summary.md written to target project's docs/brain_reboot/ with metadata header
- [ ] Previous version archived with date-stamped filename before overwrite
- [ ] Directory structure auto-created if missing
- [ ] POST /api/projects/<id>/progress-summary triggers generation
- [ ] GET /api/projects/<id>/progress-summary returns current summary
- [ ] Concurrent generation guard prevents duplicate runs per project
- [ ] Dashboard shows Generate button and summary display per project
- [ ] Non-git projects handled gracefully (422 error)
- [ ] Empty commit scope returns clear message without inference call
- [ ] config.yaml has progress_summary section
- [ ] All tests pass (unit + integration + existing suite)
