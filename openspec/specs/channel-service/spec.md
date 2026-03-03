# channel-service Specification

## Purpose
TBD - created by archiving change e9-s4-channel-service-cli. Update Purpose after archive.
## Requirements
### Requirement: Service Registration
The `ChannelService` class SHALL be instantiated in the app factory and registered as `app.extensions["channel_service"]`. It receives a reference to the Flask app for accessing other services and database sessions.

#### Scenario: Service available
- **WHEN** the Flask app is created
- **THEN** `app.extensions["channel_service"]` is a `ChannelService` instance

---

### Requirement: Error Hierarchy
The service SHALL define a `ChannelError` base exception with subclasses: `ChannelNotFoundError`, `NotAMemberError`, `NotChairError`, `ChannelClosedError`, `AlreadyMemberError`, `NoCreationCapabilityError`, `AgentChannelConflictError`. Each carries a human-readable message suitable for direct display.

#### Scenario: Error inheritance
- **WHEN** any channel-specific exception is raised
- **THEN** it is an instance of `ChannelError`
- **AND** has a human-readable `str()` representation

---

### Requirement: Channel Creation (FR2)
`create_channel(creator_persona, name, channel_type, description=None, intent_override=None, organisation_id=None, project_id=None, member_slugs=None)` SHALL validate the creator persona has channel creation capability, create the Channel record with status `pending`, create a ChannelMembership for the creator with `is_chair=True`, add members from `member_slugs` if provided, and return the created Channel.

#### Scenario: Successful creation
- **WHEN** a persona with `can_create_channel=True` calls `create_channel` with name and channel_type
- **THEN** a Channel is created with status `pending`
- **AND** the creator has a ChannelMembership with `is_chair=True`
- **AND** the channel slug is auto-generated

#### Scenario: Creation with members
- **WHEN** `create_channel` is called with `member_slugs=["con", "paula"]`
- **THEN** those personas are added as members
- **AND** system messages are posted for each addition

#### Scenario: No creation capability
- **WHEN** a persona with `can_create_channel=False` calls `create_channel`
- **THEN** `NoCreationCapabilityError` is raised with an actionable message

---

### Requirement: Channel Listing (FR3)
`list_channels(persona, status=None, channel_type=None, all_visible=False)` SHALL return channels filtered by the calling persona's active memberships. With `all_visible=True`, return all non-archived channels.

#### Scenario: Member-scoped listing
- **WHEN** a persona calls `list_channels` without `all_visible`
- **THEN** only channels where the persona has an active membership are returned

#### Scenario: All-visible listing
- **WHEN** `list_channels` is called with `all_visible=True`
- **THEN** all non-archived channels are returned regardless of membership

---

### Requirement: Channel Details (FR4)
`get_channel(slug)` SHALL return the Channel with members and message count, or raise `ChannelNotFoundError`.

#### Scenario: Channel found
- **WHEN** `get_channel` is called with a valid slug
- **THEN** the Channel object is returned with loaded memberships

#### Scenario: Channel not found
- **WHEN** `get_channel` is called with an invalid slug
- **THEN** `ChannelNotFoundError` is raised

---

### Requirement: Channel Update (FR4a)
`update_channel(slug, persona, description=None, intent_override=None)` SHALL validate the caller is the chair or operator, update the specified fields, and return the updated Channel. Only `description` and `intent_override` are mutable.

#### Scenario: Chair updates channel
- **WHEN** the channel chair calls `update_channel` with a new description
- **THEN** the description is updated and the Channel is returned

#### Scenario: Non-chair update attempt
- **WHEN** a non-chair, non-operator persona calls `update_channel`
- **THEN** `NotChairError` is raised

---

### Requirement: Channel Completion (FR5)
`complete_channel(slug, persona)` SHALL validate the caller is the chair, transition status to `complete`, set `completed_at`, and post a system message.

#### Scenario: Chair completes channel
- **WHEN** the channel chair calls `complete_channel`
- **THEN** channel status becomes `complete` with `completed_at` set
- **AND** a system message is posted

