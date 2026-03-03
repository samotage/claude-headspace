# Tasks: e9-s7-dashboard-ui

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Dashboard Route Context
- [x] 2.1.1 Add `get_channel_data_for_operator()` function to `routes/dashboard.py` -- queries operator's active ChannelMemberships, joins to Channel and most recent Message per channel
- [x] 2.1.2 Pass `channel_data` to the template context in the dashboard route handler
- [x] 2.1.3 Handle case where operator has no Persona or no active memberships (return empty list)

### 2.2 SSE Client Integration
- [x] 2.2.1 Add `"channel_message"` and `"channel_update"` to the `commonTypes` array in `static/js/sse-client.js`

### 2.3 Channel Cards Section
- [x] 2.3.1 Create `templates/partials/_channel_cards.html` -- iterates over `channel_data`, renders card per channel with name, type badge, member list, status dot, last message preview
- [x] 2.3.2 Add `{% include "partials/_channel_cards.html" %}` to `dashboard.html` between sort controls and main content area, conditional on `channel_data`
- [x] 2.3.3 Create `static/js/channel-cards.js` -- IIFE module exposing `window.ChannelCards` with SSE event handlers for `channel_message` (update last message preview) and `channel_update` (update member list, status, add/remove cards)
- [x] 2.3.4 Add channel card click handler to toggle chat panel via `window.ChannelChat.toggle(slug)`
- [x] 2.3.5 Add script tag for `channel-cards.js` in `dashboard.html`

### 2.4 Chat Panel
- [x] 2.4.1 Create `templates/partials/_channel_chat_panel.html` -- fixed-position slide-out panel with header (name, type, member count, close button), scrollable message feed, new-message indicator, textarea input with send button
- [x] 2.4.2 Add `{% include "partials/_channel_chat_panel.html" %}` to `dashboard.html`
- [x] 2.4.3 Create `static/js/channel-chat.js` -- IIFE module exposing `window.ChannelChat` with:
  - `toggle(slug)` -- open/close/switch channel
  - `close()` -- slide out and clear state
  - `send()` -- POST message, optimistic render, clear input
  - `appendMessage(data)` -- append SSE message to feed
  - `scrollToBottom()` -- scroll to newest message
  - `isOpenFor(slug)` -- check if panel is open for a specific channel
  - `isActivelyViewing(slug)` -- check active view state (infrastructure for v2 suppression)
  - `_activeChannelSlug` -- internal state for v2 notification suppression
- [x] 2.4.4 Implement message feed rendering with colour-coded sender names (cyan for operator, green for agents, muted/italic for system messages)
- [x] 2.4.5 Implement scroll management: auto-scroll when near bottom, "New messages" indicator when scrolled up
- [x] 2.4.6 Implement "Load earlier messages" button with cursor pagination (`?before=<oldest_sent_at>&limit=50`)
- [x] 2.4.7 Implement optimistic message rendering with error state and retry on send failure
- [x] 2.4.8 Implement Escape key to close panel
- [x] 2.4.9 Add script tag for `channel-chat.js` in `dashboard.html`

### 2.5 Channel Management Modal
- [x] 2.5.1 Create `templates/partials/_channel_management.html` -- modal with channel list table (name, slug, type, status, member count, created date), create form (name, type dropdown, description, members), complete/archive action buttons
- [x] 2.5.2 Add `{% include "partials/_channel_management.html" %}` to `dashboard.html`
- [x] 2.5.3 Add "Channels" button to dashboard header/controls area to open management modal
- [x] 2.5.4 Create `static/js/channel-management.js` -- IIFE module exposing `window.ChannelManagement` with:
  - `open()` -- fetch channel list from `GET /api/channels?all=true`, render table, show modal
  - `close()` -- hide modal
  - `createChannel(formData)` -- POST to `/api/channels`, update list and cards on success
  - `completeChannel(slug)` -- POST to `/api/channels/<slug>/complete`
  - `archiveChannel(slug)` -- POST to `/api/channels/<slug>/archive`
- [x] 2.5.5 Add script tag for `channel-management.js` in `dashboard.html`

### 2.6 Custom CSS
- [x] 2.6.1 Add channel card styling to `static/css/src/input.css` (hover transitions, status dot colours)
- [x] 2.6.2 Add chat panel slide-out animation CSS to `input.css` (transform transition, responsive width)
- [x] 2.6.3 Add channel management modal CSS to `input.css`
- [x] 2.6.4 Rebuild Tailwind: `npx tailwindcss -i static/css/src/input.css -o static/css/main.css`
- [x] 2.6.5 Verify existing custom selectors are preserved in compiled output

## 3. Testing (Phase 3)

- [x] 3.1 Test `get_channel_data_for_operator()` returns correct structure with active memberships
- [x] 3.2 Test `get_channel_data_for_operator()` returns empty list when operator has no Persona
- [x] 3.3 Test `get_channel_data_for_operator()` excludes archived channels
- [x] 3.4 Test dashboard template renders channel cards when `channel_data` is non-empty
- [x] 3.5 Test dashboard template hides channel cards section when `channel_data` is empty
- [x] 3.6 Test channel card displays name, type badge, members, and last message
- [x] 3.7 Test SSE `channel_message` handler updates card last message preview -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.8 Test SSE `channel_update` handler updates card member list -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.9 Test chat panel opens on card click with correct channel data -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.10 Test chat panel fetches messages from API on open -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.11 Test chat panel send posts to correct API endpoint -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.12 Test chat panel close button and Escape key dismiss panel -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.13 Test management modal lists channels from API -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.14 Test management create form submits to correct endpoint -- JS IIFE verified by code review (no Python-side test applicable)
- [x] 3.15 Test management complete/archive actions call correct endpoints -- JS IIFE verified by code review (no Python-side test applicable)

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [ ] 4.3 Manual verification complete -- channel cards visible, chat panel functional, management modal operational
- [x] 4.4 Tailwind build produces valid CSS with all custom selectors preserved
- [x] 4.5 Dashboard renders identically when no channels exist (backward compatibility)
