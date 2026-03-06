# Tasks: E9-S11 Channel Creation Redesign + Member Pills

## Implementation Order

Work in this sequence to minimise integration friction:
1. Backend service + API changes (shared by both surfaces)
2. Voice app frontend
3. Dashboard frontend
4. SSE wiring + readiness loop
5. Tests

---

## Phase 1: Backend — Service Layer

### [x] TASK-01: Extend `_spin_up_agent_for_persona` to accept `project_id`

**File:** `src/claude_headspace/services/channel_service.py`

Change signature from:
```python
def _spin_up_agent_for_persona(self, persona: Persona) -> Agent | None:
```
To:
```python
def _spin_up_agent_for_persona(self, persona: Persona, project_id: int | None = None) -> Agent | None:
```

- Remove: "find or reuse existing active agent" logic (lines ~1713-1717). S11 always creates fresh.
- Use `project_id` parameter for `create_agent(project_id=project_id, ...)` call
- If `project_id` is None, log a warning and return None (don't silently fall back to first project)
- Remove fallback `Project.query.first()` logic

Update all callers to pass `project_id`:
- `add_member()` — gets project_id from the membership's channel's project_id (or new `project_id` parameter)
- `promote_to_group()` — already passes project context; update call site

### [x] TASK-02: Add `create_channel_from_personas()` to `ChannelService`

**File:** `src/claude_headspace/services/channel_service.py`

New method:
```python
def create_channel_from_personas(
    self,
    creator_persona: Persona,
    channel_type: str,
    project_id: int,
    persona_slugs: list[str],
) -> Channel:
```

Steps:
1. Validate `persona_slugs` (non-empty list, each slug must resolve to an active Persona)
2. Load Project by `project_id`; raise `ProjectNotFoundError` if missing
3. Auto-generate name: join persona names with ` + ` (e.g. `Robbo + Con + Wado`)
4. Call existing `create_channel()` with `status="pending"`, generated name, `project_id`, no member_slugs/member_agent_ids
5. For each persona slug: call `_spin_up_agent_for_persona(persona, project_id=project_id)`; create ChannelMembership with `agent_id = None`
6. Inject initiation system message via `_post_system_message(channel, "Channel initiating...")`
7. Broadcast `channel_created` SSE (existing `_broadcast_channel_created`)
8. Return channel

New exception class: `ProjectNotFoundError(ChannelError)` — add alongside existing error classes at top of file.

### [x] TASK-03: Add `link_agent_to_pending_membership()` to `ChannelService`

**File:** `src/claude_headspace/services/channel_service.py`

New method:
```python
def link_agent_to_pending_membership(self, agent: Agent) -> None:
```

Steps:
1. If agent has no persona, return early
2. Query ChannelMembership where `persona_id = agent.persona_id` AND `agent_id IS NULL` AND channel status is `pending`; order by `joined_at` asc (oldest pending first)
3. If found: set `membership.agent_id = agent.id`; commit
4. Call `check_channel_ready(membership.channel_id)`
5. Log result

### [x] TASK-04: Add `check_channel_ready()` to `ChannelService`

**File:** `src/claude_headspace/services/channel_service.py`

New method:
```python
def check_channel_ready(self, channel_id: int) -> bool:
```

Steps:
1. Load Channel by id; return False if not found
2. If channel.status != "pending", return False
3. Count total memberships for channel (exclude chair — chair is operator, not an agent being spun up)
   - Actually: count all memberships where `persona_id` is NOT the operator persona
   - Or simpler: count memberships created by `create_channel_from_personas` — those with `is_chair=False` (agent members)
4. Count connected memberships: `agent_id IS NOT NULL` among the same set
5. Broadcast `channel_member_connected` SSE with connected/total counts
6. If all connected: call `_transition_to_active(channel)`, commit; inject go-signal system message; broadcast `channel_ready` SSE; return True
7. Return False

**SSE payloads:**
```python
# channel_member_connected
{
    "slug": channel.slug,
    "persona_name": membership.persona.name,
    "persona_slug": membership.persona.slug,
    "agent_id": agent.id,
    "connected_count": N,
    "total_count": M,
}

# channel_ready
{
    "slug": channel.slug,
    "name": channel.name,
}
```

Broadcast via:
```python
broadcaster.broadcast({"event": "channel_member_connected", ...})
broadcaster.broadcast({"event": "channel_ready", ...})
```

### [x] TASK-05: Extend `add_member()` to accept `project_id`

**File:** `src/claude_headspace/services/channel_service.py`

Change signature of `add_member()`:
```python
def add_member(
    self,
    slug: str,
    persona_slug: str,
    caller_persona: Persona,
    project_id: int | None = None,
) -> ChannelMembership:
```

- If `project_id` is None, fall back to `channel.project_id`
- Pass `project_id` to `_spin_up_agent_for_persona(persona, project_id=project_id)`
- Create membership with `agent_id = None` (agent is being spun up asynchronously)
- Broadcast `channel_member_added` SSE event (new event type, or reuse `channel_update`):
  ```python
  {"slug": slug, "persona_name": persona.name, "persona_slug": persona_slug, "agent_id": None}
  ```

---

## Phase 2: Backend — Hook Receiver Integration

### [x] TASK-06: Hook receiver calls `link_agent_to_pending_membership` on session-start

**File:** `src/claude_headspace/services/hook_receiver.py` (or `hook_agent_state.py`)

On session-start hook processing, after agent is created/resolved:
```python
channel_service = current_app.extensions.get("channel_service")
if channel_service and agent.persona_id:
    channel_service.link_agent_to_pending_membership(agent)
```

Locate the right insertion point: after `session_correlator` resolves/creates the agent, before returning success response.

---

## Phase 3: Backend — API Layer

### [x] TASK-07: Add `POST /api/channels` new persona-based creation path

**File:** `src/claude_headspace/routes/channels_api.py`

Extend `create_channel()` view to handle new payload shape:
```json
{
  "channel_type": "workshop",
  "project_id": 1,
  "persona_slugs": ["robbo", "con", "wado"]
}
```

Logic:
- If `persona_slugs` present in request: call `service.create_channel_from_personas()`
- If `name` present (old path): call `service.create_channel()` as before (backward compat for existing callers)
- Both paths return same `_channel_to_dict(channel)` response at 201

Add `ProjectNotFoundError` to `_ERROR_MAP`:
```python
ProjectNotFoundError: (404, "project_not_found"),
```

### [x] TASK-08: Extend `POST /api/channels/<slug>/members` with `project_id`

**File:** `src/claude_headspace/routes/channels_api.py`

In `add_member()` view:
```python
project_id = data.get("project_id")
if project_id is not None and not isinstance(project_id, int):
    return _error_response(400, "invalid_field", "project_id must be an integer")

membership = service.add_member(
    slug=slug,
    persona_slug=persona_slug,
    caller_persona=persona,
    project_id=project_id,
)
```

---

## Phase 4: Voice App Frontend

### [x] TASK-09: Redesign `#channel-picker` HTML in `voice.html`

**File:** `static/voice/voice.html`

Replace `#channel-picker` form body:
- Remove: `channel-name-input` text field
- Add: `<select id="channel-project-select">` (project single-select, required)
- Retain: `<select id="channel-type-select">` (type single-select)
- Replace: `#channel-member-list` → `<div id="channel-persona-list">` (persona checkboxes)
- Update CTA button text to `Create Channel (0 selected)` — JS updates count

Replace `#channel-chat-member-count` `<span>` with `<div id="channel-chat-member-pills">` in the channel chat header.

Shared bottom sheet (add-member mode):
- The same `#channel-picker` / `#channel-picker-backdrop` elements are reused
- A `data-mode` attribute on `#channel-picker` (value: `create` or `add-member`) controls CTA label and persona select multiplicity

### [x] TASK-10: Rewrite `openChannelPicker()` and `_submitCreateChannel()` in `voice-sidebar.js`

**File:** `static/voice/voice-sidebar.js`

`openChannelPicker(mode = 'create')`:
1. Set `data-mode` on `#channel-picker`
2. Reset project select, clear persona list
3. Fetch projects: `VoiceAPI.getProjects()` → populate `#channel-project-select`
4. On project change: fetch `VoiceAPI.getActivePersonas()` → `_renderPersonaCheckboxes(personas)` filtered/displayed for the selected project
5. Update CTA: `mode === 'create'` → "Create Channel"; `mode === 'add-member'` → "Add to Channel"
6. Wire persona checkbox changes to update CTA count label

Note: `/api/personas/active` returns all active personas regardless of project. For the project picker, all projects load; personas shown are all active ones (not project-filtered at this stage — projects are informational for the spin-up target). Implementer decision: show all active personas, user picks project to spin them under.

`_renderPersonaCheckboxes(personas, multiSelect = true)`:
- Render persona rows with `<input type="checkbox">` (multiSelect) or `<input type="radio">` (add-member)
- Include persona name and role as sub-label

`_submitCreateChannel()`:
- Collect `project_id` from `#channel-project-select`
- Collect `persona_slugs` from checked boxes (or radio for add-member)
- Collect `channel_type` from `#channel-type-select`
- Check mode: `create` → `VoiceAPI.createChannel(projectId, channelType, personaSlugs)` → close picker
- Check mode: `add-member` → `VoiceAPI.addChannelMember(currentSlug, personaSlug, projectId)` → close picker

### [x] TASK-11: Wire add-member action in `voice-channel-chat.js`

**File:** `static/voice/voice-channel-chat.js`

`case 'add-member':` — replace stub with:
```js
VoiceSidebar.openChannelPicker('add-member');
// Store current channel slug in VoiceState so _submitCreateChannel knows the target
VoiceState.addMemberTargetSlug = slug;
```

Replace member count display:
- Line ~82: `var memberCountEl = document.getElementById('channel-chat-member-count')` → update to `var memberPillsEl = document.getElementById('channel-chat-member-pills')`
- Lines ~103-105: `memberCountEl.textContent = ...` → call `_renderMemberPills(memberships)`

Add `_renderMemberPills(memberships)` function:
```js
function _renderMemberPills(memberships) {
    var container = document.getElementById('channel-chat-member-pills');
    if (!container) return;
    var html = '';
    var connected = 0, total = 0;
    for (var i = 0; i < memberships.length; i++) {
        var m = memberships[i];
        if (m.is_chair) continue; // operator pill optional — skip for now
        total++;
        var pending = !m.agent_id;
        if (!pending) connected++;
        var name = m.persona_name || m.persona_slug || 'Unknown';
        if (pending) {
            html += '<span class="channel-member-pill pending" title="' + name + ' (connecting...)">' + _esc(name) + '</span>';
        } else {
            html += '<button class="channel-member-pill" data-agent-id="' + m.agent_id + '" title="Focus ' + name + '">' + _esc(name) + '</button>';
        }
    }
    // Count text
    if (total > 0) {
        html += '<span class="channel-member-count">' + connected + ' of ' + total + ' online</span>';
    }
    container.innerHTML = html;
    // Bind focus clicks
    container.querySelectorAll('.channel-member-pill[data-agent-id]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            VoiceAPI.focusAgent(parseInt(btn.getAttribute('data-agent-id'), 10));
        });
    });
}
```

Add SSE handlers in the existing `onChannelUpdate` / SSE callback path:
```js
case 'channel_member_connected':
    _updateMemberPill(data.persona_slug, data.agent_id, data.connected_count, data.total_count);
    break;
case 'channel_ready':
    _showChannelSystemMessage('Channel ready — let\'s go.');
    _unlockChatInput();
    break;
```

### [x] TASK-12: Update `VoiceAPI.createChannel` and add `addChannelMember` in `voice-api.js`

**File:** `static/voice/voice-api.js`

```js
function createChannel(projectId, channelType, personaSlugs) {
    var body = {
        project_id: projectId,
        channel_type: channelType,
        persona_slugs: personaSlugs
    };
    return _fetchCookie('/api/channels', { method: 'POST', body: JSON.stringify(body) });
}

function addChannelMember(slug, personaSlug, projectId) {
    var body = { persona_slug: personaSlug };
    if (projectId) body.project_id = projectId;
    return _fetchCookie('/api/channels/' + encodeURIComponent(slug) + '/members', {
        method: 'POST',
        body: JSON.stringify(body)
    });
}
```

Expose `addChannelMember` in the return object.

### [x] TASK-13: Register `channel_member_connected` and `channel_ready` in `voice-sse-handler.js`

**File:** `static/voice/voice-sse-handler.js`

Add to the SSE event dispatch block:
```js
case 'channel_member_connected':
    if (typeof VoiceChannelChat !== 'undefined') {
        VoiceChannelChat.onMemberConnected(data);
    }
    break;
case 'channel_ready':
    if (typeof VoiceChannelChat !== 'undefined') {
        VoiceChannelChat.onChannelReady(data);
    }
    break;
```

Also register these event type strings in any event type whitelist.

### [x] TASK-14: Add styles in `voice.css`

**File:** `static/voice/voice.css`

```css
/* Persona picker in channel creation bottom sheet */
.channel-persona-list {
    max-height: 200px;
    overflow-y: auto;
}
.channel-persona-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    cursor: pointer;
}
.channel-persona-option input[type="checkbox"],
.channel-persona-option input[type="radio"] {
    flex-shrink: 0;
}
.channel-persona-role {
    font-size: 11px;
    color: var(--color-muted, #888);
}

/* Member pills in channel chat header */
.channel-chat-member-pills {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    padding: 4px 0;
}
.channel-member-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 500;
    background: var(--color-cyan, #00bcd4);
    color: var(--color-void, #0a0a0a);
    border: none;
    cursor: pointer;
    transition: opacity 0.15s;
}
.channel-member-pill.pending {
    background: var(--color-surface, #1a1a1a);
    color: var(--color-muted, #888);
    border: 1px solid var(--color-border, #333);
    cursor: default;
    opacity: 0.7;
}
.channel-member-count {
    font-size: 11px;
    color: var(--color-muted, #888);
    margin-left: 4px;
}
```

---

## Phase 5: Dashboard Frontend

### [x] TASK-15: Redesign `_channel_management.html` Create view

**File:** `templates/partials/_channel_management.html`

Replace the Create view content:
- Remove: `channel-create-name` input div
- Remove: `channel-create-description` textarea div
- Remove: `channel-member-autocomplete` div
- Add before type select: project picker `<select id="channel-create-project" class="form-well w-full px-3 py-2 text-sm" required><option value="">Select project...</option></select>`
- Retain: `channel-create-type` select
- Add after type: persona list `<div id="channel-create-persona-list" class="border border-border rounded overflow-y-auto" style="max-height:240px;"><!-- populated by JS --></div>`
- Update submit button: `<button type="submit" id="channel-create-submit-btn" ...>Create Channel</button>` — JS updates text with count

Also add an Add Member panel to `_channel_management.html` (or handle inline in `_channel_chat_panel.html`):
- The existing `#channel-chat-add-member` section in `_channel_chat_panel.html` contains `#channel-chat-add-member-picker` div — wire this to show a project + persona single-select form populated by JS.

### [x] TASK-16: Wire `channel-admin.js` to new creation flow

**File:** `static/js/channel-admin.js`

In `ChannelManagement.createChannel()`:
1. Read `project_id` from `#channel-create-project`
2. Read `persona_slugs` as array of checked box values in `#channel-create-persona-list`
3. Read `channel_type` from `#channel-create-type`
4. Validate: project required, at least one persona
5. POST `{project_id, channel_type, persona_slugs}` to `POST /api/channels`
6. On success: close modal, show success toast, refresh channel list

On tab switch to "Create New":
1. Fetch `/api/projects` → populate `#channel-create-project`
2. On project change: fetch `/api/personas/active` → render persona checkboxes in `#channel-create-persona-list`
3. On persona checkbox change: update submit button text with count

### [x] TASK-17: Wire `#channel-chat-add-member` in dashboard channel chat

**File:** `static/js/channel-admin.js` (or new `static/js/channel-chat.js` depending on where add-member lives)

In the existing `ChannelChat.toggleAddMember()` flow:
1. Fetch projects → populate project select in `#channel-chat-add-member-picker`
2. On project change: fetch active personas → render single-select radio list
3. On submit: POST `{persona_slug, project_id}` to `POST /api/channels/<slug>/members`
4. On success: close add-member panel, show toast

### [x] TASK-18: Register `channel_member_connected` and `channel_ready` SSE in dashboard

**File:** `static/js/channel-admin.js` (where SSE client events are bound)

In the SSE binding block (around line 598):
```js
global.sseClient.on('channel_member_connected', function(data) {
    ChannelChat.onMemberConnected(data);
});
global.sseClient.on('channel_ready', function(data) {
    ChannelChat.onChannelReady(data);
});
```

Also register in `static/js/sse-client.js` event type whitelist (around line 267).

### [x] TASK-19: Update `#channel-chat-member-pills` population in dashboard

**File:** `static/js/channel-admin.js` (wherever member pills are currently populated)

Verify `#channel-chat-member-pills` is populated from `GET /api/channels/<slug>/members` response.

Add `ChannelChat.onMemberConnected(data)`:
- Find the pending pill for `data.persona_slug`; update it to connected state; update count text

Add `ChannelChat.onChannelReady(data)`:
- Show system message in channel feed; enable chat input

---

## Phase 6: Add Custom CSS if Needed

### [x] TASK-20: Dashboard custom CSS for pending pill state (if needed)

**File:** `static/css/src/input.css`

If Tailwind `opacity-50`, `cursor-default`, `bg-surface`, `border-border` utility classes aren't sufficient for the pending pill visual, add a `.channel-member-pill-pending` custom class.

After any change, rebuild:
```bash
npx tailwindcss -i static/css/src/input.css -o static/css/main.css
```

---

## Phase 7: Tests

### [x] TASK-21: Service unit tests

**File:** `tests/services/test_channel_service_s11.py` (new)

Test:
- `create_channel_from_personas()`: creates pending channel, correct name, memberships with null agent_id, system message injected
- `link_agent_to_pending_membership()`: links agent, calls check_channel_ready
- `check_channel_ready()`: transitions to active when all linked; broadcasts channel_ready
- `_spin_up_agent_for_persona()` with project_id: no longer reuses existing agents

### [x] TASK-22: Route tests

**File:** `tests/routes/test_channels_api_s11.py` (new)

Test:
- `POST /api/channels` with `persona_slugs` + `project_id` → 201 + pending status
- `POST /api/channels` old `name` path still works (backward compat)
- `POST /api/channels/<slug>/members` with `project_id` → 201

---

## Acceptance Checklist

- [ ] Voice app: "+" button opens redesigned bottom sheet with project + persona multi-checkbox + type
- [ ] Voice app: creating a channel generates name from persona names, shows "Channel initiating..."
- [ ] Voice app: as agents connect, pills appear one by one (pending → connected state)
- [ ] Voice app: count text updates live ("1 of 3 online")
- [ ] Voice app: go-signal message appears, chat input unlocks when all connected
- [ ] Voice app: "Add member" kebab opens bottom sheet in add-member mode (single-select)
- [ ] Voice app: member pills clickable → focus API called
- [ ] Dashboard: "New Channel" opens redesigned popup with project + persona + type
- [ ] Dashboard: same progressive readiness as voice app
- [ ] Dashboard: add-member action shows project + persona single-select
- [ ] Dashboard: member pills in header, pending state visually distinct
- [ ] Backend: `POST /api/channels` with `persona_slugs` accepted; old `name` path still works
- [ ] Backend: `POST /api/channels/<slug>/members` accepts `project_id`
- [ ] Backend: session-start hook links agent to pending membership, triggers readiness check
- [ ] No schema migrations required
