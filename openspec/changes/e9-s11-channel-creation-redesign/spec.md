# Spec: E9-S11 Channel Creation Redesign + Member Pills

## Delta Specifications

This spec documents only the changes from the existing implementation. All unmentioned behaviour is preserved.

---

## 1. Database Schema Changes

**No migrations required.**

Existing schema already supports S11:
- `Channel.status` (`String(16)`, default `"pending"`) — `pending` → `active` transition already exists
- `ChannelMembership.agent_id` (`Mapped[int | None]`) — nullable, supports pending memberships
- `ChannelMembership.is_chair` — operator chair distinguished from agent members

Confirm before building:
```sql
-- Verify agent_id is nullable in ChannelMembership
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'channel_membership' AND column_name = 'agent_id';
-- Expected: is_nullable = YES
```

---

## 2. ChannelService Changes

### 2.1 New Exception

```python
class ProjectNotFoundError(ChannelError):
    """Project with the given ID does not exist."""
```

Location: alongside existing error classes at top of `channel_service.py`.

### 2.2 Modified: `_spin_up_agent_for_persona(persona, project_id)`

**Signature change:**
```python
# Before
def _spin_up_agent_for_persona(self, persona: Persona) -> Agent | None:

# After
def _spin_up_agent_for_persona(self, persona: Persona, project_id: int | None = None) -> Agent | None:
```

**Behaviour change:**
- REMOVE: "find existing active agent and return it" (lines ~1713-1717 in current codebase)
- REMOVE: `Project.query.first()` fallback
- ADD: if `project_id` is None, log warning and return None
- KEEP: async spin-up via `create_agent(project_id=project_id, persona_slug=persona.slug)`
- S11 always passes project_id from picker — never spins up without a project

**Callers to update:**
| Caller | New call |
|--------|----------|
| `add_member()` | `_spin_up_agent_for_persona(persona, project_id=project_id or channel.project_id)` |
| `promote_to_group()` | `_spin_up_agent_for_persona(persona, project_id=agent.project_id)` |

### 2.3 New: `create_channel_from_personas(creator_persona, channel_type, project_id, persona_slugs)`

```python
def create_channel_from_personas(
    self,
    creator_persona: Persona,
    channel_type: str,
    project_id: int,
    persona_slugs: list[str],
) -> Channel:
    """Create a channel by spinning up fresh agents for each persona.

    S11 replacement for V0 create_channel() when called from the redesigned
    creation pickers. Always spins up fresh agents — never reuses existing ones.

    Args:
        creator_persona: Operator persona creating the channel.
        channel_type: One of the ChannelType enum values.
        project_id: Project under which new agents are spun up.
        persona_slugs: Non-empty list of active persona slugs.

    Returns:
        The created Channel in 'pending' status.

    Raises:
        NoCreationCapabilityError: If creator cannot create channels.
        ProjectNotFoundError: If project_id does not resolve to a project.
        PersonaNotFoundError: If any slug is not an active persona.
        ValueError: If persona_slugs is empty.
    """
```

**Auto-name format:** `" + ".join(persona.name for persona in personas_in_order)`

Example: `["robbo", "con", "wado"]` → `"Robbo + Con + Wado"`

**Membership creation:** For each persona slug, create `ChannelMembership(channel_id, persona_id, agent_id=None, is_chair=False, status="active")` BEFORE kicking off spin-up. This ensures the membership record exists for `link_agent_to_pending_membership` to find.

**Initiation system message:** injected via `_post_system_message(channel, "Channel initiating...")` after memberships are committed.

### 2.4 New: `link_agent_to_pending_membership(agent)`

```python
def link_agent_to_pending_membership(self, agent: Agent) -> None:
    """Link a newly-registered agent to any pending channel membership.

    Called from session-start hook after agent creation. Finds the oldest
    pending membership for this agent's persona and links it.

    Args:
        agent: The newly-registered Agent instance (must have persona).
    """
```

**Query:**
```python
membership = (
    ChannelMembership.query
    .join(Channel, ChannelMembership.channel_id == Channel.id)
    .filter(
        ChannelMembership.persona_id == agent.persona_id,
        ChannelMembership.agent_id.is_(None),
        Channel.status == "pending",
    )
    .order_by(ChannelMembership.joined_at.asc())
    .first()
)
```

### 2.5 New: `check_channel_ready(channel_id)`

