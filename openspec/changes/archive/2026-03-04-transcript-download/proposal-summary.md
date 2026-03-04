# Proposal Summary: transcript-download

## Architecture Decisions

1. **New service + new route blueprint** -- TranscriptExportService handles assembly logic, a dedicated blueprint handles HTTP delivery. This follows the established pattern where routes are thin wrappers and services contain business logic.

2. **Database-first assembly** -- Transcripts are assembled from existing database records (Turn, Command, Agent, Message, Channel, Persona models) rather than raw JSONL files. This ensures consistency with what the user sees in the dashboard/voice app and avoids filesystem parsing complexity.

3. **Dual delivery** -- Each transcript is both returned as a browser download (Content-Disposition: attachment) and saved server-side to `data/transcripts/`. This gives users immediate access plus persistent server-side copies.

4. **No database migrations** -- The feature reads existing models only. No new tables or columns needed.

5. **Portal kebab menu pattern** -- Voice app and dashboard agent kebab menus use the existing PortalKebabMenu component with its action builder/handler pattern. Dashboard channel chat uses the inline kebab menu pattern already in the template.

## Implementation Approach

### Backend

Create `TranscriptExportService` with two main methods:
- `assemble_agent_transcript(agent_id)` -- queries Turn records across all Commands for the agent, builds Markdown with YAML frontmatter
- `assemble_channel_transcript(channel_slug)` -- queries Message records for the channel, builds Markdown with YAML frontmatter

Both methods return a tuple of `(filename, markdown_content)` and handle server-side persistence.

Create `transcript_download_bp` blueprint with two endpoints:
- `GET /api/agents/<agent_id>/transcript`
- `GET /api/channels/<slug>/transcript`

### Frontend

Add a `download` SVG icon to PortalKebabMenu.ICONS. Then add "Download Transcript" as a menu action in all 4 locations:

1. **Voice agent kebab** (`voice-sidebar.js`): Add to `_buildVoiceActions`, handle in `_handleVoiceAction`
2. **Voice channel kebab** (`voice-channel-chat.js`): Add to `buildChannelChatActions`, handle in `handleChannelChatAction`
3. **Dashboard agent kebab** (`agent-lifecycle.js`): Add to `buildDashboardActions`, handle in `handleDashboardAction`
4. **Dashboard channel kebab** (`channel-chat.js` + `_channel_chat_panel.html`): Add button to template, handle in `_handleKebabAction`

Download is triggered via `window.open()` or a hidden anchor element to initiate the browser download without blocking the UI.

## Files to Modify

### New Files
- `src/claude_headspace/services/transcript_export.py` -- transcript assembly service
- `src/claude_headspace/routes/transcript_download.py` -- download API blueprint
- `data/transcripts/.gitkeep` -- server-side storage directory

### Modified Files (Backend)
- `src/claude_headspace/app.py` -- register transcript_download blueprint

### Modified Files (Frontend)
- `static/js/portal-kebab-menu.js` -- add `download` icon to ICONS
- `static/voice/voice-sidebar.js` -- add download action to agent kebab menu
- `static/voice/voice-channel-chat.js` -- add download action to channel kebab menu
- `static/js/agent-lifecycle.js` -- add download action to dashboard agent kebab menu
- `static/js/channel-chat.js` -- add download handler for dashboard channel kebab
- `templates/partials/_channel_chat_panel.html` -- add download button to inline kebab menu

### Test Files (New)
- `tests/services/test_transcript_export.py` -- service unit tests
- `tests/routes/test_transcript_download.py` -- route tests

## Acceptance Criteria

1. User can download agent session transcript as .md from voice app agent kebab menu
2. User can download channel chat transcript as .md from voice app channel kebab menu
3. User can download agent session transcript from dashboard agent card kebab menu
4. User can download channel chat transcript from dashboard channel chat kebab menu
5. Downloaded file has YAML frontmatter with all specified metadata fields
6. Every message attributed by display name with timestamp
7. Server-side copy saved in `data/transcripts/` with correct filename convention
8. Transcripts are clean, human-readable Markdown
9. Download does not block the chat UI
10. Visual feedback (toast) during transcript assembly

## Constraints and Gotchas

- **Internal turns excluded**: Turn.is_internal = true entries (team sub-agent communications) must be filtered out of agent session transcripts
- **Persona fallback**: Agents without personas should use "unknown" as persona_slug in filenames and "Agent" as display name
- **Channel chair resolution**: Channel transcripts need to resolve the chair persona via ChannelMembership.is_chair
- **data/transcripts/ gitignored**: The directory should be created with .gitkeep but actual transcript files should be gitignored (they contain session content)
- **Large conversations**: NFR1 requires handling thousands of messages without timeout -- streaming or chunked assembly may be needed for very large sessions, but initial implementation with simple query + string concatenation should suffice for realistic sizes
- **Dashboard channel kebab is inline**: Unlike the portal-based menus, the dashboard channel chat uses an inline HTML kebab menu in the Jinja template, requiring a different integration pattern (adding a `<button>` element to the template + JS handler)

## Git Change History

### Related OpenSpec History
- `e5-s2-project-show-core` -- prior change establishing project-level features pattern
- `e9-s5-api-sse-endpoints` -- channels API endpoints pattern
- `e9-s7-dashboard-ui` -- dashboard channel chat UI pattern
- `2026-03-04-voice-app-kebab-menus` -- most recent: added kebab menus to voice app (direct predecessor)

### Recent Related Commits
- `f679208` -- "style: rename 'End Channel' to 'Archive Channel' in kebab menu" (2026-03-05)
- `1d8d9ac` -- "docs: add voice app kebab menus and transcript download PRDs" (2026-03-05)
- `8ee6b96` -- "fix: channel chat kebab menu transparent background" (2026-03-04)
- `3324266` -- "feat: channel chat UX improvements -- agent auth header, self-join, kebab menu" (2026-03-04)
- `4ddff90c` -- "feat(handoff): implement end-to-end agent handoff via kebab menu" (2026-03-01)

### Patterns Detected
- Portal kebab menu pattern: actions array + onAction callback via PortalKebabMenu.open()
- Dashboard channel kebab: inline HTML buttons + delegated click handler via data-action attributes
- Service registration: `app.extensions["service_name"]` pattern
- Route blueprint: thin wrapper + service delegation pattern

## Q&A History

No clarifications needed -- PRD is clear and complete.

## Dependencies

- No new Python packages required
- No new npm packages required
- No database migrations required
- Depends on existing models: Turn, Command, Agent, Message, Channel, Persona, ChannelMembership
- Depends on PRD: Voice App Kebab Menus (already implemented as of 2026-03-04)

## Testing Strategy

### Unit Tests (services)
- `test_transcript_export.py`: Test agent session assembly (multiple commands, turns ordering, internal turn filtering, empty sessions, persona fallback), channel assembly (multiple participants, message ordering, empty channels), metadata/frontmatter generation, filename generation

### Route Tests (routes)
- `test_transcript_download.py`: Test agent transcript endpoint (200 success, 404 missing agent, Content-Disposition headers), channel transcript endpoint (200 success, 404 missing channel, Content-Disposition headers), server-side file persistence

### Manual Verification
- Download from all 4 kebab menu locations
- Verify Markdown output is clean and usable
- Verify toast feedback during download

## OpenSpec References

- Proposal: `openspec/changes/transcript-download/proposal.md`
- Tasks: `openspec/changes/transcript-download/tasks.md`
- Spec: `openspec/changes/transcript-download/specs/transcript-download/spec.md`
