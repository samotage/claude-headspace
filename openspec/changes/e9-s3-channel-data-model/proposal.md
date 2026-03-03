# Proposal: e9-s3-channel-data-model

## Why

The inter-agent communication system (Epic 9) requires a data foundation before any services, routes, or UI can be built. Currently, agents in Claude Headspace cannot communicate with each other — there is no data model for conversations between personas. This sprint creates the foundational tables: Channel (named conversation container), ChannelMembership (persona-to-channel links with mutable agent delivery), and Message (immutable communication records with bidirectional Turn/Command traceability).

All design decisions are resolved from the Inter-Agent Communication Workshop (Section 1, Decisions 1.1–1.5). This is a pure data model sprint — no services, routes, CLI, or delivery mechanics.

## What Changes

- Add `ChannelType` PostgreSQL enum: `workshop`, `delegation`, `review`, `standup`, `broadcast`
- Add `MessageType` PostgreSQL enum: `message`, `system`, `delegation`, `escalation`
- Add `Channel` model (12 columns): name, slug (auto-generated `{type}-{name}-{id}`), channel_type, description, intent_override, organisation_id FK, project_id FK, created_by_persona_id FK, status (pending/active/complete/archived), timestamps
- Add `ChannelMembership` model (9 columns): channel_id FK, persona_id FK, agent_id FK, position_assignment_id (plain Integer — target table not yet created), is_chair, status, timestamps
- Add `Message` model (11 columns): channel_id FK, persona_id FK, agent_id FK, content, message_type, metadata (JSONB), attachment_path, source_turn_id FK, source_command_id FK, sent_at
- Add unique constraint `uq_channel_persona` on ChannelMembership (channel_id, persona_id)
- Add partial unique index `uq_active_agent_one_channel` on ChannelMembership (agent_id) WHERE status='active' AND agent_id IS NOT NULL
- Add nullable `source_message_id` FK column to existing Turn model (SET NULL ondelete)
- Register all new models and enums in `models/__init__.py`
- Create single Alembic migration for all changes

## Impact

### Affected Specs
- Database schema (new tables: channels, channel_memberships, messages; modified: turns)
- SQLAlchemy model layer (3 new model files, 1 modified)

### Affected Code
- `src/claude_headspace/models/channel.py` (new — Channel model, ChannelType enum, slug auto-generation)
- `src/claude_headspace/models/channel_membership.py` (new — ChannelMembership model)
- `src/claude_headspace/models/message.py` (new — Message model, MessageType enum)
- `src/claude_headspace/models/turn.py` (modified — add source_message_id column and source_message relationship)
- `src/claude_headspace/models/__init__.py` (modified — register new models and enums)
- `migrations/versions/` (new migration file)

### Dependencies
- Epic 8 (Persona, Role, Organisation, Position models) — all complete
- Epic 9 Sprint 2 (PersonaType system) — must be complete (logical dependency for channel services in S4)

### Blocking
This change blocks:
- Sprint 4 (ChannelService + CLI) — needs all three table models
- Sprint 5 (API + SSE) — needs models for endpoints
- Sprint 6 (Delivery Engine) — needs Message and ChannelMembership models
- Sprint 7 (Dashboard UI) — needs models for display
- Sprint 8 (Voice Bridge integration) — needs channel models
