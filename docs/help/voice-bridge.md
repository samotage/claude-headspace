# Voice Bridge

Voice Bridge is a Progressive Web App (PWA) for hands-free voice interaction with your Claude Code agents from a mobile device. Speak commands, hear responses read aloud, and manage agents without touching the keyboard.

## How It Works

Voice Bridge runs as a lightweight web app served from your Headspace server. It connects to the same voice bridge API endpoints used by the dashboard, but adds speech input/output for a fully hands-free workflow.

```
Your phone (PWA)
  → SpeechRecognition converts voice to text
  → POST /api/voice/command with text + agent_id
  → Server sends text to agent via tmux send-keys
  → Agent processes and resumes
  → SSE pushes state change back to PWA
  → SpeechSynthesis reads the response aloud
```

### Chat Display & Turn Ordering

The voice chat displays conversation turns in chronological order based on
timestamps from the Claude Code JSONL transcript (the ground truth for when
events actually happened in the conversation).

Turns arrive via two paths:
1. **SSE push (immediate):** When hooks fire, turns are created and pushed to
   the chat in real-time. Timestamps are approximate at this stage.
2. **Transcript reconciliation (seconds later):** The file watcher reads the
   JSONL transcript and corrects timestamps to their actual conversation time.
   If turns need reordering, the chat updates automatically.

This means you may occasionally see a turn appear and then shift position
slightly as its timestamp is corrected. This is normal behaviour — it reflects
the system ensuring chronological accuracy.

For technical details, see [Transcript & Chat Sequencing](../architecture/transcript-chat-sequencing.md).

## Prerequisites

- **Voice bridge enabled** in `config.yaml` (disabled by default)
- **Headspace server running** and accessible from your phone (same Wi-Fi network)
- **tmux sessions** — agents must be running inside tmux for the input bridge to work
- **Modern browser** — Safari (iOS) or Chrome (Android) with Web Speech API support

## Setup

### 1. Enable Voice Bridge

Add or update the `voice_bridge` section in `config.yaml`:

```yaml
voice_bridge:
  enabled: true
  auth:
    token: "your-secret-token"
    localhost_bypass: true
```

Restart the server after changing this setting.

### 2. Find Your Server Address

Your phone needs to reach the Headspace server over your local network. Find your Mac's IP address:

```bash
ipconfig getifaddr en0
```

Your server URL will be `http://<ip>:5055` (e.g. `http://192.168.1.42:5055`).

### 3. Open the PWA

On your phone's browser, navigate to:

```
http://<your-mac-ip>:5055/voice
```

### 4. First-Launch Setup

The first time you open Voice Bridge, you'll see a setup screen asking for:

- **Server URL** — your Headspace server address (e.g. `http://192.168.1.42:5055`)
- **Authentication Token** — the token from your `config.yaml`

These are stored in your browser's localStorage and persist between sessions.

### 5. Install as PWA (Optional)

For a native app experience:

- **iPhone/iPad:** In Safari, tap **Share** (box with arrow) then **Add to Home Screen**
- **Android:** In Chrome, tap the **three-dot menu** then **Install app** or **Add to Home Screen**

The app launches in standalone mode (no browser chrome) and works offline for the app shell.

## Using Voice Bridge

### Agent List

After connecting, you'll see your active agents with:

- **Project name** and **state badge** (colour-coded by state)
- **"Needs Input" indicator** for agents in AWAITING_INPUT state
- **Task summary** showing what the agent is working on
- **Last activity** timestamp

The list updates in real-time via SSE. When an agent transitions to AWAITING_INPUT, you'll hear an audio cue.

### Sending a Voice Command

**Method 1: Microphone**

1. Tap the **microphone button** at the bottom of the agent list
2. Speak your command — you'll see a live transcription on screen
3. The app detects when you're finished speaking (after a configurable silence timeout)
4. Your command is sent to the target agent automatically

**Method 2: Text Input**

A text field is always available below the transcription area. Type your response and tap **Send** or press Enter.

### How Speech Detection Works

The app uses the Web Speech API to convert your voice to text. It determines when you've finished speaking using two mechanisms:

- **Silence timeout** — if you stop speaking for 800ms (configurable), the utterance is finalized and sent. If you resume speaking within this window, the timer resets (debounce).
- **Done word** — saying "send", "over", or "done" at the end of your utterance immediately finalizes and sends the command. The done word is stripped from the text before sending.

### Agent Targeting

**Manual selection (default):** Tap an agent card in the list to select it, then speak or type your command. If you press the mic button without selecting an agent, you'll be prompted to select one first.

**Auto-targeting:** When enabled in settings, if exactly one agent is waiting for input, the mic button automatically selects it — no need to tap the card first. This can be turned on in Settings > Voice Input > Auto-target agent.

### Structured Questions

