## ADDED Requirements

### Requirement: Slide-Out Chat Panel
The dashboard SHALL provide a fixed-position chat panel that slides in from the right edge of the viewport, overlaying the dashboard content without pushing or resizing the main layout.

#### Scenario: Panel appearance
- **WHEN** the chat panel is opened
- **THEN** a 440px-wide panel slides in from the right with a CSS transform transition
- **AND** the panel is full-height, z-index 50, with `bg-surface` background and left border

#### Scenario: Mobile responsive
- **WHEN** the viewport is narrower than 768px
- **THEN** the chat panel width is 100% of the viewport

### Requirement: Chat Panel Header
The panel header SHALL display the channel name, channel type badge, member count, and a close button.

#### Scenario: Header content
- **WHEN** the chat panel is open for a channel
- **THEN** the header shows the channel name as primary text, type and member count as muted meta text, and a close button (x symbol)

### Requirement: Message Feed Display
The panel body SHALL display messages in chronological order with newest messages at the bottom.

#### Scenario: Regular message rendering
- **WHEN** a regular message is displayed
- **THEN** it shows the sender persona name (bold, cyan for operator, green for agents), message content, and a relative timestamp with absolute timestamp on hover

#### Scenario: System message rendering
- **WHEN** a system message is displayed (message_type = "system")
- **THEN** it renders with centered, muted, italic styling

### Requirement: Message Feed Loading
On panel open, the chat panel SHALL fetch the most recent 50 messages from `GET /api/channels/<slug>/messages?limit=50`.

#### Scenario: Initial load
- **WHEN** the chat panel opens for a channel
- **THEN** it fetches the 50 most recent messages and renders them in chronological order
- **AND** scrolls to the bottom to show the newest messages

#### Scenario: Load earlier messages
- **WHEN** the user clicks "Load earlier messages" at the top of the feed
- **THEN** it fetches the next 50 messages using `?before=<oldest_sent_at>&limit=50`
- **AND** prepends them to the feed without changing the user's scroll position

### Requirement: Real-Time Message Append
When a `channel_message` SSE event arrives for the currently open channel, the new message SHALL append to the bottom of the feed.

#### Scenario: User at bottom of feed
- **WHEN** a new message arrives via SSE and the user's scroll position is within 50px of the bottom
- **THEN** the message appends and the feed auto-scrolls to show it

#### Scenario: User scrolled up
- **WHEN** a new message arrives via SSE and the user has scrolled up (more than 50px from bottom)
- **THEN** the message appends but the feed does NOT auto-scroll
- **AND** a "New messages below" indicator is shown that the user can click to scroll down

### Requirement: Send Message
The panel footer SHALL contain a textarea input and send button for posting messages.

#### Scenario: Successful send
- **WHEN** the user types a message and presses Enter (or clicks Send)
- **THEN** the message is sent via `POST /api/channels/<slug>/messages` with `{content: "..."}`
- **AND** the message appears immediately in the feed (optimistic rendering)
- **AND** the input clears

#### Scenario: Shift+Enter for newline
- **WHEN** the user presses Shift+Enter in the textarea
- **THEN** a newline is inserted instead of sending

#### Scenario: Send failure
- **WHEN** the API call fails (non-2xx response)
- **THEN** the optimistically rendered message shows an error indicator (red border or icon)
- **AND** a "Retry" option is available
- **AND** the input content is preserved for re-editing

### Requirement: Chat Panel Close
The chat panel SHALL close when the close button is clicked or the Escape key is pressed.

#### Scenario: Close via button
- **WHEN** the user clicks the close button (x)
- **THEN** the panel slides out to the right and sets `aria-hidden="true"`

#### Scenario: Close via Escape
- **WHEN** the user presses the Escape key while the chat panel is open
- **THEN** the panel slides out to the right and sets `aria-hidden="true"`

### Requirement: Active Channel Slug Tracking
The chat panel JS SHALL maintain a `window.ChannelChat._activeChannelSlug` variable identifying the currently viewed channel. This serves as infrastructure for v2 notification suppression.

#### Scenario: Panel open
- **WHEN** the chat panel is open for a channel
- **THEN** `_activeChannelSlug` is set to that channel's slug

#### Scenario: Panel closed
- **WHEN** the chat panel is closed
- **THEN** `_activeChannelSlug` is set to `null`
