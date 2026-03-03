---
validation:
  status: valid
  validated_at: '2026-03-03T14:23:04+11:00'
---

## Product Requirements Document (PRD) — Channel Data Model

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 3 — Channel, ChannelMembership, Message tables, enums, and Turn extension
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The inter-agent communication system needs a data foundation before any services, routes, or UI can be built. This sprint creates that foundation: three new database tables (Channel, ChannelMembership, Message), two new enums (ChannelType, MessageType), and one modification to the existing Turn model (source_message_id FK).

These tables implement the structural design resolved in the Inter-Agent Communication Workshop (Section 1, Decisions 1.1–1.5). Channel is a named conversation container at the system level, cross-project by default. ChannelMembership links personas to channels with mutable agent delivery targets and optional organisational capacity context. Message is the immutable, atomic unit of channel communication with bidirectional traceability to the existing Turn and Command models.

This is a pure data model sprint. No services, no routes, no CLI, no delivery mechanics. The building agent creates model files, registers them, writes Alembic migrations, and stops. Sprints 4–8 build behaviour on top of this foundation.

All design decisions are resolved in the Inter-Agent Communication Workshop, Section 1 (5 decisions: 1.1–1.5). See `docs/workshop/interagent-communication/sections/section-1-channel-data-model.md`.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace currently tracks agents, commands, and turns within individual projects. Agents cannot communicate with each other. There is no data model for conversations between personas, no way to record messages exchanged in a workshop or delegation, and no structure for tracking who participates in which conversation.

The Organisation Workshop (Epic 8) established personas, roles, positions, and organisational hierarchy. The next layer — inter-agent communication — requires a channel-based messaging model that sits above projects and connects personas across the system.

The workshop resolved the full table design: columns, types, constraints, FK ondelete behaviours, enums, and indexes. This sprint translates those resolved decisions into SQLAlchemy models and Alembic migrations. There are no open design questions.

### 1.2 Target User

The building agent implementing Sprint 4 (ChannelService + CLI), Sprint 5 (API + SSE), and Sprint 6 (Delivery Engine). These sprints depend on the exact table structure, relationship definitions, and constraint semantics defined here.

### 1.3 Success Moment

The building agent for Sprint 4 imports `Channel`, `ChannelMembership`, `Message`, `ChannelType`, and `MessageType` from the models package, writes a `ChannelService` that creates channels, adds members, and posts messages, and every operation works against the database without a single schema surprise. The data model is exactly what the workshop specified — no gaps, no ambiguities, no "we'll figure it out later" columns.

---

## 2. Scope

### 2.1 In Scope

- ChannelType enum: `workshop`, `delegation`, `review`, `standup`, `broadcast`
- MessageType enum: `message`, `system`, `delegation`, `escalation`
- Channel model with all columns from workshop Decision 1.1
- ChannelMembership model with all columns from workshop Decision 1.1/1.4
- Message model with all columns from workshop Decisions 1.1/1.2/1.3
- Slug auto-generation for Channel via after_insert event (same pattern as Persona)
- Unique constraint on ChannelMembership (channel_id, persona_id)
- Partial unique index `uq_active_agent_one_channel` on ChannelMembership
- Turn.source_message_id FK addition to existing Turn model
- Bidirectional relationships on all new models
- Alembic migration(s) creating all three tables, the partial unique index, and the Turn FK
- Model registration in `models/__init__.py`

### 2.2 Out of Scope

- PersonaType table or Persona.persona_type_id (Sprint 2 — separate prerequisite)
- PositionAssignment table (not yet implemented; ChannelMembership.position_assignment_id FK is defined but the target table does not yet exist — see Technical Context 6.8)
- ChannelService, any service layer (Sprint 4)
- CLI commands for channel management (Sprint 4)
- API endpoints, SSE event types (Sprint 5)
- Delivery engine, fan-out, queuing (Sprint 6)
- Dashboard UI for channels (Sprint 7)
- Voice bridge channel integration (Sprint 8)
- Message edit or delete functionality (by design — messages are immutable)
- Channel lifecycle state machine logic (Sprint 4 — the `status` column is created here; transition rules are service-layer)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. `flask db upgrade` runs cleanly, creating the `channels`, `channel_memberships`, and `messages` tables
2. The `channeltype` PostgreSQL enum exists with values: `workshop`, `delegation`, `review`, `standup`, `broadcast`
3. The `messagetype` PostgreSQL enum exists with values: `message`, `system`, `delegation`, `escalation`
4. A Channel record can be created with all required fields; slug is auto-generated as `{channel_type}-{name}-{id}` after insert
5. A ChannelMembership record can be created linking a channel to a persona, with optional agent_id and position_assignment_id
6. Attempting to insert a duplicate (channel_id, persona_id) pair raises an IntegrityError
7. The partial unique index `uq_active_agent_one_channel` prevents two active memberships for the same agent_id
8. The partial unique index allows the same agent_id in multiple memberships where status != 'active' or agent_id IS NULL
9. A Message record can be created with all required fields (channel_id, content, message_type, sent_at)
10. The Turn model has a new nullable `source_message_id` FK column that references the messages table
11. Deleting a Channel cascades to delete all its ChannelMembership and Message records
12. Deleting a Persona cascades to delete their ChannelMembership records; Message.persona_id is set to NULL
13. All new models are importable from `claude_headspace.models`
14. All new enums are importable from `claude_headspace.models`

