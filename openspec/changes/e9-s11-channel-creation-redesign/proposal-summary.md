# Proposal Summary: E9-S11 Channel Creation Redesign + Member Pills

## Architecture Decisions

### 1. Persona-slugs API path, backward-compatible with name-based legacy path
`POST /api/channels` detects the new path by presence of `persona_slugs` field. The V0 `name`-based path is retained untouched. This avoids breaking any non-UI callers and keeps the route logic clean via a single `if "persona_slugs" in data:` branch.

### 2. Always-fresh agent spin-up — no reuse
`_spin_up_agent_for_persona()` removes the "find existing active agent" reuse logic from the S10 pattern. S11 extends S10's spin-up but makes freshness mandatory. The `project_id` parameter is required (not optional in practice) — if None is passed, the method returns None with a warning rather than silently spinning up under the wrong project.

### 3. Membership-first, then spin-up
`create_channel_from_personas()` creates all ChannelMembership records with `agent_id = null` BEFORE kicking off async agent spin-ups. This ensures the membership records exist for `link_agent_to_pending_membership()` to find when agents register. Race condition risk is minimal because the session-start hook arrives after the tmux process starts.

### 4. Readiness check triggered from session-start hook, not polled
Rather than a background poll for agent readiness, `link_agent_to_pending_membership()` is called synchronously in the session-start hook path (inside try/except). This is already the point where we know an agent has registered — no polling needed.

### 5. Shared bottom sheet per surface, parameterised by mode
Within each surface, the same component handles both creation and add-member. A `data-mode` attribute on `#channel-picker` (voice) or a JS mode variable (dashboard) controls multi-select vs. single-select and CTA label. No duplication.

### 6. Operator chair excluded from readiness counting
`check_channel_ready()` counts only non-chair memberships. The operator's chair membership links to the operator's active agent at creation time (existing behaviour); it does not participate in the pending → active readiness flow.

---

## Implementation Approach

Work in this order:
1. **Backend first** — service methods + API extension + hook receiver integration
2. **Voice app** — frontend changes, fully functional end-to-end against the updated backend
3. **Dashboard** — frontend changes, same backend
4. **SSE wiring** — integrated into each surface's build step, but test end-to-end last
5. **Tests** — run targeted tests after each phase

The backend is purely additive (new methods + new request path). No existing behaviour changes until `_spin_up_agent_for_persona` is modified — audit callers before changing that method.

---

## Files to Modify

### Backend
| File | Change |
|------|--------|
| `src/claude_headspace/services/channel_service.py` | New: `create_channel_from_personas`, `link_agent_to_pending_membership`, `check_channel_ready`, `ProjectNotFoundError`. Modified: `_spin_up_agent_for_persona(project_id)`, `add_member(project_id)` |
| `src/claude_headspace/routes/channels_api.py` | Extend `create_channel` view with persona-slugs path; extend `add_member` view with project_id; add `ProjectNotFoundError` to error map |
| `src/claude_headspace/services/hook_receiver.py` | Call `link_agent_to_pending_membership` in session-start hook path |

### Voice App (Standalone Static App — `static/voice/`)
| File | Change |
|------|--------|
| `static/voice/voice.html` | Redesign `#channel-picker` form (remove name input, add project select + persona list); replace `#channel-chat-member-count` span with `#channel-chat-member-pills` div |
| `static/voice/voice-sidebar.js` | Rewrite `openChannelPicker(mode)` and `_submitCreateChannel()`; add `_renderPersonaCheckboxes()` |
| `static/voice/voice-channel-chat.js` | Wire `add-member` case; replace member count with `_renderMemberPills()`; add `onMemberConnected()` and `onChannelReady()` |
| `static/voice/voice-api.js` | Update `createChannel(projectId, channelType, personaSlugs)`; add `addChannelMember(slug, personaSlug, projectId)` |
| `static/voice/voice-sse-handler.js` | Register `channel_member_connected` and `channel_ready` handlers |
| `static/voice/voice.css` | Styles: `.channel-persona-list`, `.channel-persona-option`, `.channel-member-pill`, `.channel-member-pill.pending`, `.channel-member-count` |

### Dashboard (Jinja + Tailwind + Dashboard JS)
| File | Change |
|------|--------|
| `templates/partials/_channel_management.html` | Redesign Create view: remove name/description/agent-autocomplete; add project select + persona checkbox list |
| `static/js/channel-admin.js` | Rewrite `createChannel()` with new payload; add project/persona loading; wire add-member project picker; add `onMemberConnected()` and `onChannelReady()` SSE handlers |
| `static/js/sse-client.js` | Add `channel_member_connected`, `channel_ready`, `channel_member_added` to event type whitelist |
| `static/css/src/input.css` | Add `.channel-member-pill-pending` custom CSS if Tailwind utilities insufficient |

