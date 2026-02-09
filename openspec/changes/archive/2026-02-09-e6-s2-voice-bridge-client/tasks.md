## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### PWA Foundation

- [x] 2.1 Create `static/voice/` directory structure (html, css, js, icons, manifest, sw)
- [x] 2.2 Create `voice.html` — PWA entry point with viewport meta, manifest link, app shell structure
- [x] 2.3 Create `manifest.json` — PWA manifest with name, icons, display:standalone, theme colours
- [x] 2.4 Create `sw.js` — service worker for app shell caching (cache-first for static, network-first for API)
- [x] 2.5 Create `voice.css` — mobile-first responsive CSS for all screens (agent list, listening, question, settings)

### Speech Input

- [x] 2.6 Create `voice-input.js` — SpeechRecognition wrapper with start/stop/abort
- [x] 2.7 Implement end-of-utterance detection with configurable silence timeout (default 800ms, range 600-1200ms)
- [x] 2.8 Implement done-word detection ("send", "over", "done") for immediate finalization
- [x] 2.9 Implement debounce mechanism — reset timeout if speech resumes within window
- [x] 2.10 Add text input fallback — standard text field with send button

### Speech Output

- [x] 2.11 Create `voice-output.js` — SpeechSynthesis wrapper with queue management
- [x] 2.12 Implement structured response reading: status_line → pause → results → pause → next_action
- [x] 2.13 Implement audio cues via Web Audio API oscillator tones (ready, sent, needs-input, error)
- [x] 2.14 Add TTS toggle and audio cues toggle (both stored in localStorage)

### API Client & SSE

- [x] 2.15 Create `voice-api.js` — HTTP client with Bearer token auth for all voice bridge endpoints
- [x] 2.16 Implement SSE connection to `/api/events/stream` with event filtering for agent status changes
- [x] 2.17 Implement SSE auto-reconnect with exponential backoff and polling fallback
- [x] 2.18 Implement connection status indicator (connected/reconnecting/offline)

### Agent Interaction UI

- [x] 2.19 Create `voice-app.js` — main app controller managing screens, state, and event flow
- [x] 2.20 Implement agent list view — project name, state badge (colour-coded), input-needed indicator, task summary
- [x] 2.21 Implement listening/command mode — mic indicator, live transcription, target agent display
- [x] 2.22 Implement question/response mode — question text, structured option buttons OR free-text input
- [x] 2.23 Implement auto-targeting — single awaiting agent receives commands without selection
- [x] 2.24 Implement agent selection — tap in list or speak project name to target

### Configuration & Auth

- [x] 2.25 Implement first-launch setup — server URL and token prompt, store in localStorage
- [x] 2.26 Implement settings screen — silence timeout slider, done-word selector, TTS toggle, audio cues, verbosity
- [x] 2.27 Store all settings in localStorage, load on app init

### Flask Integration

- [x] 2.28 Add route to serve voice PWA at `/voice` in voice_bridge.py
- [x] 2.29 Create placeholder PWA icons (192x192, 512x512)

## 3. Testing (Phase 3)

- [ ] 3.1 Test voice-api.js — API client calls (mock fetch), token auth, error handling
- [ ] 3.2 Test voice-input.js — utterance detection, done-word, debounce, timeout config
- [ ] 3.3 Test voice-output.js — TTS queue, audio cue generation, toggle persistence
- [ ] 3.4 Test voice-app.js — screen navigation, agent list rendering, auto-target logic
- [ ] 3.5 Test settings persistence — localStorage read/write, default values
- [ ] 3.6 Test service worker — cache strategy, offline app shell loading
- [ ] 3.7 Test PWA manifest — installability, standalone mode, icons

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification on iPhone Safari
- [ ] 4.4 PWA installable via "Add to Home Screen"
- [ ] 4.5 Bundle size under 100KB uncompressed
