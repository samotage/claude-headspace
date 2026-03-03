# Epic 9 Roadmap: Inter-Agent Communication

**Project:** Claude Headspace v3.2
**Epic:** Epic 9 — Inter-Agent Communication
**Author:** Robbo (workshopped with Sam)
**Status:** Roadmap — Baseline for PRD Orchestration
**Date:** 2026-03-03

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 9 implementation. It breaks Epic 9 into 8 sprints (1 sprint = 1 PRD = 1 OpenSpec change), maps the dependency chain, and provides the foundation for orchestrating the build sequence. All design decisions are resolved — every sprint has a validated PRD.

**Epic 9 Goal:** Give personas the ability to communicate with each other through structured channels — named conversation containers that carry messages between agents, the operator, and future external participants.

**Epic 9 Value Proposition:**

- **Structured Group Communication** — Personas can create channels (workshop, delegation, review, standup, broadcast), add members, and exchange messages — transforming Headspace from a monitoring surface into a collaboration platform
- **Operator as Participant** — The operator (Sam) is modelled as a first-class person/internal Persona who participates in channels alongside agents, sending and receiving messages through the dashboard, CLI, and voice bridge
- **Delivery Engine** — Messages fan out to channel members automatically: tmux injection for online agents (state-safe, respecting agent lifecycle), SSE for the operator and remote agents, deferred storage for offline personas
- **Agent Response Capture** — When an agent composes a response (COMPLETION/END_OF_COMMAND turn), the delivery engine detects channel membership and relays the response back to the channel — enabling genuine group conversations without manual relay
- **Voice-First Channel Management** — The operator creates, manages, and participates in channels via natural voice commands through the existing voice bridge
- **Handoff Continuity** — Independent of the channel system, the handoff pipeline gains scannable filenames, startup detection, and operator-gated rehydration

**The Differentiator:** Until now, communication in Claude Headspace is strictly one-to-one: operator sends a command to an agent, agent responds. Agents cannot talk to each other. The operator is the sole relay point between agents working on the same problem. Epic 9 removes the operator as bottleneck by introducing channels where multiple personas converse directly. Robbo can ask Con a question, Paula can challenge Robbo's design, and the operator can observe, participate, or stay silent — all within a named, persistent channel with full audit trail. Combined with the persona identity system from Epic 8, this transforms Headspace agents from isolated workers into a communicating team.

**Success Criteria:**

- Operator creates a workshop channel with Robbo and Paula via voice: "Create a workshop channel called persona alignment with Robbo and Paula" — channel created, members added, agents spun up
- Operator sends a message from the dashboard chat panel — message fans out to both agents via tmux
- Robbo composes a response — stop hook fires, delivery engine detects COMPLETION, posts response as channel Message, Paula receives it
- Paula disagrees — her response fans out to Robbo and the operator; the operator sees it in real-time on the dashboard
- The entire conversation is preserved as an immutable message history in the channel
- A new agent starts for Robbo's persona — the dashboard shows the 3 most recent handoffs with scannable filenames, the operator clicks to copy a path and tells the new Robbo to continue

**Architectural Foundation:** Builds on Epic 8's persona system (Persona, Role, Organisation, Position models, persona assets, skill injection, handoff executor), the tmux bridge (per-pane locks, `send_text()`), the hook receiver pipeline (stop hook, IntentDetector, CommandLifecycleManager), the SSE broadcaster, and the existing session correlator infrastructure.

**Dependencies:** Epic 8 must be complete before Epic 9 begins. Sprint 1 (Handoff Improvements) is standalone. Sprints 2-8 form a linear dependency chain for the channel system.

**Design Source:** All architectural decisions resolved in the Inter-Agent Communication Workshop across Sections 0-4: `docs/workshop/interagent-communication/sections/`. ERD and data model decisions in Section 1. Channel operations in Section 2. Delivery engine in Section 3. Group workshop use case in Section 4.

---

## Dependency Graph

