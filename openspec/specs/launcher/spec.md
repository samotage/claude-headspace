# launcher Specification

## Purpose
TBD - created by archiving change e1-s11-launcher-script. Update Purpose after archive.
## Requirements
### Requirement: CLI Entry Point

The system SHALL provide a `claude-headspace` CLI command.

#### Scenario: CLI is available

Given the user has installed claude-headspace
When the user runs `claude-headspace --help`
Then usage information is displayed

#### Scenario: Start command exists

Given the CLI is available
When the user runs `claude-headspace start`
Then a monitored Claude Code session is initiated

### Requirement: Session UUID Generation

The system SHALL generate a unique session identifier for each new session.

#### Scenario: UUID generation

Given a user runs `claude-headspace start`
When the session is initiated
Then a unique UUID is generated
And the UUID is used to identify this session

### Requirement: Project Detection

The system SHALL detect project information from the current working directory.

#### Scenario: Git repository detected

Given the user is in a git repository
When the session starts
Then the project name is extracted from git
And the current branch is captured

#### Scenario: Non-git directory

Given the user is in a non-git directory
When the session starts
Then the directory name is used as the project name
And the session proceeds without branch information

### Requirement: iTerm2 Pane ID Capture

The system SHALL capture the iTerm2 pane identifier when available.

#### Scenario: Running in iTerm2

Given the user runs the CLI in iTerm2
When the session starts
Then the iTerm pane ID is captured from ITERM_SESSION_ID

#### Scenario: Running in other terminal

Given the user runs the CLI outside iTerm2
When the session starts
Then a warning is displayed about missing pane ID
And the session proceeds without pane ID

### Requirement: POST /api/sessions Endpoint

The system SHALL provide an endpoint to register sessions.

#### Scenario: Session registration success

Given a valid registration request
When POST /api/sessions is called
Then status 201 is returned
And the response includes agent_id, session_uuid, project_id, project_name

#### Scenario: Registration with new project

Given a project path not in the database
When POST /api/sessions is called
Then a new Project record is created
And a new Agent record is created

#### Scenario: Registration with existing project

Given a project path already in the database
When POST /api/sessions is called
Then the existing Project is used
And a new Agent record is created

### Requirement: DELETE /api/sessions/<uuid> Endpoint

The system SHALL provide an endpoint to mark sessions as ended.

#### Scenario: Session cleanup success

Given a session exists with the given UUID
When DELETE /api/sessions/<uuid> is called
Then status 200 is returned
And the Agent record is marked as ended

#### Scenario: Session cleanup unknown UUID

Given no session exists with the given UUID
When DELETE /api/sessions/<uuid> is called
Then status 404 is returned

### Requirement: Environment Configuration

The system SHALL configure environment variables for Claude Code.

#### Scenario: Environment variables set

Given a session is being started
When Claude Code is launched
Then CLAUDE_HEADSPACE_URL is set to the Flask server URL
And CLAUDE_HEADSPACE_SESSION_ID is set to the session UUID

### Requirement: Claude Code Launch

The system SHALL launch the Claude CLI as a child process.

#### Scenario: Claude CLI found

Given the `claude` command is available
When the session starts
Then Claude Code is launched with configured environment

#### Scenario: Claude CLI not found

Given the `claude` command is not available
When the session starts
Then error message is displayed
And exit code 3 is returned

#### Scenario: Arguments passed through

Given the user provides additional arguments
When `claude-headspace start -- --model opus` is run
Then the arguments are passed to the claude command

### Requirement: Session Cleanup on Exit

The system SHALL clean up sessions when Claude Code exits.

#### Scenario: Normal exit cleanup

Given Claude Code exits normally
When the process ends
Then DELETE /api/sessions/<uuid> is called

#### Scenario: SIGINT cleanup

Given the user presses Ctrl+C
When SIGINT is received
Then DELETE /api/sessions/<uuid> is called
And the process exits

#### Scenario: SIGTERM cleanup

Given SIGTERM is sent to the process
When the signal is received
Then DELETE /api/sessions/<uuid> is called
And the process exits

### Requirement: Prerequisite Validation

The system SHALL validate prerequisites before proceeding.

#### Scenario: Flask server reachable

Given the Flask server is running
When validation runs
Then validation passes

#### Scenario: Flask server unreachable

Given the Flask server is not running
When validation runs
Then error message is displayed
And exit code 2 is returned

### Requirement: Exit Codes

The system SHALL use distinct exit codes for different outcomes.

#### Scenario: Exit codes

Given different failure modes
When the CLI exits
Then exit code 0 indicates success
And exit code 1 indicates general error
And exit code 2 indicates server unreachable
And exit code 3 indicates claude CLI not found
And exit code 4 indicates registration failed

