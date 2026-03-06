# voice-pwa-channels Specification

## Purpose
TBD - created by archiving change e9-s8-voice-bridge-channels. Update Purpose after archive.
## Requirements
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

### Requirement: Voice App Channel Creation Bottom Sheet — Redesigned

The voice app `#channel-picker` bottom sheet SHALL be redesigned to show a project picker + channel type selector + persona multi-checkbox, replacing the V0 name/type/existing-agents form.

#### Scenario: Bottom sheet opens (create mode)

- **WHEN** the operator taps "+" next to Channels in the sidebar
- **THEN** the `#channel-picker` bottom sheet MUST open with:
  - A project `<select>` populated from `GET /api/projects`
  - A channel type `<select>` (workshop, delegation, review, standup, broadcast) — retained from V0
  - An empty persona list `#channel-persona-list`
  - A CTA button showing "Create Channel (0 selected)"
- **AND** the old name text input MUST NOT be present

#### Scenario: Project selected — persona list populates

- **WHEN** the operator selects a project from the project picker
- **THEN** the persona list MUST populate with active personas from `GET /api/personas/active`
- **AND** each persona MUST be shown as a checkbox with persona name and role label

#### Scenario: Persona checkbox changes — CTA count updates

- **WHEN** the operator checks or unchecks personas
- **THEN** the CTA button text MUST update to reflect selected count (e.g. "Create Channel (3 selected)")

#### Scenario: Submit — persona-based channel creation

- **WHEN** the operator selects a project, at least one persona, and a type, then taps the CTA
- **THEN** `POST /api/channels` MUST be called with `{project_id, channel_type, persona_slugs: [...]}`
- **AND** the bottom sheet MUST close on success
- **AND** the channel name MUST be auto-generated server-side (no client-side name construction required)

#### Scenario: Submit with no personas selected

- **WHEN** the operator taps CTA without selecting any personas
- **THEN** the submission MUST be blocked (CTA disabled or validation error shown)

---

### Requirement: Voice App Add Member — Stub Replaced

The voice app "Add member" action in the channel kebab menu SHALL be wired to the channel picker in single-select add-member mode, replacing the stub message.

#### Scenario: Add member tapped (voice app)

- **WHEN** the operator taps "Add member" in the channel chat kebab menu
- **THEN** the `#channel-picker` bottom sheet MUST open in add-member mode:
  - Project picker present (may select different project from channel's project)
  - Persona list shows as single-select (radio buttons, not checkboxes)
  - CTA reads "Add to Channel"
- **AND** the stub message "Member picker not yet available in voice app..." MUST NOT appear

#### Scenario: Add member submitted

- **WHEN** the operator selects a project and persona and taps "Add to Channel"
- **THEN** `POST /api/channels/<slug>/members` MUST be called with `{persona_slug, project_id}`
- **AND** the bottom sheet MUST close on success

---

### Requirement: VoiceAPI.createChannel Signature Update

The `VoiceAPI.createChannel` function SHALL accept `(projectId, channelType, personaSlugs)` instead of `(name, channelType, memberAgentIds)`.

#### Scenario: createChannel call

- **WHEN** `VoiceAPI.createChannel(projectId, channelType, personaSlugs)` is called
- **THEN** `POST /api/channels` MUST receive body `{project_id, channel_type, persona_slugs}`
- **AND** `member_agents` field MUST NOT be sent

---

### Requirement: VoiceAPI.addChannelMember — New Function

A new `VoiceAPI.addChannelMember(slug, personaSlug, projectId)` function SHALL be available.

#### Scenario: addChannelMember call

- **WHEN** `VoiceAPI.addChannelMember(slug, personaSlug, projectId)` is called
- **THEN** `POST /api/channels/<slug>/members` MUST receive body `{persona_slug, project_id}`

