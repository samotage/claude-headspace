---
validation:
  status: valid
  validated_at: '2026-03-03T14:26:27+11:00'
---

## Product Requirements Document (PRD) — Dashboard UI: Channel Cards, Chat Panel, Management

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 7 — Dashboard channel cards, chat panel, management tab, notification integration
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The channel infrastructure (data model, service layer, API, SSE events, delivery engine) is built in Sprints 2-6. The operator still has no way to see or interact with channels from the dashboard. This sprint builds the frontend: channel cards at the top of the dashboard, a chat panel for reading and sending messages, a management tab for channel CRUD, and macOS notification integration with per-channel rate limiting.

Channel cards sit above all project sections on the dashboard. Each active channel the operator has joined shows its name, member list, and last message. Clicking a card opens a slide-out chat panel with the full message feed and an input box for sending. A management tab provides create/view/archive operations. All updates arrive in real-time via `channel_message` and `channel_update` SSE events on the existing `/api/events/stream` endpoint.

Notifications fire via the existing `NotificationService` with a new per-channel rate limiter (30 seconds per channel, configurable). When the operator is actively viewing a channel's chat panel, notifications for that channel are suppressed.

This sprint produces no new backend services, models, or API endpoints. It consumes the API from Sprint 5 and handles the SSE events defined there. All work is in Jinja2 templates, vanilla JavaScript modules, and Tailwind CSS.

All design decisions are resolved in the Inter-Agent Communication Workshop: Section 1.1 (UI/UX Context), Section 3.4 (Operator Delivery), and Section 4 (Group Workshop Use Case). See `docs/workshop/interagent-communication/sections/`.

---

## 1. Context & Purpose

### 1.1 Context

The channel system has a complete backend: data model (S3), service layer (S4), REST API and SSE events (S5), and delivery engine (S6). Agents can create channels, send messages, and receive fan-out delivery via tmux. The operator can use the CLI and voice bridge to participate. But the dashboard -- the operator's primary monitoring surface -- has no channel awareness.

The existing dashboard layout (`templates/dashboard.html`) has three view modes: project (Kanban columns per project), priority (flat agent list), and Kanban (commands by lifecycle state). All views focus on individual agents. Channels are cross-project, cross-agent constructs that need their own dedicated space.

The existing SSE infrastructure (`static/js/sse-client.js`) supports typed event handlers with `sseClient.on(eventType, handler)`. The dashboard SSE integration (`static/js/dashboard-sse.js`) handles `card_refresh`, `state_transition`, `turn_created`, and other event types. Adding `channel_message` and `channel_update` handlers follows the same pattern.

The existing `NotificationService` (`src/claude_headspace/services/notification_service.py`) provides macOS notifications via `terminal-notifier` with per-agent rate limiting (a dict of `agent_id -> last_notification_time`). Channel notifications need per-channel rate limiting -- same mechanism, different key.

### 1.2 Target User

The operator (Sam), who monitors multiple agents across projects and needs to see channel conversations, participate in workshops, and manage channel lifecycle -- all from the dashboard without switching to the terminal.

### 1.3 Success Moment

Sam opens the dashboard. Above all project columns, he sees two channel cards: "persona-alignment" with Robbo and Paula, and "api-redesign" with Con and Gavin. The persona-alignment card shows Paula's last message: "I disagree with the skill injection approach..." Sam clicks it. A chat panel slides out from the right showing the full conversation. He types "Paula raises a good point. Robbo, thoughts?" in the input box, hits Enter, and the message appears in the feed. Robbo's agent receives it via tmux. When Robbo responds, the message appears in Sam's chat panel in real-time. Meanwhile, a macOS notification pops up for the api-redesign channel -- Con asked a question 30 seconds ago and Sam hasn't looked at that channel yet.

---

## 2. Scope

### 2.1 In Scope

- Channel cards section at the top of the dashboard, above all project sections
- Each active channel card: channel name, member list (persona names), last message preview
- Real-time card updates via `channel_message` and `channel_update` SSE events
- Click channel card to open a slide-out chat panel
- Chat panel: full message feed (chat-style), scrollable, newest at bottom
- Chat panel input box: text input at bottom, sends via POST to `/api/channels/<slug>/messages`
- Chat panel operator identity: messages posted with operator's Persona, `agent_id = NULL`
- Chat panel close button to dismiss the panel
- Channel management tab: create, view, archive channels via `/api/channels` endpoints
- New JS module for channel SSE event handling (`channel-cards.js` or similar)
- New Jinja2 partial for channel cards section (`partials/_channel_cards.html`)
- New Jinja2 partial or template section for chat panel (`partials/_channel_chat_panel.html`)
- macOS notification integration: channel messages trigger notifications via S6's delivery engine (server-side, already implemented)
- Notification suppression when operator is actively viewing the channel's chat panel (frontend focus flag — v1 uses 30-second rate limit as sufficient floor; active view suppression is v2)
- CSS styling consistent with existing dashboard theme (dark, monospace, Tailwind utilities)

