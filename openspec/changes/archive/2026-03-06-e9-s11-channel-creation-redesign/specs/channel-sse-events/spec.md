## ADDED Requirements

### Requirement: channel_member_connected SSE Event

The system SHALL broadcast a `channel_member_connected` SSE event when a pending membership's `agent_id` is set (an agent connects to a pending channel).

#### Scenario: Agent connects to pending channel

- **WHEN** `link_agent_to_pending_membership()` sets `membership.agent_id` and the channel is still pending
- **THEN** a `channel_member_connected` SSE event MUST be broadcast with:
  - `channel_slug`: the channel's slug
  - `persona_name`: the persona's display name
  - `persona_slug`: the persona's slug
  - `agent_id`: the newly-linked agent's ID
  - `connected_count`: count of memberships with non-null agent_id (non-chair)
  - `total_count`: total non-chair membership count for the channel

#### Scenario: Voice app receives channel_member_connected

- **WHEN** the voice app SSE handler receives a `channel_member_connected` event for the current channel
- **THEN** the pending pill for that persona MUST transition to connected state
- **AND** the count text MUST update to reflect the new connected/total ratio

#### Scenario: Dashboard receives channel_member_connected

- **WHEN** the dashboard SSE handler receives a `channel_member_connected` event for the open channel
- **THEN** the pending pill for that persona in `#channel-chat-member-pills` MUST transition to connected state

---

### Requirement: channel_ready SSE Event

The system SHALL broadcast a `channel_ready` SSE event when all non-chair memberships are linked and the channel transitions to `active`.

#### Scenario: All agents connected — channel_ready broadcast

- **WHEN** `check_channel_ready()` determines all non-chair memberships have agent_id set
- **THEN** a `channel_ready` SSE event MUST be broadcast with:
  - `channel_slug`: the channel's slug
  - `name`: the channel's name

#### Scenario: Voice app receives channel_ready

- **WHEN** the voice app SSE handler receives a `channel_ready` event for the current channel
- **THEN** the chat input MUST become enabled (unlocked)
- **AND** a go-signal system message MUST appear in the message feed

#### Scenario: Dashboard receives channel_ready

- **WHEN** the dashboard SSE handler receives a `channel_ready` event for the open channel
- **THEN** the chat input MUST become enabled
- **AND** a go-signal system message MUST appear in the channel feed

---

### Requirement: channel_member_added SSE Event

The system SHALL broadcast a `channel_member_added` SSE event when a new membership is created via the add-member flow (before the agent connects).

#### Scenario: Add member initiated

- **WHEN** `add_member()` creates a new ChannelMembership with `agent_id = null`
- **THEN** a `channel_member_added` SSE event MUST be broadcast with:
  - `channel_slug`: the channel's slug
  - `persona_name`: the persona's display name
  - `persona_slug`: the persona's slug
  - `agent_id`: null (agent not yet connected)

#### Scenario: Both surfaces receive channel_member_added

- **WHEN** either the voice app or dashboard SSE handler receives a `channel_member_added` event for the current channel
- **THEN** a new pending pill MUST appear in the member pills display for that persona
