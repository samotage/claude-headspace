# channel-delivery Specification

## Purpose
TBD - created by archiving change e9-s6-delivery-engine. Update Purpose after archive.
## Requirements
### Requirement: Service Registration (NFR5)
`ChannelDeliveryService` SHALL be registered as `app.extensions["channel_delivery_service"]` following the existing service registration pattern in `app.py`.

#### Scenario: Service available
- **WHEN** the Flask app is created with database connected
- **THEN** `app.extensions["channel_delivery_service"]` is a `ChannelDeliveryService` instance

---

### Requirement: Post-Commit Fan-Out Trigger (FR1)
When `ChannelService.send_message()` commits a Message to the database, the delivery engine SHALL be invoked as a post-commit side effect to deliver the message to all other active members.

#### Scenario: Message fan-out
- **WHEN** a Message is persisted via `ChannelService.send_message()`
- **THEN** `ChannelDeliveryService.deliver_message()` is called
- **AND** all active (non-muted) members excluding the sender receive the message

---

### Requirement: Member Iteration (FR2)
The delivery engine SHALL iterate all ChannelMembership records for the message's channel where `status = 'active'`, excluding the membership record matching the sender's persona.

#### Scenario: Skip sender
- **WHEN** the sender has persona_id = 5
- **THEN** the membership with persona_id = 5 is excluded from delivery

#### Scenario: Skip muted members
- **WHEN** a membership has `status = 'muted'`
- **THEN** that member does not receive delivery

---

### Requirement: Delivery Per Member Type (FR3)
The delivery engine SHALL deliver messages according to the member type: tmux for internal online agents, notification for operators, deferred for offline agents, no-op for remote/external (SSE handled by ChannelService).

#### Scenario: Internal online agent
- **WHEN** a member is an internal persona with an active agent and available tmux pane
- **THEN** the message is delivered via `tmux_bridge.send_text()` with the envelope format

#### Scenario: Internal offline agent
- **WHEN** a member is an internal persona with no active agent
- **THEN** no delivery action is taken (message persists in channel history for context briefing)

#### Scenario: Operator (person/internal)
- **WHEN** a member is an internal person (operator)
- **THEN** a macOS notification is sent via `NotificationService.send_channel_notification()`

#### Scenario: Remote/external agent or person
- **WHEN** a member is remote or external
- **THEN** no delivery action is taken (SSE already broadcast by ChannelService)

---

### Requirement: Failure Isolation (FR4)
If delivery fails for one member (tmux error, notification exception), the engine SHALL log the failure and continue delivering to remaining members.

#### Scenario: Partial failure
- **WHEN** delivery to member A fails with an exception
- **THEN** delivery to members B and C still proceeds
- **AND** the failure is logged at warning level

---

### Requirement: Tmux Delivery Envelope (FR5)
Messages delivered to agents via tmux SHALL be wrapped in the envelope format: `[#channel-slug] PersonaName (agent:ID):\n{message content}`.

#### Scenario: Agent sender
- **WHEN** a message from persona "Paula" (agent:1087) is delivered to another agent via tmux in channel "architecture-review"
- **THEN** the tmux text is `[#architecture-review] Paula (agent:1087):\n{content}`

#### Scenario: Operator sender
- **WHEN** a message from the operator (no agent) is delivered
- **THEN** the agent tag is `(operator)` instead of `(agent:ID)`

---

### Requirement: COMMAND COMPLETE Stripping (FR6)
The `COMMAND COMPLETE` footer SHALL be stripped from message content before channel relay. The original text remains on the agent's individual Turn record.

#### Scenario: Footer present
- **WHEN** a message contains the COMMAND COMPLETE footer pattern
- **THEN** the footer is stripped from the relayed content
- **AND** the original Turn.text is unchanged

#### Scenario: No footer
- **WHEN** a message does not contain the footer pattern
- **THEN** the content is used as-is

---

### Requirement: Completion Relay Trigger (FR7)
When `process_stop()` processes a Turn classified as COMPLETION or END_OF_COMMAND for an agent that is a member of an active channel, the delivery engine SHALL post the agent's response as a new Message in that channel.

#### Scenario: Agent completes in channel
- **WHEN** an agent's stop hook produces a COMPLETION Turn
- **AND** the agent has an active ChannelMembership
- **THEN** `relay_agent_response()` posts the Turn text as a new channel Message via `ChannelService.send_message()`

#### Scenario: Agent not in channel
- **WHEN** an agent's stop hook produces a COMPLETION Turn
- **AND** the agent has no active ChannelMembership
- **THEN** no relay occurs

---

### Requirement: Message Attribution (FR8)
The relayed Message SHALL carry `persona_id` from the agent's persona, `agent_id` from the agent, `source_turn_id` from the triggering Turn, and `source_command_id` from the agent's current Command.

#### Scenario: Attribution fields
- **WHEN** a response is relayed as a channel Message
- **THEN** the Message has correct persona_id, agent_id, source_turn_id, and source_command_id

---

### Requirement: Completion-Only Relay (FR9)
Only Turns with intent COMPLETION or END_OF_COMMAND SHALL be relayed to the channel. PROGRESS, QUESTION, and other intents are NOT relayed.

