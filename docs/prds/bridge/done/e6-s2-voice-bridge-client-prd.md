---
validation:
  status: valid
  validated_at: '2026-02-09T19:32:29+11:00'
---

## Product Requirements Document (PRD) — Voice Bridge Mobile Client

**Project:** Claude Headspace
**Scope:** PWA mobile client for hands-free voice interaction with Claude Code agents
**Author:** Sam (PRD Workshop)
**Status:** Draft
**Depends on:** e6-s1-voice-bridge-server

---

## Executive Summary

With the Voice Bridge Server (e6-s1) providing voice-friendly API endpoints, authentication, and enhanced question data, a mobile client is needed to complete the hands-free interaction loop. This PRD covers a Progressive Web App (PWA) for iPhone and iPad that enables the user to speak commands to Claude Code agents, hear concise voice responses, and answer agent questions — all without touching the Mac or looking at a screen.

The client uses browser-native speech recognition and synthesis APIs to keep dependencies minimal. It connects to the Claude Headspace Flask server over the local network using the token authentication from e6-s1.

---

## 1. Context & Purpose

### 1.1 Context

The Voice Bridge Server (e6-s1) exposes voice-friendly API endpoints for: listing agents with status, submitting commands, retrieving output summaries, and fetching question details with structured options. All responses are formatted for listening (concise status + key results + next action). Token-based authentication secures LAN access.

What's needed is a lightweight mobile client that:
- Captures speech input and converts it to text commands
- Sends commands to the server and receives voice-friendly responses
- Speaks responses aloud so the user can operate hands-free
- Presents agent questions (structured options or free-text) for voice or text response
- Provides audio cues for state changes so the user knows what's happening without looking

### 1.2 Target User

The project owner using an iPhone or iPad on the same local network as their Mac — on the couch, on a bike, cooking, or otherwise away from the desk.

### 1.3 Success Moment

The user's phone chimes to indicate an agent needs input. They say "what's the question?" and hear the full question read aloud. They speak their answer, hear a confirmation tone, and the agent resumes — all hands-free, without looking at the screen.

---

## 2. Scope

### 2.1 In Scope

- Progressive Web App installable on iPhone/iPad via Safari "Add to Home Screen"
- Speech-to-text input via browser speech recognition
- Automatic end-of-utterance detection with configurable silence timeout
- Optional spoken "done word" (e.g., "send", "over") to finalize input immediately
- Text input fallback for quiet environments or precise input
- Text-to-speech output for all voice-friendly API responses
- Audio cues (earcons) for key events: ready, sent, agent needs input, error
- Agent list view showing status, project, and input-needed indicators
- Question presentation: structured options (selectable) or full question text (free-text response)
- Auto-targeting: when only one agent needs input, commands route automatically
- SSE connection for real-time status updates from the server
- Token-based authentication (configured once, stored locally)
- Configurable silence timeout and done-word settings

### 2.2 Out of Scope

- Native iOS app (PWA only for v1)
- Wake-word detection (e.g., "Hey Claude") — extension point only
- Offline speech recognition
- Remote access beyond LAN
- Desktop browser support (optimised for mobile Safari only)
- Complex session management or terminal output display
- Modifications to the existing desktop dashboard

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User can speak a command on iPhone and have it delivered to a specific agent, with the agent resuming processing
2. User can hear agent status summaries read aloud without looking at the screen
3. Structured agent questions are presented with selectable options; free-text questions show the full question for spoken response
4. End-of-utterance detection reliably finalises input after a configurable silence period (600-1200ms)
5. The spoken "done word" immediately finalises input when detected
6. Audio cues play for key state transitions (agent needs input, command sent, error)
7. The PWA is installable on iPhone via "Add to Home Screen" and launches in standalone mode
8. Real-time status updates arrive via SSE without manual refresh

### 3.2 Non-Functional Success Criteria

1. Speech recognition starts within 1 second of user activating listening mode
2. End-to-end latency from speech finalisation to agent receipt is under 3 seconds on LAN
3. The PWA loads and is interactive within 2 seconds on iPhone
4. TTS begins speaking the response within 1 second of receiving the API response
5. The client works on iOS Safari 16+ (iPhone and iPad)

---

## 4. Functional Requirements (FRs)

### Speech Input

**FR1:** The client supports active listening mode where speech is continuously captured and converted to text. Listening is activated by a clear UI action (tap or voice activation) and remains active until the utterance is finalised.

