## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend

- [x] 2.1 Create `TranscriptExportService` (`src/claude_headspace/services/transcript_export.py`)
  - Agent session transcript assembly: query all Turns across all Commands for an Agent, ordered chronologically
  - Channel chat transcript assembly: query all Messages for a Channel, ordered chronologically
  - Markdown formatting with YAML frontmatter (FR4): type, identifier, project, persona, agent_id, participants, start_time, end_time, message_count, exported_at
  - Message body formatting (FR3/FR5): actor display name, timestamp, full message text
  - Filename generation (FR6): `{type}-{persona_slug}-{agent_id}-{datetime}.md`
  - Server-side persistence (FR7): save to `data/transcripts/`

- [x] 2.2 Create transcript download route (`src/claude_headspace/routes/transcript_download.py`)
  - `GET /api/agents/<agent_id>/transcript` -- assemble and download agent session transcript
  - `GET /api/channels/<slug>/transcript` -- assemble and download channel chat transcript
  - Content-Disposition header for browser download (FR8)
  - Error handling for missing agents/channels

- [x] 2.3 Register blueprint in `app.py`

- [x] 2.4 Create `data/transcripts/` directory with `.gitkeep`

### Frontend -- Icons

- [x] 2.5 Add `download` SVG icon to `PortalKebabMenu.ICONS` in `static/js/portal-kebab-menu.js`

### Frontend -- Voice App Agent Kebab (FR9)

- [x] 2.6 Add "Download Transcript" action to `_buildVoiceActions` in `static/voice/voice-sidebar.js`
- [x] 2.7 Add download handler to `_handleVoiceAction` in `static/voice/voice-sidebar.js`

### Frontend -- Voice App Channel Kebab (FR10)

- [x] 2.8 Add "Download Transcript" action to `buildChannelChatActions` in `static/voice/voice-channel-chat.js`
- [x] 2.9 Add download handler to `handleChannelChatAction` in `static/voice/voice-channel-chat.js`

### Frontend -- Dashboard Agent Card Kebab (FR11)

- [x] 2.10 Add "Download Transcript" action to `buildDashboardActions` in `static/js/agent-lifecycle.js`
- [x] 2.11 Add download handler to `handleDashboardAction` in `static/js/agent-lifecycle.js`

### Frontend -- Dashboard Channel Chat Kebab (FR12)

- [x] 2.12 Add "Download Transcript" menu item to `templates/partials/_channel_chat_panel.html`
- [x] 2.13 Add download handler to `_handleKebabAction` in `static/js/channel-chat.js`

### Frontend -- Loading Feedback (FR13)

- [x] 2.14 Add visual feedback (loading state indicator) while transcript is being assembled in all 4 download handlers

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for `TranscriptExportService` -- agent session transcript assembly, metadata formatting, filename generation
- [x] 3.2 Unit tests for `TranscriptExportService` -- channel chat transcript assembly with multiple participants
- [x] 3.3 Route tests for `/api/agents/<agent_id>/transcript` -- success, missing agent, empty session
- [x] 3.4 Route tests for `/api/channels/<slug>/transcript` -- success, missing channel, empty channel
- [x] 3.5 Verify server-side file persistence in `data/transcripts/`

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete -- download from all 4 kebab menu locations
- [ ] 4.4 Verify Markdown output is clean and human-readable
