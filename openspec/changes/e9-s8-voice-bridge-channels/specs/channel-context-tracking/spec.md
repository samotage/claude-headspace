## ADDED Requirements

### Requirement: Session-Scoped Channel Context
The voice bridge SHALL maintain a per-session "current channel" reference. When a channel operation succeeds, the referenced channel becomes the current channel. Subsequent commands using "this channel" or "the channel" resolve to the current channel.

#### Scenario: Context set after successful operation
- **WHEN** the operator sends a message to `#persona-alignment-workshop`
- **AND** the operation succeeds
- **THEN** the current channel context is set to `persona-alignment-workshop`

#### Scenario: "This channel" resolution
- **WHEN** the operator says "add Con to this channel"
- **AND** the current channel context is `persona-alignment-workshop`
- **THEN** "this channel" resolves to `persona-alignment-workshop`

#### Scenario: No context set
- **WHEN** the operator says "add Con to this channel"
- **AND** no current channel context exists
- **THEN** an error is returned: "No current channel context. Specify the channel name."

### Requirement: Context Storage
Channel context SHALL be stored in the voice bridge's in-memory state keyed by auth identifier (Bearer token or "localhost" for localhost bypass). Context is NOT persisted to DB. It resets when the server restarts.

#### Scenario: Independent contexts per auth token
- **WHEN** two different auth tokens interact with channels
- **THEN** each has its own independent channel context

### Requirement: Auth Identifier Extraction
The `_get_auth_id()` function SHALL extract a stable identifier from the current request: the Bearer token string if present, or "localhost" for localhost-bypass authenticated requests.

#### Scenario: Bearer token present
- **WHEN** the request has `Authorization: Bearer abc123`
- **THEN** `_get_auth_id()` returns `"abc123"`

#### Scenario: Localhost bypass
- **WHEN** the request has no Authorization header (localhost bypass)
- **THEN** `_get_auth_id()` returns `"localhost"`

### Requirement: Channel Type Inference
When the operator creates a channel, the channel type SHALL be inferred from voice keywords: workshop, delegation/delegate, review, standup/stand up, broadcast/announce/announcement. If no type keyword is present, the default type SHALL be `workshop`.

#### Scenario: Type keyword present
- **WHEN** the operator says "create a delegation channel for auth refactor"
- **THEN** the channel type is inferred as `delegation`

#### Scenario: No type keyword
- **WHEN** the operator says "create a channel called persona alignment"
- **THEN** the channel type defaults to `workshop`

### Requirement: Member List Extraction
When the operator says "create ... with [members]", member names SHALL be extracted by splitting on "and", ",", and "&" separators. Each extracted name is fuzzy-matched against active personas.

#### Scenario: Multiple members
- **WHEN** the operator says "with Robbo and Paula"
- **THEN** `_extract_member_refs()` returns `["Robbo", "Paula"]`

#### Scenario: Comma-separated members
- **WHEN** the operator says "with Robbo, Paula, Con"
- **THEN** `_extract_member_refs()` returns `["Robbo", "Paula", "Con"]`
