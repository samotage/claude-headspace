# Proposal Summary: e9-s12-voice-promote-to-group

## Architecture Decisions

1. **Frontend-only change** -- zero backend work. Consumes S10's existing `POST /api/agents/<id>/promote-to-group` endpoint as-is.
2. **Persona picker parameterisation** -- refactor `showPersonaPicker()` to accept an optional `onSelect` callback rather than duplicating the picker. This keeps the code DRY and avoids a second persona picker UI.
3. **Kebab menu placement** -- "Create Group Channel" lives in the agent chat header kebab only (not the sidebar card). The operator is already in the chat context when the need arises.

## Implementation Approach

The change touches three voice app JS files with minimal surface area:

1. **Add kebab action** in `voice-chat-controller.js` -- insert "Create Group Channel" into `buildAgentChatActions()` after "Handoff" with the same `_agentHasPersona()` guard, add handler in `handleAgentChatAction()`.
2. **Refactor persona picker** in `voice-sidebar.js` -- modify `showPersonaPicker()` to accept an optional callback. When provided, the callback receives the selected persona slug instead of calling `_doCreateAgent()`. Filter out the current agent's persona when invoked from the promote flow.
3. **Wire success handling** -- on 201 response, use `VoiceChannelChat.openChannel()` to switch the chat panel to the new group channel, show success toast.

## Files to Modify

### JavaScript (voice app)
- `static/voice/voice-chat-controller.js` -- kebab menu action + promote handler (primary integration point)
- `static/voice/voice-sidebar.js` -- `showPersonaPicker()` refactor to accept callback, persona filtering logic

### JavaScript (potentially)
- `static/voice/voice-channel-chat.js` -- if `openChannel()` needs any adaptation for promote-originated channel switches
- `static/voice/voice-app.js` or `static/voice/voice-sse-handler.js` -- only if PortalKebabMenu ICONS registry lives here

### No changes required
- Backend Python files -- S10's endpoint is consumed as-is
- HTML templates -- existing voice page markup sufficient
- CSS -- existing voice app styles cover the new UI elements

## Acceptance Criteria

1. Agent chat header kebab shows "Create Group Channel" only for active agents with a persona
2. Clicking the action opens the persona picker with the current agent's persona filtered out
3. Selecting a persona calls `POST /api/agents/<id>/promote-to-group` with `{ persona_slug }`
4. Loading indicator visible during API call
5. On success: voice chat panel switches to new group channel, success toast displayed
6. On error: error toast displayed, remains on current chat
7. Original 1:1 agent chat remains accessible in sidebar
8. Existing persona picker behaviour (agent creation) is not broken by the refactor

## Constraints and Gotchas

1. **`showPersonaPicker()` is hardwired** -- currently calls `_doCreateAgent(projectName, slug)` on selection via a closure over `_pendingPersonaProject`. The refactor must preserve this default behaviour while adding callback support.
2. **No "confirm" step in current picker** -- the existing picker triggers on single click (no separate confirm button). The promote flow should follow the same pattern for consistency.
3. **Persona filtering requires agent persona slug** -- the chat controller must pass the current agent's persona slug to the picker so it can be filtered out. This data is available from the persona badge or agent state.
4. **API response structure** -- the promote endpoint returns `_channel_to_dict(channel)` (201). The `openChannel()` call needs the channel ID from this response.
5. **SSE channel_update** -- the new channel should appear in the sidebar automatically via existing SSE handling. No additional sidebar code needed.

## Git Change History

### Related Files (recent commits)
- `voice-chat-controller.js` -- recent work on draft message preservation (b18dc5eb), kebab menu patterns well established
- `voice-sidebar.js` -- active development for S11 channel creation redesign, persona picker is stable
- `voice-channel-chat.js` -- recent work on member pill state labels (7c073b49), state colors (51241243), draft preservation (b18dc5eb)
- `channels_api.py` -- promote-to-group endpoint added in S10, recently updated for channel membership badges (1b5d8ebf)

### OpenSpec History
- `e9-s8-voice-bridge-channels` (archived 2026-03-03) -- established voice + channels integration patterns

### Patterns Detected
- Voice JS files use IIFE pattern with namespace objects (`VoiceSidebar`, `VoiceChatController`)
- Kebab actions follow `buildActions() -> handleAction(actionId)` pattern
- API calls use `CHUtils.apiFetch()` for fetch with error handling
- Toast notifications via `Toast.success()` / `Toast.error()` or `showToast()`

## Q&A History

No clarifications needed -- the PRD is clear and the backend dependency (S10) is verified present.

## Dependencies

- **S10 promote-to-group endpoint** -- `POST /api/agents/<id>/promote-to-group` (verified present in `channels_api.py`)
- **Voice app kebab system** -- `buildAgentChatActions()`, `handleAgentChatAction()` in `voice-chat-controller.js`
- **Voice persona picker** -- `showPersonaPicker()` in `voice-sidebar.js`
- **Voice channel chat** -- `VoiceChannelChat.openChannel()` for panel switching
- **No new npm/pip dependencies**
- **No database migrations**

## Testing Strategy

1. **Manual testing** (primary) -- the voice app is a standalone HTML+JS page; test the full flow end-to-end:
   - Open voice page, navigate to agent chat for an agent with a persona
   - Open kebab menu, verify "Create Group Channel" appears
   - Click action, verify persona picker opens with current persona filtered out
   - Select persona, verify loading state, verify chat switches to new channel
   - Verify error handling with network failures
2. **Regression** -- verify existing persona picker flow (agent creation) still works
3. **Playwright screenshot verification** -- take before/after screenshots of kebab menu and promote flow

## OpenSpec References

- Proposal: `openspec/changes/e9-s12-voice-promote-to-group/proposal.md`
- Tasks: `openspec/changes/e9-s12-voice-promote-to-group/tasks.md`
- Spec: `openspec/changes/e9-s12-voice-promote-to-group/specs/voice-promote-to-group/spec.md`