```
E9-S1 (Handoff Improvements)     ← standalone, no channel dependency
   |
   |   E9-S2 (PersonaType System) ← identity infrastructure
   |     |
   |     v
   |   E9-S3 (Channel Data Model) ← tables: Channel, ChannelMembership, Message
   |     |
   |     v
   |   E9-S4 (ChannelService + CLI) ← business logic + agent CLI
   |     |
   |     v
   |   E9-S5 (API + SSE Endpoints) ← REST API + SSE event types
   |     |
   |     v
   |   E9-S6 (Delivery Engine) ← fan-out, response capture, queue
   |     |
   |     v
   |   E9-S7 (Dashboard UI) ← channel cards, chat panel, management
   |     |
   |     v
   |   E9-S8 (Voice Bridge Channels) ← voice routing, fuzzy matching
```

Sprint 1 can be built at any time — it modifies the existing handoff pipeline with no channel dependencies. Sprints 2-8 are strictly sequential: each layer depends on the one below it.

---

## Epic 9 Story Mapping

| Story ID | Story Name | Subsystem | PRD Location | Sprint | Priority |
|----------|-----------|-----------|-------------|--------|----------|
| E9-S1 | Handoff Continuity Improvements | `handoff` | channels/ | 1 | P1 |
| E9-S2 | PersonaType System | `persona` | channels/ | 2 | P1 |
| E9-S3 | Channel Data Model | `channels` | channels/ | 3 | P1 |
| E9-S4 | ChannelService + CLI | `channels` | channels/ | 4 | P1 |
| E9-S5 | API + SSE Endpoints | `channels` | channels/ | 5 | P1 |
| E9-S6 | Channel Delivery Engine | `channels` | channels/ | 6 | P1 |
| E9-S7 | Dashboard UI: Channel Cards, Chat Panel, Management | `ui` | channels/ | 7 | P1 |
| E9-S8 | Voice Bridge Channel Routing Extensions | `voice` | channels/ | 8 | P1 |

---

## Sprint Breakdown

### Sprint 1: Handoff Continuity Improvements (E9-S1)

**Goal:** Make the handoff pipeline production-ready — scannable filenames, startup detection of prior handoffs, operator-gated rehydration via synthetic dashboard turns, and a CLI for handoff history.

**Dependencies:** E8-S14 (HandoffExecutor — done). No channel dependency. Can be built independently of Sprints 2-8.

**Deliverables:**

**Handoff Filename Reform:**

- New format: `{YYYY-MM-DDTHH:MM:SS}_{summary-slug}_{agent-id:NNN}.md`
- Modified `generate_handoff_file_path()` with `<insert-summary>` placeholder
- Modified `compose_handoff_instruction()` with filename format guidance for departing agent
- Glob fallback in polling thread for agent-chosen summary variations

**Startup Detection:**

- New `HandoffDetectionService` — scans persona handoff directory on agent creation
- Surfaces most recent 3 handoffs as `synthetic_turn` SSE event
- Dashboard renders synthetic turns as visually distinct system bubbles with copyable file paths
- Operator decides whether to rehydrate — manual copy-paste flow, not automatic

**Handoff History CLI:**

- `flask org persona handoffs <slug>` — lists all handoffs, newest first
- `--limit N` and `--paths` options
- Filesystem-only data source (no DB query)

**PRD Location:** `docs/prds/channels/e9-s1-handoff-improvements-prd.md`

**Key Technical Decisions:**

- Filename uses underscore separators for clean 3-section split (timestamp, summary, agent-tag) — decided (0A.1)
- Startup detection triggers after persona assignment in SessionCorrelator — decided (0A.2)
- Synthetic turns are dashboard-only SSE events, never delivered to the agent — decided (0A.3)
- Rehydration is manual (operator copies path, pastes into message) — decided (0A.4)
- Legacy handoff filenames accepted without migration — decided (0A.1)

