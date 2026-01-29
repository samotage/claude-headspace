---
validation:
  status: valid
  validated_at: '2026-01-29T11:07:40+11:00'
---

## Product Requirements Document (PRD) — Launcher Script

**Project:** Claude Headspace v3.1
**Scope:** CLI tool for launching monitored Claude Code sessions
**Author:** PM Agent (Workshop)
**Status:** Draft
**Epic:** 1
**Sprint:** 11

---

## Executive Summary

The launcher script provides a CLI tool (`claude-headspace`) that enables users to launch Claude Code sessions with full monitoring integration. By running `claude-headspace start` from any project directory, users get a session that is immediately visible in the dashboard with correct project association and iTerm2 pane identification for click-to-focus functionality.

This capability is essential for the Claude Headspace value proposition: without explicit session registration, the dashboard cannot capture iTerm pane IDs (breaking click-to-focus) or set up environment variables (breaking hooks integration). The launcher bridges the gap between passive file watching and active session management.

Success is measured by: sessions appearing in the dashboard within 1 second of launch, correct project and pane ID association, and clean session lifecycle management (including graceful cleanup on exit).

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace monitors Claude Code sessions via jsonl file watching. However, passive monitoring has limitations:

- **No iTerm pane ID:** File watching cannot determine which terminal pane hosts a session
- **No environment setup:** Hooks require environment variables set before Claude Code starts
- **Late discovery:** Sessions are discovered only after jsonl files are created, missing the session start event
- **No explicit lifecycle:** Sessions may linger in the dashboard after the user exits

The launcher script solves these problems by explicitly registering sessions before Claude Code starts and cleaning up when it exits.

### 1.2 Target User

Developers using Claude Code who want their sessions tracked in the Claude Headspace dashboard with full functionality:
- Click-to-focus from dashboard to iTerm
- Instant state updates via hooks
- Clean session lifecycle visibility

### 1.3 Success Moment

The user runs `claude-headspace start` in their project directory. Within one second, they see their new session appear in the dashboard with the correct project name. When they later click the session card in the dashboard, their iTerm window focuses. When they exit Claude Code, the session is marked inactive in the dashboard.

---

## 2. Scope

### 2.1 In Scope

- `claude-headspace` CLI tool (Python-based for portability)
- `start` command that launches a monitored Claude Code session
- Unique session identifier generation
- Project detection from current working directory
- iTerm2 pane identifier capture
- Session registration with Claude Headspace application via HTTP
- API endpoint for session registration (`POST /api/sessions`)
- API endpoint for session cleanup (`DELETE /api/sessions/<uuid>`)
- Environment variable configuration for Claude Code hooks
- Launch of `claude` CLI with configured environment
- Cleanup on exit (mark session inactive)
- Signal handling for graceful cleanup (SIGINT, SIGTERM)
- Error handling with clear user-facing messages
- Validation of prerequisites (Flask server running, claude CLI available)

### 2.2 Out of Scope

- AppleScript focus functionality (Sprint 12)
- Hook receiver endpoints (Sprint 13)
- Hook installation or configuration scripts
- Multiple terminal emulator support (iTerm2 only in Epic 1)
- Session resume or reconnect functionality
- GUI or TUI interface
- Shell completion scripts (bash/zsh/fish)
- Package distribution (PyPI, Homebrew)
- Windows or Linux support (macOS only in Epic 1)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User can run `claude-headspace start` from any directory containing a git repository
2. Session appears in Claude Headspace dashboard within 1 second of launch
3. Session is associated with the correct project (detected from working directory)
4. Session has iTerm2 pane identifier captured (when running in iTerm2)
5. Claude Code launches successfully with hooks environment variables configured
6. Session is marked inactive in dashboard when Claude Code exits (normal exit or Ctrl+C)

### 3.2 Non-Functional Success Criteria

1. Clear error message displayed when Flask server is unreachable
2. Clear error message displayed when `claude` CLI is not installed
3. Warning displayed when terminal is not iTerm2 (pane ID unavailable)
4. Graceful handling of SIGINT and SIGTERM signals
5. Exit codes: 0 for success, non-zero for errors (with distinct codes for different failure modes)

---

## 4. Functional Requirements (FRs)

### CLI Tool

**FR1:** The system provides a `claude-headspace` CLI command available in the user's PATH after installation.

**FR2:** The CLI provides a `start` subcommand that initiates a monitored Claude Code session.

**FR3:** The CLI generates a unique session identifier (UUID) for each new session.

### Project Detection

**FR4:** The CLI detects the project path from the current working directory.

**FR5:** The CLI extracts project metadata (name, git remote URL, current branch) from the working directory.

