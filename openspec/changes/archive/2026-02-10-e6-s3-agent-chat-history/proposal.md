## Why

The Voice Bridge chat screen currently shows conversation turns scoped to a single task. When a command completes, the previous conversation disappears. Additionally, the agent's intermediate commentary (e.g., "Let me explore...", "I'll check that...") is only captured as a single blob when the turn completes — users don't see individual messages appearing in real-time as the agent works. This makes the chat feel like disconnected fragments rather than a continuous conversation.

## What Changes

### Real-Time Intermediate Message Capture
- Capture agent text output between tool calls as individual PROGRESS turns during post-tool-use hook processing
- Incremental transcript reading from last known position to avoid re-reading
- Deduplication between intermediate PROGRESS turns and the final COMPLETION turn from the stop hook
- Non-blocking capture (must add <50ms to post-tool-use hook response)

### Agent-Lifetime Conversation View
- Transcript endpoint returns turns across ALL tasks for an agent, ordered chronologically
- Each turn includes command_id for client-side command boundary detection
- Task metadata (instruction, state) included for rendering separators

### Cursor-Based Pagination
- Transcript endpoint supports cursor-based pagination (turn ID as cursor)
- Default page size: 50 most recent turns
- Client requests older turns by specifying cursor (oldest turn ID from previous page)
- Returns `has_more` flag for infinite scroll control

### Client-Side Enhancements (voice-app.js)
- iMessage-style timestamps (time-only today, "Yesterday", day-of-week this week, date for older)
- Smart grouping of rapid consecutive agent messages (within 2 seconds) into single bubbles
- Task boundary separators showing command instruction
- Scroll-up pagination with loading indicator and scroll position preservation
- Ended agent support: read-only mode with "Agent ended" banner, no input bar

### Chat Links Everywhere
- Chat links on project show page agent rows (active and ended agents)
- Chat links on activity page where agents are referenced
- Ended agent chat opens in read-only mode

## Impact

- Affected specs: voice-bridge (existing), voice-bridge-client (existing)
- Affected code:
  - `src/claude_headspace/routes/voice_bridge.py` — transcript endpoint pagination + agent-scoped query
  - `src/claude_headspace/services/hook_lifecycle_bridge.py` — intermediate PROGRESS turn capture in post-tool-use
  - `src/claude_headspace/services/transcript_reader.py` — incremental read for intermediate capture
  - `src/claude_headspace/services/hook_receiver.py` — deduplication tracking, transcript position state
  - `static/voice/voice-app.js` — pagination, smart grouping, timestamps, command separators, ended agent UI
  - `static/voice/voice-api.js` — pagination params, ended agent transcript fetch
  - `static/voice/voice.css` — command separator styles, loading indicator, ended agent banner
  - `templates/project_show.html` — chat links for agents
  - `static/js/project_show.js` — render chat links in agent rows
  - `static/js/activity.js` — render chat links in agent references
  - `templates/activity.html` — (no template changes needed; JS renders agent references)
- Related OpenSpec history:
  - e6-s1-voice-bridge-server (2026-02-09) — server API and transcript endpoint
  - e6-s2-voice-bridge-client (2026-02-09) — PWA client and chat screen
  - e5-s4-tmux-bridge (2026-02-04) — underlying tmux bridge for commands
