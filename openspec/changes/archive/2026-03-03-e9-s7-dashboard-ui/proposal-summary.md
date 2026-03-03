# Proposal Summary: e9-s7-dashboard-ui

## Architecture Decisions
- Channel cards positioned above all project sections in all three view modes (project, priority, Kanban)
- Slide-out chat panel overlays from the right (440px desktop, full-width mobile) -- no layout push
- Channel management implemented as a modal (Option A) matching existing waypoint editor/brain reboot patterns
- All functionality is frontend-only: Jinja2 templates, vanilla JS (IIFE modules), Tailwind CSS
- No new backend routes, blueprints, or services -- consumes existing S5 API endpoints and SSE events
- Dashboard route handler extended with `get_channel_data_for_operator()` for server-rendered initial state
- Real-time updates via `channel_message` and `channel_update` SSE events on existing stream
- v1 notification suppression relies on 30-second per-channel rate limit from S6; active view suppression deferred to v2
- Optimistic message rendering with error state and retry on send failure

## Implementation Approach
- Add `get_channel_data_for_operator()` to `routes/dashboard.py` -- queries operator's Persona, active ChannelMemberships, Channel + last Message per channel
- Create three Jinja2 partials: `_channel_cards.html`, `_channel_chat_panel.html`, `_channel_management.html`
- Include partials in `dashboard.html` between sort controls and main content area (conditional on `channel_data`)
- Create three vanilla JS IIFE modules: `channel-cards.js` (`window.ChannelCards`), `channel-chat.js` (`window.ChannelChat`), `channel-management.js` (`window.ChannelManagement`)
- Register `channel_message` and `channel_update` in SSE client `commonTypes` array
- Handlers registered via `window.sseClient.on()` in `channel-cards.js`
- Chat panel maintains `_activeChannelSlug` variable as infrastructure for v2 notification suppression
- Custom CSS added to `input.css` for slide-out animation, channel card hover states, responsive widths

## Files to Modify

### Modified Files
- `templates/dashboard.html` -- add partial includes, script tags for new JS modules
- `static/js/sse-client.js` -- add `channel_message` and `channel_update` to `commonTypes` array
- `static/css/src/input.css` -- add channel card, chat panel, management modal custom CSS
- `src/claude_headspace/routes/dashboard.py` -- add `get_channel_data_for_operator()`, pass to template context

### New Files (Templates)
- `templates/partials/_channel_cards.html` -- channel cards section, server-rendered from `channel_data`
- `templates/partials/_channel_chat_panel.html` -- slide-out chat panel container
- `templates/partials/_channel_management.html` -- channel management modal

### New Files (JavaScript)
- `static/js/channel-cards.js` -- card rendering, SSE handlers, card click delegation
- `static/js/channel-chat.js` -- chat panel open/close/toggle, message feed, send, scroll management
- `static/js/channel-management.js` -- management modal open/close, create form, lifecycle actions

### Tests
- Route tests for `get_channel_data_for_operator()` (operator with/without Persona, with/without memberships, archived channel exclusion)
- Template rendering tests (cards visible/hidden based on `channel_data`)

## Acceptance Criteria
- Channel cards appear at the top of the dashboard for operators with active channel memberships
- Each card displays name, type badge, members, status indicator, and last message preview
- Clicking a card opens a slide-out chat panel with the channel's message feed
- Chat panel supports sending messages, optimistic rendering, scroll management, and "Load earlier" pagination
- SSE events update cards and chat panel in real-time without page reload
- Channel management modal provides create, complete, and archive operations
- Dashboard renders identically when no channels exist (backward compatibility)
- No new npm dependencies, no new backend routes or services

## Constraints and Gotchas
- S5 API endpoints (`/api/channels/*`) and SSE event types (`channel_message`, `channel_update`) must be functional before this sprint can be built
- Operator identity for messages is resolved server-side from Flask session -- no client-side identity management needed
- S1 (Handoff Improvements) also modifies `sse-client.js` `commonTypes` -- building agents should check for prior modifications and append
- Chat panel z-index 50 must not conflict with existing dashboard overlays (toast, modals)
- Tailwind build must preserve all existing custom selectors in `input.css`
- `form-well` class used for chat textarea must exist in `input.css`

## Git Change History

### Related Files
- `templates/dashboard.html` -- existing dashboard template with view modes, sort controls, partial includes
- `static/js/sse-client.js` -- existing SSE client with `commonTypes` array and `on()` handler registration
- `static/js/dashboard-sse.js` -- existing SSE handler registration pattern to follow
- `static/css/src/input.css` -- Tailwind source CSS with custom properties and classes
- `src/claude_headspace/routes/dashboard.py` -- existing dashboard route handler

### OpenSpec History
- `e9-s3-data-model` -- Channel, ChannelMembership, Message models
- `e9-s4-service-layer` -- ChannelService methods
- `e9-s5-api-sse` -- REST API endpoints, SSE event types
- `e9-s6-delivery-engine` -- Delivery engine, notification rate limiting

### Implementation Patterns
- Jinja2 partials: `{% include "partials/_*.html" %}` pattern from objective banner, header, etc.
- SSE handlers: `sseClient.on(type, handler)` pattern from `dashboard-sse.js`
- IIFE modules: `(function(global) { ... })(window)` pattern from all existing JS files
- Global APIs: `window.FocusAPI`, `window.BrainReboot` pattern
- Modal pattern: waypoint editor, brain reboot modal show/hide
- Card styling: `bg-elevated`, `rounded-lg`, `border-border` from existing dashboard cards
- Form inputs: `.form-well` class from `input.css`
- Toast feedback: existing `partials/_toast.html` system

## Q&A History
- No clarifications needed -- PRD was comprehensive with resolved design decisions from the Inter-Agent Communication Workshop

## Dependencies

### Sprint Dependencies (Must Be Complete)
- E9-S3: Channel data model (Channel, ChannelMembership, Message tables)
- E9-S4: ChannelService (CRUD, messaging service methods)
- E9-S5: API + SSE endpoints (`/api/channels/*`, `channel_message`/`channel_update` SSE events)
- E9-S6: Delivery engine (fan-out delivery, per-channel notification rate limiting)

### Existing Infrastructure (Already Available)
- SSE broadcaster and client
- NotificationService with rate limiting pattern
- Dashboard template with view modes and partial includes
- Tailwind CSS build pipeline

## Testing Strategy

### Route Tests
- `get_channel_data_for_operator()` returns correct structure with active memberships
- Returns empty list when operator has no Persona
- Returns empty list when operator has no active memberships
- Excludes archived channels from results

### Template Tests
- Dashboard renders channel cards section when `channel_data` is non-empty
- Dashboard hides channel cards section when `channel_data` is empty

### Integration Tests (If Needed)
- Channel card displays correct content from `channel_data`
- Chat panel loads messages from API
- Send message posts to correct endpoint

## OpenSpec References
- proposal.md: openspec/changes/e9-s7-dashboard-ui/proposal.md
- tasks.md: openspec/changes/e9-s7-dashboard-ui/tasks.md
- specs:
  - openspec/changes/e9-s7-dashboard-ui/specs/channel-cards/spec.md
  - openspec/changes/e9-s7-dashboard-ui/specs/channel-chat-panel/spec.md
  - openspec/changes/e9-s7-dashboard-ui/specs/channel-management/spec.md
  - openspec/changes/e9-s7-dashboard-ui/specs/dashboard-route/spec.md
  - openspec/changes/e9-s7-dashboard-ui/specs/sse-integration/spec.md
