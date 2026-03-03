# Tasks: e9-s8-voice-bridge-channels

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Channel Intent Detection
- [x] 2.1.1 Add `_detect_channel_intent(text)` function to `voice_bridge.py` -- regex-based pattern matching for 6 channel command types (send, history, list, create, add_member, complete) returning action dict or None
- [x] 2.1.2 Implement `_SEND_PATTERNS` regex set for "send to [channel]: [content]", "message [channel]: [content]", "tell [channel]: [content]"
- [x] 2.1.3 Implement `_HISTORY_PATTERNS` regex set for "what's happening in [channel]", "what's going on in [channel]", "show [channel] messages", "channel history for [channel]"
- [x] 2.1.4 Implement `_LIST_PATTERNS` regex set for "list channels", "show channels", "my channels", "what channels am I in"
- [x] 2.1.5 Implement `_CREATE_PATTERNS` regex set for "create a [type] channel [called name] [with members]"
- [x] 2.1.6 Implement `_ADD_MEMBER_PATTERNS` regex set for "add [persona] to [channel]", "add [persona] to this channel"
- [x] 2.1.7 Implement `_COMPLETE_PATTERNS` regex set for "complete/finish/close/end [channel]"
- [x] 2.1.8 Insert channel intent detection into `voice_command()` between handoff detection and agent resolution

### 2.2 Channel Name Matching
- [x] 2.2.1 Add `_match_channel(channel_ref, channels)` function -- fuzzy match against active channels via exact slug, exact name, substring, token overlap
- [x] 2.2.2 Implement article/noise word stripping ("the", "a", "an") and punctuation cleanup
- [x] 2.2.3 Implement ambiguity resolution -- return clarification when multiple matches within 0.2 score gap
- [x] 2.2.4 Implement no-match handling with actionable error response

### 2.3 Channel Context Tracking
- [x] 2.3.1 Add module-level `_channel_context` dict for per-session channel state
- [x] 2.3.2 Add `_set_channel_context(auth_id, channel_slug)` function
- [x] 2.3.3 Add `_get_channel_context(auth_id)` function
- [x] 2.3.4 Add `_get_auth_id()` function -- extract Bearer token or "localhost" from request
- [x] 2.3.5 Add `_resolve_channel_ref(channel_ref, auth_id)` function -- resolve "this channel" / "the channel" to actual slug

### 2.4 Channel Type Inference
- [x] 2.4.1 Add `_CHANNEL_TYPE_KEYWORDS` mapping and `_infer_channel_type(text)` function -- keyword matching with "workshop" default

### 2.5 Member Extraction
- [x] 2.5.1 Add `_extract_member_refs(members_text)` function -- split on "and", ",", "&" separators
- [x] 2.5.2 Add `_match_persona_for_channel(name_ref)` function -- fuzzy match persona name/slug using same algorithm as channel matching

### 2.6 Channel Intent Handler
- [x] 2.6.1 Add `_handle_channel_intent(intent, text, formatter)` dispatch function -- route to appropriate action handler based on intent action
- [x] 2.6.2 Add `_handle_channel_send(intent, channel_service, formatter, auth_id)` -- resolve channel, call `ChannelService.send_message()`, format response
- [x] 2.6.3 Add `_handle_channel_history(intent, channel_service, formatter, auth_id)` -- resolve channel, retrieve last 10 messages, format summary
- [x] 2.6.4 Add `_handle_channel_list(channel_service, operator_persona, formatter)` -- list operator's visible channels
- [x] 2.6.5 Add `_handle_channel_create(intent, channel_service, formatter, auth_id)` -- infer type, extract members, create channel, add members
- [x] 2.6.6 Add `_handle_channel_add_member(intent, channel_service, formatter, auth_id)` -- resolve persona and channel, add member
- [x] 2.6.7 Add `_handle_channel_complete(intent, channel_service, formatter, auth_id)` -- resolve channel, complete it
- [x] 2.6.8 Add operator persona resolution via `Persona.get_operator()` as prerequisite for channel operations

