## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Database & Model Layer

- [x] 2.1 Add `transcript_path` column to Agent model (`models/agent.py`)
- [x] 2.2 Create Alembic migration for `transcript_path` column
- [x] 2.3 Run migration against development database

### Hook Infrastructure

- [x] 2.4 Add `POST_TOOL_USE` to `HookEventType` enum in `hook_receiver.py`
- [x] 2.5 Add `POST /hook/post-tool-use` endpoint in `routes/hooks.py`
- [x] 2.6 Implement `process_post_tool_use()` in `hook_receiver.py` (AWAITING_INPUT → PROCESSING resumption)
- [x] 2.7 Enhance `process_notification()` to store `message` and `title` from payload as turn context
- [x] 2.8 Enhance `process_session_start()` to capture and persist `transcript_path` from payload
- [x] 2.9 Add PostToolUse resumption logic in `hook_lifecycle_bridge.py`
- [x] 2.10 Update `bin/install-hooks.sh` with Notification matchers (`elicitation_dialog`, `permission_prompt`, `idle_prompt`) and PostToolUse hooks

### Transcript Content Capture

- [x] 2.11 Create transcript reader utility (read `.jsonl`, extract last agent response, truncate to max length)
- [x] 2.12 Integrate transcript reader into Stop hook processing — populate AGENT/COMPLETION turn text
- [x] 2.13 Handle missing/unreadable transcript files gracefully (warning log, fallback to empty text)

### File Watcher Content Pipeline

- [x] 2.14 Add transcript file registration to file watcher (track file positions for incremental reads)
- [x] 2.15 Implement new entry detection in file watcher polling loop
- [x] 2.16 Wire regex-based question detection (via existing `intent_detector`) on new transcript entries
- [x] 2.17 Implement `awaiting_input_timeout` timer — if no PostToolUse/Stop within timeout, trigger inference
- [x] 2.18 Integrate inference question classification for ambiguous output
- [x] 2.19 Add timer cancellation logic when PostToolUse or Stop events arrive

### Configuration

- [x] 2.20 Add `awaiting_input_timeout` (default 10s) to `file_watcher` section in `config.yaml`
- [x] 2.21 Wire config value through to file watcher service

### Intelligence Integration

- [x] 2.22 Create question classification prompt for inference service
- [x] 2.23 Ensure captured turn text flows through existing summarisation service
- [x] 2.24 Verify priority scoring receives real content from command summaries

## 3. Testing (Phase 3)

### Unit Tests

- [ ] 3.1 Test transcript reader: parse `.jsonl`, extract last agent response, handle edge cases
- [ ] 3.2 Test `process_post_tool_use()` in hook_receiver (AWAITING_INPUT → PROCESSING)
- [ ] 3.3 Test enhanced `process_notification()` with message/title storage
- [ ] 3.4 Test `process_session_start()` transcript_path capture
- [ ] 3.5 Test PostToolUse resumption in hook_lifecycle_bridge
- [ ] 3.6 Test file watcher content pipeline (new entry detection, regex classification, timeout logic)
- [ ] 3.7 Test timer cancellation on PostToolUse/Stop arrival
- [ ] 3.8 Test inference question classification prompt

### Route Tests

- [ ] 3.9 Test `POST /hook/post-tool-use` endpoint (valid payload, missing fields, agent correlation)
- [ ] 3.10 Test enhanced `POST /hook/notification` endpoint (with message/title fields)
- [ ] 3.11 Test `POST /hook/session-start` with transcript_path in payload
- [ ] 3.12 Test `POST /hook/stop` with transcript content extraction

### Integration Tests

- [ ] 3.13 Test full Notification → AWAITING_INPUT → PostToolUse → PROCESSING flow
- [ ] 3.14 Test transcript content capture end-to-end (Stop hook → turn text populated)
- [ ] 3.15 Test file watcher → regex detection → AWAITING_INPUT transition
- [ ] 3.16 Test file watcher → timeout → inference → question classification flow

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification of hook installer output
- [ ] 4.4 Verify transcript_path migration runs cleanly
