# Tasks: e1-s11-launcher-script

## Phase 1: Setup

- [ ] Review existing Agent and Project models
- [ ] Review existing Flask app structure for blueprint registration
- [ ] Plan CLI architecture and module structure

## Phase 2: Implementation

### API Endpoints (FR13-FR17)
- [ ] Create sessions.py blueprint with sessions_bp
- [ ] Implement POST /api/sessions endpoint
  - Accept: session_uuid, project_path, working_directory, iterm_pane_id
  - Create/update Project record from path
  - Create Agent record with session_uuid
  - Return: status, agent_id, session_uuid, project_id, project_name
- [ ] Implement DELETE /api/sessions/<uuid> endpoint
  - Mark Agent as inactive (set ended timestamp or similar)
  - Return: status, session_uuid
- [ ] Register sessions_bp in app.py

### CLI Package Structure (FR1-FR3)
- [ ] Create src/claude_headspace/cli/__init__.py
- [ ] Create src/claude_headspace/cli/launcher.py with main entry point
- [ ] Create bin/claude-headspace wrapper script
- [ ] Implement `start` subcommand parser

### Project Detection (FR4-FR6)
- [ ] Implement get_project_info() function
  - Detect git repository
  - Extract project name from directory or git remote
  - Extract current branch
  - Handle non-git directories gracefully

### iTerm2 Integration (FR7-FR8)
- [ ] Implement get_iterm_pane_id() function
  - Check ITERM_SESSION_ID environment variable
  - Return None with warning if not in iTerm2

### Session Registration (FR9-FR12)
- [ ] Implement register_session() function
  - Generate UUID
  - POST to /api/sessions
  - Handle success/failure responses
  - 2-second timeout for HTTP requests

### Environment Configuration (FR18-FR20)
- [ ] Implement setup_environment() function
  - Set CLAUDE_HEADSPACE_URL
  - Set CLAUDE_HEADSPACE_SESSION_ID

### Claude Code Launch (FR21-FR24)
- [ ] Implement verify_claude_cli() function
  - Check `claude` command availability
  - Return clear error if not found
- [ ] Implement launch_claude() function
  - Spawn subprocess with configured environment
  - Pass through additional arguments
  - Wait for process exit

### Session Cleanup (FR25-FR28)
- [ ] Implement cleanup_session() function
  - DELETE to /api/sessions/<uuid>
  - Handle failures gracefully (log warning)
- [ ] Implement signal handlers
  - SIGINT handler (Ctrl+C)
  - SIGTERM handler
  - Both call cleanup_session()

### Error Handling (FR29-FR31)
- [ ] Implement validate_prerequisites() function
  - Check Flask server is reachable (GET /health)
  - Check claude CLI available
- [ ] Define exit codes module
  - EXIT_SUCCESS = 0
  - EXIT_ERROR = 1
  - EXIT_SERVER_UNREACHABLE = 2
  - EXIT_CLAUDE_NOT_FOUND = 3
  - EXIT_REGISTRATION_FAILED = 4
- [ ] Implement user-friendly error messages

## Phase 3: Testing

- [ ] Test POST /api/sessions creates agent and project
- [ ] Test POST /api/sessions with existing project
- [ ] Test DELETE /api/sessions/<uuid> marks session ended
- [ ] Test DELETE /api/sessions with unknown uuid (404)
- [ ] Test CLI project detection (git repo)
- [ ] Test CLI project detection (non-git directory)
- [ ] Test CLI iTerm detection
- [ ] Test CLI prerequisite validation
- [ ] Test CLI registration flow
- [ ] Test CLI cleanup on normal exit

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] CLI executable from bin/claude-headspace
- [ ] Integration test: full launch → cleanup cycle
- [ ] Error messages are clear and actionable
- [ ] No console errors