#### Scenario: PROGRESS turn
- **WHEN** a stop hook produces a PROGRESS Turn
- **THEN** no channel relay occurs

#### Scenario: QUESTION turn
- **WHEN** a stop hook produces a QUESTION Turn
- **THEN** no channel relay occurs

---

### Requirement: One-Agent-One-Channel Attribution (FR10)
The delivery engine SHALL enforce one-agent-one-channel attribution. When an agent produces output, the delivery engine looks up their single active ChannelMembership to determine the target channel. No disambiguation is needed.

#### Scenario: Single channel lookup
- **WHEN** agent #1053 produces a COMPLETION Turn
- **THEN** the delivery engine queries their single active ChannelMembership
- **AND** no disambiguation is needed

---

### Requirement: In-Memory Queue Structure (FR11)
The delivery engine SHALL maintain an in-memory queue as a `dict[int, deque[int]]` mapping `agent_id` to `deque` of Message IDs.

#### Scenario: Queue structure
- **WHEN** messages are queued for agent 5
- **THEN** `self._queues[5]` is a `deque` of Message IDs in FIFO order

---

### Requirement: State Safety Check (FR12)
Before delivering a message via tmux, the delivery engine SHALL check the target agent's current command state. Only AWAITING_INPUT and IDLE are safe. PROCESSING, COMMANDED, and COMPLETE are unsafe (message is queued).

#### Scenario: Safe state delivery
- **WHEN** an agent is in AWAITING_INPUT
- **THEN** the message is delivered immediately via tmux

#### Scenario: Unsafe state queuing
- **WHEN** an agent is in PROCESSING
- **THEN** the Message ID is added to the agent's queue

---

### Requirement: Queue Drain on State Transition (FR13)
When an agent transitions to AWAITING_INPUT or IDLE, the delivery engine SHALL deliver the oldest queued message (FIFO). Only one message per transition.

#### Scenario: Drain on AWAITING_INPUT
- **WHEN** `CommandLifecycleManager.update_command_state()` transitions to AWAITING_INPUT
- **THEN** `drain_queue(agent_id)` is called
- **AND** the oldest queued message is delivered

#### Scenario: Drain on IDLE (after complete_command)
- **WHEN** `process_stop()` calls `complete_command()` and commits
- **THEN** `drain_queue(agent_id)` is called

---

### Requirement: Pane Health Check (FR14)
Before tmux delivery, the delivery engine SHALL consult `CommanderAvailability.is_available(agent_id)`. If unavailable, the message stays queued.

#### Scenario: Pane unavailable
- **WHEN** `CommanderAvailability.is_available(agent_id)` returns False
- **THEN** the message stays queued
- **AND** a warning is logged

---

### Requirement: Feedback Loop Prevention (FR15)
The delivery engine SHALL prevent feedback loops via three independent mechanisms: completion-only relay, source tracking (`source_turn_id` on Messages), and IntentDetector gating.

#### Scenario: Natural conversation
- **WHEN** agent A responds to a channel message and agent B responds to A's relay
- **THEN** both responses are relayed normally (this is a conversation, not a loop)
- **AND** only composed final responses circulate (no intermediate output)

---

### Requirement: No New Database Tables (NFR1)
The delivery engine SHALL NOT add new database tables or columns. It uses existing Message and ChannelMembership models from S3.

#### Scenario: Schema unchanged
- **WHEN** the delivery engine is deployed
- **THEN** no new migration files are created
- **AND** the existing schema is unchanged

---

### Requirement: Best-Effort Delivery (NFR2)
The delivery engine SHALL NOT retry failed deliveries. Failed deliveries are logged at warning level. Messages persist in channel history for later access.

#### Scenario: Failed delivery not retried
- **WHEN** a tmux `send_text()` call fails
- **THEN** the failure is logged
- **AND** no retry is attempted
- **AND** the message remains in channel history

---

### Requirement: Concurrency (NFR3)
Fan-out to N agents SHALL use N parallel tmux operations via existing per-pane `RLock`. The delivery engine SHALL NOT introduce a global lock across panes.

#### Scenario: Parallel fan-out
- **WHEN** a message fans out to 3 agents
- **THEN** each delivery uses the existing per-pane lock independently
- **AND** no global lock serializes the fan-out

---

### Requirement: Thread Safety (NFR6)
The in-memory delivery queue dict SHALL use a `threading.Lock` for queue mutations (add, drain, check).

#### Scenario: Concurrent queue access
- **WHEN** two threads enqueue messages simultaneously
- **THEN** the Lock serializes access and no messages are lost

---

### Requirement: Channel Notification (Section 6.14)
`NotificationService` SHALL have a `send_channel_notification()` method with per-channel rate limiting (30-second window).

#### Scenario: Notification sent
- **WHEN** a message is delivered to the operator
- **THEN** a macOS notification is sent with channel name, sender name, and content preview

#### Scenario: Rate limited
- **WHEN** two channel notifications fire within 30 seconds for the same channel
- **THEN** the second notification is suppressed

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

