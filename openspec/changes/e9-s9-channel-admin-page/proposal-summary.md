# Proposal Summary: e9-s9-channel-admin-page

## Architecture Decisions

1. **Dedicated page, not modal** — `/channels` follows the established page pattern (`/personas`, `/activity`, `/projects`) rather than enhancing the existing modal. The modal is deprecated.
2. **Client-side filtering** — Status filters and text search operate client-side for v1 (channel count expected < 100). No server-side pagination needed.
3. **Reuse existing API** — All CRUD operations use existing S5 endpoints. Only two new thin route handlers needed (DELETE channel, DELETE member).
4. **Reuse MemberAutocomplete** — The existing `member-autocomplete.js` component provides persona search/selection. Reuse for both the create form and the add-member action in the detail panel.
5. **Inline detail panel** — Channel detail expands inline below the row (accordion pattern), not a separate page or modal. Keeps the operator in context.
6. **Attention threshold in JS** — The 2-hour attention signal threshold lives in the JS config for v1. PRD explicitly notes this should migrate to `config.yaml` if the feature proves useful.

## Implementation Approach

This is a **frontend-heavy sprint** with minimal backend work. The implementation breaks into:

1. **Backend (thin):** Two new API endpoints — `DELETE /api/channels/<slug>` and `DELETE /api/channels/<slug>/members/<persona_slug>` — plus corresponding ChannelService methods. Both are thin handlers following the existing `_channel_route` decorator pattern.
2. **Page route:** New `channels_page.py` blueprint serving the Jinja2 template. Follows the `personas.py` pattern of a simple page-serving route.
3. **Template:** `channels.html` extending `base.html` with the standard layout: header, filter tabs, search, table, detail panel, create form.
4. **JavaScript:** New `channel-admin.js` IIFE module for all page interactivity. Follows existing patterns (fetch API, DOM manipulation, SSE subscription).
5. **Navigation:** Add "channels" link to `_header.html` in both desktop tab group and mobile drawer.
6. **Deprecation:** Replace dashboard modal button with `/channels` link, remove `_channel_management.html` include.

## Files to Modify

### New Files
- `src/claude_headspace/routes/channels_page.py` — page-serving blueprint
- `templates/channels.html` — admin page template
- `static/js/channel-admin.js` — page controller JS

### Modified Files (Backend)
- `src/claude_headspace/routes/channels_api.py` — add DELETE channel and DELETE member endpoints
- `src/claude_headspace/services/channel_service.py` — add `delete_channel()` and `remove_member()` methods
- `src/claude_headspace/app.py` — register new blueprint

### Modified Files (Frontend)
- `templates/partials/_header.html` — add "channels" nav link (desktop + mobile)
- `templates/dashboard.html` — replace modal button with `/channels` link
- `static/css/src/input.css` — attention signal animation (amber pulse)

### Deprecated Files
- `templates/partials/_channel_management.html` — superseded by `/channels` page
- `static/js/channel-management.js` — modal no longer used from dashboard

### Test Files
- `tests/routes/test_channels_page.py` — page serving tests
- `tests/routes/test_channels_api.py` — add tests for DELETE endpoints
- `tests/services/test_channel_service.py` — add tests for delete/remove methods

## Acceptance Criteria

1. `/channels` page is accessible and renders with channel list
2. Header navigation includes "channels" link with active state
3. Status filter tabs work (Active default, Pending, Complete, Archived, All)
4. Text search filters by name/slug in real-time
5. Attention signals appear on stale active channels (> 2 hours idle)
6. Channel detail panel expands/collapses with full metadata and member list
7. Create channel form works with persona autocomplete picker
8. Lifecycle actions work: Complete, Archive, Delete (with confirmation)
9. Member management works: Add member, Remove member (with sole-chair prevention)
10. SSE events update the list in real-time
11. Dashboard modal button replaced with link to `/channels`
12. No new Python/npm dependencies
13. Tablet-width (768px+) responsive
14. Dark theme consistent with existing pages

## Constraints and Gotchas

