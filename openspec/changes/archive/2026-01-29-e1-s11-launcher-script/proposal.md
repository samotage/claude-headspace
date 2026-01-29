# Proposal: e1-s11-launcher-script

## Summary

Create a `claude-headspace` CLI tool that launches Claude Code sessions with full monitoring integration. This bridges the gap between passive file watching and active session management by explicitly registering sessions, capturing iTerm pane IDs, and setting up environment variables for hooks.

## Motivation

Claude Headspace monitors sessions via jsonl file watching, but passive monitoring has limitations:
- No iTerm pane ID capture (breaking click-to-focus)
- No environment setup (breaking hooks integration)
- Late session discovery (missing session start events)
- No explicit lifecycle management (sessions may linger)

The launcher script solves these by registering sessions before Claude Code starts and cleaning up on exit.

## Impact

### Files to Create
- `bin/claude-headspace` - CLI entry point script
- `src/claude_headspace/cli/__init__.py` - CLI package
- `src/claude_headspace/cli/launcher.py` - Main launcher implementation
- `src/claude_headspace/routes/sessions.py` - Session API routes blueprint
- `tests/cli/test_launcher.py` - CLI tests
- `tests/routes/test_sessions.py` - API route tests

### Files to Modify
- `src/claude_headspace/app.py` - Register sessions blueprint
- `pyproject.toml` - Add CLI entry point (if using setuptools)

### Database Changes
None - uses existing Agent and Project models.

## Definition of Done

- [ ] `claude-headspace start` command launches monitored Claude Code session
- [ ] Session UUID generated and associated with session
- [ ] Project detection from working directory (git-aware)
- [ ] iTerm2 pane ID captured when available
- [ ] POST /api/sessions endpoint for registration
- [ ] DELETE /api/sessions/<uuid> endpoint for cleanup
- [ ] Environment variables set (CLAUDE_HEADSPACE_URL, CLAUDE_HEADSPACE_SESSION_ID)
- [ ] Claude CLI launched with configured environment
- [ ] Cleanup on exit (normal, SIGINT, SIGTERM)
- [ ] Prerequisite validation (Flask server, claude CLI)
- [ ] Distinct exit codes for different failure modes
- [ ] User-friendly error messages
- [ ] All tests passing

## Risks

- **iTerm2 Detection**: Getting the pane ID reliably requires AppleScript or environment variables. Will use `ITERM_SESSION_ID` env var.
- **Process Management**: Child process lifecycle needs careful signal handling to ensure cleanup runs.
- **Flask Server Dependency**: CLI requires Flask server to be running. Clear error messaging is critical.

## Alternatives Considered

1. **Shell script instead of Python**: Rejected - Python provides better cross-platform consistency and integration with Flask app
2. **Direct database access from CLI**: Rejected - HTTP API provides cleaner separation and doesn't require database credentials in CLI
3. **Daemon mode**: Out of scope - single-session launcher is simpler and meets MVP requirements