### 3.2 Non-Functional Success Criteria

1. No existing tests break — the migration is additive (new tables, one new nullable column on Turn)
2. The migration is reversible (`flask db downgrade` drops the tables and Turn column cleanly)
3. Model files follow existing codebase patterns (mapped_column style, TYPE_CHECKING imports, relationship definitions)
4. All FK ondelete behaviours match the workshop specification exactly

---

## 4. Functional Requirements (FRs)

### Channel Model

**FR1: Channel table**
The system shall create a `channels` table with the columns specified in Technical Context 6.1.

**FR2: ChannelType enum**
The system shall create a PostgreSQL enum `channeltype` with values: `workshop`, `delegation`, `review`, `standup`, `broadcast`.

**FR3: Channel slug auto-generation**
On insert, the Channel model shall auto-generate its slug as `{channel_type.value}-{slugified_name}-{id}` using the same after_insert event mechanism as Persona. A temporary slug is assigned on initial insert, then replaced post-insert when the id is available.

### ChannelMembership Model

**FR4: ChannelMembership table**
The system shall create a `channel_memberships` table with the columns specified in Technical Context 6.2.

**FR5: Unique constraint on (channel_id, persona_id)**
The system shall enforce a unique constraint on the combination of `channel_id` and `persona_id` — a persona can only be in a channel once.

**FR6: Partial unique index for one-agent-one-channel**
The system shall create a partial unique index `uq_active_agent_one_channel` on the `agent_id` column, filtered to rows where `status = 'active' AND agent_id IS NOT NULL`. This prevents an agent instance from being active in more than one channel simultaneously.

### Message Model

**FR7: Message table**
The system shall create a `messages` table with the columns specified in Technical Context 6.3.

**FR8: MessageType enum**
The system shall create a PostgreSQL enum `messagetype` with values: `message`, `system`, `delegation`, `escalation`.

**FR9: Messages are immutable**
The Message model shall have no `edited_at`, `deleted_at`, or similar lifecycle columns. Messages are write-once records. Immutability is structural (no columns for mutation), not enforced by database triggers.

### Turn Model Extension

**FR10: Turn.source_message_id FK**
The system shall add a nullable `source_message_id` column to the existing `turns` table, referencing `messages.id` with `ondelete SET NULL`. **Note:** This column is created in this sprint but its population mechanism (setting `source_message_id` when a Turn is created as a result of a channel message delivery) is a v2 concern. V1 delivery (S6) uses `Message.source_turn_id` for Turn→Message traceability; the reverse Message→Turn link via `Turn.source_message_id` will be populated when the delivery engine can correlate an agent's input Turn with the channel Message that triggered it.

### Relationships

**FR11: Bidirectional relationships**
All new models shall define bidirectional SQLAlchemy relationships as specified in Technical Context 6.5.

### Registration

**FR12: Model registration**
All new models (Channel, ChannelMembership, Message) and enums (ChannelType, MessageType) shall be registered in `models/__init__.py` following the existing pattern.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Additive migration**
The migration creates new tables and adds one nullable column to an existing table. No existing data is modified. No backfill required.

**NFR2: Existing tests unaffected**
No existing model, relationship, or query is modified in a way that could break existing tests. The only change to an existing model (Turn) is adding a nullable column with no default — transparent to existing code.

**NFR3: Consistent patterns**
Model files shall follow the same structure as existing models: `mapped_column` style, `DateTime(timezone=True)` for timestamps, `TYPE_CHECKING` block for relationship type hints, `__repr__` method, doc comment on the class.

