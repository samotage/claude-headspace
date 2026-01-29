# focus Specification

## Purpose
TBD - created by archiving change e1-s12-applescript-integration. Update Purpose after archive.
## Requirements
### Requirement: Focus API Endpoint

The system SHALL provide an API endpoint to trigger iTerm2 focus for a specific agent.

#### Scenario: Focus endpoint success

Given an agent exists with a valid iterm_pane_id
When POST /api/focus/<agent_id> is called
Then status 200 is returned
And the response includes status "ok", agent_id, and pane_id

#### Scenario: Agent not found

Given no agent exists with the given ID
When POST /api/focus/<agent_id> is called
Then status 404 is returned
And error_type is "agent_not_found"

### Requirement: AppleScript Focus Execution

The system SHALL execute AppleScript to activate iTerm2 and focus a specific pane.

#### Scenario: Successful focus

Given iTerm2 is running
And the pane_id is valid
When focus is triggered
Then iTerm2 is brought to foreground
And the correct pane is selected as active session

#### Scenario: Focus across Spaces

Given iTerm2 is on a different macOS Space
When focus is triggered
Then the system switches to the correct Space
And iTerm2 is brought to foreground

#### Scenario: Restore minimized window

Given the iTerm2 window is minimized
When focus is triggered
Then the window is restored
And the correct pane is focused

### Requirement: Permission Error Handling

The system SHALL detect and report macOS Automation permission errors.

#### Scenario: Permission denied

Given Automation permission is not granted
When focus is triggered
Then error_type "permission_denied" is returned
And the message guides user to System Settings → Privacy & Security → Automation

### Requirement: iTerm2 Not Running Handling

The system SHALL handle when iTerm2 is not running.

#### Scenario: iTerm2 not running

Given iTerm2 application is not running
When focus is triggered
Then error_type "iterm_not_running" is returned
And the message suggests starting iTerm2

### Requirement: Missing Pane ID Handling

The system SHALL handle agents without pane IDs.

#### Scenario: No pane ID stored

Given an agent exists but has no iterm_pane_id
When focus is triggered
Then error_type "pane_not_found" is returned
And fallback_path contains the project path

#### Scenario: Stale pane ID

Given an agent has iterm_pane_id that no longer exists
When focus is triggered
Then error_type "pane_not_found" is returned
And fallback_path contains the project path

### Requirement: Fallback Path

The system SHALL provide fallback path in error responses for existing agents.

#### Scenario: Fallback path included

Given an agent exists
When focus fails for any reason
Then the error response includes fallback_path
And fallback_path contains the agent's project path

### Requirement: Focus Timeout

The system SHALL implement timeout to prevent blocking.

#### Scenario: AppleScript timeout

Given AppleScript execution hangs
When focus is triggered
Then the API returns within 2 seconds
And an appropriate error is returned

### Requirement: Focus Event Logging

The system SHALL log focus attempts to the event system.

#### Scenario: Focus event logged

Given a focus attempt is made
When the operation completes (success or failure)
Then an event with type "focus_attempted" is logged
And the event includes agent_id, pane_id, outcome, error_type, latency_ms

