## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Backend — API Gap Endpoints (Phase 2a)

- [x] 2.1 Add `delete_channel(slug)` method to ChannelService — soft-delete or hard-delete, enforce archived/empty precondition
- [x] 2.2 Add `remove_member(slug, persona_slug)` method to ChannelService — remove membership record, broadcast SSE update
- [x] 2.3 Add `DELETE /api/channels/<slug>` route to `channels_api.py` — thin handler with `_channel_route` decorator, confirmation required client-side
- [x] 2.4 Add `DELETE /api/channels/<slug>/members/<persona_slug>` route to `channels_api.py` — thin handler delegating to ChannelService
- [x] 2.5 Write tests for new delete channel endpoint (success, not-archived error, not-found)
- [x] 2.6 Write tests for new remove member endpoint (success, not-a-member error, sole-chair prevention)

## 3. Page Route & Template (Phase 2b)

- [x] 3.1 Create `src/claude_headspace/routes/channels_page.py` blueprint — serve `/channels` page, inject channel list data via `GET /api/channels`
- [x] 3.2 Register blueprint in `app.py`
- [x] 3.3 Create `templates/channels.html` — extends `base.html`, includes `_header.html`, follows `personas.html` layout pattern
- [x] 3.4 Add "channels" link to `templates/partials/_header.html` nav (both desktop tabs and mobile drawer)
- [x] 3.5 Implement channel list table markup — columns: name, type badge, status label, member count, last activity, created, actions
- [x] 3.6 Implement status filter tabs (Active default, Pending, Complete, Archived, All) with visual active indicator
- [x] 3.7 Implement text search input for client-side name/slug filtering
- [x] 3.8 Implement channel detail expandable panel — full metadata, member list, lifecycle actions
- [x] 3.9 Implement create channel form (inline or modal) — name, type dropdown, description, member picker
- [x] 3.10 Implement attention signal indicators — amber pulse for active channels with no activity > configurable threshold

## 4. Frontend JavaScript (Phase 2c)

- [x] 4.1 Create `static/js/channel-admin.js` — IIFE module exposing `ChannelAdmin` global
- [x] 4.2 Implement `init()` — fetch channels via `GET /api/channels`, render table, set up filter state
- [x] 4.3 Implement filter tab switching — filter rendered rows by status, persist selected filter in session
- [x] 4.4 Implement client-side text search — filter rows by name/slug as user types
- [x] 4.5 Implement channel detail expand/collapse — fetch full channel detail via `GET /api/channels/<slug>`, render member list and metadata
- [x] 4.6 Implement lifecycle actions — Complete (`POST .../complete`), Archive (`POST .../archive`), Delete (`DELETE .../`) with confirmation dialog
- [x] 4.7 Implement member management — Add member via persona picker (`POST .../members`), Remove member (`DELETE .../members/<slug>`)
- [x] 4.8 Implement SSE subscription — listen to `channel_message` and `channel_update` events, update affected rows in real-time
- [x] 4.9 Implement attention signal logic — calculate time since last activity, apply/remove amber indicator based on configurable threshold
- [x] 4.10 Integrate MemberAutocomplete picker for create form and add-member action

## 5. Dashboard Integration (Phase 2d)

- [x] 5.1 Replace "Channel Management" modal button on dashboard with link to `/channels`
- [x] 5.2 Deprecate `_channel_management.html` partial — remove include or gate behind feature flag
- [x] 5.3 Verify channel cards on dashboard remain unaffected (SSE flow unchanged)

## 6. Styling (Phase 2e)

- [x] 6.1 Add attention signal CSS (amber pulse animation) to `static/css/src/input.css`
- [x] 6.2 Ensure all new markup follows dark theme + Tailwind conventions
- [x] 6.3 Verify tablet-width (768px+) responsiveness
- [x] 6.4 Rebuild Tailwind: `npx tailwindcss -i static/css/src/input.css -o static/css/main.css`

## 7. Testing (Phase 3)

- [x] 7.1 Route tests for `/channels` page serving (200 response, template rendered)
- [x] 7.2 Route tests for DELETE channel endpoint
- [x] 7.3 Route tests for DELETE member endpoint
- [x] 7.4 Service tests for `delete_channel` logic (precondition enforcement)
- [x] 7.5 Service tests for `remove_member` logic (sole-chair prevention)
- [x] 7.6 Visual verification via Playwright CLI screenshot of `/channels` page

## 8. Final Verification

- [x] 8.1 All tests passing
- [ ] 8.2 No linter errors
- [x] 8.3 Tailwind build output verified (custom selectors present)
- [ ] 8.4 Manual verification: navigate to /channels, filter, search, expand detail, create, complete, archive, delete
- [ ] 8.5 Verify SSE updates work (create channel from dashboard, see it appear on /channels)