**NFR4: PostgreSQL-only**
All SQL in migrations (including the partial unique index) shall be PostgreSQL-compatible. No SQLite compatibility layer.

---

## 6. Technical Context

### 6.1 Channel Table — Full Column Specification

| Column | SQLAlchemy Type | Constraints | Default | ondelete | Purpose |
|--------|----------------|-------------|---------|----------|---------|
| `id` | `Integer` | PK | auto | — | Standard integer PK |
| `name` | `String(128)` | NOT NULL | — | — | Human-readable name |
| `slug` | `String(128)` | NOT NULL, UNIQUE | `_temp_slug()` | — | Auto-generated: `{channel_type}-{name}-{id}` |
| `channel_type` | `Enum(ChannelType)` | NOT NULL | — | — | One of 5 types |
| `description` | `Text` | NULLABLE | — | — | What this channel is for |
| `intent_override` | `Text` | NULLABLE | — | — | Custom intent, overrides type default |
| `organisation_id` | `Integer FK → organisations.id` | NULLABLE | — | SET NULL | Optional org scope |
| `project_id` | `Integer FK → projects.id` | NULLABLE | — | SET NULL | Optional project scope |
| `created_by_persona_id` | `Integer FK → personas.id` | NULLABLE | — | SET NULL | Who created the channel |
| `status` | `String(16)` | NOT NULL | `"pending"` | — | Lifecycle: pending, active, complete, archived |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | `datetime.now(utc)` | — | Creation timestamp |
| `completed_at` | `DateTime(timezone=True)` | NULLABLE | — | — | When channel entered complete state |
| `archived_at` | `DateTime(timezone=True)` | NULLABLE | — | — | When channel was archived |

**ChannelType enum definition:**

```python
class ChannelType(enum.Enum):
    WORKSHOP = "workshop"
    DELEGATION = "delegation"
    REVIEW = "review"
    STANDUP = "standup"
    BROADCAST = "broadcast"
```

**Slug auto-generation** uses the same pattern as `Persona` (see `src/claude_headspace/models/persona.py`):

```python
def _temp_slug() -> str:
    return f"_pending_{uuid4().hex[:12]}"

# after_insert event:
def generate_slug(self) -> str:
    type_part = self.channel_type.value  # e.g. "workshop"
    name_part = self._slugify(self.name)  # e.g. "persona-alignment"
    return f"{type_part}-{name_part}-{self.id}"
```

The `_slugify()` static method should match Persona's implementation: lowercase, replace non-alphanumeric with hyphens, collapse consecutive hyphens, strip leading/trailing hyphens.

### 6.2 ChannelMembership Table — Full Column Specification

| Column | SQLAlchemy Type | Constraints | Default | ondelete | Purpose |
|--------|----------------|-------------|---------|----------|---------|
| `id` | `Integer` | PK | auto | — | Standard integer PK |
| `channel_id` | `Integer FK → channels.id` | NOT NULL | — | CASCADE | Which channel |
| `persona_id` | `Integer FK → personas.id` | NOT NULL | — | CASCADE | Who (stable identity) |
| `agent_id` | `Integer FK → agents.id` | NULLABLE | — | SET NULL | Current delivery target (mutable) |
| `position_assignment_id` | `Integer FK → position_assignments.id` | NULLABLE | — | SET NULL | Organisational capacity |
| `is_chair` | `Boolean` | NOT NULL | `False` | — | Channel authority |
| `status` | `String(16)` | NOT NULL | `"active"` | — | active, left, muted |
| `joined_at` | `DateTime(timezone=True)` | NOT NULL | `datetime.now(utc)` | — | When persona joined |
| `left_at` | `DateTime(timezone=True)` | NULLABLE | — | — | When persona left |

**Table-level constraints:**

```python
__table_args__ = (
    db.UniqueConstraint("channel_id", "persona_id", name="uq_channel_persona"),
)
```

**Partial unique index** (created in migration, not in model `__table_args__`):

```sql
CREATE UNIQUE INDEX uq_active_agent_one_channel
ON channel_memberships (agent_id)
WHERE status = 'active' AND agent_id IS NOT NULL;
```

This index ensures an agent instance can only be an active member of one channel at a time. It does NOT constrain person-type personas (who have no agent_id) or inactive memberships (status = 'left' or 'muted').

