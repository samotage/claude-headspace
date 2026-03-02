# Section 5: Migration & Integration Checklist

**Status:** Living document — populated as decisions resolve
**Workshop:** [Epic 9 — Inter-Agent Communication](../interagent-communication-workshop.md)
**Canonical data model:** [`../../erds/headspace-org-erd-full.md`](../../erds/headspace-org-erd-full.md)

**Purpose:** Consolidate all model changes, new tables, and integration points required by this epic. Populated as decisions are resolved.

---

### Database Changes

| Migration | Model | Change | Priority | Source |
|---|---|---|---|---|
| Create `persona_types` table | PersonaType | New lookup table: 4 rows (agent/person × internal/external). `type_key` and `subtype` both NOT NULL. Unique constraint on `(type_key, subtype)`. | High — blocks all other channel migrations | [1.1](section-1-channel-data-model.md#11-channel-model) |
| Add `persona_type_id` to `personas` | Persona | New FK to `persona_types`, NOT NULL. Backfill existing personas as agent/internal (type_key='agent', subtype='internal'). | High — blocks channel membership | [1.1](section-1-channel-data-model.md#11-channel-model) |
| Create `channels` table | Channel | New table: name, slug, channel_type enum, description, intent_override, organisation_id (FK nullable, SET NULL), project_id (FK nullable, SET NULL), created_by_persona_id (FK nullable, SET NULL), status (default 'pending'), created_at, completed_at (nullable), archived_at (nullable). Slug auto-generated via after_insert event. | High | [1.1](section-1-channel-data-model.md#11-channel-model), [2.1](section-2-channel-operations.md#21-channel-lifecycle) |
| Create `channel_memberships` table | ChannelMembership | New table: channel_id (FK), persona_id (FK), agent_id (FK nullable), position_assignment_id (FK nullable), is_chair, status, joined_at, left_at. Unique constraint on `(channel_id, persona_id)`. | High | [1.1](section-1-channel-data-model.md#11-channel-model) |
| Create `messages` table | Message | New table: channel_id (FK), persona_id (FK nullable, SET NULL), agent_id (FK nullable), content, message_type enum (message/system/delegation/escalation), metadata (JSONB nullable), attachment_path (String(1024) nullable), source_turn_id (FK nullable), source_command_id (FK nullable), sent_at. | High | [1.1](section-1-channel-data-model.md#11-channel-model)/[1.2](section-1-channel-data-model.md#12-message-model)/[1.3](section-1-channel-data-model.md#13-message-types) |
| Add `source_message_id` to `turns` | Turn | New FK to `messages`, NULLABLE, ondelete SET NULL. Enables tracing a Turn back to the channel message that caused it. NULL for Turns from normal terminal input. | High | [1.2](section-1-channel-data-model.md#12-message-model) |
| Create partial unique index on `channel_memberships` | ChannelMembership | `CREATE UNIQUE INDEX uq_active_agent_one_channel ON channel_memberships (agent_id) WHERE status = 'active' AND agent_id IS NOT NULL;` — one agent instance per active channel. | High | [1.4](section-1-channel-data-model.md#14-membership-model) |
| Create operator Persona | Persona (data) | Insert person/internal Persona for operator (Sam). Role: "operator" (create Role if needed). No Agent instances, no PositionAssignment. | Medium — needed for channel participation | [1.1](section-1-channel-data-model.md#11-channel-model) |
| ~~Update `channels.status` enum~~ | ~~Channel~~ | ~~Folded into Create `channels` table migration above. Status column with 4-state lifecycle (pending/active/complete/archived) and default 'pending' is part of initial table creation, not a separate update.~~ | ~~N/A~~ | ~~[2.1](section-2-channel-operations.md#21-channel-lifecycle)~~ |
| ~~Add `completed_at` to `channels`~~ | ~~Channel~~ | ~~Folded into Create `channels` table migration above. `completed_at` (nullable) is part of initial table creation.~~ | ~~N/A~~ | ~~[2.1](section-2-channel-operations.md#21-channel-lifecycle)~~ |

### New Services

| Service | Purpose | Dependencies |
|---|---|---|
| `ChannelService` | Core service layer for all channel operations (create, join, leave, complete, send message, etc.). CLI, API, voice bridge, and dashboard all delegate to this. Registered as `app.extensions["channel_service"]`. | DB models (Channel, ChannelMembership, Message), PersonaRegistration (capability checks), Broadcaster (SSE events) |
| `channels_api` blueprint | REST endpoints at `/api/channels`. Thin HTTP wrapper around ChannelService. | ChannelService, session token auth (existing), Flask session auth (existing) |
| `ChannelDeliveryService` | Fan-out delivery engine. Iterates channel members, dispatches per member type (tmux/SSE/deferred). In-memory delivery queue for agents not in safe state. Integrates with CommanderAvailability for pane health. | ChannelService, TmuxBridge (existing), Broadcaster (existing), CommanderAvailability (existing), CommandLifecycleManager (state transition hooks) |

### Integration Points

| Existing System | Integration | Notes | Source |
|---|---|---|---|
| Tmux Bridge | Message delivery to local agents | Reuse existing `send_text()` | Pending (Section 3) |
| Hook Receiver | Agent response capture for channel relay | New processing path | Pending (Section 3) |
| SSE Broadcaster | Two new event types: `channel_message`, `channel_update` | Broadcast on existing stream, type-filtered | [2.3](section-2-channel-operations.md#23-api-endpoints) |
| Remote Agent API | Channel access via existing session tokens | Token → agent → persona → membership. No new auth. | [2.3](section-2-channel-operations.md#23-api-endpoints) |
| Voice Bridge | Semantic picker extended for channel-name matching | Fuzzy match on name/slug, same algorithm as agent picker | [2.3](section-2-channel-operations.md#23-api-endpoints) |
| Dashboard | Channel cards above project sections, management tab | Uses same `/api/channels` endpoints as remote agents | [2.3](section-2-channel-operations.md#23-api-endpoints) |
