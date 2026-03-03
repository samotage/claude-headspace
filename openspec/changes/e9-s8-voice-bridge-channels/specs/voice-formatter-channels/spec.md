## ADDED Requirements

### Requirement: Channel Message Sent Confirmation
The `VoiceFormatter` SHALL provide a `format_channel_message_sent(channel_slug)` method that returns a voice-formatted confirmation with the channel slug.

#### Scenario: Message sent successfully
- **WHEN** a message is sent to `#persona-alignment-workshop`
- **THEN** the response contains `status_line: "Message sent to #persona-alignment-workshop."`, empty `results`, and `next_action: "none"`

### Requirement: Channel History Formatting
The `VoiceFormatter` SHALL provide a `format_channel_history(channel_slug, messages, verbosity)` method that formats the last N messages with persona attribution.

#### Scenario: Messages available
- **WHEN** the channel has messages
- **THEN** the response contains `status_line: "Last N messages in #channel-slug."` and `results` as `["Persona: content", ...]`

#### Scenario: No messages
- **WHEN** the channel has no messages
- **THEN** the response contains `status_line: "No messages in #channel-slug."` and empty `results`

#### Scenario: Concise verbosity
- **WHEN** verbosity is "concise"
- **THEN** message content is truncated to 80 characters with "..." suffix

### Requirement: Channel Creation Confirmation
The `VoiceFormatter` SHALL provide a `format_channel_created(channel_slug, channel_type, member_results)` method that confirms creation with member join status.

#### Scenario: Channel created with members
- **WHEN** channel `#persona-alignment-workshop` (workshop) is created with members
- **THEN** `status_line: "Created channel #persona-alignment-workshop (workshop)."` and `results` contains member status strings like `["Robbo joined.", "Paula -- agent spinning up."]`

### Requirement: Channel Completion Confirmation
The `VoiceFormatter` SHALL provide a `format_channel_completed(channel_slug)` method.

#### Scenario: Channel completed
- **WHEN** channel `#persona-alignment-workshop` is completed
- **THEN** `status_line: "Channel #persona-alignment-workshop completed."` with empty `results`

### Requirement: Channel List Formatting
The `VoiceFormatter` SHALL provide a `format_channel_list(channels)` method that formats channel list with slug, type, and status.

#### Scenario: Active channels exist
- **WHEN** the operator has 3 active channels
- **THEN** `status_line: "3 active channels."` and `results` contains `["#slug (type, status)", ...]`

#### Scenario: No active channels
- **WHEN** the operator has no active channels
- **THEN** `status_line: "No active channels."` and `next_action` suggests creating a channel

### Requirement: Member Added Confirmation
The `VoiceFormatter` SHALL provide a `format_channel_member_added(persona_name, channel_slug, spinning_up)` method.

#### Scenario: Member added (agent running)
- **WHEN** persona "Con" is added to a channel and their agent is running
- **THEN** `status_line: "Con added to #channel-slug."`

#### Scenario: Member added (agent spinning up)
- **WHEN** persona "Paula" is added but their agent needs to spin up
- **THEN** `status_line: "Paula added to #channel-slug (agent spinning up)."`

### Requirement: Channel Error Responses
Channel operation errors SHALL use the existing `VoiceFormatter.format_error()` pattern with actionable suggestions specific to the error type.

#### Scenario: Not a channel member
- **WHEN** the operator is not a member of the target channel
- **THEN** `status_line: "You're not a member of #channel-slug."` and `next_action` suggests joining

#### Scenario: Channel already complete
- **WHEN** the target channel is complete or archived
- **THEN** `status_line: "Channel #channel-slug is complete."` and `next_action` suggests creating a new channel

#### Scenario: Ambiguous channel match
- **WHEN** multiple channels match the operator's query
- **THEN** `status_line: "Multiple channels match 'query'."` and `results` lists matching channel slugs
