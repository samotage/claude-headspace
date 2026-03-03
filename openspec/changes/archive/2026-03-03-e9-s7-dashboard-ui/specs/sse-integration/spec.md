## ADDED Requirements

### Requirement: SSE Event Type Registration
The SSE client SHALL register `channel_message` and `channel_update` as common event types in the `commonTypes` array of `static/js/sse-client.js`.

#### Scenario: Event type registration
- **WHEN** the SSE client initialises
- **THEN** `channel_message` and `channel_update` are included in `commonTypes`
- **AND** typed SSE events of these types are dispatched to registered handlers

### Requirement: Channel Message SSE Handler
The `channel-cards.js` module SHALL register a handler for `channel_message` SSE events via `window.sseClient.on('channel_message', handler)`.

#### Scenario: Message event with card visible
- **WHEN** a `channel_message` event arrives for a channel with a visible card
- **THEN** the card's last message preview updates with the new sender name and content preview

#### Scenario: Message event with chat panel open
- **WHEN** a `channel_message` event arrives for the channel currently open in the chat panel
- **THEN** the message is appended to the chat panel feed (delegated to `window.ChannelChat.appendMessage()`)

### Requirement: Channel Update SSE Handler
The `channel-cards.js` module SHALL register a handler for `channel_update` SSE events via `window.sseClient.on('channel_update', handler)`.

#### Scenario: Member joined
- **WHEN** a `channel_update` event arrives with `update_type` of `member_joined`
- **THEN** the affected card's member list updates to include the new member name

#### Scenario: Member left
- **WHEN** a `channel_update` event arrives with `update_type` of `member_left`
- **THEN** the affected card's member list updates to remove the departed member name

#### Scenario: Channel completed
- **WHEN** a `channel_update` event arrives with `update_type` of `channel_completed`
- **THEN** the affected card's status indicator changes from active (green) to complete (muted)

#### Scenario: Channel archived
- **WHEN** a `channel_update` event arrives with `update_type` of `channel_archived`
- **THEN** the channel card is removed from the cards section

### Requirement: Vanilla JS IIFE Pattern
All new JavaScript modules SHALL follow the existing IIFE pattern `(function(global) { ... })(window)` and expose their APIs on the `window` object.

#### Scenario: Module globals
- **WHEN** the JavaScript modules are loaded
- **THEN** `window.ChannelCards`, `window.ChannelChat`, and `window.ChannelManagement` are available as global objects

### Requirement: No New npm Dependencies
No new npm packages SHALL be added. All functionality uses vanilla JavaScript consistent with the existing frontend.

#### Scenario: Package check
- **WHEN** the implementation is complete
- **THEN** `package.json` has no new dependencies added by this sprint
