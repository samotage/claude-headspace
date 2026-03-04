# Proposal Summary: voice-app-kebab-menus

## Architecture Decisions

1. **Reuse `PortalKebabMenu` shared component** -- Both the agent chat and channel chat kebab menus will use the existing portal-based kebab menu component (`static/js/portal-kebab-menu.js`). This component is already loaded in `voice.html` and handles positioning, outside-click dismissal, touch events, and SSE reload deferral. No new menu component is needed.

2. **Action builder functions per context** -- Each context (agent chat, channel chat) gets its own action builder function that returns an array of action objects. This follows the established pattern used by `_buildVoiceActions()` in `voice-sidebar.js` and `buildDashboardActions()` in `agent-lifecycle.js`. New actions (e.g., transcript download) can be added by appending to these arrays.

3. **Channel context via generic `agentId` parameter** -- The `PortalKebabMenu.open()` API uses `agentId` as a context identifier. For channel menus, this parameter will carry the channel slug or a channel-specific identifier. The `onAction` callback receives both the action ID and context ID, so no API change is needed.

4. **Chair detection from `VoiceState.channelMembers`** -- Channel member data (including `is_chair` flags) is already fetched and stored in `VoiceState.channelMembers` when a channel is opened. Chair-only action visibility is determined by checking this existing state -- no additional API calls needed.

5. **CSS in `voice.css`** -- New styles for chat header kebab buttons go in `static/voice/voice.css`, consistent with existing kebab button styles already defined there. No changes to `input.css` / Tailwind are needed since the voice app uses its own CSS.

## Implementation Approach

The implementation is primarily frontend JavaScript and HTML changes. No backend routes, no database migrations, no Python changes.

**Phase 1: Shared component enrichment**
- Add channel-context SVG icons to `PortalKebabMenu.ICONS` (add-member, complete, archive, copy-slug, leave)

**Phase 2: Agent chat header kebab**
- Add kebab trigger button to `main-header` in `voice.html`
- Add action builder + handler functions in `voice-chat-controller.js`
- Wire up the trigger on screen show

**Phase 3: Channel chat header kebab**
- Add kebab trigger button to `channel-chat-header` in `voice.html`
- Add action builder + handler functions in `voice-channel-chat.js`
- Wire up the trigger on channel open, with chair detection

**Phase 4: CSS + integration**
- Style kebab buttons in headers
- Close menus on screen transitions
- Verify touch targets, layout stability

## Files to Modify

### JavaScript (static/js/)
- `static/js/portal-kebab-menu.js` -- Add channel-context icons to `ICONS` object

### JavaScript (static/voice/)
- `static/voice/voice-chat-controller.js` -- Agent chat kebab action builder + handlers
- `static/voice/voice-channel-chat.js` -- Channel chat kebab action builder + handlers
- `static/voice/voice-app.js` -- Close kebab on screen transitions, outside click updates

### HTML
- `static/voice/voice.html` -- Add kebab trigger buttons to `main-header` (agent chat) and `channel-chat-header` (channel chat)

### CSS
- `static/voice/voice.css` -- Kebab trigger button styles in chat headers, touch target sizing

## Acceptance Criteria

1. Agent chat header displays a kebab menu trigger with actions: fetch context, attach, agent info, reconcile, handoff (conditional), dismiss
2. Channel chat header displays a kebab menu trigger with actions: add member, channel info, complete (chair-only), archive (chair-only), copy slug, leave
3. Destructive actions (dismiss, handoff, archive) show ConfirmDialog before executing
4. Chair-only actions (complete, archive) are only visible to the channel chair
5. Menus close on action selection, outside click/tap, and Escape key
6. Minimum 44px tap targets on touch devices
7. No layout shifts or interference with chat message display or input
8. Consistent visual style between agent chat and channel chat kebab menus

## Constraints and Gotchas

1. **Touch event handling** -- The voice app has a known touch vs click event issue (see MEMORY.md: "Touch vs Click Event Handling"). The `PortalKebabMenu` already handles this with both `click` and `touchend` event delegation, so this should be covered. But verify on iPad/iPhone.

2. **SSE reload deferral** -- When a kebab menu is open, SSE-triggered sidebar refreshes must be deferred. The existing `_sseReloadDeferred` pattern in `voice-sse-handler.js` already checks `PortalKebabMenu.isOpen()`. No change needed for sidebar kebabs, but verify that chat header kebab open state is also checked.

3. **Voice app is static HTML** -- `voice.html` is NOT a Jinja template. It is a static file served directly. No server-side rendering of actions -- all action lists are built in JavaScript at runtime.

4. **Agent data availability in chat header** -- When building agent chat actions, the agent's persona name and ended status must be available. Check that `VoiceState` has the necessary fields when the chat screen is active.

5. **Portal menu z-index** -- The portal menu uses `z-index: 150`. Verify this is above the chat header (which may have its own z-index for sticky positioning).

6. **Multiple menus** -- Only one portal kebab menu can be open at a time (shared singleton). Opening a chat header kebab will auto-close any sidebar kebab, and vice versa. This is correct behavior.

## Git Change History

### Related OpenSpec History
- `e5-s2-project-show-core` (archived 2026-02-03) -- project show page, unrelated but demonstrates the OpenSpec workflow

### Recent Relevant Commits
- `4ddff90c` (2026-03-01) -- `feat(handoff): implement end-to-end agent handoff via kebab menu` -- established the portal kebab pattern for agent cards
- `f679208` (2026-03-05) -- `style: rename 'End Channel' to 'Archive Channel' in kebab menu` -- recent channel kebab rename on dashboard
- `1d8d9ac` (2026-03-05) -- `docs: add voice app kebab menus and transcript download PRDs` -- the PRD itself
- `8ee6b96` (2026-03-05) -- `fix: channel chat kebab menu transparent background` -- recent CSS fix for channel chat kebab styling
- `3324266` (2026-03-05) -- `feat: channel chat UX improvements` -- recent channel chat header improvements

### Patterns Detected
- Portal-based kebab menus with action builder functions (agent-lifecycle.js, voice-sidebar.js)
- ConfirmDialog for destructive actions
- VoiceState as the central state store for voice app
- Event delegation for menu item click/touch handling

## Q&A History

No clarification questions were needed. The PRD is clear and the existing codebase patterns directly support the required implementation.

## Dependencies

- No new npm packages
- No new Python packages
- No database migrations
- No API changes
- Depends on existing: `PortalKebabMenu`, `ConfirmDialog`, `VoiceAPI`, `VoiceState`, `VoiceLayout`

## Testing Strategy

1. **Visual verification via Playwright CLI** -- Screenshot agent chat header and channel chat header with menus open
2. **Manual verification** -- Test on desktop Chrome and mobile Safari/Chrome for touch targets
3. **Action flow testing** -- Verify each action (dismiss, handoff, add member, leave, etc.) triggers the correct behavior
4. **Chair-only testing** -- Verify complete/archive actions hidden for non-chair members
5. **Confirm dialog testing** -- Verify destructive actions show confirmation before executing
6. **Integration testing** -- Verify menu closes on screen transitions, SSE reloads deferred correctly

## OpenSpec References

- **Proposal:** `openspec/changes/voice-app-kebab-menus/proposal.md`
- **Tasks:** `openspec/changes/voice-app-kebab-menus/tasks.md`
- **Spec:** `openspec/changes/voice-app-kebab-menus/specs/voice-app-kebab-menus/spec.md`