**position_assignment_id FK note:** The `position_assignments` table does not yet exist in the codebase (see Section 6.8). The FK is defined in the model but the migration must handle this — see Section 6.8 for the approach.

### 6.3 Message Table — Full Column Specification

| Column | SQLAlchemy Type | Constraints | Default | ondelete | Purpose |
|--------|----------------|-------------|---------|----------|---------|
| `id` | `Integer` | PK | auto | — | Standard integer PK |
| `channel_id` | `Integer FK → channels.id` | NOT NULL | — | CASCADE | Which channel |
| `persona_id` | `Integer FK → personas.id` | NULLABLE | — | SET NULL | Sender identity (stable). NULL = system message or persona deleted. |
| `agent_id` | `Integer FK → agents.id` | NULLABLE | — | SET NULL | Sender agent instance. NULL for person-type or system messages. |
| `content` | `Text` | NOT NULL | — | — | Message content (markdown) |
| `message_type` | `Enum(MessageType)` | NOT NULL | — | — | Structural type |
| `metadata` | `JSONB` | NULLABLE | — | — | Extensible structured data |
| `attachment_path` | `String(1024)` | NULLABLE | — | — | Single file path in /uploads |
| `source_turn_id` | `Integer FK → turns.id` | NULLABLE | — | SET NULL | Turn that spawned this message |
| `source_command_id` | `Integer FK → commands.id` | NULLABLE | — | SET NULL | Sender's active Command |
| `sent_at` | `DateTime(timezone=True)` | NOT NULL | `datetime.now(utc)` | — | When the message was sent |

**MessageType enum definition:**

```python
class MessageType(enum.Enum):
    MESSAGE = "message"
    SYSTEM = "system"
    DELEGATION = "delegation"
    ESCALATION = "escalation"
```

**Immutability:** No `edited_at`, `deleted_at`, `parent_message_id`, or per-recipient delivery tracking columns. Messages are write-once. This is a deliberate design choice — agent conversations are operational records.

### 6.4 Turn Model Extension

Add one column to the existing Turn model (`src/claude_headspace/models/turn.py`):

```python
# Channel message traceability
source_message_id: Mapped[int | None] = mapped_column(
    ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
)
```

Add a relationship:

```python
source_message: Mapped["Message | None"] = relationship(
    "Message", foreign_keys=[source_message_id]
)
```

The `TYPE_CHECKING` block in `turn.py` needs a conditional import for `Message`.

### 6.5 Bidirectional Relationships

All relationships must be bidirectional. Here is the complete relationship map:

**Channel model:**
```python
# Scoping FKs
organisation: Mapped["Organisation | None"] = relationship("Organisation")
project: Mapped["Project | None"] = relationship("Project")
created_by_persona: Mapped["Persona | None"] = relationship("Persona")

# Children
memberships: Mapped[list["ChannelMembership"]] = relationship(
    "ChannelMembership", back_populates="channel",
    cascade="all, delete-orphan"
)
messages: Mapped[list["Message"]] = relationship(
    "Message", back_populates="channel",
    cascade="all, delete-orphan",
    order_by="Message.sent_at"
)
```

**ChannelMembership model:**
```python
channel: Mapped["Channel"] = relationship("Channel", back_populates="memberships")
persona: Mapped["Persona"] = relationship("Persona")
agent: Mapped["Agent | None"] = relationship("Agent")
```

**Message model:**
```python
channel: Mapped["Channel"] = relationship("Channel", back_populates="messages")
persona: Mapped["Persona | None"] = relationship("Persona")
agent: Mapped["Agent | None"] = relationship("Agent")
source_turn: Mapped["Turn | None"] = relationship(
    "Turn", foreign_keys="[Message.source_turn_id]"
)
source_command: Mapped["Command | None"] = relationship("Command")
```

**Turn model (addition):**
```python
source_message: Mapped["Message | None"] = relationship(
    "Message", foreign_keys=[source_message_id]
)
```

**Note on back_populates:** The Channel → Organisation, Channel → Project, and Channel → Persona relationships are intentionally one-directional (no back_populates on the target models). Adding `channels` relationship lists to Organisation, Project, and Persona would require modifying those models. This can be added in a future sprint if navigation from those models to channels is needed. The building agent should NOT add back_populates or relationship definitions to Organisation, Project, Persona, Agent, Turn, or Command models beyond the Turn.source_message addition specified in 6.4.

### 6.6 New Files