#### Scenario: Non-chair completion attempt
- **WHEN** a non-chair persona calls `complete_channel`
- **THEN** `NotChairError` is raised

---

### Requirement: List Members (FR5b)
`list_members(slug)` SHALL return all ChannelMembership records for the channel, including persona name, agent_id, status, `is_chair`, and timestamps.

#### Scenario: List members
- **WHEN** `list_members` is called with a valid slug
- **THEN** all membership records are returned with persona details

---

### Requirement: Add Member (FR6)
`add_member(slug, persona_slug, caller_persona)` SHALL validate the caller is an active member, validate the target persona exists, validate the channel is not closed, enforce one-agent-one-channel, create the membership, post a system message, and generate a context briefing.

#### Scenario: Successful member add
- **WHEN** an active member adds a valid persona to an active channel
- **THEN** a ChannelMembership is created
- **AND** a system message is posted

#### Scenario: Target has no running agent
- **WHEN** `add_member` targets a persona with no running agent
- **THEN** async agent spin-up is initiated
- **AND** the membership is created with `agent_id=NULL`

#### Scenario: One-agent-one-channel conflict
- **WHEN** `add_member` targets a persona whose agent is already active in another channel
- **THEN** `AgentChannelConflictError` is raised with the conflicting channel name and a leave command

#### Scenario: Channel is closed
- **WHEN** `add_member` is called on a `complete` or `archived` channel
- **THEN** `ChannelClosedError` is raised

---

### Requirement: Leave Channel (FR7)
`leave_channel(slug, persona)` SHALL set membership status to `left`, set `left_at`, post a system message. If the last active member leaves, auto-transition to `complete`.

#### Scenario: Member leaves
- **WHEN** a member calls `leave_channel`
- **THEN** membership status is `left` with `left_at` set
- **AND** a system message is posted

#### Scenario: Last active member leaves
- **WHEN** the last active member leaves (muted excluded from count)
- **THEN** the channel auto-transitions to `complete`

---

### Requirement: Chair Transfer (FR8)
`transfer_chair(slug, target_persona_slug, caller_persona)` SHALL validate the caller is the current chair, validate the target is an active member, transfer `is_chair`, and post a system message.

#### Scenario: Successful transfer
- **WHEN** the chair transfers to an active member
- **THEN** `is_chair` moves from old to new chair
- **AND** a system message is posted

#### Scenario: Non-chair transfer attempt
- **WHEN** a non-chair persona calls `transfer_chair`
- **THEN** `NotChairError` is raised

---

### Requirement: Mute/Unmute (FR9)
`mute_channel(slug, persona)` SHALL set membership status to `muted`. `unmute_channel(slug, persona)` SHALL set it back to `active`. Both post system messages.

#### Scenario: Mute
- **WHEN** a member mutes the channel
- **THEN** membership status is `muted` and a system message is posted

#### Scenario: Unmute
- **WHEN** a muted member unmutes
- **THEN** membership status is `active` and a system message is posted

---

### Requirement: Send Message (FR10)
`send_message(slug, content, persona, agent=None, message_type='message', attachment_path=None, source_turn_id=None, source_command_id=None)` SHALL validate the sender is active, validate the channel is not closed, validate message_type is not `system`, write the Message record, transition `pending` to `active` on first non-system message, broadcast SSE event, and return the Message.

#### Scenario: Successful send
- **WHEN** an active member sends a message
- **THEN** a Message record is created and returned

#### Scenario: First message activates channel
- **WHEN** the first non-system message is sent to a `pending` channel
- **THEN** the channel transitions to `active`

#### Scenario: System type rejected
- **WHEN** `send_message` is called with `message_type='system'`
- **THEN** a ValueError is raised

#### Scenario: Channel closed
- **WHEN** `send_message` is called on a `complete` or `archived` channel
- **THEN** `ChannelClosedError` is raised

---

### Requirement: Message History (FR11)
`get_history(slug, persona, limit=50, since=None, before=None)` SHALL validate the caller is a member (active, left, or muted), return messages ordered by `sent_at` ascending with cursor pagination.

