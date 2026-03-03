# Specification: e9-s3-channel-data-model

## ADDED Requirements

### Requirement: ChannelType Enum

The system SHALL create a PostgreSQL enum `channeltype` with exactly 5 values: `workshop`, `delegation`, `review`, `standup`, `broadcast`.

#### Scenario: Enum Values
- **WHEN** ChannelType enum is queried for values
- **THEN** exactly 5 values are returned matching the specification

---

### Requirement: MessageType Enum

The system SHALL create a PostgreSQL enum `messagetype` with exactly 4 values: `message`, `system`, `delegation`, `escalation`.

#### Scenario: Enum Values
- **WHEN** MessageType enum is queried for values
- **THEN** exactly 4 values are returned matching the specification

---

### Requirement: Channel Model

The system SHALL persist Channels with id (PK), name (String 128, NOT NULL), slug (String 128, NOT NULL, UNIQUE, auto-generated), channel_type (ChannelType enum, NOT NULL), description (Text, nullable), intent_override (Text, nullable), organisation_id (FK to organisations.id, nullable, SET NULL), project_id (FK to projects.id, nullable, SET NULL), created_by_persona_id (FK to personas.id, nullable, SET NULL), status (String 16, NOT NULL, default "pending"), created_at (DateTime TZ, NOT NULL, default now), completed_at (DateTime TZ, nullable), archived_at (DateTime TZ, nullable).

#### Scenario: Create Channel
- **WHEN** a Channel is created with name and channel_type
- **THEN** the channel is persisted with auto-generated id, default status "pending", and default created_at

#### Scenario: Channel Slug Auto-Generation
- **WHEN** a Channel is inserted into the database
- **THEN** the slug is auto-generated as `{channel_type.value}-{slugified_name}-{id}` after insert

#### Scenario: Channel Status Values
- **WHEN** a Channel's status is set
- **THEN** it accepts values: pending, active, complete, archived

---

### Requirement: Channel Slug Auto-Generation

The Channel model SHALL auto-generate its slug using an `after_insert` event listener, following the same pattern as the Persona model. A temporary slug is assigned on initial insert via `_temp_slug()`, then replaced post-insert when the id is available.

#### Scenario: Slug Format
- **WHEN** a Channel with name "Persona Alignment" and channel_type WORKSHOP and id 42 generates its slug
- **THEN** the slug is "workshop-persona-alignment-42"

#### Scenario: Slug Sanitization
- **WHEN** a Channel name contains special characters or mixed case
- **THEN** the slug is lowercased, non-alphanumeric characters replaced with hyphens, consecutive hyphens collapsed, leading/trailing hyphens stripped

---

### Requirement: ChannelMembership Model

The system SHALL persist ChannelMemberships with id (PK), channel_id (FK to channels.id, NOT NULL, CASCADE), persona_id (FK to personas.id, NOT NULL, CASCADE), agent_id (FK to agents.id, nullable, SET NULL), position_assignment_id (Integer, nullable, no FK constraint), is_chair (Boolean, NOT NULL, default False), status (String 16, NOT NULL, default "active"), joined_at (DateTime TZ, NOT NULL, default now), left_at (DateTime TZ, nullable).

#### Scenario: Create Membership
- **WHEN** a ChannelMembership is created with channel_id and persona_id
- **THEN** the membership is persisted with default status "active" and default is_chair False

#### Scenario: Position Assignment Column
- **WHEN** a ChannelMembership is created with position_assignment_id
- **THEN** the value is stored as a plain Integer (no FK constraint — target table not yet created)

---

### Requirement: ChannelMembership Unique Constraint

The system SHALL enforce a unique constraint `uq_channel_persona` on (channel_id, persona_id). A persona can only be in a channel once.

#### Scenario: Duplicate Membership
- **WHEN** a second ChannelMembership is inserted with the same (channel_id, persona_id) pair
- **THEN** an IntegrityError is raised

---

### Requirement: Partial Unique Index for One-Agent-One-Channel

The system SHALL create a partial unique index `uq_active_agent_one_channel` on ChannelMembership(agent_id) WHERE status = 'active' AND agent_id IS NOT NULL. This prevents an agent instance from being active in more than one channel simultaneously.

#### Scenario: Agent Active in Two Channels
- **WHEN** agent_id 7 has an active membership in channel A
- **AND** a new active membership for agent_id 7 is inserted in channel B
- **THEN** an IntegrityError is raised

#### Scenario: Agent in Multiple Channels with Non-Active Status
- **WHEN** agent_id 7 has a membership with status 'left' in channel A
- **AND** a new active membership for agent_id 7 is inserted in channel B
- **THEN** the insert succeeds

#### Scenario: NULL Agent in Multiple Channels
- **WHEN** multiple memberships with agent_id NULL and status 'active' exist
- **THEN** no constraint violation occurs (NULL is not equal to NULL)

---

### Requirement: Message Model

The system SHALL persist Messages with id (PK), channel_id (FK to channels.id, NOT NULL, CASCADE), persona_id (FK to personas.id, nullable, SET NULL), agent_id (FK to agents.id, nullable, SET NULL), content (Text, NOT NULL), message_type (MessageType enum, NOT NULL), metadata (JSONB, nullable), attachment_path (String 1024, nullable), source_turn_id (FK to turns.id, nullable, SET NULL), source_command_id (FK to commands.id, nullable, SET NULL), sent_at (DateTime TZ, NOT NULL, default now).

