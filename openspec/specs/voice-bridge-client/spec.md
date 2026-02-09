# voice-bridge-client Specification

## Purpose
TBD - created by archiving change e6-s2-voice-bridge-client. Update Purpose after archive.
## Requirements
### Requirement: Speech Input Capture

The voice bridge client SHALL support active speech input capture via browser Speech Recognition API.

#### Scenario: Listening mode activation

- **WHEN** the user taps the microphone button or activates voice input
- **THEN** the SpeechRecognition API SHALL begin capturing speech
- **AND** a visual indicator SHALL show that listening is active

#### Scenario: End-of-utterance detection

- **WHEN** the user stops speaking
- **AND** silence exceeds the configured timeout (default 800ms, range 600-1200ms)
- **THEN** the speech input SHALL be finalized and sent as a command

#### Scenario: Done-word detection

- **WHEN** the user speaks a configured done-word ("send", "over", "done")
- **THEN** the utterance SHALL be finalized immediately regardless of silence timeout
- **AND** the done-word SHALL be stripped from the command text

#### Scenario: Debounce mechanism

- **WHEN** speech resumes within the silence timeout window
- **THEN** the timeout SHALL be reset
- **AND** the utterance SHALL NOT be split into multiple commands

#### Scenario: Text input fallback

- **WHEN** the user selects text input mode
- **THEN** a standard text field with send button SHALL be available

---

### Requirement: Speech Output

The voice bridge client SHALL support text-to-speech output and audio cues.

#### Scenario: TTS response reading

- **WHEN** an API response is received with voice-friendly format
- **AND** TTS is enabled
- **THEN** the response SHALL be read aloud: status_line first, then results, then next_action
- **AND** pauses SHALL be inserted between sections

#### Scenario: Audio cues

- **WHEN** key events occur (ready, sent, needs-input, error)
- **THEN** a distinct audio cue SHALL play
- **AND** audio cues SHALL play regardless of TTS toggle state

#### Scenario: TTS toggle

- **WHEN** the user toggles TTS off
- **THEN** responses SHALL NOT be spoken aloud
- **AND** the preference SHALL persist in localStorage

---

### Requirement: Agent List View

The voice bridge client SHALL display active agents with real-time status.

#### Scenario: Agent list rendering

- **WHEN** the agent list screen is displayed
- **THEN** each active agent SHALL show: project name, state (colour-coded), input-needed indicator, task summary

#### Scenario: Real-time updates via SSE

- **WHEN** an agent's state changes on the server
- **THEN** the agent list SHALL update automatically via SSE
- **AND** if an agent transitions to AWAITING_INPUT, the "needs input" audio cue SHALL play

#### Scenario: SSE reconnection

- **WHEN** the SSE connection drops
- **THEN** the client SHALL reconnect with exponential backoff
- **AND** SHALL fall back to periodic polling until SSE is restored

---

### Requirement: Agent Command Routing

The voice bridge client SHALL route commands to the correct agent.

#### Scenario: Auto-target single awaiting agent

- **WHEN** exactly one agent is in AWAITING_INPUT state
- **AND** no target agent is specified
- **THEN** the command SHALL be routed to that agent automatically

#### Scenario: Explicit agent selection

- **WHEN** the user taps an agent in the list or speaks its project name
- **THEN** that agent SHALL be set as the command target

#### Scenario: Command confirmation

- **WHEN** a command is successfully sent
- **THEN** a confirmation SHALL be displayed and spoken
- **AND** the "sent" audio cue SHALL play

---

### Requirement: Question Presentation

The voice bridge client SHALL present agent questions with appropriate input modes.

#### Scenario: Structured question (AskUserQuestion)

- **WHEN** an agent has a structured question with options
- **THEN** the options SHALL be displayed as tappable buttons with labels and descriptions
- **AND** the user SHALL be able to select by tapping or speaking the option number/label

#### Scenario: Free-text question

- **WHEN** an agent has a free-text question (no structured options)
- **THEN** the full question text SHALL be displayed and read aloud
- **AND** the user SHALL respond by speaking or typing

---

### Requirement: Authentication & Configuration

The voice bridge client SHALL support token authentication and user settings.

#### Scenario: First-launch setup

- **WHEN** the client launches without stored credentials
- **THEN** it SHALL prompt for server URL and authentication token
- **AND** these SHALL be stored in localStorage

#### Scenario: Settings persistence

- **WHEN** the user changes settings (timeout, done-word, TTS, verbosity)
- **THEN** the changes SHALL be stored in localStorage
- **AND** SHALL be applied immediately without app restart

---

### Requirement: PWA Installation

The voice bridge client SHALL be installable as a Progressive Web App.

#### Scenario: Add to Home Screen

- **WHEN** the user opens the voice client URL in Safari on iOS
- **THEN** the app SHALL be installable via "Add to Home Screen"
- **AND** SHALL launch in standalone mode (no browser chrome)

#### Scenario: Offline app shell

- **WHEN** the service worker is registered
- **THEN** the app shell (HTML, CSS, JS) SHALL be cached
- **AND** the app SHALL load instantly even when the server is temporarily unreachable

---

### Requirement: Connection Status

The voice bridge client SHALL indicate connection status to the server.

#### Scenario: Connected state

- **WHEN** the SSE connection is active
- **THEN** the UI SHALL indicate connected status

#### Scenario: Disconnected state

- **WHEN** the server is unreachable
- **THEN** the UI SHALL indicate offline status
- **AND** SHALL show when reconnection is being attempted

