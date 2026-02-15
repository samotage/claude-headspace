# tmux-attach Specification

## Purpose
Provides the ability to attach to an agent's tmux session from the dashboard via iTerm2, including API endpoint, AppleScript execution, and session validation.
## Requirements
### Requirement: Tmux Attach API Endpoint

The system SHALL provide an API endpoint to attach to an agent's tmux session via iTerm2. The endpoint SHALL open a new iTerm2 tab running `tmux attach -t <session_name>`, or reuse an existing tab if one is already attached to that session.

#### Scenario: Successful attach to tmux session

- **WHEN** `POST /api/agents/<id>/attach` is called for an agent with a valid `tmux_session`
- **AND** the tmux session exists
- **THEN** iTerm2 opens a tab attached to the tmux session
- **AND** status 200 is returned with `{status: "ok", agent_id, tmux_session, method: "new_tab" | "reused_tab"}`

#### Scenario: Reuse existing attached tab

- **WHEN** `POST /api/agents/<id>/attach` is called for an agent with a valid `tmux_session`
- **AND** an iTerm2 tab is already attached to that tmux session
- **THEN** the existing tab is focused instead of opening a new one
- **AND** status 200 is returned with `method: "reused_tab"`

#### Scenario: Agent not found

- **WHEN** `POST /api/agents/<id>/attach` is called for a non-existent agent
- **THEN** status 404 is returned with `detail: "agent_not_found"`

#### Scenario: Agent has no tmux session

- **WHEN** `POST /api/agents/<id>/attach` is called for an agent with `tmux_session` NULL
- **THEN** status 400 is returned with `detail: "no_tmux_session"`

#### Scenario: Tmux session no longer exists

- **WHEN** `POST /api/agents/<id>/attach` is called for an agent with a `tmux_session` value
- **AND** the tmux session has been killed or does not exist
- **THEN** status 400 is returned with `detail: "session_not_found"`
- **AND** the error message indicates the tmux session is no longer available

#### Scenario: iTerm2 not running

- **WHEN** `POST /api/agents/<id>/attach` is called
- **AND** iTerm2 is not running
- **THEN** status 500 is returned with `detail: "iterm_not_running"`

#### Scenario: AppleScript timeout

- **WHEN** `POST /api/agents/<id>/attach` is called
- **AND** the AppleScript execution exceeds the timeout
- **THEN** status 500 is returned with `detail: "timeout"`

---

### Requirement: Tmux Attach AppleScript Execution

The system SHALL execute AppleScript to open a new iTerm2 tab and run `tmux attach -t <session_name>` in it. The system SHALL first check if an existing iTerm2 tab is already attached to the target tmux session.

#### Scenario: Open new iTerm2 tab with tmux attach

- **WHEN** `attach_tmux_session(session_name)` is called
- **AND** no existing iTerm2 tab is attached to the session
- **THEN** a new iTerm2 tab is created in the frontmost window
- **AND** `tmux attach -t <session_name>` is executed in the new tab

#### Scenario: Reuse existing attached iTerm2 tab

- **WHEN** `attach_tmux_session(session_name)` is called
- **AND** an existing iTerm2 tab has a client attached to the target tmux session
- **THEN** the existing tab is focused (window brought to front, tab selected)
- **AND** no new tab is created

#### Scenario: AppleScript timeout protection

- **WHEN** AppleScript execution takes longer than 2 seconds
- **THEN** the subprocess is killed
- **AND** a timeout error is returned

---

### Requirement: Tmux Session Existence Validation

The system SHALL validate that a tmux session exists before attempting to attach.

#### Scenario: Session exists

- **WHEN** `tmux has-session -t <session_name>` returns exit code 0
- **THEN** the attach operation proceeds

#### Scenario: Session does not exist

- **WHEN** `tmux has-session -t <session_name>` returns non-zero exit code
- **THEN** the attach operation is aborted with an appropriate error