**FR6:** The CLI handles non-git directories gracefully, using the directory name as the project name.

### iTerm2 Integration

**FR7:** The CLI captures the iTerm2 pane identifier when running inside iTerm2.

**FR8:** The CLI detects when it is not running inside iTerm2 and proceeds without pane ID, displaying a warning.

### Session Registration

**FR9:** The CLI registers the session with Claude Headspace via HTTP POST before launching Claude Code.

**FR10:** The registration request includes: session UUID, project path, working directory, iTerm pane ID (if available).

**FR11:** The CLI waits for successful registration confirmation before launching Claude Code.

**FR12:** The CLI displays a clear error and exits if registration fails (server unreachable or error response).

### API Endpoints

**FR13:** The application provides a `POST /api/sessions` endpoint that accepts session registration requests.

**FR14:** The registration endpoint creates or updates the Agent record in the database.

**FR15:** The registration endpoint returns the created session details including the database agent ID.

**FR16:** The application provides a `DELETE /api/sessions/<uuid>` endpoint that marks a session as inactive.

**FR17:** The cleanup endpoint updates the Agent record to indicate the session has ended.

### Environment Configuration

**FR18:** The CLI sets `CLAUDE_HEADSPACE_URL` environment variable to the Flask server URL (e.g., `http://localhost:5050`).

**FR19:** The CLI sets `CLAUDE_HEADSPACE_SESSION_ID` environment variable to the generated session UUID.

**FR20:** These environment variables are available to Claude Code and its hook scripts.

### Claude Code Launch

**FR21:** The CLI verifies the `claude` command is available before attempting to launch.

**FR22:** The CLI launches the `claude` CLI as a child process with the configured environment.

**FR23:** The CLI passes through any additional arguments provided after `start` to the `claude` command.

**FR24:** The CLI waits for the Claude Code process to exit.

### Session Cleanup

**FR25:** The CLI sends a cleanup request to mark the session inactive when Claude Code exits normally.

**FR26:** The CLI sends a cleanup request when terminated by SIGINT (Ctrl+C).

**FR27:** The CLI sends a cleanup request when terminated by SIGTERM.

**FR28:** The CLI handles cleanup failures gracefully (log warning, don't crash).

### Error Handling

**FR29:** The CLI validates that the Flask server is reachable before proceeding.

**FR30:** The CLI provides distinct exit codes for different failure modes:
- 0: Success (Claude Code exited normally)
- 1: General error
- 2: Flask server unreachable
- 3: Claude CLI not found
- 4: Registration failed

**FR31:** Error messages are user-friendly and actionable (e.g., "Flask server not running. Start it with: flask run").

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Session registration completes within 500ms under normal conditions.

**NFR2:** The launcher adds minimal overhead to Claude Code startup (<1 second total).

**NFR3:** The CLI is implemented in Python for consistency with the Flask application.

**NFR4:** The CLI works on macOS Monterey (12.0) and later.

**NFR5:** The CLI handles network timeouts gracefully (2-second timeout for HTTP requests).

---

## 6. Technical Context

### 6.1 Environment Variables

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `CLAUDE_HEADSPACE_URL` | Flask server URL for hooks | `http://localhost:5050` |
| `CLAUDE_HEADSPACE_SESSION_ID` | Session identifier for correlation | `550e8400-e29b-41d4-a716-446655440000` |

### 6.2 API Request/Response Schemas

**POST /api/sessions**

Request:
```json
{
  "session_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "project_path": "/Users/dev/myproject",
  "working_directory": "/Users/dev/myproject",
  "iterm_pane_id": "pty-12345"
}
```

Response (201 Created):
```json
{
  "status": "registered",
  "agent_id": 42,
  "session_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "project_id": 7,
  "project_name": "myproject"
}
```

**DELETE /api/sessions/<uuid>**

Response (200 OK):
```json
{
  "status": "ended",
  "session_uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 6.3 File Locations

| File | Purpose |
|------|---------|
| `bin/claude-headspace` | CLI entry point script |
| `src/claude_headspace/cli/` | CLI implementation module |
| `src/claude_headspace/routes/sessions.py` | API routes for session management |

### 6.4 Dependencies

- Sprint 3 (Domain Models): Agent model exists
- Sprint 4 (File Watcher): SessionRegistry service exists
- Flask application running on configured port

### 6.5 Integration with Sprint 12 & 13

The launcher prepares the environment for:
- **Sprint 12 (AppleScript):** iTerm pane ID enables click-to-focus
- **Sprint 13 (Hooks):** Environment variables enable hook → headspace communication
