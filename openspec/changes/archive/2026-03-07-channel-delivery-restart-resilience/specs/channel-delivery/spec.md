## ADDED Requirements

### Requirement: Reconstruct _channel_prompted on service init

`ChannelDeliveryService` SHALL reconstruct the `_channel_prompted` set from database records when initialised, so that agent responses pending before a server restart are relayed correctly.

#### Scenario: Agent prompted but has not responded

- **WHEN** `ChannelDeliveryService` initialises
- **AND** an agent has an active `ChannelMembership` (status = "active")
- **AND** the agent is alive (`Agent.ended_at` IS NULL)
- **AND** the most recent `Message` in the agent's channel NOT sent by this agent is more recent than the most recent `Message` sent BY this agent (or the agent has never sent a message)
- **AND** the most recent non-agent message is within the stale cutoff threshold (default: 1 hour)
- **THEN** the agent's ID MUST be added to `_channel_prompted`

#### Scenario: Agent has already responded

- **WHEN** `ChannelDeliveryService` initialises
- **AND** an agent's most recent message in the channel is more recent than the most recent message from others
- **THEN** the agent's ID MUST NOT be added to `_channel_prompted`

#### Scenario: Stale messages beyond cutoff

- **WHEN** `ChannelDeliveryService` initialises
- **AND** all messages in a channel are older than the stale cutoff threshold
- **THEN** no agents from that channel SHALL be added to `_channel_prompted`

#### Scenario: Ended agent

- **WHEN** an agent has `ended_at` set (not NULL)
- **THEN** the agent MUST NOT be added to `_channel_prompted` regardless of message state

#### Scenario: Inactive membership

- **WHEN** a `ChannelMembership` has status != "active"
- **THEN** the member MUST NOT be considered for `_channel_prompted` reconstruction

---

### Requirement: Reconstruct _queue on service init

`ChannelDeliveryService` SHALL reconstruct the `_queue` dict from database records when initialised, so that messages queued for agents in unsafe states before a restart are re-queued.

#### Scenario: Agent in unsafe state with undelivered messages

- **WHEN** `ChannelDeliveryService` initialises
- **AND** an agent member's current command is in an unsafe state (not AWAITING_INPUT or IDLE)
- **AND** there are channel messages sent after the agent's last response that were not sent by this agent
- **THEN** those Message IDs MUST be added to the agent's queue in `_queue`

#### Scenario: Agent in safe state

- **WHEN** an agent's current command is in a safe state (AWAITING_INPUT or IDLE) or has no active command
- **THEN** no messages SHALL be queued for that agent during reconstruction

---

### Requirement: Reconstruction logging

The service MUST log reconstruction results at INFO level including:
- Number of agents added to `_channel_prompted`
- Number of messages re-queued per agent
- Total reconstruction time in milliseconds
- Explicit log entry when no state was reconstructed

#### Scenario: State reconstructed with results

- **WHEN** reconstruction completes and agents were added to `_channel_prompted` or messages were re-queued
- **THEN** the service MUST log at INFO level the count of agents added and messages re-queued per agent, plus total reconstruction time

#### Scenario: No state to reconstruct

- **WHEN** reconstruction completes and no agents needed prompting and no messages needed re-queuing
- **THEN** the service MUST log at INFO level that no state was reconstructed (to confirm reconstruction ran)

---

### Requirement: Idempotent reconstruction

Reconstruction MUST be safe to execute multiple times. Running reconstruction when `_channel_prompted` or `_queue` already contain data MUST clear existing data before repopulating, preventing duplicates.

#### Scenario: Reconstruction called twice

- **WHEN** `_reconstruct_state()` is called when `_channel_prompted` already contains agent IDs
- **THEN** the sets and dicts MUST be cleared before repopulating
- **AND** the final state MUST be identical to a single reconstruction call

---

### Requirement: Reconstruction error isolation

If reconstruction fails (e.g., database error), the service MUST still initialise successfully. Reconstruction errors MUST be logged at WARNING level but MUST NOT prevent the service from handling new delivery and relay requests.

#### Scenario: Database error during reconstruction

- **WHEN** a database error occurs during reconstruction query execution
- **THEN** the error MUST be caught and logged at WARNING level
- **AND** `_channel_prompted` MUST remain empty (or cleared)
- **AND** `_queue` MUST remain empty (or cleared)
- **AND** the service MUST be fully functional for new delivery and relay operations

---

### Requirement: Query efficiency

Reconstruction MUST execute a bounded number of database queries regardless of the number of channels or members. The implementation SHOULD use 1-2 queries with appropriate joins and subqueries, NOT per-channel or per-agent query loops.

#### Scenario: Multiple channels with multiple members

- **WHEN** reconstruction runs with N active channels and M total active memberships
- **THEN** the number of SQL queries executed MUST be O(1) — bounded regardless of N or M
- **AND** reconstruction MUST complete in under 100ms for typical sizes (10 members, 1000 messages)

---

## UNCHANGED Requirements

- All existing delivery, relay, queue, and notification behaviour remains unchanged
- The `Message` model and database schema are not modified
- No new configuration options required (reconstruction is always-on; cutoff threshold uses existing config pattern)