When an agent asks a multiple-choice question (via Claude Code's `AskUserQuestion` tool), Voice Bridge shows:

- The question text at the top
- **Tappable option buttons** with labels and descriptions
- A free-text input field below (for custom responses)

Tap an option button to send that answer, or type/speak a custom response.

### Voice Output (Text-to-Speech)

When a response comes back from the server, Voice Bridge reads it aloud using your device's text-to-speech engine. Responses are read in a structured order:

1. **Status line** — e.g. "Command sent to my-project. Agent is now processing."
2. **Results** — any additional detail
3. **Next action** — what to do next (if anything)

### Audio Cues

Four short oscillator tones provide non-verbal feedback:

| Cue | Sound | When |
|-----|-------|------|
| **Ready** | 660Hz sine (rising) | App connected and ready |
| **Sent** | 880Hz sine (high) | Command successfully sent |
| **Needs Input** | 440Hz triangle (mid) | An agent is waiting for your input |
| **Error** | 220Hz sawtooth (low) | Something went wrong |

### Connection Status

A coloured dot in the header shows your connection state:

- **Green** — connected to SSE stream, receiving real-time updates
- **Yellow** — reconnecting (lost connection, retrying with exponential backoff)
- **Red** — disconnected / offline

If the SSE connection fails, the app automatically reconnects with exponential backoff (up to 30 seconds between attempts). On reconnect, missed events are replayed from the server's replay buffer.

## Settings

Tap the **gear icon** in the header to access settings. All settings are stored in localStorage on your device.

### Voice Input Settings

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| Silence timeout | 800ms | 600-1200ms | How long to wait after you stop speaking before finalizing |
| Done word | "send" | send/over/done | Word that immediately finalizes your utterance |
| Auto-target agent | Off | On/Off | When enabled, automatically targets the sole awaiting agent when pressing the mic button |

### Voice Output Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Text-to-speech | On | Read responses aloud using device TTS |
| Audio cues | On | Play oscillator tone feedback |

### Display Settings

| Setting | Default | Options | Description |
|---------|---------|---------|-------------|
| Verbosity | Normal | Brief/Normal/Full | How much detail to include in spoken responses |

### Connection Settings

| Setting | Description |
|---------|-------------|
| Server URL | Your Headspace server address |
| Token | Authentication token |

## Server Configuration

Voice bridge settings in `config.yaml`:

```yaml
voice_bridge:
  enabled: false
  auth:
    token: ""
    localhost_bypass: true
  rate_limit:
    requests_per_minute: 60
  default_verbosity: "concise"
  auto_target: false
```

- `enabled` — Enable the voice bridge services. When disabled, the `/voice` page still loads but API calls will lack voice formatting. Enable to activate token auth and voice-friendly response formatting.
- `auth.token` — Bearer token required for API calls. Leave empty for no authentication (not recommended for network access). Set a strong random string when accessing from other devices on your network.
- `auth.localhost_bypass` — Skip token authentication for requests from localhost (127.0.0.1). Useful for development. Disable if you want to enforce token auth even locally.
- `rate_limit.requests_per_minute` — Maximum API requests per minute per token. Prevents runaway calls. Default of 60 is generous for voice interaction.
- `default_verbosity` — Server-side default for response detail level: `concise`, `normal`, or `detailed`. The client can override this per-request via settings.
- `auto_target` — When enabled, voice commands without an explicit agent_id automatically target the sole awaiting agent. When disabled (default), the user must always select an agent before sending a command. The PWA settings toggle can override this per-device.

## API Endpoints

Voice Bridge uses four API endpoints (all require Bearer token auth unless localhost bypass is active):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voice/sessions` | GET | List active agents with voice-formatted status |
| `/api/voice/command` | POST | Send a command to an agent |
| `/api/voice/agents/<id>/output` | GET | Get recent output/tasks for an agent |
| `/api/voice/agents/<id>/question` | GET | Get full question context for an awaiting agent |

The `/voice` page itself is served without authentication so the PWA can load before credentials are entered.

## Offline Support

The service worker caches the app shell (HTML, CSS, JS, icons, manifest) using a cache-first strategy. This means:

- The app loads instantly on repeat visits, even offline
- API calls use a network-first strategy (falls back to a "you're offline" JSON response)
- The app shell updates when a new version is deployed (cache is versioned)

## Relationship to Input Bridge

Voice Bridge and the [Input Bridge](input-bridge) (dashboard respond widget) serve the same purpose — sending text to agents that need input — but through different interfaces:

| | Input Bridge | Voice Bridge |
|--|-------------|-------------|
| **Interface** | Dashboard widget | Standalone PWA |
| **Input** | Click buttons / type | Speak / type |
| **Output** | Visual on card | Spoken via TTS + visual |
| **Device** | Desktop browser | Mobile phone |
| **Auth** | Session (same machine) | Bearer token |
| **Underlying mechanism** | tmux send-keys | tmux send-keys |

Both ultimately use `tmux send-keys` to deliver text to the agent's terminal pane. Voice Bridge adds speech I/O and a mobile-optimised interface on top.

## Troubleshooting

### "No agents are waiting for input"

Commands can only be sent to agents in **AWAITING_INPUT** state. If no agents are waiting, Voice Bridge returns a 409 status. Wait for an agent to ask a question or prompt for input.

### Microphone not working

- **iOS Safari:** You must grant microphone permission when prompted. Check Settings > Safari > Microphone.
- **Chrome Android:** Check site settings for microphone permission.
- **Desktop:** Ensure your browser has microphone access in system settings.
- The Web Speech API requires a **secure context** (HTTPS) on some browsers. On your local network over HTTP, Safari is more permissive than Chrome.

### Connection keeps dropping

- Check that your phone and Mac are on the same Wi-Fi network
- Verify the server URL is correct (try opening it in your phone's browser)
- The SSE connection auto-reconnects with exponential backoff (up to 30 seconds between retries)
- If SSE fails, the app reconnects automatically with exponential backoff

### "Authentication required" error

- Verify the token in Voice Bridge settings matches the one in `config.yaml`
- If accessing from localhost, ensure `localhost_bypass: true` is set
- Check that `voice_bridge.enabled` is `true` in config.yaml

### No sound / TTS not speaking

- Check that your device is not in silent/mute mode
- Verify TTS is enabled in Voice Bridge settings (gear icon)
- On iOS, you may need to tap the screen once before audio plays (browser autoplay policy)
- The `initAudio()` function unlocks the AudioContext on your first tap of the mic button

### PWA won't install

- On iOS, PWA installation is only available through **Safari** (not Chrome or Firefox)
- The manifest must be served from the same origin — verify `/static/voice/manifest.json` loads correctly
- Try clearing Safari website data and reloading
