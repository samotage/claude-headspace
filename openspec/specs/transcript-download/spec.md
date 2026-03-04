# transcript-download Specification

## Purpose
TBD - created by archiving change transcript-download. Update Purpose after archive.
## Requirements
### Requirement: Agent Session Transcript Assembly (FR1, FR3)

The system SHALL assemble a complete transcript from an agent session by querying all Turn records across all Commands belonging to the Agent, ordered chronologically by Turn.timestamp. Each turn entry SHALL include the actor's display name (Persona.name for AGENT turns, "Operator" for USER turns), the timestamp in ISO 8601 format, and the full Turn.text content. Internal turns (Turn.is_internal = true) SHALL be excluded.

#### Scenario: Agent with multiple commands and turns

- **WHEN** an agent session transcript is requested for an agent with 3 commands and 15 turns
- **THEN** the transcript SHALL contain all 15 non-internal turns ordered chronologically across all 3 commands

#### Scenario: Agent with no turns

- **WHEN** an agent session transcript is requested for an agent with no turns
- **THEN** the system SHALL return an empty transcript body with valid frontmatter showing message_count: 0

### Requirement: Channel Chat Transcript Assembly (FR2, FR3)

The system SHALL assemble a complete transcript from a channel chat by querying all Message records belonging to the Channel, ordered chronologically by Message.sent_at. Each message entry SHALL include the sender's display name (Persona.name for persona-authored messages, "System" for system messages), the timestamp in ISO 8601 format, and the full Message.content.

#### Scenario: Channel with multiple participants

- **WHEN** a channel transcript is requested for a channel with 4 participants and 30 messages
- **THEN** the transcript SHALL contain all 30 messages with correct persona attribution

#### Scenario: Channel with no messages

- **WHEN** a channel transcript is requested for a channel with no messages
- **THEN** the system SHALL return an empty transcript body with valid frontmatter showing message_count: 0

### Requirement: YAML Frontmatter Metadata (FR4)

The transcript SHALL be formatted as Markdown with YAML frontmatter containing:
- `type`: "chat" for agent sessions, "channel" for group chats
- `identifier`: Agent.session_uuid (for chat) or Channel.slug (for channel)
- `project`: Project.name
- `persona`: Persona.slug of the agent (for chat) or channel chair persona (for channel)
- `agent_id`: Agent.id
- `participants`: list of participant names with roles
- `start_time`: ISO 8601 timestamp of the first message/turn
- `end_time`: ISO 8601 timestamp of the last message/turn
- `message_count`: total number of messages/turns in the transcript
- `exported_at`: ISO 8601 timestamp of generation time

#### Scenario: Agent session frontmatter

- **WHEN** an agent transcript is generated
- **THEN** the frontmatter SHALL contain type "chat", the agent's session UUID as identifier, and the agent's persona slug

#### Scenario: Channel chat frontmatter

- **WHEN** a channel transcript is generated
- **THEN** the frontmatter SHALL contain type "channel", the channel slug as identifier, and the chair's persona slug

### Requirement: Transcript Body Format (FR5)

Each message in the transcript body SHALL use the format:

```
### {display_name} — {timestamp}

{message_text}
```

Where display_name is the actor/sender name, timestamp is human-readable (e.g., "2026-03-05 09:30:00 AEDT"), and message_text is the full content. Messages SHALL be separated by blank lines for readability.

#### Scenario: Message format consistency

- **WHEN** a transcript contains turns from both USER and AGENT actors
- **THEN** each turn SHALL use the H3 heading format with display name, em-dash separator, and timestamp, followed by the full message text

### Requirement: File Naming Convention (FR6)

The transcript filename SHALL follow the convention: `{type}-{persona_slug}-{agent_id}-{datetime}.md` where:
- `type` is "chat" or "channel"
- `persona_slug` is the agent's persona slug (for chat) or chair's persona slug (for channel)
- `agent_id` is the Agent.id (integer)
- `datetime` is the export timestamp in format `YYYYMMDD-HHMMSS`

