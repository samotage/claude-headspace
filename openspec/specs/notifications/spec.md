# notifications Specification

## Purpose
TBD - created by archiving change e2-s4-macos-notifications. Update Purpose after archive.
## Requirements
### Requirement: Command Complete Notification

The system SHALL send a macOS notification when an agent's task transitions to the complete state.

#### Scenario: Command completes with notifications enabled

When an agent completes a task
And notifications are globally enabled
And command_complete notifications are enabled
Then a macOS notification appears within 500ms
And the notification includes the agent name
And the notification includes the project context

#### Scenario: Command completes with notifications disabled

When an agent completes a task
And notifications are globally disabled
Then no notification is sent

### Requirement: Awaiting Input Notification

The system SHALL send a macOS notification when an agent transitions to the awaiting_input state.

#### Scenario: Agent needs input with notifications enabled

When an agent transitions to awaiting_input state
And notifications are globally enabled
And awaiting_input notifications are enabled
Then a macOS notification appears within 500ms
And the notification indicates user action is required

#### Scenario: Agent needs input with notifications disabled

When an agent transitions to awaiting_input state
And notifications are globally disabled
Then no notification is sent

### Requirement: Click-to-Navigate

The system SHALL enable click-to-navigate functionality on notifications.

#### Scenario: User clicks notification

When the user clicks a notification
Then the default browser opens
And the dashboard URL includes highlight parameter
And the relevant agent card is highlighted
And the card is scrolled into view

#### Scenario: Highlight auto-removal

When the dashboard highlights an agent card
Then the highlight fades after 2-3 seconds

### Requirement: Rate Limiting

The system SHALL rate-limit notifications per agent to prevent spam.

#### Scenario: Multiple events within cooldown

When an agent triggers multiple notification events
And the events occur within the rate limit period
Then only the first notification is sent
And subsequent notifications are suppressed

#### Scenario: Event after cooldown expires

When an agent triggers a notification event
And the previous event was longer ago than the rate limit period
Then the notification is sent

### Requirement: Notification Preferences

The system SHALL provide configurable notification preferences.

#### Scenario: Global toggle disabled

When the user disables notifications globally
Then no notifications are sent for any event type

#### Scenario: Per-event toggle disabled

When the user disables command_complete notifications
And awaiting_input notifications are enabled
Then only awaiting_input notifications are sent

#### Scenario: Sound toggle disabled

When the user disables notification sounds
Then notifications appear silently

### Requirement: Availability Detection

The system SHALL detect terminal-notifier availability.

#### Scenario: terminal-notifier installed

When terminal-notifier is installed
Then the availability status is true
And notifications can be sent

#### Scenario: terminal-notifier not installed

When terminal-notifier is not installed
Then the availability status is false
And setup instructions are displayed in preferences UI
And the system continues operating without crashing

### Requirement: Preferences API

The system SHALL provide REST API endpoints for notification preferences.

#### Scenario: Get preferences

When GET /api/notifications/preferences is called
Then the response includes current preferences
And the response includes availability status

#### Scenario: Update preferences

When PUT /api/notifications/preferences is called
With valid preference data
Then the preferences are updated
And the preferences persist to config.yaml

### Requirement: Preferences Persistence

The system SHALL persist notification preferences across restarts.

#### Scenario: Preferences survive restart

When the user modifies notification preferences
And the application restarts
Then the modified preferences are loaded
And the previous settings are retained

