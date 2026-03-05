## MODIFIED Requirements

### Requirement: HTTP Channel Authentication (FR1)

The channels API `_resolve_caller()` function SHALL accept agent identity only via validated Bearer tokens (SessionTokenService) or dashboard session cookies (Persona.get_operator()). Unauthenticated identity headers (e.g., `X-Headspace-Agent-ID`) SHALL NOT be accepted.

#### Scenario: Agent authenticates via valid Bearer token

- **WHEN** a request includes `Authorization: Bearer <valid_token>`
- **AND** the token validates via SessionTokenService
- **AND** the token's agent has an active persona
- **THEN** the request is authenticated as that agent's persona

#### Scenario: Agent provides invalid Bearer token

- **WHEN** a request includes `Authorization: Bearer <invalid_token>`
- **THEN** the request is rejected with 401 `invalid_session_token`

#### Scenario: Agent sends X-Headspace-Agent-ID header without token

- **WHEN** a request includes `X-Headspace-Agent-ID` header without a valid Bearer token
- **THEN** the header is ignored
- **AND** authentication falls through to session cookie or fails with 401

#### Scenario: Operator authenticates via session cookie

- **WHEN** no Bearer token is present
- **AND** no agent identity header is present
- **THEN** the operator persona is resolved via `Persona.get_operator()`
- **AND** the request proceeds with operator identity

#### Scenario: No valid authentication

- **WHEN** no Bearer token, no valid session cookie
- **THEN** the request is rejected with 401 `unauthorized`

---

### Requirement: CLI Caller Identity Resolution (FR2) — MODIFIED from caller-identity spec

The `resolve_caller()` function SHALL resolve the calling agent using tmux pane detection only. The `HEADSPACE_AGENT_ID` environment variable override SHALL NOT be accepted.

#### Scenario: Tmux pane detection

- **WHEN** tmux `display-message -p '#{pane_id}'` returns a valid pane ID
- **AND** an active Agent has that `tmux_pane_id`
- **THEN** the Agent is returned

#### Scenario: Tmux not available

- **WHEN** tmux is not running or `display-message` fails
- **THEN** `CallerResolutionError` is raised

#### Scenario: HEADSPACE_AGENT_ID env var is set

- **WHEN** `HEADSPACE_AGENT_ID` environment variable is set
- **THEN** it is ignored — env var identity override is not supported

#### Scenario: No resolution

- **WHEN** tmux pane detection does not resolve an agent
- **THEN** `CallerResolutionError` is raised with message: "Error: Cannot identify calling agent. Are you running in a Headspace-managed session?"

---

### Requirement: CLI Command Restriction (FR3)

Mutating CLI commands (those that create channels, send messages, modify memberships, manage personas, or change channel state) SHALL be restricted to operator-initiated contexts. An agent running in a tmux pane SHALL NOT be able to use these commands.

#### Scenario: Agent attempts mutating CLI command

- **WHEN** a caller is resolved as an agent (via tmux pane binding)
- **AND** the caller invokes a mutating CLI command (send, create, add, leave, complete, transfer-chair, mute, unmute, persona register)
- **THEN** the command is rejected with an error message indicating the operation is restricted to operators

#### Scenario: Operator uses mutating CLI command

- **WHEN** the caller cannot be resolved as an agent (CallerResolutionError)
- **AND** the caller invokes a mutating CLI command from a non-agent context
- **THEN** the command proceeds normally

#### Scenario: Read-only CLI commands remain accessible

- **WHEN** any caller (agent or operator) invokes a read-only CLI command (list, show, members, history, persona list, persona handoffs)
- **THEN** the command proceeds normally regardless of caller context

---

### Requirement: System-Mediated Routing (FR4, FR5)

Internal agent messages SHALL reach channels exclusively through system-mediated routing via `ChannelDeliveryService.relay_agent_response()`. Only turns with COMPLETION or END_OF_COMMAND intents SHALL be relayed.

#### Scenario: Agent completes a task in a channel

- **WHEN** an agent's turn is classified as COMPLETION or END_OF_COMMAND
- **AND** the agent has an active channel membership
- **THEN** the turn text is posted as a channel message via `ChannelDeliveryService.relay_agent_response()`
- **AND** the message's source_turn_id and source_command_id are set for traceability

#### Scenario: Agent mid-processing output

- **WHEN** an agent's turn is classified as PROGRESS, ANSWER, QUESTION, or COMMAND
- **THEN** the turn text is NOT relayed to any channel

#### Scenario: Agent not in a channel

- **WHEN** an agent's turn is classified as COMPLETION or END_OF_COMMAND
- **AND** the agent has no active channel membership
- **THEN** no channel message is created

---

### Requirement: Remote Agent Token Auth Preservation (FR6)

Remote agents (those without tmux pane infrastructure identity) SHALL continue to authenticate via validated Bearer tokens. The SessionTokenService validation path SHALL NOT be modified or degraded.

#### Scenario: Remote agent posts to channel

- **WHEN** a remote agent sends a POST to `/api/channels/<slug>/messages`
- **AND** the request includes a valid Bearer token
- **THEN** the message is accepted and posted to the channel

---

### Requirement: Operator Dashboard Auth Preservation (FR7)

Dashboard operators SHALL continue to authenticate via session cookies. The `Persona.get_operator()` fallback path SHALL NOT be modified or degraded.

#### Scenario: Operator posts via dashboard

- **WHEN** an operator sends a POST to `/api/channels/<slug>/messages`
- **AND** no Bearer token is present
- **AND** `Persona.get_operator()` returns a valid operator persona
- **THEN** the message is accepted and posted to the channel
