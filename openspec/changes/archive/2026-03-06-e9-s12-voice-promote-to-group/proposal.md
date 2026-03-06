## Why

The voice app (`/voice`) is the operator's primary interaction surface, but the promote-to-group-channel capability delivered in S10 was only wired into the dashboard. This sprint closes that gap, bringing the same "Create Group Channel" action into the voice app's agent chat header kebab menu so the operator can promote a 1:1 conversation to a multi-agent group channel without leaving the voice interface.

## What Changes

- **Agent chat header kebab menu** (`voice-chat-controller.js`): Add "Create Group Channel" action after "Handoff", guarded by `_agentHasPersona()`
- **Portal kebab icon**: Register a `promote` icon in the `PortalKebabMenu.ICONS` registry (e.g. `addMember`-derived SVG conveying "add to group")
- **Persona picker parameterisation** (`voice-sidebar.js`): Refactor `showPersonaPicker()` to accept an optional callback parameter, so it can drive the promote-to-group flow instead of always calling `_doCreateAgent()`
- **Persona filtering**: Filter out the current agent's persona from the picker when invoked from the promote action
- **API integration**: Call `POST /api/agents/<id>/promote-to-group` with `{ "persona_slug": "<slug>" }` on picker confirmation
- **Loading state**: Show inline loading indicator or toast during the async promote operation
- **Success handling**: Auto-switch voice chat panel to the new group channel via `VoiceChannelChat.openChannel()` and show success toast
- **Error handling**: Show error toast on failure, remain on current chat, no partial cleanup needed (backend handles rollback)

## Impact

- Affected specs: voice-pwa-channels, channel-intent-detection
- Affected code:
  - `static/voice/voice-chat-controller.js` -- kebab menu action + promote handler
  - `static/voice/voice-sidebar.js` -- persona picker refactor to accept callback, persona filtering
  - `static/voice/voice-channel-chat.js` -- may need minor integration for auto-switch on promote success
  - No backend changes -- consumes existing `POST /api/agents/<id>/promote-to-group` from S10

### Git Context

Recent channel work (S11/S12) has focused on member pill styling, channel creation redesign, and delivery fixes. The voice app JS files (`voice-chat-controller.js`, `voice-sidebar.js`, `voice-channel-chat.js`) are actively developed with established patterns for kebab actions, persona picker, and channel chat switching.

The `showPersonaPicker()` function in `voice-sidebar.js` is currently hardwired: on persona selection, it calls `_doCreateAgent(projectName, slug)`. This needs a small refactor to accept an optional callback, which is the main integration point for this change.

OpenSpec history shows `e9-s8-voice-bridge-channels` as the most recent voice+channels change, establishing patterns for channel-related voice features.