```python
def check_channel_ready(self, channel_id: int) -> bool:
    """Check if all pending memberships are linked; transition to active if so.

    Args:
        channel_id: The channel to check.

    Returns:
        True if channel transitioned to active; False otherwise.
    """
```

**Membership counting:** count non-chair memberships only:
```python
agent_memberships = [
    m for m in channel.memberships
    if not m.is_chair
]
total = len(agent_memberships)
connected = sum(1 for m in agent_memberships if m.agent_id is not None)
```

**Go-signal message:** `"All agents connected — channel ready."`

### 2.6 Modified: `add_member(slug, persona_slug, caller_persona, project_id=None)`

```python
def add_member(
    self,
    slug: str,
    persona_slug: str,
    caller_persona: Persona,
    project_id: int | None = None,
) -> ChannelMembership:
```

- `project_id` defaults to `channel.project_id` if not provided
- Always spins up fresh agent (no existing-agent reuse)
- Creates membership with `agent_id = None` (async spin-up)
- Broadcasts `channel_member_added` SSE (new event type; payload same as `channel_member_connected` but with `agent_id: null`)

---

## 3. Hook Receiver Integration

### 3.1 Session-start hook — agent link step

**File:** `src/claude_headspace/services/hook_receiver.py`

After agent is created/resolved and persisted, add:
```python
channel_service = self.app.extensions.get("channel_service")
if channel_service and agent and agent.persona_id:
    try:
        channel_service.link_agent_to_pending_membership(agent)
    except Exception as e:
        logger.warning(f"link_agent_to_pending_membership failed: {e}")
```

This MUST be inside a try/except — channel linking is best-effort and must not block hook processing.

---

## 4. API Endpoint Changes

### 4.1 `POST /api/channels` — extended

**New request body (persona-based path):**
```json
{
    "channel_type": "workshop",
    "project_id": 1,
    "persona_slugs": ["robbo", "con", "wado"]
}
```

**Routing logic in view:**
```python
if "persona_slugs" in data:
    # S11 path
    persona_slugs = data.get("persona_slugs")
    project_id = data.get("project_id")
    channel_type = data.get("channel_type", "").strip()
    # validate...
    channel = service.create_channel_from_personas(
        creator_persona=persona,
        channel_type=channel_type,
        project_id=project_id,
        persona_slugs=persona_slugs,
    )
else:
    # Legacy path (unchanged)
    ...
```

**Validation for S11 path:**
- `persona_slugs`: list of strings, non-empty
- `project_id`: integer, required
- `channel_type`: one of ChannelType enum values

**Response:** same as existing — `_channel_to_dict(channel)`, HTTP 201

### 4.2 `POST /api/channels/<slug>/members` — extended

**New optional field in request body:**
```json
{
    "persona_slug": "robbo",
    "project_id": 2
}
```

**`project_id` validation:**
```python
project_id = data.get("project_id")
if project_id is not None and not isinstance(project_id, int):
    return _error_response(400, "invalid_field", "project_id must be an integer")
```

**New error mapping:**
```python
ProjectNotFoundError: (404, "project_not_found"),
```

---

## 5. SSE Event Specifications

### 5.1 `channel_member_connected`

Broadcast when a pending membership's `agent_id` is set.

```json
{
    "event": "channel_member_connected",
    "channel_slug": "<slug>",
    "persona_name": "Robbo",
    "persona_slug": "robbo",
    "agent_id": 42,
    "connected_count": 1,
    "total_count": 3
}
```

### 5.2 `channel_ready`

Broadcast when all non-chair memberships are linked and channel transitions to `active`.

```json
{
    "event": "channel_ready",
    "channel_slug": "<slug>",
    "name": "Robbo + Con + Wado"
}
```

### 5.3 `channel_member_added`

Broadcast when a new membership is created (from add-member flow), before agent connects.

```json
{
    "event": "channel_member_added",
    "channel_slug": "<slug>",
    "persona_name": "Wado",
    "persona_slug": "wado",
    "agent_id": null
}
```

**Broadcast via `_broadcast_update`:**
```python
self._broadcast_update(channel, "channel_member_connected", payload)
self._broadcast_update(channel, "channel_ready", payload)
self._broadcast_update(channel, "channel_member_added", payload)
```

---

## 6. Voice App Specification

### 6.1 `#channel-picker` form (voice.html)

