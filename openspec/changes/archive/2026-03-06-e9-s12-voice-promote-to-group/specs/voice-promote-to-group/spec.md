## ADDED Requirements

### Requirement: Voice App Promote-to-Group Kebab Action

The voice app agent chat header kebab menu SHALL include a "Create Group Channel" action for active agents that have a persona assigned.

#### Scenario: Menu item visibility for agent with persona

- **WHEN** the operator opens the agent chat header kebab menu for an active agent with a persona
- **THEN** the menu SHALL display "Create Group Channel" after "Handoff" and before the divider
- **AND** the action SHALL use a `promote` icon from the PortalKebabMenu icon registry

#### Scenario: Menu item hidden for agent without persona

- **WHEN** the operator opens the agent chat header kebab menu for an agent without a persona
- **THEN** the "Create Group Channel" action SHALL NOT appear in the menu

---

### Requirement: Persona Picker with Callback Support

The `showPersonaPicker()` function SHALL accept an optional callback parameter to support both agent creation and promote-to-group flows.

#### Scenario: Promote-to-group persona selection

- **WHEN** the operator selects "Create Group Channel" from the kebab menu
- **THEN** the persona picker SHALL open with available personas
- **AND** the current agent's persona SHALL be filtered out of the list
- **AND** on persona selection, the picker SHALL invoke the promote callback (not the agent creation flow)

#### Scenario: Existing agent creation flow preserved

- **WHEN** the operator triggers agent creation via the sidebar (existing flow)
- **THEN** the persona picker SHALL behave exactly as before — selecting a persona calls `_doCreateAgent()`

---

### Requirement: Promote-to-Group API Integration

On persona selection and confirm from the promote flow, the voice app SHALL call `POST /api/agents/<agent_id>/promote-to-group` with `{ "persona_slug": "<selected_slug>" }`.

#### Scenario: Successful group channel creation

- **WHEN** the API returns 201 with channel details
- **THEN** the voice chat panel SHALL switch to the new group channel
- **AND** a success toast SHALL display: "Group channel created with [original persona] and [new persona]"
- **AND** the new channel SHALL appear in the sidebar via existing SSE `channel_update` handling

#### Scenario: API failure

- **WHEN** the API returns an error response
- **THEN** an error toast SHALL display with the failure reason
- **AND** the voice chat panel SHALL remain on the current agent chat
- **AND** no partial state cleanup is required on the frontend

---

### Requirement: Loading State

The voice app SHALL display a loading indicator while the promote-to-group API call is in flight.

#### Scenario: Loading during promote

- **WHEN** the promote API call is initiated
- **THEN** a loading indicator SHALL be visible (inline header text or toast with spinner)
- **AND** the indicator SHALL be dismissed when the API call completes (success or error)

---

### Requirement: Original Chat Preservation

The promote-to-group action SHALL NOT modify, hide, or reparent the original 1:1 agent chat.

#### Scenario: Original chat accessible after promote

- **WHEN** a group channel is successfully created from an agent chat
- **THEN** the original 1:1 agent chat SHALL remain in the sidebar agent list
- **AND** the original chat SHALL be clickable and fully functional