#### Scenario: History for active member
- **WHEN** an active member requests history
- **THEN** messages are returned in chronological order

#### Scenario: History for left member
- **WHEN** a member who has left requests history
- **THEN** messages are still returned (left members can read history)

#### Scenario: Pagination
- **WHEN** `since` or `before` ISO timestamps are provided
- **THEN** messages are filtered accordingly

---

### Requirement: System Messages (FR13)
System messages SHALL be generated exclusively by the service for joins, leaves, state changes, and chair transfers. System messages have `persona_id=NULL`, `agent_id=NULL`, `message_type='system'`.

#### Scenario: System message format
- **WHEN** a structural event occurs (join, leave, complete, transfer)
- **THEN** a system message is posted with the appropriate content and NULL persona/agent IDs

---

### Requirement: Archive Channel (FR15)
`archive_channel(slug, persona)` SHALL validate the caller is the chair or operator, validate the channel is in `complete` state, transition to `archived`, set `archived_at`, and post a system message.

#### Scenario: Successful archive
- **WHEN** the chair archives a `complete` channel
- **THEN** status becomes `archived` with `archived_at` set

#### Scenario: Archive non-complete channel
- **WHEN** `archive_channel` is called on a non-`complete` channel
- **THEN** `ChannelClosedError` is raised with an appropriate message

---

### Requirement: SSE Broadcasting
The service SHALL broadcast `channel_message` events after message persistence and `channel_update` events after state-changing operations (member join/leave, status transition, chair transfer, mute/unmute).

#### Scenario: Message broadcast
- **WHEN** a message is successfully persisted
- **THEN** a `channel_message` SSE event is broadcast

#### Scenario: State change broadcast
- **WHEN** a channel state change occurs
- **THEN** a `channel_update` SSE event is broadcast

---

### Requirement: Context Briefing Generation
The service SHALL generate context briefings (last 10 messages formatted as text) for newly added members, suitable for tmux injection.

#### Scenario: Briefing with messages
- **WHEN** a member is added to a channel with existing messages
- **THEN** a formatted text block with the last 10 messages is generated

#### Scenario: Briefing for empty channel
- **WHEN** a member is added to a channel with no messages
- **THEN** an empty string is returned (no briefing)

---

### Requirement: Agent Spin-Up on Member Add
When `add_member` targets a persona with no running agent, the service SHALL initiate async agent creation using the same `create_agent` function used by remote agents and handoff. The membership is created with `agent_id=NULL`; the agent is linked when it registers.

#### Scenario: No active agent
- **WHEN** `add_member` targets a persona with no running agent
- **THEN** `create_agent(persona_slug=...)` is called asynchronously
- **AND** the membership record has `agent_id=NULL`

---

### Requirement: One-Agent-One-Channel Enforcement
The service SHALL proactively check for agent-channel conflicts before creating memberships, providing actionable error messages. The database partial unique index `uq_active_agent_one_channel` is the backstop.

#### Scenario: Agent conflict detected
- **WHEN** an agent is already active in another channel
- **THEN** `AgentChannelConflictError` is raised with the conflicting channel slug and a leave command

---

### Requirement: Channel Status Transitions
The service SHALL manage all status transitions: `pending` -> `active` (first non-system message), `active` -> `complete` (chair or auto on last leave), `complete` -> `archived` (chair/operator). No reactivation. `ChannelClosedError` raised on operations against closed channels.

#### Scenario: Pending to active
- **WHEN** the first non-system message is sent
- **THEN** channel status transitions to `active`

#### Scenario: No reactivation
- **WHEN** any operation is attempted on a `complete` or `archived` channel
- **THEN** `ChannelClosedError` is raised

---

### Requirement: Database Safety
All state-modifying operations SHALL use explicit transactions. Advisory locks SHALL protect concurrent operations (chair transfer, last-member-leave auto-complete).

#### Scenario: Concurrent leave protection
- **WHEN** two members leave simultaneously and one is the last active member
- **THEN** advisory lock ensures exactly one auto-complete occurs