### 2.2 Out of Scope

- Channel data models (S3 -- already built)
- ChannelService (S4 -- already built)
- API endpoints (S5 -- already built; this sprint CALLS them)
- SSE event type definitions (S5 -- already defined; this sprint HANDLES them)
- Delivery engine (S6 -- already built)
- Voice bridge channel routing (S8)
- Voice Chat PWA channel integration (S8 or future)
- Per-recipient delivery tracking or read receipts (v2)
- Decision extraction / LLM summarisation of channel history (future)
- Message threading or reply-to (v2)
- Unread message counts or badges (v2 -- no per-recipient tracking in v1 data model)
- Channel-specific SSE streams (not needed -- single stream with type filtering per Decision 2.3)
- Embed widget channel support (future)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Channel cards appear at the top of the dashboard, above all project sections, in all three view modes (project, priority, Kanban)
2. Each card for an active channel the operator has joined displays: channel name, comma-separated member persona names, and a truncated last message preview
3. When a `channel_message` SSE event arrives, the relevant channel card updates its last message preview without a page reload
4. When a `channel_update` SSE event arrives (member join/leave, status transition), the relevant channel card updates its member list and status without a page reload
5. Clicking a channel card opens a slide-out chat panel on the right side of the viewport
6. The chat panel displays the full message history fetched from `GET /api/channels/<slug>/messages`
7. Each message in the chat panel shows: sender persona name, message content, and timestamp
8. System messages (joins, leaves, state changes) render visually distinct from regular messages
9. The chat panel has a text input box at the bottom that sends messages via `POST /api/channels/<slug>/messages`
10. Sent messages appear in the chat feed immediately (optimistic rendering) and are confirmed by the `channel_message` SSE event
11. New messages arriving via SSE while the chat panel is open append to the bottom of the feed and auto-scroll if the user is at the bottom
12. The chat panel has a close button that dismisses it
13. A channel management tab is accessible from the dashboard (new tab or section)
14. The management tab lists all channels visible to the operator with status, type, member count, and creation date
15. The management tab provides a "Create Channel" form with: name, type (dropdown), description (optional), members (multi-select or comma-separated persona slugs)
16. The management tab provides archive and complete actions for channels the operator can manage
17. The channel cards and chat panel correctly display messages received via `channel_message` SSE events in real-time
18. N/A — per-channel notification rate limiting is implemented and validated in S6
19. N/A — active view suppression deferred to v2 (see FR19). V1 relies on 30-second per-channel rate limit from S6

### 3.2 Non-Functional Success Criteria

1. Channel cards render within 100ms of initial page load -- no blocking API calls; initial data is server-rendered via Jinja2 context
2. SSE event handling adds no perceptible latency to existing dashboard updates
3. The chat panel slide-out animation is smooth (CSS transition, not JS animation)
4. The chat panel supports channels with 100+ messages without scroll performance degradation (virtual scrolling not required for v1 -- paginate via `?limit=50` and "load more" button)
5. All new UI elements follow the existing dark theme and monospace font convention
6. No new npm dependencies -- vanilla JS only, consistent with the existing frontend
7. Notification rate limiting is thread-safe (existing `NotificationService` pattern with lock)

---

## 4. Functional Requirements (FRs)

### Channel Cards Section

**FR1: Channel cards positioned above project sections**
The dashboard template shall include a channel cards section between the sort controls / new agent control and the main content area (project view, priority view, or Kanban view). The section is visible in all three view modes.

**FR2: Channel card content**
Each channel card shall display:
- Channel name (bold, primary text)
- Channel type badge (e.g., "WORKSHOP", "DELEGATION" -- small, muted, uppercase)
- Member list: comma-separated persona names, truncated with "+N more" if exceeding available space
- Last message preview: sender persona name + truncated content (max ~100 chars), or "No messages yet" for `pending` channels
- Visual status indicator consistent with channel lifecycle state (pending/active/complete)

**FR3: Channel card real-time updates**
Channel cards shall update in response to `channel_message` and `channel_update` SSE events. When a `channel_message` event arrives for a channel with a visible card, the card's last message preview updates. When a `channel_update` event arrives, the card's member list and/or status updates.

**FR4: Channel card click opens chat panel**
Clicking a channel card shall open the chat panel for that channel. If a chat panel is already open for a different channel, it switches to the clicked channel's feed. If the same channel is clicked again, the panel closes (toggle behaviour).

### Chat Panel

