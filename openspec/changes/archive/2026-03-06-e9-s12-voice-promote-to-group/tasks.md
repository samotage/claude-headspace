## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Kebab Menu

- [x] 2.1 Register `promote` icon in PortalKebabMenu ICONS registry (voice-chat-controller.js or wherever ICONS is defined)
- [x] 2.2 Add "Create Group Channel" action to `buildAgentChatActions()` in `voice-chat-controller.js`, after "Handoff", guarded by `_agentHasPersona()`
- [x] 2.3 Add `case 'promote'` handler in `handleAgentChatAction()` to trigger the persona picker flow

### Persona Picker Refactor

- [x] 2.4 Refactor `showPersonaPicker()` in `voice-sidebar.js` to accept an optional `onSelect` callback parameter
- [x] 2.5 When `onSelect` callback is provided, invoke it with the selected persona slug instead of calling `_doCreateAgent()`
- [x] 2.6 When invoked from promote action, filter out the current agent's persona from the picker list

### API Integration & UX

- [x] 2.7 Implement promote-to-group API call (`POST /api/agents/<id>/promote-to-group` with `{ persona_slug }`) in the promote handler
- [x] 2.8 Add loading state indicator during the promote API call (inline header text or toast with spinner)
- [x] 2.9 On success: auto-switch voice chat panel to new group channel using `VoiceChannelChat.openChannel()` with channel data from API response
- [x] 2.10 On success: show success toast "Group channel created with [original persona] and [new persona]"
- [x] 2.11 On error: show error toast with failure reason, remain on current agent chat

## 3. Testing (Phase 3)

- [x] 3.1 Verify kebab menu shows "Create Group Channel" only for agents with a persona
- [x] 3.2 Verify persona picker opens with current agent's persona filtered out
- [x] 3.3 Verify promote API call fires with correct payload on persona selection
- [x] 3.4 Verify voice chat panel switches to new group channel on success
- [x] 3.5 Verify error toast displays on API failure
- [x] 3.6 Verify original 1:1 agent chat remains accessible in sidebar after promote
- [x] 3.7 Verify existing persona picker behaviour (agent creation) is not broken by the refactor

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete — full promote-to-group flow on voice page
