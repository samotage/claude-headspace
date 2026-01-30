# Voice Bridge for Claude Monitor - Capability Assessment & Plan

## Verdict: Feasible

The Voice Bridge system prompt explicitly mentions "Option B: existing Kanban monitor integration" as a valid approach. Claude Monitor is exactly that Kanban monitor, providing a solid foundation.

---

## What Already Exists (Foundation)

| Capability | Status | Details |
|------------|--------|---------|
| Session Registry | Complete | `scan_sessions()` tracks all sessions |
| Session Status | Complete | `activity_state`: processing, input_needed, idle |
| "Sessions needing input" | Complete | Already detects `input_needed` state |
| Flask API Server | Complete | Running on port 5050 |
| iTerm Integration | Complete | AppleScript for window info and focus |
| Terminal Output Capture | Partial | Captures last 400 chars via AppleScript |
| macOS Notifications | Complete | terminal-notifier integration |

---

## What Needs to Be Built

| Capability | Effort | Notes |
|------------|--------|-------|
| **Send text TO sessions** | Medium | Biggest gap. tmux recommended over AppleScript keystroke injection |
| **Full output capture** | Small | Extend existing AppleScript to capture more content |
| **LLM summarization** | Medium | Claude API integration for voice-friendly summaries |
| **WebSocket support** | Small | Flask-SocketIO for real-time updates |
| **PWA mobile client** | Medium | iOS Web Speech API for recognition + TTS |
| **Token auth** | Small | Simple shared-secret middleware |

---

## Recommended Approach

**Extend Claude Monitor** rather than building separately:

1. **Add tmux-based session routing** - Claude Code sessions run in tmux, monitor uses `tmux send-keys` and `tmux capture-pane`
2. **Add new API endpoints**: `/api/send/<session_id>`, `/api/output/<session_id>`, `/api/summary/<session_id>`
3. **Add Claude API integration** for output summarization with voice-friendly formatting
4. **Add WebSocket** for real-time status updates to mobile client
5. **Build PWA** that connects to existing monitor - uses iOS SpeechRecognition + SpeechSynthesis APIs

Single-codebase approach makes sense because session state is already managed here.

---

## Key Decision: tmux vs AppleScript for Session Input

| Approach | Pros | Cons |
|----------|------|------|
| **tmux** (Recommended) | Deterministic, reliable, works headless | Requires Claude sessions run in tmux |
| **AppleScript** | Works with existing iTerm setup | Requires Accessibility permissions, less reliable |

The Voice Bridge prompt recommends tmux, and it's the more robust choice.

---

## Architecture Overview

```
+------------------------------------------------------------------+
|                        iPhone/iPad (PWA)                          |
|  +-------------+  +-------------+  +---------------------------+  |
|  | Web Speech  |  |    TTS      |  |  WebSocket Client         |  |
|  | Recognition |  |  Playback   |  |  (real-time updates)      |  |
|  +------+------+  +------^------+  +------------+---------------+  |
|         |                |                      |                  |
|         +----------------+----------------------+                  |
|                          |                                         |
+------------------------------------------------------------------+
                           | HTTP/WebSocket (local network)
                           |
+------------------------------------------------------------------+
|                     Claude Monitor (Mac)                          |
|  +---------------------------------------------------------------+|
|  |                  Flask Server                                  ||
|  |  /api/sessions     - List sessions (existing)                 ||
|  |  /api/focus/<pid>  - Focus window (existing)                  ||
|  |  /api/send/<id>    - Send text to session (NEW)               ||
|  |  /api/output/<id>  - Get session output (NEW)                 ||
|  |  /api/summary/<id> - Get voice-friendly summary (NEW)         ||
|  |  /ws               - WebSocket for real-time (NEW)            ||
|  +---------------------------------------------------------------+|
|                          |                                        |
|  +---------------------------------------------------------------+|
|  |              Session Router (NEW)                              ||
|  |  - tmux send-keys for input                                   ||
|  |  - tmux capture-pane for output                               ||
|  +---------------------------------------------------------------+|
|                          |                                        |
|  +---------------------------------------------------------------+|
|  |           Claude API Integration (NEW)                         ||
|  |  - Summarize terminal output for voice                        ||
|  |  - Verbosity levels: concise/normal/detailed                  ||
|  +---------------------------------------------------------------+|
|                                                                   |
+------------------------------------------------------------------+
                           |
                           | tmux commands
                           v
+------------------------------------------------------------------+
|                    tmux Sessions                                   |
|  +-------------+  +-------------+  +-------------+                |
|  |  Session 1  |  |  Session 2  |  |  Session 3  |  ...          |
|  |  (raglue)   |  | (ot_monitor)|  |  (project)  |               |
|  +-------------+  +-------------+  +-------------+                |
+------------------------------------------------------------------+
```

