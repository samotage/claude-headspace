## Why

The operator cannot efficiently triage, manage, or lifecycle channels at scale. The current management modal is buried behind a button, has no filtering or search, no attention signals, no delete capability, and no way to assess which channels need action. A dedicated admin page — following the established pattern of `/personas`, `/projects`, and `/activity` — provides the operator control surface needed for channel oversight.

## What Changes

- **New `/channels` route and template** — dedicated admin page with header navigation link, following the `personas.html`/`activity.html` layout pattern
- **Channel list with filtering and search** — table view with status filter tabs (Active default, Pending, Complete, Archived, All) and client-side text search by name/slug
- **Attention signals** — visual indicators (amber pulse) for active channels with no message activity in configurable time window (default 2 hours)
- **Channel detail panel** — inline expandable panel showing full member list, message count, chair, description, timestamps, and lifecycle actions
- **Create channel form** — name, type, description, initial members with persona autocomplete picker (reusing existing `MemberAutocomplete` component)
- **Lifecycle management** — Complete (active -> complete), Archive (complete -> archived), Delete (archived/empty only, with confirmation dialog)
- **Member management** — add persona to channel, remove persona from channel from detail view
- **Real-time SSE updates** — subscribe to `channel_message` and `channel_update` events for live list updates
- **Modal deprecation** — replace dashboard "Channel Management" modal button with link to `/channels`, remove/disable `_channel_management.html`
- **API gap: DELETE endpoint** — add `DELETE /api/channels/<slug>` route handler (thin wrapper around ChannelService)
- **API gap: member removal endpoint** — add `DELETE /api/channels/<slug>/members/<persona_slug>` route handler

## Impact

- Affected specs: channel-admin-page (new)
- Affected code:
  - `src/claude_headspace/routes/channels_page.py` (new — page-serving route)
  - `src/claude_headspace/routes/channels_api.py` (add DELETE channel + DELETE member endpoints)
  - `src/claude_headspace/services/channel_service.py` (add `delete_channel`, `remove_member` methods if missing)
  - `templates/channels.html` (new — admin page template)
  - `templates/partials/_header.html` (add Channels nav link)
  - `templates/partials/_channel_management.html` (deprecate/remove)
  - `templates/dashboard.html` (replace modal button with /channels link)
  - `static/js/channel-admin.js` (new — page controller)
  - `static/js/channel-management.js` (deprecate — modal no longer used)
  - `static/js/member-autocomplete.js` (reuse for member picker)
  - `static/css/src/input.css` (attention signal animations if needed)
