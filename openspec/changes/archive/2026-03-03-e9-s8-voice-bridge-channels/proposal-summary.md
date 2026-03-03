# Proposal Summary: e9-s8-voice-bridge-channels

## Voice Bridge Channel Routing Extensions

**PRD:** `docs/prds/channels/e9-s8-voice-bridge-channels-prd.md`
**Branch:** `feature/e9-s8-voice-bridge-channels`
**Change:** `e9-s8-voice-bridge-channels`

## Overview

Extends the existing voice bridge (`/api/voice/command`) with channel awareness. The operator can create channels, send messages, query history, add members, and complete channels -- all via voice. No new endpoints are created; all routing happens within the existing `voice_command()` function.

## Key Capabilities

1. **Channel Intent Detection** -- Regex-based pattern matching for 6 command types (send, history, list, create, add_member, complete) inserted into the voice command pipeline between handoff detection and agent resolution.

2. **Fuzzy Channel Name Matching** -- 4-tier matching algorithm (exact slug -> exact name -> substring -> token overlap) with ambiguity resolution and speech-to-text robustness.

3. **Channel Context Tracking** -- In-memory per-session "current channel" so the operator can say "this channel" in follow-up commands.

4. **VoiceFormatter Channel Methods** -- 7 new formatting methods for channel responses following the existing `{status_line, results, next_action}` envelope pattern.

5. **Voice Chat PWA Channel Display** -- Channel message section in sidebar with SSE-driven real-time updates and tap-through to full message history.

## Files Modified

| File | Change Type |
|------|-------------|
| `src/claude_headspace/routes/voice_bridge.py` | Add channel detection, matching, context, handlers |
| `src/claude_headspace/services/voice_formatter.py` | Add 7 `format_channel_*` methods |
| `static/voice/voice-sidebar.js` | Add channel section rendering |
| `static/voice/voice-sse-handler.js` | Add channel SSE event handlers |
| `static/voice/voice-api.js` | Add channel SSE subscriptions |
| `static/voice/voice-state.js` | Add channels array and currentChannelSlug |

## Dependencies

- **ChannelService (S4)** -- Called but not implemented here. Graceful 503 when unavailable.
- **Channel Data Model (S3)** -- Channel, ChannelMembership models for fuzzy matching.
- **Channel SSE Events (S5)** -- `channel_message` and `channel_update` event types consumed by PWA.
- **Persona System (existing)** -- Persona name/slug lookup for member addition.

## Risk Assessment

- Low risk of false positives: channel patterns use distinctive syntax (colons, question marks, "create ... channel")
- Graceful degradation when ChannelService unavailable (503 with actionable message)
- Existing agent command path is completely unaffected -- utterances without channel patterns fall through

## Task Count

- **Implementation:** 35 tasks across 8 groups
- **Testing:** 27 test tasks across 5 groups
- **Verification:** 4 tasks