**FR5: Slide-out chat panel**
The chat panel shall be a fixed-position panel that slides in from the right edge of the viewport. Width: 400-500px on desktop, full width on mobile. The panel overlays the dashboard content -- it does not push or resize the main layout.

**FR6: Chat panel header**
The panel header shall show: channel name, channel type badge, member count, and a close button (X icon or similar).

**FR7: Message feed**
The panel body shall display messages in chronological order, newest at the bottom. Each message shows:
- Sender persona name (bold) with visual distinction for operator messages vs agent messages
- Message content (markdown rendered as plain text for v1 -- no markdown rendering library)
- Timestamp (relative: "2m ago", "1h ago"; absolute on hover)
- System messages (`message_type = "system"`) render with muted styling and centered text (e.g., "Paula joined the channel")

**FR8: Message feed loading**
On panel open, the chat panel fetches the most recent 50 messages from `GET /api/channels/<slug>/messages?limit=50`. A "Load earlier messages" button at the top fetches the next page using `?before=<oldest_sent_at>&limit=50` (cursor pagination).

**FR9: Real-time message append**
When a `channel_message` SSE event arrives for the currently open channel, the new message appends to the bottom of the feed. If the user's scroll position is at or near the bottom (within 50px), auto-scroll to show the new message. If the user has scrolled up to read history, do not auto-scroll -- show a "New messages" indicator at the bottom instead.

**FR10: Send message input**
The panel footer shall contain a text input (textarea) and a send button. Pressing Enter sends the message (Shift+Enter for newline). The input clears after sending.

**FR11: Send message API call**
Sending posts to `POST /api/channels/<slug>/messages` with body `{content: "..."}`. The operator's persona identity is resolved server-side from the dashboard session. `agent_id` is NULL (the operator is not an agent). Optimistic rendering: the message appears immediately in the feed in a "sending" state, confirmed when the `channel_message` SSE event arrives.

**FR12: Error handling**
If the send API call fails (non-2xx response), the optimistically rendered message shows an error indicator (red border or icon) with a "Retry" option. The input box content is preserved for re-editing.

### Channel Management Tab

**FR13: Management tab access**
The dashboard shall include a navigation element (tab, button, or link in the header area) to access the channel management view. This can be a separate page or a modal/panel.

**FR14: Channel list**
The management view shall list all channels visible to the operator (calls `GET /api/channels?all=true`). Each row shows: name, slug, type, status, member count, created date. Rows are clickable to view channel details.

**FR15: Create channel form**
A "Create Channel" action opens a form with:
- Name (required, text input)
- Type (required, dropdown: workshop, delegation, review, standup, broadcast)
- Description (optional, textarea)
- Members (optional, comma-separated persona slugs or searchable multi-select)

Submit calls `POST /api/channels` with the form data. On success, the new channel appears in the list and a channel card appears on the dashboard.

**FR16: Channel actions**
The management view shall provide action buttons for:
- **Complete** -- calls `POST /api/channels/<slug>/complete` (available when status is `active`)
- **Archive** -- calls `POST /api/channels/<slug>/archive` (available when status is `complete`)
- View history -- opens the chat panel for the selected channel

### Notification Integration

**FR17: Channel message notifications**
Channel message notifications are handled server-side by S6's delivery engine. No frontend notification trigger needed.

**FR18: Per-channel rate limiting**
Per-channel rate limiting is implemented in S6.