### 2.7 VoiceFormatter Channel Methods
- [x] 2.7.1 Add `format_channel_message_sent(channel_slug)` method
- [x] 2.7.2 Add `format_channel_history(channel_slug, messages, verbosity)` method -- format last N messages with persona attribution
- [x] 2.7.3 Add `format_channel_created(channel_slug, channel_type, member_results)` method
- [x] 2.7.4 Add `format_channel_completed(channel_slug)` method
- [x] 2.7.5 Add `format_channel_list(channels)` method -- format channel list with slug, type, status
- [x] 2.7.6 Add `format_channel_member_added(persona_name, channel_slug, spinning_up)` method

### 2.8 Voice Chat PWA Channel Display
- [x] 2.8.1 Add `channels` array and `currentChannelSlug` to `voice-state.js`
- [x] 2.8.2 Add `handleChannelMessage()` and `handleChannelUpdate()` SSE event handlers to `voice-sse-handler.js`
- [x] 2.8.3 Add SSE event type subscriptions for `channel_message` and `channel_update` to `voice-api.js`
- [x] 2.8.4 Add channel section rendering to `voice-sidebar.js` -- channel cards below agent list with name, status, sender, preview, timestamp
- [x] 2.8.5 Add channel message tap-through to channel detail view with conversational envelope format
- [x] 2.8.6 Apply channel message colour conventions: cyan for operator, green for agents, muted/italic for system

## 3. Testing (Phase 3)

### 3.1 Channel Intent Detection Tests
- [x] 3.1.1 Test `_detect_channel_intent()` returns correct action for each of the 6 command types
- [x] 3.1.2 Test send patterns extract channel_ref and content correctly
- [x] 3.1.3 Test history patterns extract channel_ref correctly
- [x] 3.1.4 Test create patterns extract channel_type, name, and member_refs
- [x] 3.1.5 Test add_member patterns extract persona_ref and channel_ref
- [x] 3.1.6 Test complete patterns extract channel_ref
- [x] 3.1.7 Test list patterns match all variants ("list channels", "show channels", "my channels")
- [x] 3.1.8 Test non-channel utterances return None (no false positives on agent commands)

### 3.2 Channel Name Matching Tests
- [x] 3.2.1 Test exact slug match returns confidence 1.0
- [x] 3.2.2 Test exact name match (case-insensitive) returns confidence 1.0
- [x] 3.2.3 Test substring match returns correct candidate
- [x] 3.2.4 Test token overlap match handles word reordering
- [x] 3.2.5 Test ambiguous matches return clarification with all close matches
- [x] 3.2.6 Test no match returns no_match result
- [x] 3.2.7 Test article stripping ("the workshop" matches "workshop")
- [x] 3.2.8 Test speech-to-text artifact tolerance (singular/plural, filler words)

### 3.3 Channel Context Tests
- [x] 3.3.1 Test context set and get for auth token
- [x] 3.3.2 Test "this channel" resolves to last-set context
- [x] 3.3.3 Test "this channel" raises ValueError when no context set
- [x] 3.3.4 Test different auth tokens have independent contexts

### 3.4 VoiceFormatter Channel Tests
- [x] 3.4.1 Test `format_channel_message_sent()` returns correct structure
- [x] 3.4.2 Test `format_channel_history()` with messages, empty, and concise verbosity
- [x] 3.4.3 Test `format_channel_created()` includes member results
- [x] 3.4.4 Test `format_channel_completed()` returns correct structure
- [x] 3.4.5 Test `format_channel_list()` with channels and empty state
- [x] 3.4.6 Test `format_channel_member_added()` with and without spinning_up flag

### 3.5 Integration Tests
- [x] 3.5.1 Test `/api/voice/command` routes channel send to `ChannelService.send_message()` (mocked)
- [x] 3.5.2 Test `/api/voice/command` routes channel history retrieval (mocked)
- [x] 3.5.3 Test `/api/voice/command` returns 503 when channel_service not registered
- [x] 3.5.4 Test existing agent commands still work unaffected by channel detection
- [x] 3.5.5 Test channel detection pipeline ordering: handoff -> channel -> agent

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete -- voice commands route to channels, existing agent path unaffected
- [x] 4.4 All existing voice bridge tests continue to pass