### Tests
| File | Change |
|------|--------|
| `tests/services/test_channel_service_s11.py` | New: service unit tests for all 3 new methods + modified methods |
| `tests/routes/test_channels_api_s11.py` | New: route tests for extended `POST /api/channels` and `POST /api/channels/<slug>/members` |

---

## Acceptance Criteria

From PRD Section 3 (Functional Success Criteria):

1. Channel creation in both surfaces shows project picker + persona multi-checkbox — NOT the V0 name/type/agents form
2. Each selected persona results in one new agent — no reuse of existing agents
3. Channel status is `pending` and chat input is disabled until all agents connected
4. System message "Channel initiating..." (implementer wording) injected immediately on creation
5. As each agent connects, their pill appears progressively in the header (both surfaces)
6. Header member count reflects live state: "1 of 3 online" → "3 of 3 online"
7. When all agents connected: go-signal system message injected, chat input enabled
8. If spin-up fails: system message with failure detail; channel stays pending
9. "Add member" in both surfaces opens real picker (project + persona single-select) — NOT stub/project-unaware
10. Selected project in add-member may differ from channel's original project
11. Channel chat header in both surfaces shows per-member pills (not plain count)
12. Each connected pill clicks to focus API
13. Pending pills (agent not yet connected) visually distinct from connected pills

---

## Constraints and Gotchas

### No Schema Migrations
- `ChannelMembership.agent_id` is already nullable — confirmed in model
- `Channel.status = 'pending'` is the default — confirmed in model
- No new columns needed

### `_spin_up_agent_for_persona` Caller Audit
Before removing the "reuse existing agent" logic, verify all callers:
- `add_member()` — pass `project_id or channel.project_id`
- `promote_to_group()` — pass `agent.project_id` (already available)
- Any other internal callers — check grep before modifying

### Hook Receiver Insertion Point
The `link_agent_to_pending_membership()` call must happen AFTER the agent is persisted and its `persona_id` is set. Find the correct insertion point in `hook_receiver.py` — likely after `session_correlator` resolves the agent. Must be wrapped in try/except.

### Voice App Architecture
The voice app is NOT a Jinja template. It is a standalone static HTML/JS/CSS app in `static/voice/`. Never reference dashboard JS files. All voice app changes stay within `static/voice/`.

### Tailwind CSS — Dashboard Only
Voice app uses `voice.css` for all custom styles. Dashboard uses Tailwind utility classes for pill styling; add custom CSS to `static/css/src/input.css` only if utilities are insufficient. After any `input.css` change, run:
```bash
npx tailwindcss -i static/css/src/input.css -o static/css/main.css
```
And verify custom class selectors are present in the output.

### Dashboard `#channel-chat-member-pills` Already in HTML
The `_channel_chat_panel.html` already has `<div id="channel-chat-member-pills">` in Row 2 of the header. The JS population is what needs to be wired — the HTML container is already there.

### Backward Compatibility of `POST /api/channels`
The V0 `name`-based path must remain functional. The branch in the view is:
```python
if "persona_slugs" in data:
    # S11 path
else:
    # V0 path (unchanged)
```

### SSE Event Type Whitelist
`static/js/sse-client.js` has an event type array around line 267. New event types must be registered there or they will be silently dropped.

---

## Git Change History

### Related Files — Recent Commits
- `a74a354` — `src/claude_headspace/services/channel_service.py`, `routes/channels_api.py` — E9-S10 promote-to-group: established always-spin-up pattern. Reference `promote_to_group()` and `_spin_up_agent_for_persona()` for patterns to follow/extend.
- `a44e418` — `templates/partials/_channel_management.html`, `static/js/channel-admin.js` — E9-S9 channel admin page: the creation form being superseded. Reference this commit for what's being replaced.
- `03e8607`, `09b2e57` — `channel_service.py` — channel protocol injection (recent, non-conflicting)
- Voice app channel chat: established in E9-S8 (`static/voice/voice-channel-chat.js`, `voice-sse-handler.js`)

### OpenSpec History
- No prior OpenSpec changes for this change-name. Clean slate.
- Related closed changes: `e9-s3-channel-data-model`, `e9-s4-channel-service-cli`, `e9-s5-api-sse-endpoints`, `e9-s9-channel-admin-page`, `e9-s10-promote-to-group`

