# Proposal Summary: e9-s3-channel-data-model

## Architecture Decisions

- **Channel-based messaging model:** Three new tables (Channel, ChannelMembership, Message) implement the structural design from the Inter-Agent Communication Workshop (Section 1, Decisions 1.1-1.5)
- **Cross-project by default:** Channels exist at system level with optional Organisation and Project scoping via nullable FKs (SET NULL on delete)
- **Persona-based membership with mutable agent delivery:** ChannelMembership links stable persona identities to channels; the agent_id column is mutable to track which agent instance currently receives messages
- **One-agent-one-channel enforcement:** Partial unique index on ChannelMembership(agent_id) WHERE status='active' AND agent_id IS NOT NULL prevents an agent from being active in multiple channels simultaneously
- **Messages are immutable:** No edit/delete columns by design — agent conversations are operational records with no mutation semantics
- **Bidirectional Turn/Message traceability:** Message.source_turn_id links to the Turn that spawned the message; Turn.source_message_id links back for reverse lookup (v2 population)
- **PositionAssignment FK deferred:** The position_assignments table does not yet exist; ChannelMembership.position_assignment_id is a plain Integer column without FK constraint, to be added when the target table is implemented
- **Slug auto-generation:** Channel slugs follow the Persona pattern: `{channel_type}-{slugified_name}-{id}`, generated via after_insert event

## Implementation Approach

- Create 3 new model files following existing codebase patterns (mapped_column style, DateTime(timezone=True), TYPE_CHECKING imports, __repr__)
- Add one column + relationship to existing Turn model (additive, transparent to existing code)
- Register all new models/enums in models/__init__.py
- Single Alembic migration creating all tables, enums, constraints, and the Turn column modification
- No services, routes, CLI, or delivery mechanics — this is purely data model

## Files to Modify

### New Files
- `src/claude_headspace/models/channel.py` — Channel model, ChannelType enum, slug auto-generation (after_insert event), _slugify static method
- `src/claude_headspace/models/channel_membership.py` — ChannelMembership model with unique constraint and partial unique index
- `src/claude_headspace/models/message.py` — Message model, MessageType enum, JSONB metadata, bidirectional Turn/Command FKs
- `migrations/versions/xxxx_add_channel_tables.py` — Single Alembic migration for all schema changes

### Modified Files
- `src/claude_headspace/models/turn.py` — Add source_message_id FK column (nullable, SET NULL) and source_message relationship
- `src/claude_headspace/models/__init__.py` — Register Channel, ChannelMembership, Message, ChannelType, MessageType

## Acceptance Criteria

1. `flask db upgrade` runs cleanly, creating channels, channel_memberships, and messages tables
2. `channeltype` PostgreSQL enum exists with values: workshop, delegation, review, standup, broadcast
3. `messagetype` PostgreSQL enum exists with values: message, system, delegation, escalation
4. Channel slug auto-generates as `{channel_type}-{name}-{id}` after insert
5. ChannelMembership unique constraint on (channel_id, persona_id) prevents duplicates
6. Partial unique index prevents agent_id from being active in multiple channels
7. Partial unique index allows same agent_id when status != 'active' or agent_id IS NULL
8. Message records are write-once (no edit/delete lifecycle columns)
9. Turn.source_message_id FK references messages.id with SET NULL ondelete
10. Deleting a Channel cascades to ChannelMembership and Message records
11. Deleting a Persona cascades ChannelMembership; SET NULL on Message.persona_id
12. All new models and enums importable from `claude_headspace.models`
13. No existing tests break (additive changes only)
14. Migration is reversible (`flask db downgrade` drops all new objects)

## Constraints and Gotchas

- **PersonaType dependency (logical, not structural):** Sprint 2 (PersonaType system) must be complete before Sprint 3. Channel tables don't reference persona_types directly, but channel services in S4 need persona types for delivery mechanism decisions
- **PositionAssignment FK deferred:** `position_assignment_id` on ChannelMembership is a plain Integer without FK constraint. The position_assignments table does not yet exist. FK constraint will be added when PositionAssignment model is implemented
- **Circular import risk between Message and Turn:** Both models reference each other via FKs. Must use TYPE_CHECKING conditional imports and string-based relationship references (follow the Turn.answered_by_turn_id pattern already in the codebase)
- **Partial unique index requires raw SQL:** PostgreSQL natively supports partial unique indexes but Alembic cannot generate them automatically. Use `op.execute()` with raw SQL in migration
- **No back_populates on target models:** Channel relationships to Organisation, Project, Persona, Agent are intentionally one-directional. Do NOT add `channels` relationship lists to those existing models
- **PostgreSQL-only:** All migration SQL must be PostgreSQL-compatible. No SQLite fallbacks

## Git Change History

### Feature Branch
- Branch: `feature/e9-s3-channel-data-model` (from `development`)
- Commit `ee128b9`: chore(spec): e9-s3-channel-data-model pre-build snapshot

### Related Existing Models
- `src/claude_headspace/models/persona.py` — Slug auto-generation pattern to follow
- `src/claude_headspace/models/turn.py` — Model to extend with source_message_id
- `src/claude_headspace/models/agent.py` — FK ondelete pattern reference
- `src/claude_headspace/models/organisation.py` — FK target for Channel.organisation_id
- `src/claude_headspace/models/__init__.py` — Registration pattern

## Dependencies

### Required Models (all exist)
- Persona (E8-S5) — FK target for ChannelMembership.persona_id and Message.persona_id
- Organisation (E8-S7) — FK target for Channel.organisation_id
- Project (E1) — FK target for Channel.project_id
- Agent (E1) — FK target for ChannelMembership.agent_id and Message.agent_id
- Turn (E1) — Extended with source_message_id; FK target for Message.source_turn_id
- Command (E1) — FK target for Message.source_command_id
- PersonaType (E9-S2) — Logical prerequisite (channel services need persona type classification)

### Required Packages (all installed)
- Flask-SQLAlchemy, Flask-Migrate, psycopg2-binary

## Testing Strategy

### Model Tests
- Test creation of Channel, ChannelMembership, Message with all required fields
- Test Channel slug auto-generation format
- Test ChannelType (5 values) and MessageType (4 values) enum completeness
- Test Turn.source_message_id FK addition

### Constraint Tests
- Test ChannelMembership unique constraint on (channel_id, persona_id) raises IntegrityError
- Test partial unique index prevents duplicate active agent across channels
- Test partial unique index allows NULL agent_id and non-active status

### Relationship Tests
- Test Channel -> ChannelMembership cascade delete
- Test Channel -> Message cascade delete
- Test Persona deletion cascades ChannelMembership, SET NULL on Message.persona_id
- Test Agent deletion SET NULL on ChannelMembership.agent_id and Message.agent_id

### Migration Tests
- Test `flask db upgrade` creates all tables and enums
- Test `flask db downgrade` drops all new objects cleanly
- Verify no existing tests break

## OpenSpec References

- proposal.md: openspec/changes/e9-s3-channel-data-model/proposal.md
- tasks.md: openspec/changes/e9-s3-channel-data-model/tasks.md
- spec.md: openspec/changes/e9-s3-channel-data-model/specs/channel-data-model/spec.md
