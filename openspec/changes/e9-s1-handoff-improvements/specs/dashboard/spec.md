## MODIFIED Requirements

### Requirement: Dashboard Synthetic Turn Rendering

The dashboard SHALL handle `synthetic_turn` SSE events and render them as visually distinct bubbles on the agent's dashboard card.

#### Scenario: Visual distinction

- **WHEN** a `synthetic_turn` event is received by the dashboard
- **THEN** it SHALL render with a muted background or dashed border and a "SYSTEM" label
- **AND** it SHALL appear before the agent's first real turn

#### Scenario: Copyable file paths

- **WHEN** a handoff entry is displayed in a synthetic turn
- **THEN** clicking the entry SHALL copy the full absolute file path to the clipboard

### Requirement: SSE Client Event Types

The SSE client `commonTypes` array SHALL include `synthetic_turn` to ensure the event is received by the dashboard.

#### Scenario: synthetic_turn in commonTypes

- **WHEN** the SSE client connects to the event stream
- **THEN** `synthetic_turn` SHALL be registered as a typed event handler