### Patterns Established by Prior Sprints
- Always-spin-up pattern: `channel_service.py::promote_to_group()` → `_spin_up_agent_for_persona()`
- SSE broadcast: `_broadcast_update(channel, event_type, payload_dict)`
- System message injection: `_post_system_message(channel, content)`
- Bottom sheet pattern (voice): `#channel-picker` + `#channel-picker-backdrop` in `voice.html`; open/close in `voice-sidebar.js`

---

## Q&A History

**Q: Is `Channel.status = 'pending' → 'active'` transition already wired?**
A: `_transition_to_active()` exists in `channel_service.py` (line 1644) and transitions `pending → active`. It is called from `create_channel()` when member_agent_ids or member_slugs are provided (line 224). S11 adds a new call path from `check_channel_ready()`.

**Q: Does `/api/personas/active` filter by project?**
A: No — it returns all active personas system-wide, not project-filtered. The project picker in the creation form is the spin-up target project, not a filter for persona visibility. Operators see all personas and choose which project to spin them under. This is the implementer decision for the picker UX.

**Q: Does `_spin_up_agent_for_persona` reuse existing agents in S10?**
A: Yes, currently (lines 1713-1717). S11 removes this reuse — always fresh. The S10 `promote_to_group()` method ALSO always creates fresh (it does not call `_spin_up_agent_for_persona`, it calls `create_agent` directly). S11 aligns `_spin_up_agent_for_persona` to the same always-fresh philosophy.

**Q: Does the dashboard `#channel-chat-member-pills` div already exist?**
A: Yes — `templates/partials/_channel_chat_panel.html` line 88 has `<div id="channel-chat-member-pills">` in Row 2 of the header. JS population is the missing piece.

---

## Dependencies

### Python/Backend
- No new pip packages required
- `create_agent` from `agent_lifecycle.py` — already used by `_spin_up_agent_for_persona`
- `advisory_lock` pattern already available if needed for `check_channel_ready` (follow `_auto_complete_if_empty` pattern)

### Frontend
- No new npm packages required
- `VoiceChatRenderer.esc()` available for HTML escaping in voice app
- `ConfirmDialog` available in voice app for any modal prompts

### APIs Used by S11
- `GET /api/projects` — already exists
- `GET /api/personas/active` — already exists, used by voice app for persona picker
- `POST /api/focus/<agent_id>` — already exists, used by pill click-through

---

## Testing Strategy

### Targeted Tests (Default — Run These)
```bash
pytest tests/services/test_channel_service_s11.py
pytest tests/routes/test_channels_api_s11.py
```

### What to Test

**Service tests (`test_channel_service_s11.py`)**:
- `create_channel_from_personas`: creates pending channel, correct name, null-agent memberships, system message
- `link_agent_to_pending_membership`: links correct membership, calls check_channel_ready
- `check_channel_ready`: transitions to active when all linked; broadcasts channel_ready; stays pending when not all linked
- `_spin_up_agent_for_persona(project_id=...)`: no reuse, calls create_agent with project_id; returns None if project_id=None

**Route tests (`test_channels_api_s11.py`)**:
- `POST /api/channels` with `persona_slugs` + `project_id` → 201, pending status
- `POST /api/channels` with `name` (legacy) → still works (backward compat)
- `POST /api/channels` with `persona_slugs` but no `project_id` → 400
- `POST /api/channels/<slug>/members` with `project_id` → 201
- `POST /api/channels/<slug>/members` without `project_id` → 201 (uses channel project)

**Manual verification after implementation**:
1. Voice app: create a channel from persona picker → verify pending state, pills, go-signal, input unlock
2. Voice app: add member from kebab → verify real picker opens (not stub)
3. Dashboard: create channel from management modal → same flow
4. Dashboard: add member → verify project picker present

---

## OpenSpec References

- Proposal: `openspec/changes/e9-s11-channel-creation-redesign/proposal.md`
- Tasks: `openspec/changes/e9-s11-channel-creation-redesign/tasks.md`
- Spec: `openspec/changes/e9-s11-channel-creation-redesign/spec.md`
- Delta specs:
  - `openspec/changes/e9-s11-channel-creation-redesign/specs/channel-creation-api/spec.md`
  - `openspec/changes/e9-s11-channel-creation-redesign/specs/channel-service/spec.md`
  - `openspec/changes/e9-s11-channel-creation-redesign/specs/channel-sse-events/spec.md`
  - `openspec/changes/e9-s11-channel-creation-redesign/specs/voice-app-channel-creation/spec.md`
  - `openspec/changes/e9-s11-channel-creation-redesign/specs/dashboard-channel-creation/spec.md`
  - `openspec/changes/e9-s11-channel-creation-redesign/specs/member-pills/spec.md`
