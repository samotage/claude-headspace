## ADDED Requirements

### Requirement: Channel Intent Detection in Voice Command Pipeline
The `voice_command()` function in `voice_bridge.py` SHALL detect channel-targeted utterances using regex pattern matching. Channel detection SHALL run after handoff intent detection and before agent auto-targeting. If a channel intent is detected, the function SHALL route to the appropriate `ChannelService` method and return without entering the agent path.

#### Scenario: Send message to channel
- **WHEN** the operator says "send to workshop channel: let's start"
- **THEN** `_detect_channel_intent()` returns `{"action": "send", "channel_ref": "workshop", "content": "let's start"}`
- **AND** the command is routed to `ChannelService.send_message()`

#### Scenario: Channel history query
- **WHEN** the operator says "what's happening in the workshop?"
- **THEN** `_detect_channel_intent()` returns `{"action": "history", "channel_ref": "workshop"}`
- **AND** the last 10 messages are retrieved and voice-formatted

#### Scenario: List channels
- **WHEN** the operator says "list channels", "show channels", or "my channels"
- **THEN** `_detect_channel_intent()` returns `{"action": "list"}`
- **AND** the operator's visible channels are listed via `ChannelService.list_channels()`

#### Scenario: Create channel with members
- **WHEN** the operator says "create a workshop channel called persona alignment with Robbo and Paula"
- **THEN** `_detect_channel_intent()` returns `{"action": "create", "channel_type": "workshop", "channel_ref": "persona alignment", "member_refs": ["Robbo", "Paula"]}`
- **AND** the channel is created via `ChannelService.create_channel()` with members added

#### Scenario: Add member to channel
- **WHEN** the operator says "add Con to the workshop"
- **THEN** `_detect_channel_intent()` returns `{"action": "add_member", "member_ref": "Con", "channel_ref": "workshop"}`
- **AND** the member is added via `ChannelService.add_member()`

#### Scenario: Complete channel
- **WHEN** the operator says "complete the persona alignment channel"
- **THEN** `_detect_channel_intent()` returns `{"action": "complete", "channel_ref": "persona alignment"}`
- **AND** the channel is completed via `ChannelService.complete_channel()`

#### Scenario: Non-channel utterance
- **WHEN** the operator says "fix the login bug" or any non-channel-targeted command
- **THEN** `_detect_channel_intent()` returns None
- **AND** the utterance continues through the existing agent resolution path

### Requirement: Detection Pipeline Ordering
The detection pipeline in `voice_command()` SHALL be ordered: (1) handoff intent detection, (2) channel intent detection, (3) agent resolution. This ensures handoff intents are never accidentally captured by channel patterns.

#### Scenario: Handoff intent takes precedence
- **WHEN** an utterance matches both handoff and channel patterns
- **THEN** the handoff detection stage processes it first
- **AND** channel detection is never reached

### Requirement: Channel Service Availability
When `ChannelService` is not registered in `app.extensions`, channel operations SHALL return a 503 error with voice-formatted message "Channels not available." and actionable next_action.

#### Scenario: Channel service not configured
- **WHEN** the operator says a channel command but `app.extensions["channel_service"]` is None
- **THEN** a 503 response is returned with `status_line: "Channels not available."`

### Requirement: Operator Persona Resolution
All channel operations SHALL resolve the operator's identity via `Persona.get_operator()`. If no operator persona is configured, channel operations SHALL return a 503 error with actionable guidance.

#### Scenario: No operator persona
- **WHEN** the operator says a channel command but `Persona.get_operator()` returns None
- **THEN** a 503 response is returned with `status_line: "Operator identity not configured."`
