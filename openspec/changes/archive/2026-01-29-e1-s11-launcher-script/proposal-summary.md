# Proposal Summary: e1-s11-launcher-script

## Architecture Decisions
- Python CLI tool for consistency with Flask application
- HTTP API for CLI↔Server communication (cleaner than direct DB access)
- UUID-based session identification for unique correlation
- Child process model for Claude Code launch (not daemon)
- Signal handlers for graceful cleanup (SIGINT, SIGTERM)

## Implementation Approach
- Create Flask blueprint for session API routes (POST/DELETE)
- Create CLI package under src/claude_headspace/cli/
- Use subprocess for launching Claude CLI with modified environment
- Use requests library for HTTP calls to Flask server
- Use ITERM_SESSION_ID env var for iTerm pane detection

## Files to Modify
**CLI:**
- `bin/claude-headspace` - Entry point script (new)
- `src/claude_headspace/cli/__init__.py` - CLI package (new)
- `src/claude_headspace/cli/launcher.py` - Main implementation (new)

**Routes:**
- `src/claude_headspace/routes/sessions.py` - Session API (new)
- `src/claude_headspace/app.py` - Register sessions_bp

**Tests:**
- `tests/cli/test_launcher.py` - CLI tests (new)
- `tests/routes/test_sessions.py` - API tests (new)

## Acceptance Criteria
- `claude-headspace start` launches monitored session
- Session appears in dashboard within 1 second
- Project detected from working directory
- iTerm pane ID captured when available
- Cleanup on exit (normal, SIGINT, SIGTERM)
- Clear error messages for failures
- Distinct exit codes (0-4)

## Constraints and Gotchas
- **Flask server must be running**: CLI depends on HTTP API
- **iTerm2 only**: Pane ID capture requires ITERM_SESSION_ID env var
- **macOS only**: Epic 1 scope is macOS
- **Signal handling**: Must ensure cleanup runs before exit
- **HTTP timeout**: 2 seconds per request to avoid hangs
- **Non-blocking cleanup**: Cleanup failures should log warning, not crash

## Git Change History

### Related Files
**Models (existing):**
- src/claude_headspace/models/agent.py - Agent model
- src/claude_headspace/models/project.py - Project model

**Routes (patterns to follow):**
- src/claude_headspace/routes/dashboard.py - Blueprint pattern
- src/claude_headspace/routes/health.py - Simple API endpoint pattern

**Config:**
- config.yaml - Server port configuration

### OpenSpec History
- e1-s10-logging-tab: Logging Tab (just completed)
- e1-s9-objective-tab: Objective Tab
- e1-s3-domain-models: Domain Models (Agent, Project)

### Implementation Patterns
1. Create Flask blueprint with API routes
2. Register blueprint in app.py
3. Create CLI module with argparse
4. Create bin/ script as entry point
5. Add tests for routes and CLI

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required** - requests already in dependencies
- **Sprint 3 (Domain Models):** Agent, Project models (complete)
- **Flask application running** - Required for API

## Testing Strategy
- Test POST /api/sessions creates agent and project
- Test DELETE /api/sessions marks session ended
- Test CLI project detection (git and non-git)
- Test CLI iTerm detection
- Test CLI prerequisite validation
- Test CLI registration and cleanup flow

## OpenSpec References
- proposal.md: openspec/changes/e1-s11-launcher-script/proposal.md
- tasks.md: openspec/changes/e1-s11-launcher-script/tasks.md
- spec.md: openspec/changes/e1-s11-launcher-script/specs/launcher/spec.md