| File | Purpose |
|------|---------|
| `src/claude_headspace/models/channel.py` | Channel model, ChannelType enum, slug auto-generation (after_insert event) |
| `src/claude_headspace/models/channel_membership.py` | ChannelMembership model |
| `src/claude_headspace/models/message.py` | Message model, MessageType enum |
| `migrations/versions/xxxx_add_channel_tables.py` | Alembic migration: create 3 tables, partial unique index, Turn.source_message_id FK |

### 6.7 Model Registration in `__init__.py`

Add to `src/claude_headspace/models/__init__.py`:

**Imports:**
```python
from .channel import Channel, ChannelType
from .channel_membership import ChannelMembership
from .message import Message, MessageType
```

**Docstring updates:** Add Channel, ChannelMembership, Message to the Models section. Add ChannelType, MessageType to the Enums section.

**`__all__` additions:**
```python
# In the Models section:
"Channel",
"ChannelMembership",
"Message",
# In the Enums section:
"ChannelType",
"MessageType",
```

### 6.8 PositionAssignment FK — Handling a Missing Target Table

The workshop design specifies `ChannelMembership.position_assignment_id` as a FK to `position_assignments`. The `PositionAssignment` model does not yet exist in the codebase — it is in the ERD but has not been implemented.

**Approach:** Define the column in the model WITHOUT a ForeignKey constraint for now. Use a plain nullable Integer column:

```python
position_assignment_id: Mapped[int | None] = mapped_column(
    Integer, nullable=True
)
```

Do NOT add a ForeignKey reference to a non-existent table. The FK constraint will be added in a future migration when `PositionAssignment` is implemented. Add a code comment explaining this:

```python
# FK to position_assignments deferred — table does not yet exist.
# Will be added as a FK constraint when PositionAssignment model is implemented.
position_assignment_id: Mapped[int | None] = mapped_column(
    Integer, nullable=True
)
```

No relationship definition for `position_assignment` on ChannelMembership until the target model exists.

### 6.9 Migration Details

**Single migration file** creating all three tables plus the Turn column addition:

1. **Create `channeltype` enum** — `sa.Enum('workshop', 'delegation', 'review', 'standup', 'broadcast', name='channeltype')`
2. **Create `messagetype` enum** — `sa.Enum('message', 'system', 'delegation', 'escalation', name='messagetype')`
3. **Create `channels` table** — all columns from 6.1
4. **Create `channel_memberships` table** — all columns from 6.2, including the unique constraint `uq_channel_persona`
5. **Create partial unique index** — `op.execute()` with raw SQL:
   ```python
   op.execute(
       "CREATE UNIQUE INDEX uq_active_agent_one_channel "
       "ON channel_memberships (agent_id) "
       "WHERE status = 'active' AND agent_id IS NOT NULL"
   )
   ```
6. **Create `messages` table** — all columns from 6.3
7. **Add `source_message_id` to `turns`** — `op.add_column('turns', sa.Column('source_message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True))`

**Downgrade:**
1. Drop `source_message_id` from `turns`
2. Drop `messages` table
3. Drop index `uq_active_agent_one_channel`
4. Drop `channel_memberships` table
5. Drop `channels` table
6. Drop `messagetype` enum
7. Drop `channeltype` enum

**Important:** The `position_assignment_id` column on `channel_memberships` is a plain Integer in the migration — no ForeignKey constraint. See 6.8.

### 6.10 FK ondelete Behaviour Reference

All ondelete behaviours are workshop-resolved. The building agent must implement these exactly:

| Table | Column | ondelete | Rationale |
|-------|--------|----------|-----------|
| `channels` | `organisation_id` | SET NULL | Org deletion does not destroy channels |
| `channels` | `project_id` | SET NULL | Project deletion does not destroy channels |
| `channels` | `created_by_persona_id` | SET NULL | Creator persona deletion does not destroy channels |
| `channel_memberships` | `channel_id` | CASCADE | Channel deletion removes all memberships |
| `channel_memberships` | `persona_id` | CASCADE | Persona deletion removes their memberships |
| `channel_memberships` | `agent_id` | SET NULL | Agent end sets delivery target to NULL (persona "offline") |
| `messages` | `channel_id` | CASCADE | Channel deletion removes all messages |
| `messages` | `persona_id` | SET NULL | Persona deletion preserves message audit trail |
| `messages` | `agent_id` | SET NULL | Agent end preserves message history |
| `messages` | `source_turn_id` | SET NULL | Turn deletion preserves message |
| `messages` | `source_command_id` | SET NULL | Command deletion preserves message |
| `turns` | `source_message_id` | SET NULL | Message deletion preserves Turn |