1. **No new dependencies** — vanilla JS, no frameworks, no new npm packages
2. **Tailwind v3** — use `npx tailwindcss` (NOT `npx @tailwindcss/cli`). Rebuild after CSS changes.
3. **CSS source of truth** — custom CSS goes in `static/css/src/input.css`, never in `main.css` directly
4. **MemberAutocomplete reuse** — the component currently uses `available-members` endpoint which returns agents grouped by project. For the admin page, we need persona-based selection. Verify the picker supports both modes or adapt.
5. **Delete preconditions** — channels can only be deleted if archived OR have zero active members. The frontend must enforce button visibility; the backend must enforce the precondition.
6. **Sole chair protection** — cannot remove the last chair from a channel. Both frontend (disable button) and backend (reject request) must enforce this.
7. **SSE event names** — the existing events are `channel_message` and `channel_update`. Verify these event names match what the broadcaster emits.
8. **Modal deprecation** — removing the modal include may break if other pages reference it. Verify only `dashboard.html` includes `_channel_management.html`.
9. **Chair transfer deferred** — explicitly out of scope per PRD. Do not implement.
10. **Attention threshold** — hardcoded in JS for v1. Use a constant at the top of `channel-admin.js` (e.g., `ATTENTION_THRESHOLD_MS = 2 * 60 * 60 * 1000`).

## Git Change History

### Related Files (from git_context)
- `src/claude_headspace/routes/channels_api.py` — 6 commits in last 3 days (API additions, bug fixes, adversarial review fixes)
- `src/claude_headspace/services/channel_service.py` — 5 commits (service methods, bug fixes, pagination fix)
- `static/js/channel-management.js` — 1 commit (bug fixes for modal)
- `static/js/member-autocomplete.js` — 1 commit (bug fixes)
- `tests/routes/test_channels_api.py` — 2 commits (test additions)
- `tests/services/test_channel_service.py` — 2 commits (test additions)

### OpenSpec History
- `e9-s8-voice-bridge-channels` (archived 2026-03-03) — voice bridge channel integration. Affected specs: channel-context-tracking, channel-intent-detection, channel-name-matching, voice-formatter-channels, voice-pwa-channels.

### Detected Patterns
- Backend: routes delegate to services, services handle business logic and DB operations
- Routes use `_channel_route` decorator for auth resolution and service injection
- Tests follow `test_<route_module>.py` and `test_<service_module>.py` naming
- Frontend: IIFE pattern, global namespace objects (e.g., `ChannelManagement`, `PersonasPage`, `ActivityPage`)

## Q&A History

No clarifications needed. The single detected gap ("TBD: Chair transfer from UI") is explicitly marked as deferred/out-of-scope in the PRD (Section 8, Open Decisions).

## Dependencies

- **No new Python packages**
- **No new npm packages**
- **No database migrations** — uses existing Channel, ChannelMembership, Message models
- **Existing API endpoints** — `GET /api/channels`, `GET /api/channels/<slug>`, `POST /api/channels`, `POST .../complete`, `POST .../archive`, `GET .../members`, `POST .../members`, `GET /api/channels/available-members`
- **New API endpoints** — `DELETE /api/channels/<slug>`, `DELETE /api/channels/<slug>/members/<persona_slug>`

## Testing Strategy

1. **Route tests** (`tests/routes/test_channels_page.py`) — verify page serving returns 200, template renders
2. **Route tests** (`tests/routes/test_channels_api.py`) — add tests for DELETE channel and DELETE member endpoints
3. **Service tests** (`tests/services/test_channel_service.py`) — add tests for `delete_channel` and `remove_member` methods
4. **Visual verification** — Playwright CLI screenshot of `/channels` page after implementation
5. **Manual verification** — end-to-end flow: navigate, filter, search, create, complete, archive, delete, add/remove members

## OpenSpec References

- Proposal: `openspec/changes/e9-s9-channel-admin-page/proposal.md`
- Tasks: `openspec/changes/e9-s9-channel-admin-page/tasks.md`
- Spec: `openspec/changes/e9-s9-channel-admin-page/specs/channel-admin-page/spec.md`
- PRD: `docs/prds/channels/e9-s9-channel-admin-page-prd.md`
