# channel-cards Specification

## Purpose
TBD - created by archiving change e9-s7-dashboard-ui. Update Purpose after archive.
## Requirements
### Requirement: Channel Cards Section Positioning
The dashboard SHALL include a channel cards section positioned between the sort controls and the main content area, visible in all three view modes (project, priority, Kanban).

#### Scenario: Cards visible with active channels
- **WHEN** the operator has active channel memberships
- **THEN** the channel cards section renders above all project sections
- **AND** one card is displayed per active, non-archived channel

#### Scenario: Cards hidden when no channels
- **WHEN** the operator has no active channel memberships or no channels exist
- **THEN** the channel cards section is not rendered
- **AND** the dashboard layout is identical to pre-channel state

### Requirement: Channel Card Content
Each channel card SHALL display the channel name (bold, primary text), a channel type badge (uppercase, muted), a comma-separated member list (persona names, truncated with "+N more"), a last message preview (sender name + truncated content, max ~100 chars), and a visual status indicator (green for active, amber for pending, muted for other states).

#### Scenario: Card with messages
- **WHEN** a channel has messages
- **THEN** the card displays the most recent message sender's persona name and truncated content

#### Scenario: Card without messages
- **WHEN** a channel has no messages (e.g., pending channel)
- **THEN** the card displays "No messages yet" in italic

#### Scenario: Large member list
- **WHEN** a channel has more members than can fit in the card width
- **THEN** the member list truncates with CSS text truncation

### Requirement: Channel Card Real-Time Updates
Channel cards SHALL update in real-time via SSE events without page reload.

#### Scenario: New message received
- **WHEN** a `channel_message` SSE event arrives for a visible channel card
- **THEN** the card's last message preview updates to show the new message sender and content

#### Scenario: Member change
- **WHEN** a `channel_update` SSE event arrives with `update_type` of `member_joined` or `member_left`
- **THEN** the affected card's member list updates

#### Scenario: Channel status change
- **WHEN** a `channel_update` SSE event indicates a status transition (e.g., `channel_completed`)
- **THEN** the card's status indicator updates

#### Scenario: New channel joined
- **WHEN** a `channel_update` SSE event indicates the operator joined a new active channel
- **THEN** a new channel card is dynamically added to the section

#### Scenario: Channel archived
- **WHEN** a `channel_update` SSE event indicates a channel was archived
- **THEN** the channel card is removed from the section

### Requirement: Channel Card Click Interaction
Clicking a channel card SHALL toggle the chat panel for that channel.

#### Scenario: Click to open
- **WHEN** the user clicks a channel card and the chat panel is closed
- **THEN** the chat panel opens showing that channel's messages

#### Scenario: Click to close (same channel)
- **WHEN** the user clicks the same channel card that is currently open
- **THEN** the chat panel closes

#### Scenario: Click to switch (different channel)
- **WHEN** the user clicks a different channel card while the chat panel is open
- **THEN** the chat panel switches to show the clicked channel's messages (instant swap, no slide animation)