---

## Implementation Phases

### Phase 1: tmux Session Router
- Add tmux session detection alongside iTerm
- Implement `tmux send-keys` for text input
- Implement `tmux capture-pane` for output capture
- New API endpoints: `/api/send/<session_id>`, `/api/output/<session_id>`

### Phase 2: LLM Summarization
- Add Claude API client
- Create summarization prompt for voice-friendly output
- Implement verbosity levels (concise/normal/detailed)
- New API endpoint: `/api/summary/<session_id>`

### Phase 3: WebSocket Support
- Add Flask-SocketIO
- Real-time session status updates
- State change notifications to connected clients

### Phase 4: PWA Mobile Client
- Basic HTML/CSS/JS PWA
- Web Speech Recognition API integration
- Silence/VAD-based utterance finalization
- Optional "done word" detection
- TTS for responses
- Earcons for status (ready, sent, needs input)

### Phase 5: Security & Polish
- Token-based authentication
- Rate limiting
- Access logging
- Tuning for noise conditions

---

## Voice Command Mapping

| Voice Command | API Call | Response |
|---------------|----------|----------|
| "List sessions" | GET `/api/sessions` | "You have 3 sessions: raglue is processing, ot_monitor needs input, claude_monitor is idle" |
| "Sessions needing input" | GET `/api/sessions` + filter | "One session needs input: ot_monitor" |
| "Send to raglue: run the tests" | POST `/api/send/raglue` | "Sent to raglue" |
| "What's raglue doing?" | GET `/api/summary/raglue` | Concise summary of recent output |
| "Focus ot_monitor" | POST `/api/focus/<pid>` | "Focused" |

---

## Output Format (Voice-Friendly)

Default response structure:
- **Status line**: what happened (1 sentence)
- **Key result**: 1-3 bullets
- **Next action needed**: 0-2 bullets, or "None"
- **If error**: error type + 1 suggestion

Example:
```
Tests completed with 2 failures.
- UserAuth test failed: missing token validation
- PaymentFlow test failed: timeout on checkout
You need to: Fix the token validation in auth.py
```

---

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `monitor.py` | Modify | Add tmux router, new endpoints, WebSocket |
| `voice_client/` | Create | PWA directory |
| `voice_client/index.html` | Create | PWA entry point |
| `voice_client/app.js` | Create | Speech recognition, TTS, API calls |
| `voice_client/manifest.json` | Create | PWA manifest |
| `requirements.txt` | Modify | Add flask-socketio, anthropic |
| `config.yaml` | Modify | Add voice bridge settings |

---

## Verification Plan

1. **Session listing**: `curl localhost:5050/api/sessions` returns sessions
2. **tmux send**: Send text to session, verify it appears in terminal
3. **Output capture**: Capture pane content, verify recent output returned
4. **Summarization**: Get summary, verify voice-friendly format
5. **PWA speech**: Speak command, verify transcription appears
6. **End-to-end**: Voice command -> session response -> TTS playback

---

## Open Questions

1. **tmux session naming**: How to consistently name/identify tmux sessions per project?
2. **Hybrid iTerm+tmux**: Can we support both for flexibility?
3. **Claude API costs**: Summarization on every request vs caching?
4. **PWA vs native**: PWA should work but native app would have better speech APIs
