## Why

Conversations in Claude Headspace -- both 1:1 agent sessions and group channel chats -- contain valuable content for debugging, content creation, and external analysis. Currently this content is trapped inside the dashboard with no way to export it. Users need a clean, human-readable export to use conversation content externally.

## What Changes

### Backend (New)
- **TranscriptExportService** (`src/claude_headspace/services/transcript_export.py`) -- assembles agent session transcripts (from Turn records across all Commands) and channel chat transcripts (from Message records) into Markdown with YAML frontmatter
- **Transcript download route** (`src/claude_headspace/routes/transcript_download.py`) -- new blueprint with endpoints for agent session and channel transcript download, server-side persistence to `data/transcripts/`

### Frontend (Modified)
- **Voice app agent kebab menu** (`static/voice/voice-sidebar.js`) -- add "Download Transcript" action to `_buildVoiceActions` and handler in `_handleVoiceAction`
- **Voice app channel kebab menu** (`static/voice/voice-channel-chat.js`) -- add "Download Transcript" action to `buildChannelChatActions` and handler in `handleChannelChatAction`
- **Dashboard agent card kebab menu** (`static/js/agent-lifecycle.js`) -- add "Download Transcript" action to `buildDashboardActions` and handler in `handleDashboardAction`
- **Dashboard channel chat kebab menu** (`static/js/channel-chat.js`) -- add "Download Transcript" action to `_handleKebabAction` and menu item to template
- **Dashboard channel chat template** (`templates/partials/_channel_chat_panel.html`) -- add "Download Transcript" button to kebab menu items
- **Portal kebab menu icons** (`static/js/portal-kebab-menu.js`) -- add `download` SVG icon to ICONS object

### Infrastructure
- `data/transcripts/` directory for server-side persistent copies

## Impact

- Affected specs: agent sessions (Turn/Command model queries), channels (Message model queries), kebab menus (4 locations)
- Affected code:
  - New: `src/claude_headspace/services/transcript_export.py`, `src/claude_headspace/routes/transcript_download.py`
  - Modified: `static/voice/voice-sidebar.js`, `static/voice/voice-channel-chat.js`, `static/js/agent-lifecycle.js`, `static/js/channel-chat.js`, `static/js/portal-kebab-menu.js`, `templates/partials/_channel_chat_panel.html`, `src/claude_headspace/app.py` (blueprint registration)
- No database migrations required -- reads existing Turn, Command, Agent, Message, Channel, Persona models
- No breaking changes
