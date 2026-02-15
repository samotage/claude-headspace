## ADDED Requirements

### Requirement: Agent Card Tmux Session Display

The dashboard agent card SHALL display the tmux session name when available, providing the user with the session identifier for manual use.

#### Scenario: Card state includes tmux_session

- **WHEN** `build_card_state()` is called for an agent with `tmux_session` set
- **THEN** the returned dict SHALL include `tmux_session` with the session name string

#### Scenario: Card state with no tmux_session

- **WHEN** `build_card_state()` is called for an agent with `tmux_session` NULL
- **THEN** the returned dict SHALL include `tmux_session` with value `null`

---

### Requirement: Agent Card Attach Action

The dashboard agent card SHALL display an attach button for agents with a tmux session, allowing one-click terminal attachment.

#### Scenario: Attach button visible

- **WHEN** an agent card is rendered
- **AND** the agent has a non-null `tmux_session` in card state
- **THEN** an attach action button SHALL be visible on the card

#### Scenario: Attach button hidden

- **WHEN** an agent card is rendered
- **AND** the agent has a null `tmux_session` in card state
- **THEN** the attach action button SHALL NOT be visible

#### Scenario: Attach button click

- **WHEN** the user clicks the attach button on an agent card
- **THEN** a `POST /api/agents/<id>/attach` request SHALL be sent
- **AND** success/failure feedback SHALL be displayed to the user

#### Scenario: Attach button on SSE card refresh

- **WHEN** a `card_refresh` SSE event is received with `tmux_session` set
- **THEN** the attach button SHALL appear on the refreshed card
- **WHEN** a `card_refresh` SSE event is received with `tmux_session` null
- **THEN** the attach button SHALL be hidden on the refreshed card