### 6.11 Design Decisions (All Resolved — Workshop Section 1)

| Decision | Resolution | Source |
|----------|-----------|--------|
| Channel table design | 12-column table: name, slug (auto), channel_type (5-enum), description, intent_override, organisation_id, project_id, created_by_persona_id, status (4-state), created_at, completed_at, archived_at | 1.1 |
| ChannelMembership design | Persona-based with mutable agent delivery target. Position assignment for org capacity. Chair boolean. Unique (channel_id, persona_id). | 1.1, 1.4 |
| Message table design | 10-column immutable record. Bidirectional Turn/Command links. JSONB metadata. Single attachment. | 1.2 |
| Message types | 4-type structural enum: message, system, delegation, escalation. Content intent is service-layer concern. | 1.3 |
| One agent, one channel | Partial unique index on agent_id WHERE active. Person-type personas exempt. Multiple agents for same persona is fine. | 1.4 |
| Turn.source_message_id | Nullable FK, SET NULL. Enables tracing channel-delivered Turns. | 1.2 |
| No new Event types | Messages are their own audit trail. No MESSAGE_SENT events. | 1.5 |
| Channel scoping | Cross-project by default. Nullable FKs to Organisation and Project. | 1.1, 1.5 |
| Messages immutable | No edits, no deletes. Operational records. | 1.2 |
| Slug pattern | `{channel_type}-{name}-{id}` — consistent with Persona and Organisation patterns | 1.1 |

### 6.12 Existing Code Patterns to Follow

The building agent should study these files for implementation patterns:

| File | Pattern to Reuse |
|------|-----------------|
| `src/claude_headspace/models/persona.py` | Slug auto-generation via `_temp_slug()` + `after_insert` event. `_slugify()` static method. |
| `src/claude_headspace/models/role.py` | Simple model structure: mapped_column, DateTime(timezone=True), TYPE_CHECKING imports |
| `src/claude_headspace/models/agent.py` | FK definitions with ondelete, nullable FK patterns, self-referential relationships, multiple relationship definitions |
| `src/claude_headspace/models/turn.py` | Enum definition (TurnActor, TurnIntent), JSONB column, self-referential FK (answered_by_turn_id pattern) |
| `src/claude_headspace/models/command.py` | Enum with Enum column, cascade relationships, additional indexes |
| `src/claude_headspace/models/__init__.py` | Registration pattern: import, docstring, __all__ |

### 6.13 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PositionAssignment FK breaks migration | Medium | High | Use plain Integer column without FK constraint (Section 6.8). FK added when table exists. |
| Circular import between Message and Turn | Low | Medium | Use TYPE_CHECKING conditional imports and string-based relationship references. Both models reference each other — follow the Turn.answered_by pattern. |
| Partial unique index syntax varies | Very Low | Low | PostgreSQL natively supports partial unique indexes. Use `op.execute()` with raw SQL in migration. |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides | Status |
|------------|--------|------------------|--------|
| PersonaType system | E9-S2 | PersonaType table, Persona.persona_type_id | **Prerequisite** — must be complete before S3 |
| Persona model | E8-S5 (done) | Persona table, slug generation pattern | Done |
| Organisation model | E8-S7 (done) | organisations table (FK target) | Done |
| Project model | E1 (done) | projects table (FK target) | Done |
| Agent model | E1 (done) | agents table (FK target) | Done |
| Turn model | E1 (done) | turns table (extended with source_message_id) | Done |
| Command model | E1 (done) | commands table (FK target) | Done |

**Note:** Sprint 2 (PersonaType) is a prerequisite for Sprint 3. The PersonaType table and Persona.persona_type_id must exist before channel models are migrated, because the channel system assumes all personas have a type classification. However, the three tables created in Sprint 3 do not directly reference `persona_types` — the dependency is logical (channel services in S4 need persona types to determine delivery mechanism), not structural (no FK from channel tables to persona_types).

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Section 1, Decisions 1.1–1.5) |
| 1.1     | 2026-03-03 | Robbo  | v3 cross-PRD remediation: documented `Turn.source_message_id` population mechanism as v2 in FR10 — V1 uses `Message.source_turn_id` for Turn→Message traceability only (Finding #7) |
