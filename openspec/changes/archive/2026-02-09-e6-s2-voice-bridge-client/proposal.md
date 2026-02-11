## Why

Claude Headspace's Voice Bridge Server (e6-s1) provides voice-friendly API endpoints but has no mobile client to consume them. Users must be at their Mac to interact with agents. A PWA mobile client completes the hands-free interaction loop, enabling voice commands and responses from iPhone/iPad on the same LAN.

## What Changes

### PWA App Shell
- New `static/voice/` directory containing the complete PWA client
- `voice.html` — single-page application entry point served by Flask
- `manifest.json` — PWA manifest for "Add to Home Screen" with standalone mode
- `sw.js` — service worker for app shell caching (offline load, online API calls)

### Speech Input Module
- `voice-input.js` — speech recognition via Web Speech API (`SpeechRecognition`)
- Automatic end-of-utterance detection with configurable silence timeout (600-1200ms)
- Done-word detection ("send", "over", "done") for immediate finalization
- Debounce mechanism to prevent utterance splitting
- Text input fallback for quiet environments

### Speech Output Module
- `voice-output.js` — text-to-speech via `SpeechSynthesis` API
- Reads voice-friendly responses: status line, key results, next action (with pauses)
- Audio cues (Web Audio API oscillator tones): ready, sent, needs-input, error
- Toggleable TTS and audio cues

### Agent Interaction UI
- Agent list view with project name, state (colour-coded), input-needed indicator, task summary
- Question presentation: structured options as tappable buttons OR free-text input
- Auto-targeting: single awaiting agent receives commands automatically
- Tap or voice to target specific agent

### API Client
- `voice-api.js` — HTTP client for voice bridge endpoints (sessions, command, output, question)
- Bearer token authentication from localStorage
- SSE connection for real-time agent status updates
- Auto-reconnect with exponential backoff, polling fallback

### Flask Route
- New route to serve `voice.html` at `/voice` (or `/api/voice/app`)
- Serves static files from `static/voice/`

### Configuration
- Settings screen: server URL, token, silence timeout, done-word, TTS toggle, audio cues, verbosity

## Impact

- Affected specs: voice-bridge-client (new)
- Affected code:
  - `static/voice/voice.html` — PWA entry point (new)
  - `static/voice/voice-input.js` — speech recognition module (new)
  - `static/voice/voice-output.js` — TTS and audio cues module (new)
  - `static/voice/voice-api.js` — API client and SSE module (new)
  - `static/voice/voice-app.js` — main app logic and UI controller (new)
  - `static/voice/voice.css` — mobile-first CSS (new)
  - `static/voice/manifest.json` — PWA manifest (new)
  - `static/voice/sw.js` — service worker (new)
  - `static/voice/icons/` — PWA icons (new)
  - `src/claude_headspace/routes/voice_bridge.py` — add route to serve voice app
  - `src/claude_headspace/app.py` — no changes needed (blueprint already registered)
- Related OpenSpec history:
  - e6-s1-voice-bridge-server (2026-02-09) — server API this client consumes
  - e5-s4-tmux-bridge (2026-02-04) — underlying tmux bridge
