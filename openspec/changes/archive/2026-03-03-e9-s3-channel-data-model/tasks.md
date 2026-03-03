# Commands: e9-s3-channel-data-model

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Enum Definitions
- [x] 2.1.1 Create ChannelType enum (workshop, delegation, review, standup, broadcast)
- [x] 2.1.2 Create MessageType enum (message, system, delegation, escalation)

### 2.2 Model Files
- [x] 2.2.1 Create `models/channel.py` — Channel model with ChannelType enum, slug auto-generation via after_insert event, _slugify static method
- [x] 2.2.2 Create `models/channel_membership.py` — ChannelMembership model with unique constraint (channel_id, persona_id)
- [x] 2.2.3 Create `models/message.py` — Message model with MessageType enum, JSONB metadata, bidirectional Turn/Command FKs
- [x] 2.2.4 Modify `models/turn.py` — Add source_message_id FK column and source_message relationship

### 2.3 Relationships & Constraints
- [x] 2.3.1 Define Channel bidirectional relationships (memberships, messages, organisation, project, created_by_persona)
- [x] 2.3.2 Define ChannelMembership relationships (channel, persona, agent)
- [x] 2.3.3 Define Message relationships (channel, persona, agent, source_turn, source_command)
- [x] 2.3.4 Define Turn.source_message relationship
- [x] 2.3.5 Implement all FK ondelete behaviours per workshop specification (CASCADE/SET NULL per table)

### 2.4 Model Registration
- [x] 2.4.1 Register Channel, ChannelMembership, Message in `models/__init__.py` imports
- [x] 2.4.2 Register ChannelType, MessageType in `models/__init__.py` imports
- [x] 2.4.3 Update `__all__` list and docstring

### 2.5 Migration
- [x] 2.5.1 Create Alembic migration: channeltype and messagetype enums
- [x] 2.5.2 Create Alembic migration: channels table (all columns from PRD 6.1)
- [x] 2.5.3 Create Alembic migration: channel_memberships table with uq_channel_persona constraint
- [x] 2.5.4 Create Alembic migration: partial unique index uq_active_agent_one_channel (raw SQL)
- [x] 2.5.5 Create Alembic migration: messages table (all columns from PRD 6.3)
- [x] 2.5.6 Create Alembic migration: Add source_message_id FK to turns table
- [x] 2.5.7 Implement downgrade: reverse all changes in correct order

## 3. Testing (Phase 3)

### 3.1 Model Tests
- [x] 3.1.1 Test Channel creation with all required fields
- [x] 3.1.2 Test Channel slug auto-generation (format: {type}-{name}-{id})
- [x] 3.1.3 Test ChannelMembership creation with required fields
- [x] 3.1.4 Test ChannelMembership unique constraint on (channel_id, persona_id)
- [x] 3.1.5 Test Message creation with all required fields (immutable — no edit/delete columns)
- [x] 3.1.6 Test Turn.source_message_id FK addition

### 3.2 Enum Tests
- [x] 3.2.1 Test ChannelType has exactly 5 values
- [x] 3.2.2 Test MessageType has exactly 4 values

### 3.3 Relationship Tests
- [x] 3.3.1 Test Channel → ChannelMembership cascade delete
- [x] 3.3.2 Test Channel → Message cascade delete
- [x] 3.3.3 Test Persona deletion cascades ChannelMembership, SET NULL on Message.persona_id
- [x] 3.3.4 Test Agent deletion SET NULL on ChannelMembership.agent_id and Message.agent_id
- [x] 3.3.5 Test partial unique index: prevents duplicate active agent in multiple channels
- [x] 3.3.6 Test partial unique index: allows same agent_id when status != 'active' or agent_id IS NULL

### 3.4 Migration Tests
- [x] 3.4.1 Test flask db upgrade runs cleanly
- [x] 3.4.2 Test flask db downgrade drops all new objects

## 4. Final Verification

- [x] 4.1 All existing tests still pass (no regressions)
- [x] 4.2 All new models importable from claude_headspace.models
- [x] 4.3 All new enums importable from claude_headspace.models
- [x] 4.4 Migration is reversible