**FR2:** Automatic end-of-utterance detection finalises the speech input after a configurable silence timeout (default: 800ms, range: 600-1200ms). The timeout is tunable in the client settings to accommodate different noise environments.

**FR3:** An optional spoken "done word" (configurable, default options: "send", "over", "done") immediately finalises the current utterance regardless of the silence timeout. This reduces false splits during noisy conditions (e.g., bike riding, wind).

**FR4:** A debounce mechanism prevents a single thought from being chopped into multiple commands. If speech resumes within the silence timeout window, the timeout resets.

**FR5:** Text input fallback is available via a standard text field for situations where voice input is impractical (quiet environments, precise technical input).

### Speech Output

**FR6:** All voice-friendly API responses are spoken aloud via text-to-speech when audio output mode is enabled. The user can toggle TTS on/off.

**FR7:** Audio cues (short, distinct sounds) play for key events: "ready" (listening activated), "sent" (command delivered), "needs input" (an agent is waiting), and "error" (something went wrong). Audio cues play regardless of TTS toggle.

**FR8:** TTS reads responses in the voice-friendly format from the server: status line first, then key results, then next action. Pauses are inserted between sections for clarity.

### Agent Interaction

**FR9:** An agent list view displays all active agents with: project name, current state (colour-coded), whether input is needed, and current command summary. The list updates in real-time via SSE.

**FR10:** The user can target a specific agent by tapping it in the list or by speaking its project name. When exactly one agent is awaiting input and no target is specified, commands route to it automatically.

**FR11:** When an agent is awaiting input with structured options (AskUserQuestion), the options are displayed as tappable buttons with labels and descriptions. The user can select by tapping or by speaking the option number or label.

**FR12:** When an agent is awaiting input with a free-text question (no structured options), the full question text is displayed and read aloud. The user responds by speaking or typing their answer.

**FR13:** After a command or answer is sent, the client displays and speaks a confirmation, then returns to the listening/monitoring state.

### Real-Time Updates

**FR14:** The client maintains an SSE connection to the server for real-time status updates. When an agent transitions to AWAITING_INPUT, the client plays the "needs input" audio cue and updates the agent list.

**FR15:** If the SSE connection drops, the client reconnects automatically with exponential backoff and falls back to periodic polling until SSE is restored.

### Authentication & Configuration

**FR16:** On first launch, the client prompts for the server URL and authentication token. These are stored locally (localStorage) and persist across sessions.

**FR17:** A settings screen allows configuration of: silence timeout duration, done-word selection, TTS on/off, audio cues on/off, and verbosity level (concise/normal/detailed).

### PWA Requirements

**FR18:** The client includes a web app manifest enabling "Add to Home Screen" installation on iOS Safari with standalone display mode, appropriate icons, and theme colours.

**FR19:** A service worker provides basic offline caching of the app shell (HTML, CSS, JS) so the client loads instantly even when the server is temporarily unreachable. API calls still require network connectivity.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The client is built with vanilla HTML, CSS, and JavaScript — no framework dependencies. This matches the existing Claude Headspace frontend approach and minimises bundle size.

**NFR2:** The total client bundle (HTML + CSS + JS) is under 100KB uncompressed, ensuring fast initial load.

**NFR3:** The client is optimised for mobile Safari on iOS 16+. Other browsers are not a priority but should not be actively broken.

**NFR4:** All client state (token, settings, preferences) is stored in localStorage. No server-side session state is required.

**NFR5:** The client handles network interruptions gracefully — queued commands are retried, and the UI indicates connectivity status.

---

## 6. UI Overview

The mobile client has three primary screens:

### Home / Agent List

A clean, mobile-optimised list of active agents. Each agent shows:
- Project name (prominent)
- State indicator (colour dot or badge: green=processing, amber=awaiting input, grey=idle)
- Current command summary (1 line)
- Tap to select as target

A prominent microphone button at the bottom activates listening mode. When one agent needs input, a banner highlights it.

### Listening / Command Mode

Full-screen listening interface:
- Large microphone indicator (pulsing when listening)
- Live transcription text as speech is recognised
- Target agent indicator (which agent will receive the command)
- "Done word" hint text
- Cancel button to abort

### Question / Response Mode

Displayed when viewing an agent's pending question:
- Question text (large, readable)
- Structured options as buttons (if available)
- Free-text input area (if no structured options)
- Speak or type response
- Back button to return to agent list

### Settings

Simple configuration screen:
- Server URL and token
- Silence timeout slider (600-1200ms)
- Done-word selector
- TTS toggle
- Audio cues toggle
- Verbosity level selector
