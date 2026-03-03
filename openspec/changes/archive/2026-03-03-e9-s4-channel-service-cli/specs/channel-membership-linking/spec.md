## ADDED Requirements

### Requirement: Agent-to-Membership Linking on Registration (FR14)
When the session correlator / hook receiver links a new agent to a persona (during `process_session_start()`), the system SHALL check for any ChannelMembership where `persona_id = agent.persona_id AND agent_id IS NULL AND status = 'active'` and update `agent_id` to the new agent's ID.

#### Scenario: Agent linked to pending membership
- **WHEN** a new agent registers with persona_id 5
- **AND** a ChannelMembership exists with persona_id=5, agent_id=NULL, status='active'
- **THEN** the membership's agent_id is updated to the new agent's ID

#### Scenario: No pending memberships
- **WHEN** a new agent registers with a persona that has no pending channel memberships
- **THEN** no membership records are modified

---

### Requirement: Context Briefing Delivery on Post-Registration (FR14a)
After linking an agent to a ChannelMembership (FR14), the system SHALL generate and deliver the context briefing (last 10 messages) to the agent via tmux. This is the delivery trigger for agents spun up asynchronously by `add_member`.

#### Scenario: Briefing delivered
- **WHEN** an agent is linked to a ChannelMembership in a channel with messages
- **THEN** a context briefing (last 10 messages) is generated and sent to the agent's tmux session

#### Scenario: Empty channel
- **WHEN** an agent is linked to a ChannelMembership in a channel with no messages
- **THEN** no briefing is delivered

---

### Requirement: Modification Location
The agent-to-membership linking logic SHALL be added to `process_session_start()` in `hook_receiver.py`, after the persona assignment block. This follows the sequential append pattern for modifications at the same logical point.

#### Scenario: Execution order
- **WHEN** `process_session_start()` runs
- **THEN** persona assignment occurs first
- **AND** channel membership linking occurs after persona assignment
- **AND** context briefing delivery occurs after membership linking