**FR19: Active view suppression (v2 — deferred)**
Active view suppression (suppressing notifications when the operator has the channel's chat panel open) is deferred to v2. The 30-second per-channel rate limit (S6 FR, NotificationService extension) provides sufficient spam protection for v1. The chat panel JS maintains a `window.ChannelChat._activeChannelSlug` variable as infrastructure for v2 suppression — but v1 does not use it to gate notifications. Implementation in v2: the SSE handler checks this flag before triggering a notification (see Section 6.5 code example for the pattern).

**FR20: Notification content**
Channel notifications shall show:
- Title: "Channel Message"
- Subtitle: `#{channel_name}`
- Message: `{persona_name}: {content_preview}` (truncated to 100 chars)

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Vanilla JS only**
All new JavaScript shall be vanilla JS modules following the existing IIFE pattern (`(function(global) { ... })(window)`). No React, Vue, Alpine, or other framework dependencies. No new npm packages.

**NFR2: Tailwind CSS styling**
All new styling shall use Tailwind utility classes from the existing `tailwind.config.js` configuration and custom properties from `static/css/src/input.css`. Any new custom CSS classes shall be added to `input.css`, not to `main.css` directly (build artifact).

**NFR3: Theme consistency**
Channel cards, chat panel, and management tab shall use the existing dark theme: `bg-void`, `bg-deep`, `bg-surface`, `bg-elevated` backgrounds, monospace font (`--font-mono`), `--cyan`, `--green`, `--amber` accents, `--border` and `--border-bright` borders.

**NFR4: SSE handler registration**
New SSE event type handlers (`channel_message`, `channel_update`) shall be registered in the existing `sse-client.js` `commonTypes` array and handled in a new JS module. The SSE client's `on()` method is the handler registration mechanism.

**NFR5: No new backend routes or services**
No new backend routes, blueprints, or services. All backend channel logic (including notification rate limiting) is handled by S4-S6. This sprint is frontend-only: Jinja2 templates, vanilla JavaScript, and Tailwind CSS.

**NFR6: Backward-compatible dashboard**
If no channels exist or the operator has no active channel memberships, the channel cards section is hidden. The dashboard renders identically to pre-channel state.

---

## 6. Technical Context

### 6.1 Files to Modify

| File | Change |
|------|--------|
| `templates/dashboard.html` | Add `{% include "partials/_channel_cards.html" %}` between sort controls and main content area. Add chat panel partial include. Add channel management JS script tag. |
| `static/js/sse-client.js` | Add `"channel_message"` and `"channel_update"` to the `commonTypes` array (lines 245-266) so typed SSE events are dispatched to handlers. |
| `static/js/dashboard-sse.js` | Import/call channel card update functions when `channel_message` and `channel_update` events are received. Alternatively, the new channel JS module registers its own handlers directly on `window.sseClient`. |
| `static/css/src/input.css` | Add custom CSS for channel cards, chat panel slide-out animation, and channel-specific styling not achievable with Tailwind utilities alone. |
| `src/claude_headspace/routes/dashboard.py` | Add `get_channel_data_for_operator()` function. Call it in the dashboard route handler and pass result as `channel_data` template context variable (see Section 6.15). |

### 6.2 New Files

| File | Purpose |
|------|---------|
| `templates/partials/_channel_cards.html` | Jinja2 partial: channel cards section, server-rendered on initial load. Iterates over `channel_data` context variable. Conditional: hidden if no channels. |
| `templates/partials/_channel_chat_panel.html` | Jinja2 partial: slide-out chat panel container. Initially hidden. Populated dynamically by JS on channel card click. |
| `templates/partials/_channel_management.html` | Jinja2 partial or template: channel list, create form, action buttons. May be a modal or dedicated section. |
| `static/js/channel-cards.js` | JS module: channel card rendering, SSE event handlers for `channel_message` and `channel_update`, card click handler, channel card DOM updates. |
| `static/js/channel-chat.js` | JS module: chat panel open/close, message feed rendering, message sending, scroll management, focus flag for notification suppression. |
| `static/js/channel-management.js` | JS module: management tab interactions, create channel form handling, channel list rendering, action button handlers. |

### 6.3 Dashboard Layout — Channel Cards Positioning

The channel cards section goes between the sort controls block and the main content area in `dashboard.html`. This matches the workshop decision (Section 1.1 UI/UX Context): "Dashboard card for each active channel sits at the top of the dashboard, above all project sections."

Current layout order in `dashboard.html`:
1. Header (`partials/_header.html`)
2. Objective banner (`partials/_objective_banner.html`)
3. Recommended next panel (conditional)
4. Sort controls + New Agent button
5. **--- Channel cards go HERE ---**
6. Content area (project view / priority view / Kanban view)

```html
<!-- In dashboard.html, after sort controls div, before content area -->
{% if channel_data %}
    {% include "partials/_channel_cards.html" %}
{% endif %}
```

The `channel_data` context variable is a list of dicts, each containing: `slug`, `name`, `channel_type`, `status`, `members` (list of persona names), `last_message` (dict with `persona_name`, `content_preview`, `sent_at` or `None`). This is computed in the dashboard route handler from the operator's active channel memberships.

### 6.4 Channel Card HTML Structure

Each channel card follows the existing dashboard card conventions (`card-editor` class, line-number gutter) but with a simpler structure suited to channels:

```html
<section id="channel-cards-section" class="mb-4">
  <div class="flex flex-wrap gap-3">
    {% for channel in channel_data %}
    <article class="channel-card bg-elevated rounded-lg border border-border
                    cursor-pointer hover:border-cyan/50 transition-colors
                    min-w-[280px] max-w-[360px] flex-1"
             data-channel-slug="{{ channel.slug }}"
             onclick="window.ChannelChat && window.ChannelChat.toggle('{{ channel.slug }}')">
      <div class="px-3 py-2 border-b border-border flex items-center justify-between">
        <div class="flex items-baseline gap-2">
          <span class="text-primary text-sm font-medium">{{ channel.name }}</span>
          <span class="text-muted text-xs uppercase">{{ channel.channel_type }}</span>
        </div>
        <span class="channel-status-dot w-2 h-2 rounded-full
                     {% if channel.status == 'active' %}bg-green
                     {% elif channel.status == 'pending' %}bg-amber
                     {% else %}bg-muted{% endif %}">
        </span>
      </div>
      <div class="px-3 py-2">
        <div class="text-muted text-xs mb-1 truncate channel-members">
          {{ channel.members | join(', ') }}
        </div>
        <div class="text-secondary text-xs truncate channel-last-message"
             data-channel-slug="{{ channel.slug }}">
          {% if channel.last_message %}
            <span class="text-cyan">{{ channel.last_message.persona_name }}:</span>
            {{ channel.last_message.content_preview }}
          {% else %}
            <span class="italic">No messages yet</span>
          {% endif %}
        </div>
      </div>
    </article>
    {% endfor %}
  </div>
</section>
```

### 6.5 Chat Panel Structure and Interaction Model

The chat panel is a fixed-position element that slides in from the right edge of the viewport. It overlays the dashboard content without pushing it.

```html
<!-- Chat panel (initially hidden, populated by JS) -->
<aside id="channel-chat-panel"
       class="fixed top-0 right-0 h-full w-[440px] bg-surface border-l border-border
              transform translate-x-full transition-transform duration-200 ease-in-out
              z-50 flex flex-col"
       aria-hidden="true">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-3 border-b border-border">
    <div>
      <h2 id="chat-panel-title" class="text-primary text-sm font-medium"></h2>
      <span id="chat-panel-meta" class="text-muted text-xs"></span>
    </div>
    <button onclick="window.ChannelChat && window.ChannelChat.close()"
            class="text-muted hover:text-primary p-1" aria-label="Close chat panel">
      &times;
    </button>
  </div>

  <!-- Message feed -->
  <div id="chat-panel-messages"
       class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
    <!-- Messages rendered by JS -->
  </div>

  <!-- New message indicator (hidden by default) -->
  <div id="chat-new-messages-indicator"
       class="hidden px-4 py-1 bg-cyan/10 text-cyan text-xs text-center cursor-pointer border-t border-cyan/20"
       onclick="window.ChannelChat && window.ChannelChat.scrollToBottom()">
    New messages below
  </div>

  <!-- Input -->
  <div class="px-4 py-3 border-t border-border">
    <div class="flex gap-2">
      <textarea id="chat-panel-input"
                class="form-well flex-1 px-3 py-2 text-sm resize-none"
                rows="2"
                placeholder="Type a message..."
                onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault(); window.ChannelChat && window.ChannelChat.send();}">
      </textarea>
      <button onclick="window.ChannelChat && window.ChannelChat.send()"
              class="px-3 py-2 text-sm font-medium rounded bg-cyan/20 text-cyan border border-cyan/30 hover:bg-cyan/30 transition-colors self-end">
        Send
      </button>
    </div>
  </div>
</aside>
```

#### Chat panel state machine:

| State | Transition | Action |
|-------|-----------|--------|
| Closed (translate-x-full) | Click channel card | Fetch messages, populate feed, slide in (remove translate-x-full) |
| Open for channel A | Click same card A | Slide out (add translate-x-full) |
| Open for channel A | Click different card B | Replace feed with channel B messages (no slide animation -- instant swap) |
| Open | Click close button | Slide out |
| Open | Escape key | Slide out |

#### Focus flag for notification suppression:

The chat panel JS maintains a `window.ChannelChat._activeChannelSlug` variable. When the panel is open and the browser tab is visible (`document.visibilityState === 'visible'`), this slug identifies the "actively viewed" channel. The SSE handler for `channel_message` checks this flag before triggering a notification:

```javascript
// In channel-cards.js SSE handler:
sseClient.on('channel_message', function(data) {
  // Update the channel card's last message preview
  updateChannelCard(data.channel_slug, data);

  // Append to chat panel if this channel is currently open
  if (window.ChannelChat && window.ChannelChat.isOpenFor(data.channel_slug)) {
    window.ChannelChat.appendMessage(data);
  }

  // Notification handled server-side by S6 delivery engine.
  // V2: active view suppression will check window.ChannelChat.isActivelyViewing()
  // and call POST /api/channels/<slug>/viewing to suppress server-side notifications.
});
```

### 6.6 SSE Event Handling

Two SSE event types to handle, both defined in Sprint 5 (Decision 2.3):

#### `channel_message` event

```json
{
  "channel_slug": "workshop-persona-alignment-7",
  "message_id": 42,
  "persona_slug": "architect-robbo-3",
  "persona_name": "Robbo",
  "content_preview": "The persona_id constraint is resolved.",
  "message_type": "message",
  "sent_at": "2026-03-03T10:23:45Z"
}
```

Handler actions:
1. Update the matching channel card's last message preview
2. If the chat panel is open for this channel, append the message to the feed
3. If the chat panel is NOT open for this channel (or is closed), trigger a macOS notification (subject to rate limiting)

#### `channel_update` event

```json
{
  "channel_slug": "workshop-persona-alignment-7",
  "update_type": "member_joined",
  "detail": {"persona_name": "Con", "persona_slug": "con-builder-5"}
}
```

Handler actions:
1. Update the matching channel card's member list
2. If `update_type` is a status transition (e.g., `"channel_completed"`), update the card's status indicator
3. If a new channel the operator has joined transitions to `active`, create a new card dynamically
4. If a channel is archived, remove its card from the section

#### SSE client registration

Add to `commonTypes` array in `static/js/sse-client.js`:

```javascript
const commonTypes = [
  // ... existing types ...
  "channel_message",
  "channel_update",
];
```

The new `channel-cards.js` module registers its own handlers via `window.sseClient.on()` -- same pattern as `dashboard-sse.js` registers handlers for `card_refresh` and `state_transition`.

**Note:** S1 (Handoff Improvements) also modifies `sse-client.js` `commonTypes` to add `synthetic_turn`. Building agents should check for prior modifications and append.

### 6.7 Message Feed Rendering

Each message in the chat panel feed is rendered by JS from API response data:

```javascript
function renderMessage(msg) {
  var div = document.createElement('div');

  if (msg.message_type === 'system') {
    // System messages: centered, muted, italic
    div.className = 'text-center text-muted text-xs italic py-1';
    div.textContent = msg.content;
    return div;
  }

  // Regular messages
  var isOperator = !msg.agent_id; // operator has no agent_id
  div.className = 'flex flex-col gap-0.5';

  var header = document.createElement('div');
  header.className = 'flex items-baseline gap-2';

  var name = document.createElement('span');
  name.className = isOperator ? 'text-cyan text-xs font-medium' : 'text-green text-xs font-medium';
  name.textContent = msg.persona_name;
  header.appendChild(name);

  var time = document.createElement('span');
  time.className = 'text-muted text-xs';
  time.textContent = formatRelativeTime(msg.sent_at);
  time.title = new Date(msg.sent_at).toLocaleString();
  header.appendChild(time);

  div.appendChild(header);

  var content = document.createElement('div');
  content.className = 'text-secondary text-sm pl-0 break-words';
  content.textContent = msg.content;
  div.appendChild(content);

  return div;
}
```

Colour coding by sender type:
- Operator messages: `text-cyan` name (matches the existing cyan accent for operator elements)
- Agent messages: `text-green` name (matches the agent-related green accent)
- System messages: `text-muted`, centered, italic

### 6.8 Scroll Management

The chat panel message feed implements smart scrolling:

1. **On open:** scroll to bottom (most recent messages)
2. **On new message (via SSE):** if scroll position is within 50px of the bottom, auto-scroll to show the new message. Otherwise, show a "New messages below" indicator bar that the user can click to scroll down.
3. **Load earlier messages:** clicking "Load earlier" at the top fetches older messages via `?before=<oldest_sent_at>&limit=50` and prepends them. Scroll position is preserved (the user stays at the same message they were reading).

```javascript
function isNearBottom(container) {
  return container.scrollHeight - container.scrollTop - container.clientHeight < 50;
}

function appendMessageAndMaybeScroll(container, messageEl) {
  var wasNearBottom = isNearBottom(container);
  container.appendChild(messageEl);
  if (wasNearBottom) {
    container.scrollTop = container.scrollHeight;
  } else {
    showNewMessageIndicator();
  }
}
```

### 6.9 Notification Integration

#### Backend: per-channel rate limiting

NotificationService is extended with per-channel rate limiting by S6 (delivery engine sprint). This sprint (S7) does not modify NotificationService. The `send_channel_notification()` method is available for the dashboard to call if needed, but the primary notification path is server-side via S6's delivery engine.

#### Frontend: notification trigger path

The notification trigger flows from the frontend SSE handler:

1. `channel_message` SSE event arrives in `channel-cards.js`
2. JS checks: is this channel actively viewed? (`window.ChannelChat.isActivelyViewing(slug)`)
3. If NOT actively viewed, JS calls `POST /api/notifications/channel` (new lightweight endpoint) OR the notification is triggered server-side when the SSE event is broadcast

**Preferred approach: server-side notification trigger.** The `channel_message` SSE event is broadcast by the backend when a new message is posted. The backend already knows when to fire notifications. The notification should fire from the ChannelService (or the delivery engine in S6) when a message is created, not from the frontend.

The frontend's role is only to suppress notifications: the chat panel JS sends a periodic heartbeat or sets a flag via `POST /api/channels/<slug>/viewing` to tell the backend the operator is actively viewing that channel. The backend checks this flag before sending a notification.

**Simpler alternative for v1:** Fire notifications server-side for all channel messages with rate limiting. No suppression for actively viewed channels in v1. The 30-second rate limit already prevents spam. Suppression can be added in v2 when the operator reports annoyance.

Implementation choice is left to the building agent -- both approaches are acceptable for v1. The 30-second per-channel rate limit is the minimum requirement.

### 6.10 Channel Management Tab

The management tab provides a simple CRUD interface for channels. It can be implemented as:

**Option A: Modal panel** (simpler, lower risk) -- a button in the header or sort controls area opens a modal with channel list and create form. Uses the same modal pattern as the existing waypoint editor and brain reboot modals.

**Option B: Dedicated route** -- a `/channels` page with its own template. More surface area but separates concerns.

**Recommended: Option A** for v1. The modal approach matches existing dashboard patterns and avoids a new route.

#### Management tab API calls

| Action | API Call |
|--------|---------|
| List channels | `GET /api/channels?all=true` |
| View channel details | `GET /api/channels/<slug>` |
| Create channel | `POST /api/channels` with `{name, channel_type, description?, members?}` |
| Complete channel | `POST /api/channels/<slug>/complete` |
| Archive channel | `POST /api/channels/<slug>/archive` |
| View members | `GET /api/channels/<slug>/members` |

### 6.11 Operator Identity for Messages

When the operator sends a message from the chat panel, the message is attributed to the operator's internal Persona (PersonaType: person/internal). The `POST /api/channels/<slug>/messages` endpoint resolves the caller's identity from the Flask session:

- `persona_id`: operator's Persona ID (resolved from session)
- `agent_id`: `NULL` (the operator is not an agent)
- `source_turn_id`: `NULL` (no Turn for operator messages)
- `source_command_id`: `NULL` (no Command for operator messages)

This is already defined in Section 3.4 of the workshop. The dashboard JS does not need to send identity information -- the backend resolves it from the session cookie.

### 6.12 Channel Cards Responsive Behaviour

- **Desktop (>= 1024px):** Channel cards display in a horizontal flex row, wrapping to multiple rows if needed. Each card is 280-360px wide.
- **Tablet (768-1023px):** Cards stack in a 2-column grid.
- **Mobile (< 768px):** Cards stack vertically, full width. Chat panel is full-width overlay.

The chat panel uses responsive width:
```css
#channel-chat-panel {
  width: 440px;
}
@media (max-width: 768px) {
  #channel-chat-panel {
    width: 100%;
  }
}
```

### 6.13 Design Decisions (All Resolved -- Workshop Sections 1.1, 3.4, 4.1-4.3)

| Decision | Resolution | Source |
|----------|-----------|--------|
| Channel cards position | Top of dashboard, above all project sections | Section 1.1 UI/UX Context |
| Chat panel interaction | Slide-out from right, click card to toggle | Section 3.4 |
| Operator sending path | Dashboard chat panel input box, POST to messages API | Section 3.4 |
| Operator identity | Operator's Persona, agent_id=NULL | Section 3.4 |
| Notification delivery | Existing NotificationService (macOS terminal-notifier) | Section 3.4 |
| Notification rate limiting | Per-channel, 30-second window, configurable | Section 3.4 |
| Notification suppression | Actively viewed channel suppresses notifications | Section 3.4 |
| Channel management surface | Dashboard management tab (create, view, archive) | Section 1.1 UI/UX Context |
| SSE event types | `channel_message` and `channel_update` on existing stream | Section 2.3 |
| Client-side channel filtering | Dashboard JS filters SSE events by channel membership | Section 2.3 |
| No per-channel SSE streams | Single stream with type filtering, 100-connection limit | Section 2.3 |
| Workshop history access | Chat panel shows complete history for completed channels | Section 4.3 |
| Completed channel cards | Remain visible until archived | Section 4.3 |
| Message ordering | Chronological by `sent_at`, best-effort | Section 4.2 |

### 6.14 Existing Patterns to Follow

| Pattern | Existing Example | How to Follow |
|---------|-----------------|---------------|
| Jinja2 partial includes | `{% include "partials/_objective_banner.html" %}` | Channel cards and chat panel as `partials/_channel_*.html` |
| SSE event registration | `commonTypes` array in `sse-client.js` + `sseClient.on()` in `dashboard-sse.js` | Add channel types to `commonTypes`, register handlers in `channel-cards.js` |
| IIFE JS modules | `(function(global) { ... })(window)` in every `static/js/*.js` | Same pattern for new channel JS modules |
| Global JS API | `window.FocusAPI`, `window.BrainReboot` | `window.ChannelCards`, `window.ChannelChat` |
| Modal pattern | `partials/_waypoint_editor.html` + `brain-reboot.js` | Channel management modal follows same show/hide pattern |
| Card styling | `.card-editor`, `.card-line`, `.line-num` classes | Channel cards use simpler layout but same `bg-elevated`, `rounded-lg`, `border-border` |
| Form inputs | `.form-well` class in `input.css` | Chat panel textarea uses `form-well` |
| Notification service | `NotificationService._rate_limit_tracker` per agent_id | `_channel_rate_limit_tracker` per channel_slug, same locking pattern |
| Toast feedback | `partials/_toast.html` | Channel create/error feedback via existing toast system |

### 6.15 Dashboard Route Context Variable

The dashboard route handler (`routes/dashboard.py` or equivalent) needs to provide `channel_data` to the template context. This is a query to the operator's active ChannelMemberships, joining to Channel and the most recent Message per channel.

```python
# In dashboard route handler:
def get_channel_data_for_operator():
    """Fetch active channels with last message for dashboard cards."""
    from claude_headspace.models import Persona
    operator = Persona.get_operator()
    if not operator:
        return []
    memberships = ChannelMembership.query.filter_by(
        persona_id=operator.id,
        status='active'
    ).all()

    channel_data = []
    for m in memberships:
        channel = m.channel
        if channel.status == 'archived':
            continue
        members = [cm.persona.name for cm in channel.memberships
                   if cm.status == 'active']
        last_msg = Message.query.filter_by(
            channel_id=channel.id
        ).order_by(Message.sent_at.desc()).first()

        channel_data.append({
            'slug': channel.slug,
            'name': channel.name,
            'channel_type': channel.channel_type.value,
            'status': channel.status,
            'members': members,
            'last_message': {
                'persona_name': last_msg.persona.name if last_msg and last_msg.persona else 'System',
                'content_preview': last_msg.content[:100] if last_msg else None,
                'sent_at': last_msg.sent_at.isoformat() if last_msg else None,
            } if last_msg else None,
        })
    return channel_data
```

This function queries at page load time. After initial render, all updates come via SSE events.

### 6.16 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Chat panel obscures important agent cards | Medium | Low | Panel slides from right, doesn't push content. User can close anytime. 440px width leaves most of the dashboard visible on standard monitors. |
| SSE event volume from active channels causes performance issues | Low | Medium | Channel message events are lightweight (content preview, not full message). Rate of human + agent messaging is naturally low (seconds between messages, not milliseconds). |
| Operator identity resolution from Flask session fails for non-authenticated dashboard views | Low | Medium | The dashboard already requires session auth for all interactive features (respond to agent, brain reboot). Channel operations follow the same pattern. |
| Large channel member lists overflow card width | Medium | Low | Truncate with "+N more" after 3-4 names. Full member list visible in chat panel header or channel details. |
| Notification suppression based on frontend focus flag is unreliable (browser tab hidden, system sleep) | Medium | Low | The 30-second rate limit provides a floor. Even without suppression, notifications are not spammy at 30-second intervals. |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| Channel data model | E9-S3 | Channel, ChannelMembership, Message tables |
| ChannelService | E9-S4 | Service methods for channel CRUD, messaging |
| API + SSE endpoints | E9-S5 | `/api/channels/*` REST API, `channel_message` and `channel_update` SSE event types |
| Delivery engine | E9-S6 | Fan-out delivery to agents (not directly used by dashboard, but produces the messages the dashboard displays) |
| SSE broadcaster | E1-S7 (done) | Event broadcast infrastructure |
| NotificationService | Existing (done) | macOS notification delivery, rate limiting pattern |
| Dashboard template | Existing (done) | Template structure, script loading, partial includes |
| SSE client JS | Existing (done) | `SSEClient` class, typed event handling |

All Sprint 5 API endpoints must be functional before this sprint can be built. The dashboard JS calls these endpoints and handles the SSE events they emit.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Sections 1.1, 3.4, 4.1-4.3) |
| 1.1     | 2026-03-03 | Robbo  | v2 cross-PRD remediation: implemented active view suppression in v1 FR19 (Finding #3), updated NFR5 to frontend-only (Finding #4), added dashboard.py to Files to Modify (Finding #8), rephrased SC17-19 to S7 responsibilities (Finding #10), updated FR16/Section 6.10 archive endpoint to POST (Finding #5) |
| 1.2     | 2026-03-03 | Robbo  | v3 cross-PRD remediation: deferred active view suppression FR19 to v2 — v1 relies on 30-second per-channel rate limit from S6; resolved contradiction between FR19 and Section 2.1 scope note (Cycle 1 Finding #4) |
| 1.3     | 2026-03-03 | Robbo  | v3 Cycle 2 remediation: updated SC19 to match FR19 v2 deferral (Cycle 2 Finding #1); removed client-side `triggerChannelNotification()` from Section 6.5 code example — notifications are server-side via S6 (Cycle 2 Finding #4) |
