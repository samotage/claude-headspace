## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Shared Component Updates

- [ ] 2.1.1 Add channel-context SVG icons to `PortalKebabMenu.ICONS` in `portal-kebab-menu.js` (add-member, complete, end/archive, copy-slug, leave)
- [ ] 2.1.2 Ensure PortalKebabMenu supports both `agentId` and a generic `contextId` parameter for channel context

### 2.2 Agent Chat Header Kebab Menu

- [ ] 2.2.1 Add kebab trigger button to agent chat header in `voice.html` (inside `main-header`, after the state pill / header-actions area)
- [ ] 2.2.2 Build agent chat action list function in `voice-chat-controller.js` (or relevant module): dismiss, attach, context, info, reconcile, handoff (conditional on persona)
- [ ] 2.2.3 Wire kebab trigger to open `PortalKebabMenu` with agent chat actions
- [ ] 2.2.4 Implement action handlers: dismiss (with ConfirmDialog), attach (focus iTerm/tmux), context (fetch context), info (navigate/display), reconcile (trigger reconciliation), handoff (with ConfirmDialog, conditional on persona)
- [ ] 2.2.5 Ensure kebab closes on outside click, action selection, and Escape key

### 2.3 Channel Chat Header Kebab Menu

- [ ] 2.3.1 Add kebab trigger button to channel chat header in `voice.html` (inside `channel-chat-header`, right-aligned)
- [ ] 2.3.2 Build channel chat action list function in `voice-channel-chat.js`: add-member, info, complete (chair-only), end/archive (chair-only), copy-slug, leave
- [ ] 2.3.3 Wire kebab trigger to open `PortalKebabMenu` with channel chat actions
- [ ] 2.3.4 Implement chair-only visibility: determine chair status from `VoiceState.channelMembers` and conditionally include complete/end actions
- [ ] 2.3.5 Implement action handlers: add-member (expand picker), info (toggle info panel or navigate), complete (API call), end/archive (with ConfirmDialog), copy-slug (clipboard), leave (API call + navigate back)
- [ ] 2.3.6 Ensure kebab closes on outside click, action selection, and Escape key

### 2.4 Styling

- [ ] 2.4.1 Add CSS for kebab trigger buttons in chat headers (`voice.css`) -- consistent with existing `.agent-kebab-btn` / `.project-kebab-btn` styling
- [ ] 2.4.2 Ensure 44px minimum tap targets on touch devices (`@media (pointer: coarse)`)
- [ ] 2.4.3 Verify menu does not cause layout shifts or interfere with chat input/scrolling
- [ ] 2.4.4 Destructive actions visually differentiated (red text via existing `.kill-action` class)
- [ ] 2.4.5 Divider separating destructive from non-destructive actions

### 2.5 Integration

- [ ] 2.5.1 Close chat header kebab menus when navigating between screens (agent chat <-> channel chat <-> sidebar)
- [ ] 2.5.2 Defer SSE reloads while kebab menu is open (extend existing `_sseReloadDeferred` pattern)
- [ ] 2.5.3 Update `voice-app.js` close-on-outside-click handler to include chat header kebab menus

## 3. Testing (Phase 3)

- [ ] 3.1 Visual verification: agent chat header shows kebab trigger with correct actions
- [ ] 3.2 Visual verification: channel chat header shows kebab trigger with correct actions
- [ ] 3.3 Verify chair-only actions (complete, end) hidden for non-chair members
- [ ] 3.4 Verify destructive actions (dismiss, end, handoff) show ConfirmDialog before executing
- [ ] 3.5 Verify menu closes on: action selection, outside click/tap, Escape key
- [ ] 3.6 Verify touch targets meet 44px minimum on touch devices
- [ ] 3.7 Verify no layout shifts when opening/closing menus
- [ ] 3.8 Verify menus work on both desktop and mobile/tablet viewports
- [ ] 3.9 Test navigation: kebab menus close when switching screens

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete on desktop and mobile viewports
- [ ] 4.4 Playwright screenshot verification of both kebab menus
