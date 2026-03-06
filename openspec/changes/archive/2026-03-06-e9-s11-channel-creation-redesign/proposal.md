## Why

Channel creation currently requires agents to already be running before a channel can be created — a V0 delivery shortcut. The designed intent is that channel creation is self-contained: the operator picks a project and selects personas, and the system spins up new agents automatically. Additionally, the voice app's "Add member" action is a stub, and both surfaces show a plain member count with no per-member identity or focus link. This sprint delivers the full designed experience across both the voice app and the dashboard.

## What Changes

- **Channel creation redesign — both surfaces**: Replace V0 name/type/agents form with project picker + persona multi-checkbox in the voice app bottom sheet and the dashboard channel creation popup. Channel name auto-generated from persona names. New `POST /api/channels` path accepts `persona_slugs[]` + `project_id`; legacy `name` path retained for backward compatibility.
- **Wire voice app "Add member" stub**: `voice-channel-chat.js` add-member stub replaced with the creation bottom sheet in single-select mode. Dashboard add-member flow gets a project picker for cross-project support.
- **Per-member pills — both surfaces**: Replace plain member count with per-member pills in channel chat headers. Pending pills (agent not yet connected) visually distinct; connected pills clickable to focus API. Real-time updates via SSE.
- **Channel readiness model**: Channel stays `pending` until all agents connect. Chat input locked in pending state. Progressive pill appearance as agents connect. Go-signal system message and input unlock when all ready.
- **New SSE events**: `channel_member_connected`, `channel_ready`, `channel_member_added` broadcast from ChannelService.
- **Hook receiver integration**: session-start hook links newly-registered agents to pending channel memberships and triggers the readiness check.

## Impact

- Affected specs: channel creation API, channel service, hook receiver, voice app channel creation, dashboard channel management, member pills, SSE events
- Affected code:
  - `src/claude_headspace/services/channel_service.py` — new `create_channel_from_personas()`, `link_agent_to_pending_membership()`, `check_channel_ready()`; extended `_spin_up_agent_for_persona(project_id)` and `add_member(project_id)`
  - `src/claude_headspace/routes/channels_api.py` — extend `POST /api/channels` with persona-slugs path; extend `POST /api/channels/<slug>/members` with `project_id`
  - `src/claude_headspace/services/hook_receiver.py` — call `link_agent_to_pending_membership` on session-start
  - `static/voice/voice.html` — redesign `#channel-picker` form; replace `#channel-chat-member-count` with `#channel-chat-member-pills`
  - `static/voice/voice-sidebar.js` — rewrite `openChannelPicker()` and `_submitCreateChannel()`
  - `static/voice/voice-channel-chat.js` — wire add-member; replace member count with pills
  - `static/voice/voice-api.js` — update `createChannel()` signature; add `addChannelMember()`
  - `static/voice/voice-sse-handler.js` — handle `channel_member_connected` and `channel_ready`
  - `static/voice/voice.css` — styles for persona list, member pills, pending state
  - `templates/partials/_channel_management.html` — redesign create view with project + persona picker
  - `static/js/channel-admin.js` — creation form submit with new payload; add-member project picker; SSE pill updates
  - `static/js/sse-client.js` — register new event types in whitelist
  - `static/css/src/input.css` — custom CSS for dashboard pending pill state if needed
  - `tests/services/test_channel_service_s11.py` — service unit tests (new)
  - `tests/routes/test_channels_api_s11.py` — route tests (new)
- Related git context:
  - E9-S10 `a74a354` established the always-spin-up agent pattern (used by S11)
  - E9-S9 `a44e418` set the S9 channel creation form that S11 supersedes on dashboard
  - E9-S8 established voice app channel chat panel (S11 extends)
  - E9-S5 defined `POST /api/channels/<slug>/members` without project_id (S11 extends)