**Before (V0):**
```html
<input type="text" id="channel-name-input" ...>
<select id="channel-type-select">...</select>
<div id="channel-member-list"><!-- existing agents --></div>
<button id="channel-create-submit">Create</button>
```

**After (S11):**
```html
<select id="channel-project-select">
    <option value="">Select project...</option>
</select>
<select id="channel-type-select">...</select>  <!-- retained -->
<div id="channel-persona-list"><!-- active personas --></div>
<button id="channel-create-submit">Create Channel (0 selected)</button>
```

**Bottom sheet shared between create and add-member:**
- `data-mode="create"` → multi-select checkboxes, CTA "Create Channel (N selected)"
- `data-mode="add-member"` → single-select radio, CTA "Add to Channel"

### 6.2 `#channel-chat-member-count` → `#channel-chat-member-pills` (voice.html)

**Before:**
```html
<span id="channel-chat-member-count" class="channel-chat-member-count"></span>
```

**After:**
```html
<div id="channel-chat-member-pills" class="channel-chat-member-pills"></div>
```

### 6.3 `VoiceAPI.createChannel` signature

**Before:** `createChannel(name, channelType, memberAgentIds)`
**After:** `createChannel(projectId, channelType, personaSlugs)`

```javascript
// POST /api/channels body
{
    project_id: projectId,       // integer
    channel_type: channelType,   // string
    persona_slugs: personaSlugs  // string[]
}
```

### 6.4 `VoiceAPI.addChannelMember` (new)

```javascript
addChannelMember(slug, personaSlug, projectId)
// POST /api/channels/<slug>/members body
{
    persona_slug: personaSlug,
    project_id: projectId  // optional
}
```

---

## 7. Dashboard Specification

### 7.1 Channel management create form

**Before (S9):**
- Fields: name (text), type (select), description (textarea), members (autocomplete from existing agents)
- Submit: `POST /api/channels` with `{name, channel_type, description, members: [slugs]}`

**After (S11):**
- Fields: project (select), type (select), personas (checkbox list from active personas)
- Remove: name input, description textarea, existing-agent autocomplete
- Submit: `POST /api/channels` with `{project_id, channel_type, persona_slugs: [slugs]}`

### 7.2 Add member panel (dashboard channel chat)

Existing `#channel-chat-add-member` / `#channel-chat-add-member-picker` div in `_channel_chat_panel.html`:

**Before:** incomplete / project-unaware
**After:**
- Project select (`#add-member-project-select`)
- Persona radio list (`#add-member-persona-list`)
- Submit button calling `POST /api/channels/<slug>/members` with `{persona_slug, project_id}`

### 7.3 `#channel-chat-member-pills` population (dashboard)

Already present in `_channel_chat_panel.html`. JS must:
1. Load members from `GET /api/channels/<slug>/members` on channel open
2. Render pills: pending pills for `agent_id: null`; connected pills for `agent_id: N`
3. Update on `channel_member_connected` SSE: transition pending → connected
4. Update on `channel_ready` SSE: inject go-signal system message, enable input

---

## 8. NFR Confirmations

| NFR | Confirmation |
|-----|-------------|
| No framework dependencies | All voice app JS in IIFE pattern; dashboard in existing module pattern |
| No schema migrations | ChannelMembership.agent_id nullable confirmed; Channel.status = pending confirmed |
| CSS surface-specific | Voice app: voice.css; Dashboard: Tailwind + input.css if needed |
| Shared component per surface | Voice: one `#channel-picker` bottom sheet, mode parameter; Dashboard: one picker component in channel-admin.js |

---

## 9. Backward Compatibility

- `POST /api/channels` with `name` field → legacy path (unchanged); no regression
- `POST /api/channels/<slug>/members` without `project_id` → falls back to `channel.project_id` (unchanged behaviour)
- `get_available_members()` endpoint retained for any other consumers
- `_spin_up_agent_for_persona` callers outside S11 scope: `promote_to_group()` updated to pass project_id; if any other caller exists, add `project_id=None` guard

---

## 10. Out-of-Scope Confirmations

Per PRD Section 2.2, the following are explicitly NOT implemented:
- Reusing existing running agents at channel creation
- Cross-project member addition at creation time (creation-time project picker is single-project)
- Removing members from a channel
- Agent reconnection after crash
- Specific wording of system messages (implementer decision)
