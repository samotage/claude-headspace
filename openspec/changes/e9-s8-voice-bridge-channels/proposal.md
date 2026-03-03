# Proposal: e9-s8-voice-bridge-channels

## Why

The voice bridge is the operator's primary hands-free interface for managing agents, but it has no awareness of channels. With channel infrastructure landing in Sprints 3-7, the operator needs to route channel operations via voice as naturally as agent commands -- saying "send to the workshop channel: let's align on the persona spec" and having it land in the right channel without switching to the dashboard or CLI.

## What Changes

- Add channel intent detection stage to `voice_command()` in `voice_bridge.py`, inserted between handoff detection and agent resolution
- Implement regex-based pattern matching for 6 channel command types: send, history, list, create, add_member, complete
- Add fuzzy channel name matching (exact slug -> exact name -> substring -> token overlap) against active channels
- Add fuzzy persona name matching for member addition commands using the same algorithm
- Add in-memory per-session channel context tracking ("this channel" / "the channel" resolution)
- Add channel type inference from voice keywords (workshop, delegation, review, standup, broadcast)
- Add member list extraction from "with X and Y" suffixes in create commands
- Add 7 new `format_channel_*` methods to `VoiceFormatter` for channel response formatting
- Add channel message display section to Voice Chat PWA sidebar (`voice-sidebar.js`)
- Add `channel_message` and `channel_update` SSE event handlers to Voice Chat PWA (`voice-sse-handler.js`, `voice-api.js`)
- Add `channels` array and `currentChannelSlug` to `voice-state.js`

## Impact

### Affected specs
- None directly modified -- this sprint extends existing voice bridge capabilities with channel routing

### Affected code

**Modified files:**
- `src/claude_headspace/routes/voice_bridge.py` -- add `_detect_channel_intent()`, `_match_channel()`, `_match_persona_for_channel()`, `_handle_channel_intent()` and 6 action handlers, channel context tracking functions
- `src/claude_headspace/services/voice_formatter.py` -- add `format_channel_message_sent()`, `format_channel_history()`, `format_channel_created()`, `format_channel_completed()`, `format_channel_list()`, `format_channel_member_added()`, `format_channel_error()` methods
- `static/voice/voice-sidebar.js` -- add channel section rendering below agent list
- `static/voice/voice-sse-handler.js` -- add `handleChannelMessage()` and `handleChannelUpdate()` SSE event handlers
- `static/voice/voice-api.js` -- add SSE event type subscriptions for `channel_message` and `channel_update`
- `static/voice/voice-state.js` -- add `channels` array and `currentChannelSlug` state

**New files:**
- None -- all changes are modifications to existing files

### Breaking changes
None -- channel intent detection only activates on channel-targeted utterances. Utterances without channel patterns continue through the existing agent resolution path unchanged.
