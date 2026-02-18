# Proposal Summary: e3-s4-git-analyzer

## Architecture Decisions
- **Two separate service classes**: GitAnalyzer (pure utility, no Flask deps) and ProgressSummaryService (Flask-aware, orchestrates the pipeline)
- GitAnalyzer uses `subprocess.run` with `git log` for read-only commit extraction — no gitpython or other heavy dependencies
- ProgressSummaryService follows the same pattern as SummarisationService/PriorityScoringService: constructor takes InferenceService + optional Flask app
- Progress summary files are **repo artifacts** written to the target project's filesystem, not stored in Claude Headspace database
- Concurrent generation guard via `threading.Lock` + `set[int]` of in-progress project IDs — cleared on completion/error
- Three commit scope modes: `since_last` (default, falls back to `last_n`), `last_n`, `time_based`

## Implementation Approach
- Create GitAnalyzer as a standalone class that can be tested independently without Flask context
- ProgressSummaryService wraps GitAnalyzer + InferenceService + file I/O
- Routes blueprint follows the same pattern as priority routes (lazy db import, service from app.extensions)
- Dashboard integration: button + summary display area + JS handler for async generation
- Config defaults added to config.py DEFAULTS dict

## Files to Modify

### New Files
- `src/claude_headspace/services/git_analyzer.py` — GitAnalyzer class with scope modes and commit parsing
- `src/claude_headspace/services/progress_summary.py` — ProgressSummaryService with generation, archiving, guard
- `src/claude_headspace/routes/progress_summary.py` — Progress summary API blueprint
- `tests/services/test_git_analyzer.py` — GitAnalyzer unit tests
- `tests/services/test_progress_summary.py` — ProgressSummaryService unit tests
- `tests/routes/test_progress_summary.py` — Route unit tests

### Modified Files
- `src/claude_headspace/app.py` — Register ProgressSummaryService and blueprint
- `src/claude_headspace/config.py` — Add progress_summary defaults
- `templates/dashboard.html` or `templates/partials/_project_panel.html` — Add generate button and summary display

## Acceptance Criteria
- Git analyzer extracts commits with all three scope modes
- Maximum commit cap enforced (truncate to most recent)
- Progress summary generated as 3-5 paragraph narrative via E3-S1 inference (level="project")
- progress_summary.md written to target project's docs/brain_reboot/ with metadata header
- Previous version archived with date-stamped filename (with same-day suffix handling)
- Directory structure auto-created if missing
- POST /api/projects/<id>/progress-summary triggers generation
- GET /api/projects/<id>/progress-summary returns current summary
- Concurrent generation guard prevents duplicate runs per project
- Dashboard shows Generate button and summary display per project
- Non-git projects handled gracefully (422)
- Empty scope returns message without inference call
- config.yaml has progress_summary section

## Constraints and Gotchas
- **Git operations MUST be read-only** — never write, commit, or push to target repos
- **Lazy imports for db**: Route files use `from ..database import db` inside functions. Test patches target `src.claude_headspace.database.db`.
- **Project.path is the filesystem path** to the target repo — used for both git commands and file writes
- **subprocess.run for git**: Use `cwd=repo_path`, `capture_output=True`, `text=True`, `timeout=30`
- **since_last scope**: Parse the metadata header from existing progress_summary.md to get the generation timestamp. Metadata format: YAML frontmatter between `---` markers.
- **File write atomicity**: Archive BEFORE writing new file. If new write fails, archived version is preserved.
- **Same-day archive suffix**: Check for existing `progress_summary_YYYY-MM-DD.md` and append `_2`, `_3` etc.
- **Test mock strategy**: Mock `subprocess.run` for git commands, mock `InferenceService.infer()` for LLM calls, use `tmp_path` fixture for filesystem operations
- **Config access**: Use `get_value(config, "progress_summary", "default_scope", default="since_last")` pattern from config.py
- **Permission errors on target repos**: Catch `PermissionError` and `OSError` from file I/O, log and return error without crashing

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/inference_service.py`, `src/claude_headspace/services/summarisation_service.py`, `src/claude_headspace/services/priority_scoring.py`
- Routes: `src/claude_headspace/routes/summarisation.py`, `src/claude_headspace/routes/priority.py`
- Models: `src/claude_headspace/models/project.py`
- Config: `src/claude_headspace/config.py`, `src/claude_headspace/app.py`

### OpenSpec History
- E3-S1 (openrouter-integration): Added InferenceService, InferenceCall model, inference routes
- E3-S2 (turn-command-summarisation): Added SummarisationService, SSE broadcast pattern
- E3-S3 (priority-scoring): Added PriorityScoringService, priority routes, debounce pattern

### Implementation Patterns
- Service: constructor(inference_service, app=None), sync method, config access via get_value()
- Routes: Blueprint, lazy db import, service from app.extensions, error handling (503/404/422/409)
- Tests: MagicMock for services, tmp_path for filesystem, subprocess mock for git, pytest fixtures

## Q&A History
- No clarifications needed — PRD is comprehensive and consistent with existing patterns

## Dependencies
- No new packages — uses subprocess (stdlib), pathlib (stdlib), threading (stdlib), E3-S1 InferenceService
- Depends on E3-S1 (inference service) being complete (merged)
- No database migrations needed — no new models or columns

## Testing Strategy
- **GitAnalyzer unit tests**: All three scope modes, commit cap, edge cases (non-git, empty, permissions), git log parsing
- **ProgressSummaryService unit tests**: Prompt building, file write/archive, concurrent guard, error handling, metadata parsing
- **Route unit tests**: POST trigger (success, 404, 422, 409, 503), GET retrieve (success, 404, no summary)
- **Filesystem tests**: Use tmp_path fixture for directory creation, archiving, same-day suffix
- **Existing test regression**: Verify all 930+ existing tests still pass

## OpenSpec References
- proposal.md: openspec/changes/e3-s4-git-analyzer/proposal.md
- tasks.md: openspec/changes/e3-s4-git-analyzer/tasks.md
- spec.md: openspec/changes/e3-s4-git-analyzer/specs/git-analyzer/spec.md
