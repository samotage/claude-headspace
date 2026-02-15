## ADDED Requirements

### Requirement: Tmux Attach Endpoint

The focus blueprint SHALL provide a `POST /api/agents/<id>/attach` endpoint for attaching to an agent's tmux session. This is distinct from the existing focus endpoint which brings an existing window to the foreground.

#### Scenario: Attach endpoint routes to attach logic

- **WHEN** `POST /api/agents/<id>/attach` is called
- **THEN** the request is handled by the attach logic (not the focus logic)
- **AND** the response format matches the attach API specification in the `tmux-attach` capability

#### Scenario: Attach endpoint validates tmux session exists

- **WHEN** `POST /api/agents/<id>/attach` is called for an agent with `tmux_session` set
- **THEN** the endpoint SHALL verify the tmux session exists before invoking AppleScript
- **AND** return `detail: "session_not_found"` if the session is gone

#### Scenario: Attach event logged

- **WHEN** an attach attempt is made (success or failure)
- **THEN** the event is logged with agent_id, tmux_session, outcome, error_type, and latency_ms