#### Scenario: Create Message
- **WHEN** a Message is created with channel_id, content, and message_type
- **THEN** the message is persisted with default sent_at

#### Scenario: Message Immutability
- **WHEN** the Message model is inspected
- **THEN** it has no edited_at, deleted_at, or similar lifecycle mutation columns

---

### Requirement: Turn.source_message_id FK

The system SHALL add a nullable `source_message_id` column to the existing `turns` table, referencing `messages.id` with ondelete SET NULL.

#### Scenario: Turn with Source Message
- **WHEN** a Turn is created with source_message_id referencing a Message
- **THEN** the Turn is persisted with the FK relationship

#### Scenario: Message Deletion Preserves Turn
- **WHEN** a Message referenced by Turn.source_message_id is deleted
- **THEN** the Turn's source_message_id is set to NULL (not cascade deleted)

---

### Requirement: Bidirectional Relationships

All new models SHALL define bidirectional SQLAlchemy relationships:
- Channel.memberships <-> ChannelMembership.channel (back_populates, cascade all delete-orphan)
- Channel.messages <-> Message.channel (back_populates, cascade all delete-orphan, ordered by sent_at)
- Channel.organisation, Channel.project, Channel.created_by_persona (one-directional, no back_populates on target)
- ChannelMembership.persona, ChannelMembership.agent (one-directional)
- Message.persona, Message.agent, Message.source_turn, Message.source_command (one-directional)
- Turn.source_message (one-directional, foreign_keys specified)

#### Scenario: Channel Cascade Delete
- **WHEN** a Channel is deleted
- **THEN** all associated ChannelMembership and Message records are cascade deleted

#### Scenario: Message Ordering
- **WHEN** Channel.messages is accessed
- **THEN** messages are ordered by sent_at ascending

---

### Requirement: Model Registration

All new models (Channel, ChannelMembership, Message) and enums (ChannelType, MessageType) SHALL be registered in `models/__init__.py` following the existing pattern: import statements, docstring additions, and `__all__` list entries.

#### Scenario: Import from Package
- **WHEN** `from claude_headspace.models import Channel, ChannelType, ChannelMembership, Message, MessageType` is executed
- **THEN** all imports succeed

---

### Requirement: FK ondelete Behaviours

All FK ondelete behaviours SHALL match the workshop specification exactly:
- channels.organisation_id: SET NULL
- channels.project_id: SET NULL
- channels.created_by_persona_id: SET NULL
- channel_memberships.channel_id: CASCADE
- channel_memberships.persona_id: CASCADE
- channel_memberships.agent_id: SET NULL
- messages.channel_id: CASCADE
- messages.persona_id: SET NULL
- messages.agent_id: SET NULL
- messages.source_turn_id: SET NULL
- messages.source_command_id: SET NULL
- turns.source_message_id: SET NULL

#### Scenario: Organisation Deletion
- **WHEN** an Organisation referenced by a Channel is deleted
- **THEN** Channel.organisation_id is SET NULL

#### Scenario: Channel Deletion Cascades
- **WHEN** a Channel is deleted
- **THEN** all ChannelMembership and Message records for that channel are deleted

#### Scenario: Persona Deletion
- **WHEN** a Persona is deleted
- **THEN** their ChannelMembership records are cascade deleted
- **AND** Message.persona_id for their messages is SET NULL

---

### Requirement: Alembic Migration

The system SHALL create a single Alembic migration file that:
1. Creates channeltype PostgreSQL enum
2. Creates messagetype PostgreSQL enum
3. Creates channels table with all columns
4. Creates channel_memberships table with uq_channel_persona unique constraint
5. Creates partial unique index uq_active_agent_one_channel via raw SQL
6. Creates messages table with all columns
7. Adds source_message_id column to turns table

The migration SHALL be reversible, with downgrade dropping all objects in reverse order.

#### Scenario: Clean Upgrade
- **WHEN** `flask db upgrade` is run
- **THEN** all three tables, both enums, and the Turn column are created without errors

#### Scenario: Clean Downgrade
- **WHEN** `flask db downgrade` is run after upgrade
- **THEN** all new objects are dropped cleanly (Turn column, tables, indexes, enums)

---

### Requirement: Turn Model Extension

The Turn model SHALL have a nullable `source_message_id` column (Integer FK to messages.id, SET NULL ondelete) for channel message traceability. This column is additive and transparent to existing Turn code.

#### Scenario: Turn Source Message Column
- **WHEN** the Turn model is inspected
- **THEN** it contains a nullable `source_message_id` column referencing messages.id

#### Scenario: Source Message Deletion
- **WHEN** a Message referenced by Turn.source_message_id is deleted
- **THEN** the Turn's source_message_id is SET NULL

---

### Requirement: Channel Models Package Registration

Channel, ChannelMembership, Message models and ChannelType, MessageType enums SHALL be importable from the `claude_headspace.models` package.

#### Scenario: New Models Importable
- **WHEN** `from claude_headspace.models import Channel, ChannelMembership, Message` is executed
- **THEN** all three model classes are available

#### Scenario: New Enums Importable
- **WHEN** `from claude_headspace.models import ChannelType, MessageType` is executed
- **THEN** both enum classes are available
