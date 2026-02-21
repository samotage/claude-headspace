# Delta Spec: Handoff Trigger UI

## ADDED Requirements

### Requirement: Handoff threshold configuration

The `context_monitor` config section SHALL include a `handoff_threshold` key (integer, 10-100) with default value 80. This threshold determines when persona agents become eligible for handoff. The threshold can be configured as low as 10% for testing and debugging purposes.

#### Scenario: Default handoff threshold
- **WHEN** no custom handoff_threshold is set in config
- **THEN** handoff_threshold defaults to 80

#### Scenario: Low threshold for testing
- **GIVEN** handoff_threshold configured as 10
- **AND** a persona agent with context_percent_used = 12
- **WHEN** card state is built
- **THEN** handoff_eligible is true

---

### Requirement: Handoff eligibility computation

During card state building, each agent's handoff eligibility SHALL be computed as a boolean. An agent is handoff-eligible when ALL conditions are true: agent has a persona (persona_id is not None), agent has context usage data (context_percent_used is not None), and agent's context usage percentage meets or exceeds the configured handoff_threshold. No additional database queries — uses existing eager-loaded relationships.

#### Scenario: Persona agent crosses handoff threshold
- **GIVEN** an agent with persona and context_percent_used = 82
- **AND** handoff_threshold is 80
- **WHEN** card state is built
- **THEN** handoff_eligible is true

#### Scenario: Persona agent below threshold
- **GIVEN** an agent with persona and context_percent_used = 70
- **AND** handoff_threshold is 80
- **WHEN** card state is built
- **THEN** handoff_eligible is false

#### Scenario: Anonymous agent above threshold
- **GIVEN** an agent with no persona and context_percent_used = 90
- **WHEN** card state is built
- **THEN** handoff_eligible is false

#### Scenario: Agent without context data
- **GIVEN** an agent with persona and context_percent_used = None
- **WHEN** card state is built
- **THEN** handoff_eligible is false

---

### Requirement: Card state handoff fields

The card state JSON context block SHALL include two new fields: `handoff_eligible` (boolean) indicating whether the agent meets all handoff criteria, and `handoff_threshold` (integer) with the configured threshold percentage. These fields are included in both initial page render data and SSE card_refresh event payloads.

#### Scenario: Card state includes handoff fields
- **GIVEN** a persona agent with context_percent_used = 85
- **AND** handoff_threshold is 80
- **WHEN** card state is built
- **THEN** the context dict contains handoff_eligible = true
- **AND** the context dict contains handoff_threshold = 80

---

### Requirement: Handoff button on agent card

The agent card SHALL display a "Handoff" button when the agent is handoff-eligible. The button is hidden when the agent has no persona, is below threshold, or has no context data. The button provides loading/disabled state during handoff request.

#### Scenario: Handoff button visible for eligible agent
- **GIVEN** a persona agent with context_percent_used = 85 and handoff_threshold = 80
- **WHEN** the card renders
- **THEN** a "Handoff" button is displayed on the card

#### Scenario: Handoff button hidden for anonymous agent
- **GIVEN** an anonymous agent with context_percent_used = 90
- **WHEN** the card renders
- **THEN** no handoff button is displayed

---

### Requirement: Context bar handoff indicator

When an agent's context usage exceeds the handoff threshold AND the agent has a persona, the context usage display SHALL show a handoff-specific visual indicator distinct from warning (65%) and high (75%) tiers. Anonymous agents retain existing behaviour without handoff styling.

#### Scenario: Context bar shows handoff tier
- **GIVEN** a persona agent with context_percent_used = 85 and handoff_threshold = 80
- **WHEN** the card renders
- **THEN** the context bar displays handoff-tier styling distinct from warning and high

#### Scenario: Anonymous agent no handoff indicator
- **GIVEN** an anonymous agent with context_percent_used = 90
- **WHEN** the card renders
- **THEN** the context bar shows existing high-tier styling only

---

### Requirement: SSE card refresh handoff updates

The SSE card_refresh handler SHALL update handoff button visibility and context bar handoff indicator in real-time. When context usage crosses the threshold in either direction, the card updates without requiring a page reload.

#### Scenario: Context crosses threshold via SSE
- **GIVEN** a persona agent card with context_percent_used = 78
- **WHEN** an SSE card_refresh event arrives with context_percent_used = 81
- **AND** handoff_threshold is 80
- **THEN** the handoff button appears on the card
- **AND** context bar changes to handoff-tier styling

---

### Requirement: Handoff button click action

When the operator clicks the handoff button, it SHALL send a POST request to `/api/agents/<id>/handoff` with `{ "reason": "context_limit" }`. The button enters loading/disabled state during the request to prevent double-clicks. The endpoint handler is defined by E8-S14; this sprint implements the client-side request only.

#### Scenario: Handoff button clicked
- **GIVEN** a handoff-eligible agent with id = 42
- **WHEN** the operator clicks the handoff button
- **THEN** a POST request is sent to /api/agents/42/handoff
- **AND** the request body contains reason = context_limit
- **AND** the button shows loading state until response

---

### Requirement: Anonymous agent exclusion

Anonymous agents (those without a persona) SHALL never display the handoff button or handoff-related context bar indicators, regardless of their context usage level. Existing context monitoring visuals (warning/high tiers) remain unchanged for all agents.

#### Scenario: Anonymous agent always excluded
- **GIVEN** an agent with no persona and context_percent_used = 95
- **WHEN** card state is built and the card renders
- **THEN** handoff_eligible is false
- **AND** no handoff button is displayed
- **AND** no handoff context bar indicator is shown