#### Scenario: Filename for agent session

- **WHEN** a transcript is generated for agent 42 with persona "shorty" at 2026-03-05 09:30:00
- **THEN** the filename SHALL be `chat-shorty-42-20260305-093000.md`

#### Scenario: Filename with no persona

- **WHEN** a transcript is generated for agent 7 with no persona
- **THEN** the filename SHALL use "unknown" as persona_slug: `chat-unknown-7-20260305-093000.md`

### Requirement: Server-Side Persistence (FR7)

The transcript SHALL be saved as a file in `data/transcripts/` using the filename from FR6. The directory SHALL be created if it does not exist.

#### Scenario: Successful save

- **WHEN** a transcript is generated
- **THEN** a copy SHALL exist at `data/transcripts/{filename}` with identical content to the downloaded file

### Requirement: Browser Download (FR8)

The transcript SHALL be delivered to the user's browser with:
- `Content-Type: text/markdown; charset=utf-8`
- `Content-Disposition: attachment; filename="{filename}"`

#### Scenario: Download headers

- **WHEN** the transcript download endpoint is called
- **THEN** the response SHALL trigger a browser file download with the correct filename

### Requirement: UI Integration -- Voice App Agent Chat (FR9)

A "Download Transcript" action SHALL be added to the voice app agent chat kebab menu (portal-based menu in `voice-sidebar.js`). The action SHALL appear for both active and ended agents.

#### Scenario: Voice app agent kebab menu includes download

- **WHEN** the user opens the agent kebab menu in the voice app
- **THEN** a "Download Transcript" action SHALL appear in the menu for both active and ended agents

### Requirement: UI Integration -- Voice App Channel Chat (FR10)

A "Download Transcript" action SHALL be added to the voice app channel chat kebab menu (portal-based menu in `voice-channel-chat.js`). The action SHALL appear for all channels regardless of status.

#### Scenario: Voice app channel kebab menu includes download

- **WHEN** the user opens the channel chat kebab menu in the voice app
- **THEN** a "Download Transcript" action SHALL appear in the menu

### Requirement: UI Integration -- Dashboard Agent Card (FR11)

A "Download Transcript" action SHALL be added to the dashboard agent card kebab menu (portal-based menu in `agent-lifecycle.js`).

#### Scenario: Dashboard agent card kebab menu includes download

- **WHEN** the user opens the agent card kebab menu on the dashboard
- **THEN** a "Download Transcript" action SHALL appear in the menu

### Requirement: UI Integration -- Dashboard Channel Chat (FR12)

A "Download Transcript" action SHALL be added to the dashboard channel chat kebab menu (inline menu in `_channel_chat_panel.html` and `channel-chat.js`).

#### Scenario: Dashboard channel chat kebab menu includes download

- **WHEN** the user opens the channel chat kebab menu on the dashboard
- **THEN** a "Download Transcript" action SHALL appear in the menu

### Requirement: Visual Feedback (FR13)

The download action SHALL provide visual feedback while the transcript is being assembled. This MAY be a brief loading state on the menu item or a toast notification indicating the download is in progress.

#### Scenario: Download initiated

- **WHEN** the user clicks "Download Transcript"
- **THEN** a toast or loading indicator SHALL appear while the transcript is being assembled

#### Scenario: Download complete

- **WHEN** the transcript download completes
- **THEN** the browser download SHALL trigger and any loading indicator SHALL be dismissed

### Requirement: Non-Blocking Download (NFR2)

The download operation SHALL NOT block the chat UI. The user SHALL be able to continue interacting with the chat while the transcript is being assembled.

#### Scenario: Async download

- **WHEN** a transcript download is initiated via the kebab menu
- **THEN** the chat input and message feed SHALL remain fully interactive during transcript assembly