**Files Modified:** `handoff_executor.py`, `session_correlator.py`, `app.py`
**Files Created:** `handoff_detection.py`, dashboard JS for synthetic turn rendering, CLI command

**Risks:**

- Agents may fail to replace the `<insert-summary>` placeholder — mitigated by glob fallback
- Agents may insert underscores in the summary — mitigated by graceful CLI parsing

---

### Sprint 2: PersonaType System (E9-S2)

**Goal:** Classify every persona into one of four quadrants (agent/internal, agent/external, person/internal, person/external) and model the operator as a first-class person-type Persona.

**Dependencies:** E8-S5 (Persona model — done). Prerequisite for S3-S8.

**Deliverables:**

**PersonaType Lookup Table:**

- New `PersonaType` model with `type_key` (agent/person) and `subtype` (internal/external)
- 4 seeded rows, explicitly numbered IDs, unique constraint on `(type_key, subtype)`
- NOT NULL `persona_type_id` FK on Persona with `ondelete=RESTRICT`
- All existing personas backfilled as agent/internal (id=1)

**Operator Identity:**

- New "operator" Role created in migration
- New "Sam" Persona record (person/internal, role=operator, status=active)
- `Persona.get_operator()` class method for runtime lookup

**Channel Creation Capability:**

- `can_create_channel` property on Persona model
- person/internal and agent/internal return `True`; external quadrants return `False`

**PRD Location:** `docs/prds/channels/e9-s2-persona-type-system-prd.md`

**Key Technical Decisions:**

- Lookup table (not enum) — explicit IDs for deterministic FK references — decided (1.1)
- `ondelete=RESTRICT` on persona_type_id — type rows are infrastructure, not runtime entities — decided (workshop convention)
- `default=1` on persona_type_id — new personas get agent/internal without modifying registration service — decided (1.1)
- `can_create_channel` is a model property, not a DB column — decided (2.1)
- External quadrants modelled but not exercised in v1 — decided (1.1)

**Data Model:**

```python
class PersonaType(db.Model):
    __tablename__ = "persona_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    type_key: Mapped[str] = mapped_column(String(16), nullable=False)   # agent | person
    subtype: Mapped[str] = mapped_column(String(16), nullable=False)    # internal | external
    # UniqueConstraint("type_key", "subtype")
```

**Files Modified:** `persona.py` (model), `models/__init__.py`
**Files Created:** `persona_type.py` (model), Alembic migration

**Risks:**

- Migration on populated personas table — mitigated by 3-step pattern (add NULLABLE, backfill, alter NOT NULL)
- `default=1` silently creates wrong type for future person personas — mitigated by documentation

---

### Sprint 3: Channel Data Model (E9-S3)

**Goal:** Create the three core channel tables (Channel, ChannelMembership, Message), two enums (ChannelType, MessageType), and extend Turn with `source_message_id` — the complete data foundation for inter-agent communication.

**Dependencies:** E9-S2 (PersonaType — logical prerequisite, not structural FK). Pure data model sprint — no services, no routes, no behaviour.

**Deliverables:**

**Channel Table (12 columns):**

- name, slug (auto-generated `{type}-{name}-{id}`), channel_type (5-value enum), description, intent_override
- Scoping FKs: organisation_id (SET NULL), project_id (SET NULL), created_by_persona_id (SET NULL)
- Lifecycle: status (pending/active/complete/archived), created_at, completed_at, archived_at

**ChannelMembership Table (9 columns):**

