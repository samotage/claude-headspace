## ADDED Requirements

### Requirement: Smart Message Grouping

The chat client SHALL group rapid consecutive agent messages into single chat bubbles.

#### Scenario: Rapid agent messages

- **WHEN** consecutive agent turns arrive within 2 seconds of each other
- **AND** they share the same intent type
- **THEN** they SHALL be rendered as a single bubble with individual texts separated by line breaks

#### Scenario: Intent change breaks group

- **WHEN** an agent turn has a different intent than the previous agent turn
- **THEN** a new message group SHALL start regardless of time proximity

#### Scenario: User messages never grouped

- **WHEN** a USER turn (COMMAND, ANSWER) is encountered
- **THEN** it SHALL always render as its own bubble
- **AND** it SHALL break any active agent message group

---

### Requirement: iMessage-Style Timestamps

The chat view SHALL display timestamps following iMessage conventions.

#### Scenario: First message timestamp

- **WHEN** the first message in the conversation is rendered
- **THEN** a timestamp SHALL be displayed above it

#### Scenario: Time gap timestamp

- **WHEN** a message arrives more than 5 minutes after the previous message
- **THEN** a timestamp separator SHALL be displayed between them

#### Scenario: Timestamp formatting

- **WHEN** the message is from today
- **THEN** the timestamp SHALL show time only (e.g., "2:30 PM")
- **WHEN** the message is from yesterday
- **THEN** the timestamp SHALL show "Yesterday 2:30 PM"
- **WHEN** the message is from this week (but not today/yesterday)
- **THEN** the timestamp SHALL show day-of-week with time (e.g., "Monday 2:30 PM")
- **WHEN** the message is from earlier than this week
- **THEN** the timestamp SHALL show month/day with time (e.g., "Feb 3, 2:30 PM")

---

### Requirement: Task Boundary Separators

The chat view SHALL display visual separators between task boundaries.

#### Scenario: Task transition in conversation

- **WHEN** consecutive turns belong to different tasks
- **THEN** a visual separator SHALL be rendered between them
- **AND** the separator SHALL show the task instruction text

#### Scenario: Separator styling

- **WHEN** a task separator is rendered
- **THEN** it SHALL be centered text with horizontal rules
- **AND** it SHALL be visually distinct from messages but unobtrusive

---

### Requirement: Chat Links Everywhere

Chat links SHALL be available on all pages where agents appear.

#### Scenario: Project show page

- **WHEN** the project show page displays agent rows
- **THEN** each agent row SHALL include a chat link (both active and ended agents)

#### Scenario: Activity page

- **WHEN** the activity page displays individual agent references
- **THEN** each agent reference SHALL include a chat link

#### Scenario: Ended agent chat link

- **WHEN** a chat link for an ended agent is clicked
- **THEN** the chat SHALL open in read-only mode
- **AND** the input bar SHALL be hidden or disabled
- **AND** a banner SHALL indicate the agent session has concluded

---

### Requirement: Ended Agent Chat UI

The chat view SHALL fully support ended agents with read-only conversation display.

#### Scenario: Ended agent chat view

- **WHEN** the chat view is opened for an ended agent
- **THEN** the input bar SHALL be hidden or replaced with an "Agent ended" indicator
- **AND** the typing indicator SHALL NOT be shown

#### Scenario: Scroll-up pagination for chat history

- **WHEN** the user scrolls to the top of the chat message area
- **THEN** the client SHALL request the next page of older messages using cursor-based pagination
- **AND** SHALL prepend new messages above existing content
- **AND** SHALL preserve the user's scroll position

#### Scenario: Loading indicators

- **WHEN** older messages are being fetched
- **THEN** a loading spinner SHALL appear at the top of the message area
- **WHEN** all history has been loaded
- **THEN** an indicator SHALL show that no more messages are available
