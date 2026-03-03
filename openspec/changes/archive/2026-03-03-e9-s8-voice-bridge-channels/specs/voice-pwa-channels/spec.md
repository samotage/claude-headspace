## ADDED Requirements

### Requirement: Channel Messages in Sidebar
The Voice Chat PWA (`/voice`) SHALL display channel messages from `channel_message` SSE events. Channel messages appear in a dedicated section of the sidebar below the agent list, showing: channel name (prefixed with #), sender persona name, message content preview, and relative timestamp.

#### Scenario: Channel message received via SSE
- **WHEN** a `channel_message` SSE event arrives
- **THEN** the sidebar channel section updates to show the new message's channel, sender, preview, and timestamp
- **AND** channels with newer messages appear first

#### Scenario: No channels active
- **WHEN** no `channel_message` or `channel_update` SSE events have been received
- **THEN** the channel section is not rendered in the sidebar

### Requirement: Channel State Management
The `voice-state.js` module SHALL include a `channels` array and a `currentChannelSlug` string for channel tracking in the Voice Chat PWA.

#### Scenario: State initialization
- **WHEN** the Voice Chat PWA loads
- **THEN** `channels` is initialized as an empty array and `currentChannelSlug` is null

#### Scenario: Channel update from SSE
- **WHEN** a `channel_update` SSE event arrives with new channel data
- **THEN** the `channels` array is updated to reflect the new state

### Requirement: Channel SSE Event Handlers
The `voice-sse-handler.js` module SHALL implement `handleChannelMessage()` and `handleChannelUpdate()` handlers. The `voice-api.js` module SHALL subscribe to `channel_message` and `channel_update` SSE event types.

#### Scenario: Channel message event
- **WHEN** an SSE event with type `channel_message` arrives
- **THEN** `handleChannelMessage()` is called, updating the sidebar and `VoiceState.channels`

#### Scenario: Channel update event
- **WHEN** an SSE event with type `channel_update` arrives
- **THEN** `handleChannelUpdate()` is called, updating the sidebar (member changes, status changes, new/removed channels)

### Requirement: Channel Message Tap-Through
Tapping a channel message in the sidebar SHALL navigate to a channel detail view showing the full message history in conversational envelope format, consistent with the existing agent chat view.

#### Scenario: Tap channel card
- **WHEN** the user taps a channel card in the sidebar
- **THEN** a channel detail view opens showing full message history
- **AND** messages are rendered as bubbles with persona attribution

### Requirement: Channel Message Visual Conventions
Channel message rendering in the Voice Chat PWA SHALL follow the same conventions as S7's dashboard chat panel: operator messages in cyan, agent messages in green, system messages muted and centered.

#### Scenario: Operator message displayed
- **WHEN** a channel message is from the operator
- **THEN** the message bubble is styled in cyan

#### Scenario: Agent message displayed
- **WHEN** a channel message is from an agent persona
- **THEN** the message bubble is styled in green

#### Scenario: System message displayed
- **WHEN** a channel message is a system message (join/leave/status change)
- **THEN** the message is styled muted and centered
