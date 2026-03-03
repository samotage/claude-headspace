# Proposal: e9-s7-dashboard-ui

## Why

The channel infrastructure (data model, service layer, API, SSE events, delivery engine) is complete from Sprints 2-6, but the operator has no way to see or interact with channels from the dashboard. This sprint builds the frontend surface: channel cards at the top of the dashboard, a slide-out chat panel for reading and sending messages, a management modal for channel CRUD, and SSE integration for real-time updates.

## What Changes

- Add channel cards section to the dashboard, positioned above all project sections in all three view modes
- Each card displays channel name, type badge, member list, status indicator, and last message preview
- Real-time card updates via `channel_message` and `channel_update` SSE event handlers
- Slide-out chat panel (right edge, 440px) with full message feed, send input, and scroll management
- Chat panel supports optimistic message rendering, cursor-based pagination, and smart auto-scroll
- Channel management modal with channel list, create form, complete/archive actions
- Dashboard route handler extended to provide `channel_data` template context variable
- SSE client `commonTypes` extended with `channel_message` and `channel_update` event types
- Three new JS modules: `channel-cards.js`, `channel-chat.js`, `channel-management.js`
- Three new Jinja2 partials: `_channel_cards.html`, `_channel_chat_panel.html`, `_channel_management.html`
- Custom CSS for chat panel slide-out animation and channel-specific styling in `input.css`

## Impact

### Affected specs
- None directly modified -- this sprint creates new frontend components that consume existing S5 API endpoints and SSE events

### Affected code

**Modified files:**
- `templates/dashboard.html` -- add channel card and chat panel partial includes, management JS script tags
- `static/js/sse-client.js` -- add `channel_message` and `channel_update` to `commonTypes` array
- `static/css/src/input.css` -- add channel card, chat panel, and management custom CSS
- `src/claude_headspace/routes/dashboard.py` -- add `get_channel_data_for_operator()` and pass to template context

**New files:**
- `templates/partials/_channel_cards.html` -- channel cards section partial
- `templates/partials/_channel_chat_panel.html` -- slide-out chat panel partial
- `templates/partials/_channel_management.html` -- management modal partial
- `static/js/channel-cards.js` -- channel card rendering and SSE handlers
- `static/js/channel-chat.js` -- chat panel open/close, message feed, send, scroll management
- `static/js/channel-management.js` -- management modal interactions

### Breaking changes
None -- channel cards section is conditionally rendered only when the operator has active channel memberships. Dashboard renders identically to pre-channel state when no channels exist.