- channel_id (CASCADE), persona_id (CASCADE) — unique constraint on the pair
- agent_id (SET NULL) — mutable delivery target, partial unique index `uq_active_agent_one_channel`
- position_assignment_id (plain Integer — FK deferred, target table doesn't exist yet)
- is_chair, status (active/left/muted), joined_at, left_at

**Message Table (11 columns):**

- channel_id (CASCADE), persona_id (SET NULL), agent_id (SET NULL)
- content (Text), message_type (4-value enum), metadata (JSONB), attachment_path
- Bidirectional traceability: source_turn_id (SET NULL), source_command_id (SET NULL)
- sent_at — immutable records, no edited_at or deleted_at

**Turn Extension:**

- New nullable `source_message_id` FK to messages (SET NULL) — enables tracing channel-delivered Turns

**Enums:**

- `ChannelType`: workshop, delegation, review, standup, broadcast
- `MessageType`: message, system, delegation, escalation

**PRD Location:** `docs/prds/channels/e9-s3-channel-data-model-prd.md`

**Key Technical Decisions:**

- Channels are cross-project by default (nullable org/project FKs) — decided (1.1, 1.5)
- Messages are immutable — no edits, no deletes, operational records — decided (1.2)
- One agent, one active channel — partial unique index on agent_id WHERE active — decided (1.4)
- No new Event types — messages are their own audit trail — decided (1.5)
- Slug pattern `{channel_type}-{name}-{id}` — consistent with Persona and Organisation — decided (1.1)

**Data Model:**

```
Channel ──< ChannelMembership >── Persona
  |                |
  |              agent_id ──> Agent (mutable delivery target)
  |
  └──< Message ──> Persona, Agent, Turn, Command
         |
         v
       Turn.source_message_id (reverse link)
```

**Files Created:** `channel.py`, `channel_membership.py`, `message.py` (models), Alembic migration
**Files Modified:** `turn.py`, `models/__init__.py`

**Risks:**

- PositionAssignment FK breaks migration — mitigated by plain Integer column without FK constraint
- Circular import between Message and Turn — mitigated by TYPE_CHECKING imports

---

### Sprint 4: ChannelService + CLI (E9-S4)

**Goal:** Build the centralised ChannelService — the single service class all channel operations flow through — and the CLI that agents use to interact with channels from their terminal sessions.

**Dependencies:** E9-S3 (Channel data model), E9-S2 (PersonaType for capability checks).

**Deliverables:**

**ChannelService (`app.extensions["channel_service"]`):**

- Channel CRUD: `create_channel()`, `list_channels()`, `get_channel()`, `update_channel()`, `complete_channel()`, `archive_channel()`
- Membership: `add_member()` (with async agent spin-up), `leave_channel()`, `transfer_chair()`, `mute_channel()`, `unmute_channel()`, `list_members()`
- Messages: `send_message()` (fire-and-forget — DB write, return immediately), `get_history()` (cursor pagination)
- Channel lifecycle state machine: pending -> active (first non-system message) -> complete (explicit or auto on last member leave) -> archived
- System message generation for all structural events (joins, leaves, chair transfers, state changes)
- One-agent-one-channel enforcement with actionable error messages
- Context briefing on member add (last 10 messages)
- SSE broadcasting: `channel_message` and `channel_update` events after persistence

**Caller Identity Resolution:**

- Two-strategy cascade: `HEADSPACE_AGENT_ID` env var override, tmux pane detection fallback
- Shared utility in `services/caller_identity.py`

**CLI Commands:**

- `flask channel` group: create, list, show, members, add, leave, complete, transfer-chair, mute, unmute
- `flask msg` group: send, history
- Conversational envelope format for history display, `--format yaml` for machine consumption
- `--members` flag on create accepts comma-separated persona slugs

**Error Hierarchy:**

- `ChannelError` base with subclasses: `ChannelNotFoundError`, `NotAMemberError`, `NotChairError`, `ChannelClosedError`, `AlreadyMemberError`, `NoCreationCapabilityError`, `AgentChannelConflictError`

**Agent-to-Membership Linking:**

- Session correlator modification: when a new agent registers for a persona, update any ChannelMembership with NULL agent_id
- Context briefing delivered via tmux after agent-to-membership linking

**PRD Location:** `docs/prds/channels/e9-s4-channel-service-cli-prd.md`

**Key Technical Decisions:**

- CLI namespace: standalone `flask channel` and `flask msg` — not under `flask org` — decided (2.2)
- Caller identity: env var override takes precedence, tmux pane detection is fallback — decided (2.2)
- Channel lifecycle: 4-state (pending -> active -> complete -> archived), no reactivation — decided (2.1)
- Message send is fire-and-forget — write to DB, return immediately — decided (2.2, 3.1)
- System messages are service-generated only, never CLI-callable — decided (2.2)
- Agent spin-up on add is async — same pattern as remote agents — decided (2.1)

**Files Created:** `channel_service.py`, `caller_identity.py`, `channel_cli.py`, `msg_cli.py`
**Files Modified:** `app.py`, `session_correlator.py`

**Risks:**

- Caller identity resolution fails in non-tmux environments — mitigated by env var override
- Race condition on last-member-leave auto-complete — mitigated by advisory locks

---

### Sprint 5: API + SSE Endpoints (E9-S5)

**Goal:** Expose the ChannelService over HTTP — a thin REST wrapper in the `channels_api` blueprint — and define two new SSE event types (`channel_message`, `channel_update`) on the existing broadcaster stream.

**Dependencies:** E9-S4 (ChannelService), E9-S2 (PersonaType for auth resolution).

**Deliverables:**

**REST API (14 endpoints):**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/channels` | Create a channel |
| GET | `/api/channels` | List channels for calling persona |
| GET | `/api/channels/<slug>` | Channel detail |
| PATCH | `/api/channels/<slug>` | Update channel (chair/operator) |
| POST | `/api/channels/<slug>/complete` | Complete channel |
| POST | `/api/channels/<slug>/archive` | Archive channel |
| GET | `/api/channels/<slug>/members` | List members |
| POST | `/api/channels/<slug>/members` | Add persona to channel |
| POST | `/api/channels/<slug>/leave` | Leave channel |
| POST | `/api/channels/<slug>/mute` | Mute delivery |
| POST | `/api/channels/<slug>/unmute` | Resume delivery |
| POST | `/api/channels/<slug>/transfer-chair` | Transfer chair role |
| GET | `/api/channels/<slug>/messages` | Message history (cursor-paginated) |
| POST | `/api/channels/<slug>/messages` | Send a message |

**Authentication:**

- Dual auth: Flask session cookie (dashboard/operator) + `Authorization: Bearer` session tokens (remote agents)
- `_resolve_caller()` helper resolves persona from whichever mechanism is present
- Operator identity via `Persona.get_operator()` for dashboard session auth

**SSE Event Types:**

- `channel_message` — broadcast when a message is posted (any frontend)
- `channel_update` — broadcast on state changes (member join/leave, status transition, chair transfer, mute/unmute)
- Both types on existing `/api/events/stream`, no per-channel SSE streams

**Error Envelope:**

- Standard format: `{error: {code, message, status}}`
- 13 machine-readable error codes (missing_fields, not_a_member, not_chair, etc.)

**PRD Location:** `docs/prds/channels/e9-s5-api-sse-endpoints-prd.md`

**Key Technical Decisions:**

- Single `channels_api` blueprint, slug-based URLs (not integer IDs) — decided (2.3)
- No per-channel SSE streams — single stream with type filtering respects 100-connection limit — decided (2.3)
- No new auth mechanism — session cookies + existing session tokens — decided (2.3)
- Cursor pagination on messages by `sent_at` timestamp — decided (2.3)
- SSE broadcasts from ChannelService (not route handlers) — consistent regardless of frontend — decided (2.3)

**Files Created:** `routes/channels_api.py`
**Files Modified:** `app.py`
**No Changes Required:** `broadcaster.py`, `session_token.py`, `sse.py` (existing infrastructure handles new event types automatically)

**Risks:**

- Dashboard session auth doesn't cleanly resolve to persona — mitigated by Persona.get_operator() fallback
- SSE event volume from busy channels — mitigated by existing broadcaster queue limits

---

### Sprint 6: Channel Delivery Engine (E9-S6)

**Goal:** Build the runtime engine that delivers messages to channel members and captures agent responses back into the channel — the fan-out loop that makes group chat work.

**Dependencies:** E9-S4 (ChannelService), E9-S2 (PersonaType for member type resolution). Integrates with hook receiver, CommandLifecycleManager, tmux bridge, and NotificationService.

**Deliverables:**

**ChannelDeliveryService (`app.extensions["channel_delivery_service"]`):**

- **Fan-out:** Post-commit side effect. Iterates active (non-muted) members excluding sender. Delivery per member type:
  - Agent (internal, online): tmux `send_text()` with envelope format `[#slug] Name (agent:ID):\n{content}`
  - Person (internal — operator): macOS notification via NotificationService
  - Agent/Person (offline): deferred — message persists in channel history
  - Remote/external: SSE broadcast already handled by ChannelService

- **Agent Response Capture:** When hook receiver's `process_stop()` produces a COMPLETION or END_OF_COMMAND Turn for a channel member, post the response as a new channel Message — triggering fan-out to all other members

- **COMMAND COMPLETE Stripping:** Machine-parseable footer stripped from channel message content before relay (retained on individual Turn record)

- **Delivery Queue:** In-memory `dict[agent_id, deque[message_id]]`. State safety: deliver only in AWAITING_INPUT or IDLE; queue for PROCESSING, COMMANDED, COMPLETE

- **Queue Drain:** When CommandLifecycleManager transitions agent to safe state, deliver oldest queued message (FIFO, one per transition)

- **Feedback Loop Prevention:** Three independent mechanisms:
  1. Completion-only relay (no PROGRESS/tool-use noise)
  2. Source tracking (`source_turn_id` on Messages)
  3. IntentDetector gating (only COMPLETION/END_OF_COMMAND pass through)

- **Notification Extension:** `send_channel_notification()` added to NotificationService with per-channel rate limiting (30s window)

**PRD Location:** `docs/prds/channels/e9-s6-delivery-engine-prd.md`

**Key Technical Decisions:**

- Best-effort delivery — no retry, no delivery tracking table — decided (3.1)
- Completion-only relay — agents relay composed responses, not intermediate thinking — decided (3.2, 0.2)
- Safe states for delivery: AWAITING_INPUT and IDLE only — decided (3.3)
- One message per drain (natural pacing) — decided (3.3)
- In-memory queue (lost on restart, messages persist in DB for context briefing) — decided (3.3)
- Envelope format: `[#slug] Name (agent:ID):\n{content}` — decided (0.3)
- Per-pane locks via existing tmux bridge — no new global lock — decided (0.1)

**Files Created:** `channel_delivery.py`
**Files Modified:** `hook_receiver.py` (response capture insertion point), `command_lifecycle.py` (queue drain on state transition), `app.py`, `notification_service.py`

**Risks:**

- Agent ping-pong in busy channels — mitigated by PROCESSING queue + natural state machine pacing (v2 cooldown if needed)
- Queue grows unbounded for offline agents — mitigated: offline agents have no queue, only online agents in unsafe states
- Race condition between relay and process_stop commit — mitigated: relay fires AFTER both commits in two-commit pattern

---

### Sprint 7: Dashboard UI (E9-S7)

**Goal:** Build the frontend — channel cards at the top of the dashboard, slide-out chat panel for reading and sending messages, channel management modal, and real-time SSE integration.

**Dependencies:** E9-S5 (API endpoints), E9-S6 (delivery engine produces the messages displayed). Frontend-only sprint — Jinja2, vanilla JS, Tailwind CSS. No new backend services.

**Deliverables:**

**Channel Cards Section:**

- Positioned above all project sections in all dashboard view modes (project, priority, Kanban)
- Each card: channel name, type badge, member list, last message preview, status indicator
- Real-time updates via `channel_message` and `channel_update` SSE events
- Click to open chat panel (toggle behaviour)

**Slide-Out Chat Panel:**

- Fixed-position panel, slides from right (440px desktop, full width mobile)
- Message feed: chronological, sender name (colour-coded: cyan for operator, green for agents), timestamps (relative + absolute on hover)
- System messages: muted, centered, italic
- Smart scrolling: auto-scroll when near bottom, "New messages" indicator when scrolled up
- Text input at bottom: Enter to send, Shift+Enter for newline
- Optimistic rendering with error indicator on failure
- "Load earlier messages" button for backward cursor pagination

**Channel Management Modal:**

- Channel list with name, slug, type, status, member count, created date
- Create channel form: name, type dropdown, description, members
- Complete and archive actions

**SSE Integration:**

- `channel_message` and `channel_update` added to `commonTypes` in sse-client.js
- New JS modules: `channel-cards.js`, `channel-chat.js`, `channel-management.js`
- Notification suppression flag infrastructure for v2 (`window.ChannelChat._activeChannelSlug`)

**Server-Side Context:**

- `get_channel_data_for_operator()` function in dashboard route handler
- Provides `channel_data` template context variable for initial server render

**PRD Location:** `docs/prds/channels/e9-s7-dashboard-ui-prd.md`

**Key Technical Decisions:**

- Channel cards above all project sections, visible in all view modes — decided (Section 1.1)
- Chat panel slides from right, overlays content (doesn't push) — decided (Section 3.4)
- Vanilla JS IIFE modules, no framework — decided (NFR1)
- No per-channel SSE streams — single stream with type filtering — decided (Section 2.3)
- Notification active-view suppression deferred to v2 — 30s rate limit from S6 is sufficient floor — decided (Section 3.4)
- Backward-compatible: no channels = no cards section = dashboard renders identically — decided (NFR6)

**Files Created:** `partials/_channel_cards.html`, `partials/_channel_chat_panel.html`, `partials/_channel_management.html`, `channel-cards.js`, `channel-chat.js`, `channel-management.js`
**Files Modified:** `dashboard.html`, `sse-client.js`, `dashboard-sse.js`, `input.css`, `routes/dashboard.py`

**Risks:**

- Chat panel obscures important agent cards — mitigated: 440px width leaves most dashboard visible, user can close anytime
- Large channel member lists overflow card width — mitigated: truncate with "+N more"

---

### Sprint 8: Voice Bridge Channel Routing Extensions (E9-S8)

**Goal:** Extend the voice bridge with channel awareness — semantic matching for channel names, voice command routing for channel operations, and Voice Chat PWA channel display.

**Dependencies:** E9-S4 (ChannelService), E9-S5 (SSE event types). Final sprint — all channel infrastructure must be operational.

**Deliverables:**

**Channel Intent Detection:**

- New detection stage in `voice_command()`, between handoff detection and agent resolution
- Regex pattern matching (no LLM call): send to channel, channel history, create channel, add member, complete channel, list channels
- Detection pipeline order: handoff -> channel -> agent

**Fuzzy Channel Name Matching:**

- Match against channel name and slug: exact -> substring -> token overlap
- Ambiguity resolution: multiple matches return clarification prompt listing options
- Handles speech-to-text artifacts: missing articles, singular/plural, filler words

**Channel Context Tracking:**

- Per-session "current channel" (in-memory, keyed by auth token)
- "this channel" / "the channel" resolves to most recently referenced channel

**Channel Type Inference:**

- Keyword matching: "workshop", "delegation", "review", "standup", "broadcast"
- Default: workshop

**Voice-Formatted Responses:**

- New VoiceFormatter methods: `format_channel_message_sent()`, `format_channel_history()`, `format_channel_created()`, `format_channel_completed()`, `format_channel_list()`, `format_channel_member_added()`
- Existing `{status_line, results, next_action}` envelope

**Voice Chat PWA Integration:**

- Channel section in sidebar below agent list
- `channel_message` and `channel_update` SSE event handling
- Channel message tap-through to detail view with message history

**PRD Location:** `docs/prds/channels/e9-s8-voice-bridge-channels-prd.md`

**Key Technical Decisions:**

- Extend existing `/api/voice/command` — no new endpoints — decided (2.3)
- Regex-only channel detection (no LLM fallback) — distinctive patterns make regex reliable — decided (2.3)
- Voice bridge is the primary operator channel interface; dashboard and CLI are secondary — decided (4.1)
- Channel type inferred from keywords, default workshop — decided (4.1)
- Context tracking per auth token, in-memory, resets on restart — decided (derived from 4.1)

**Files Modified:** `voice_bridge.py`, `voice_formatter.py`, `voice-sidebar.js`, `voice-sse-handler.js`, `voice-api.js`, `voice-state.js`
**Files Created:** None — all modifications to existing files.

**Risks:**

- Channel intent false positives on agent commands — mitigated: distinctive syntax markers (colon separator, "create ... channel")
- Speech-to-text garbles channel names — mitigated: fuzzy matching with token overlap
- ChannelService not available during development — mitigated: graceful 503 error

---

## Cross-Cutting Concerns

### Shared Modification Points

Several files are modified by multiple sprints. Building agents should check for prior modifications and append rather than replace:

| File | Modified By | What Each Sprint Does |
|------|------------|----------------------|
| `session_correlator.py` | S1, S4 | S1: call `HandoffDetectionService.detect_and_emit()` after persona assignment. S4: update ChannelMembership agent_id after persona assignment. Both target the same logical point — append sequentially. |
| `sse-client.js` `commonTypes` | S1, S7 | S1: add `synthetic_turn`. S7: add `channel_message`, `channel_update`. Append to the array. |
| `app.py` | S1, S2, S4, S5, S6 | Service and blueprint registration. Each sprint adds its own registration line. |

### New Data Models Summary

| Model | Sprint | Purpose |
|-------|--------|---------|
| PersonaType | S2 | Persona classification lookup (4 rows) |
| Channel | S3 | Named conversation container |
| ChannelMembership | S3 | Persona-to-channel link with mutable agent delivery target |
| Message | S3 | Immutable message record with bidirectional traceability |

### New Services Summary

| Service | Sprint | Extension Key |
|---------|--------|--------------|
| HandoffDetectionService | S1 | `handoff_detection_service` |
| ChannelService | S4 | `channel_service` |
| ChannelDeliveryService | S6 | `channel_delivery_service` |

### New SSE Event Types

| Event Type | Sprint Defined | Sprint Consumed |
|------------|---------------|----------------|
| `synthetic_turn` | S1 | S1 (dashboard) |
| `channel_message` | S5 | S7 (dashboard), S8 (voice PWA) |
| `channel_update` | S5 | S7 (dashboard), S8 (voice PWA) |

---

## Build Sequence

The recommended orchestration order:

1. **E9-S1** (Handoff Improvements) — standalone, can start immediately
2. **E9-S2** (PersonaType System) — can start immediately, S3 depends on it
3. **E9-S3** (Channel Data Model) — blocked by S2
4. **E9-S4** (ChannelService + CLI) — blocked by S3
5. **E9-S5** (API + SSE Endpoints) — blocked by S4
6. **E9-S6** (Delivery Engine) — blocked by S4 (calls ChannelService)
7. **E9-S7** (Dashboard UI) — blocked by S5 (calls API endpoints)
8. **E9-S8** (Voice Bridge Channels) — blocked by S4 (calls ChannelService), S5 (SSE events for PWA)

S1 and S2 can be built in parallel. S5 and S6 could theoretically be built in parallel (both depend on S4, not on each other), but S7 depends on S5 and S8 depends on both S4 and S5.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-03 | Robbo | Initial roadmap synthesised from 8 validated PRDs (E9-S1 through E9-S8) |
