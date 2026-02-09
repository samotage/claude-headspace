# Proposal Summary: e6-s2-voice-bridge-client

## Architecture Decisions
- Pure vanilla JS PWA — no frameworks, no build step, no bundler
- All files served from `static/voice/` as static assets via Flask
- Browser-native APIs only: Web Speech API (SpeechRecognition), SpeechSynthesis, Web Audio API (oscillator tones)
- localStorage for all settings, auth tokens, and user preferences
- SSE for real-time agent status updates (same `/api/events/stream` endpoint the dashboard uses)
- Mobile-first CSS (no Tailwind — standalone CSS file for the PWA)

## Implementation Approach
- Build as a standalone PWA in `static/voice/` — completely independent of the main dashboard
- 5 JS modules: `voice-input.js`, `voice-output.js`, `voice-api.js`, `voice-app.js`, plus the service worker `sw.js`
- Single HTML entry point (`voice.html`) with screen-based navigation via CSS show/hide
- Service worker caches app shell (cache-first), uses network-first for API calls
- Flask route at `/voice` serves the HTML; static files served by Flask's built-in static handler
- Audio cues via Web Audio API oscillator tones (no audio file dependencies)

## Files to Modify

### New Files (static/voice/)
- `static/voice/voice.html` — PWA entry point, app shell structure
- `static/voice/voice.css` — mobile-first responsive CSS
- `static/voice/voice-input.js` — SpeechRecognition wrapper (silence timeout, done-word, debounce)
- `static/voice/voice-output.js` — SpeechSynthesis wrapper + Web Audio API cues
- `static/voice/voice-api.js` — HTTP client + SSE connection + Bearer auth
- `static/voice/voice-app.js` — main app controller (screens, state, events)
- `static/voice/manifest.json` — PWA manifest (standalone, icons, theme)
- `static/voice/sw.js` — service worker (cache-first static, network-first API)
- `static/voice/icons/icon-192.png` — placeholder PWA icon
- `static/voice/icons/icon-512.png` — placeholder PWA icon

### Modified Files
- `src/claude_headspace/routes/voice_bridge.py` — add `/voice` route to serve PWA HTML

## Acceptance Criteria
- PWA installable via "Add to Home Screen" on iOS Safari
- Launches in standalone mode (no browser chrome)
- Voice input via SpeechRecognition with configurable silence timeout
- Done-word detection ("send", "over", "done") for immediate finalization
- Debounce prevents utterance splitting
- Text input fallback available
- TTS reads responses with structured pauses between sections
- Audio cues play for key events (ready, sent, needs-input, error)
- Agent list shows real-time status via SSE
- Auto-targets single awaiting agent
- Structured questions display as tappable buttons
- Bearer token authentication for all API calls
- Settings persist in localStorage
- App shell loads offline via service worker
- Bundle size under 100KB uncompressed

## Constraints and Gotchas
- Web Speech API (`SpeechRecognition`) requires HTTPS or localhost — LAN access over HTTP may not work on all browsers; iOS Safari may have limitations
- `SpeechRecognition` is `webkitSpeechRecognition` on Safari/iOS — must use vendor prefix
- iOS Safari has restrictions on audio playback without user gesture — audio cues must be initialized after first user tap
- Service worker scope is limited to its directory — must be at `/static/voice/sw.js` and scope set to `/static/voice/`
- SSE connection shares the same `/api/events/stream` endpoint as the main dashboard — filter for relevant event types only
- The voice bridge server API (e6-s1) endpoints: `/api/voice/sessions`, `/api/voice/command`, `/api/voice/agents/<id>/output`, `/api/voice/agents/<id>/question`
- All API responses include a `voice` object with `{status_line, results[], next_action}` format
- Bearer token auth required on all `/api/voice/*` endpoints

## Git Change History

### Related Files
- Routes: `src/claude_headspace/routes/voice_bridge.py` (existing, add /voice route)
- Services: `src/claude_headspace/services/voice_auth.py` (existing, token auth)
- Services: `src/claude_headspace/services/voice_formatter.py` (existing, response formatting)
- Models: `src/claude_headspace/models/turn.py` (existing, voice bridge columns added in e6-s1)
- Config: `config.yaml` (voice_bridge section added in e6-s1)
- Static: `static/voice/` (new directory)

### OpenSpec History
- e6-s1-voice-bridge-server (2026-02-09) — server API this client consumes (merged, PR #51)
- e5-s4-tmux-bridge (2026-02-04) — underlying tmux bridge for command delivery
- e5-s7-dashboard-respond (2026-02-06) — respond UI in main dashboard

### Implementation Patterns
- Vanilla JS modules — consistent with existing `static/js/` patterns in the project
- No build step — all JS served directly as static files
- Service registration pattern not needed (client-side only)
- Flask blueprint route addition follows existing pattern in `voice_bridge.py`

## Q&A History
- No clarifications needed — PRD was clear and complete
- No gaps or conflicts detected during proposal review

## Dependencies
- No new Python packages needed
- No new npm packages needed
- No database migrations needed
- Relies on voice bridge server API (e6-s1, already merged)
- Relies on existing SSE endpoint (`/api/events/stream`)

## Testing Strategy
- **voice-api.js tests** — mock fetch, token auth headers, error handling, SSE reconnection
- **voice-input.js tests** — SpeechRecognition mock, utterance detection, done-word stripping, debounce, timeout configuration
- **voice-output.js tests** — SpeechSynthesis mock, TTS queue, audio cue generation, toggle persistence
- **voice-app.js tests** — screen navigation, agent list rendering, auto-target logic, question display
- **Settings tests** — localStorage read/write, default values, immediate application
- **Service worker tests** — cache strategy verification, offline app shell
- **PWA manifest tests** — installability, standalone mode, icon references
- Note: These are client-side JS tests. Since the project uses pytest for Python, testing approach for JS modules should use simple inline test harness or validate via route-level Python tests for the Flask serving route.

## OpenSpec References
- proposal.md: openspec/changes/e6-s2-voice-bridge-client/proposal.md
- tasks.md: openspec/changes/e6-s2-voice-bridge-client/tasks.md
- spec.md: openspec/changes/e6-s2-voice-bridge-client/specs/voice-bridge-client/spec.md
