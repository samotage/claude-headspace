## ADDED Requirements

### Requirement: create_channel_from_personas() — Persona-Based Channel Orchestration

The ChannelService SHALL provide a `create_channel_from_personas()` method that creates a pending channel and initiates one fresh agent spin-up per persona slug.

#### Scenario: Successful persona-based channel creation

- **WHEN** `create_channel_from_personas(creator_persona, channel_type, project_id, persona_slugs)` is called with valid inputs
- **THEN** a Channel MUST be created with status `pending`
- **AND** the channel name MUST be auto-generated as persona names joined by " + "
- **AND** one ChannelMembership with `agent_id = null` and `is_chair = false` MUST be created per persona slug
- **AND** `_spin_up_agent_for_persona(persona, project_id)` MUST be called once per persona slug
- **AND** a system message MUST be injected via `_post_system_message`
- **AND** `_broadcast_channel_created` MUST be called

#### Scenario: Empty persona_slugs

- **WHEN** `persona_slugs` is an empty list
- **THEN** the method MUST raise `ValueError`

#### Scenario: Invalid project_id

- **WHEN** `project_id` does not resolve to an existing Project
- **THEN** the method MUST raise `ProjectNotFoundError`

---

### Requirement: link_agent_to_pending_membership() — Agent Registration Link

The ChannelService SHALL provide a `link_agent_to_pending_membership()` method that links a newly-registered agent to any pending channel membership for that agent's persona.

#### Scenario: Pending membership found

- **WHEN** `link_agent_to_pending_membership(agent)` is called for an agent whose persona has a pending channel membership (`agent_id IS NULL`, channel status `pending`)
- **THEN** the oldest such membership's `agent_id` MUST be set to `agent.id`
- **AND** `check_channel_ready(channel_id)` MUST be called for that channel

#### Scenario: No pending membership

- **WHEN** `link_agent_to_pending_membership(agent)` is called for an agent with no pending memberships
- **THEN** the method MUST return without error or side effects

#### Scenario: Agent has no persona

- **WHEN** `link_agent_to_pending_membership(agent)` is called for an agent without a persona
- **THEN** the method MUST return early without any DB queries

---

### Requirement: check_channel_ready() — Channel Readiness Transition

The ChannelService SHALL provide a `check_channel_ready()` method that transitions a channel to `active` when all non-chair memberships are linked to agents.

#### Scenario: All agents connected — transition to active

- **WHEN** `check_channel_ready(channel_id)` is called and all non-chair memberships have non-null `agent_id`
- **THEN** the channel status MUST transition from `pending` to `active`
- **AND** a go-signal system message MUST be injected
- **AND** a `channel_ready` SSE event MUST be broadcast
- **AND** the method MUST return `True`

#### Scenario: Not all agents connected yet

- **WHEN** `check_channel_ready(channel_id)` is called and at least one non-chair membership has `agent_id = null`
- **THEN** the channel status MUST remain `pending`
- **AND** a `channel_member_connected` SSE event MUST be broadcast with connected/total counts
- **AND** the method MUST return `False`

#### Scenario: Channel not in pending status

- **WHEN** `check_channel_ready(channel_id)` is called for a channel that is not in `pending` status
- **THEN** the method MUST return `False` without modifying the channel

---

## MODIFIED Requirements

### Requirement: _spin_up_agent_for_persona() — Always Fresh, Project-Aware

The `_spin_up_agent_for_persona()` internal method SHALL accept a `project_id` parameter and MUST always create a fresh agent (never reuse an existing running agent).

#### Scenario: Spin up with explicit project_id

- **WHEN** `_spin_up_agent_for_persona(persona, project_id=5)` is called
- **THEN** `create_agent(project_id=5, persona_slug=persona.slug)` MUST be called
- **AND** any existing active agents for that persona MUST NOT be reused

#### Scenario: No project_id provided

- **WHEN** `_spin_up_agent_for_persona(persona, project_id=None)` is called
- **THEN** the method MUST log a warning and return `None`
- **AND** no `create_agent` call MUST be made

---

### Requirement: add_member() — Cross-Project Support

The `add_member()` method SHALL accept an optional `project_id` parameter for cross-project member addition.

#### Scenario: Add member with cross-project project_id

- **WHEN** `add_member(slug, persona_slug, caller_persona, project_id=7)` is called
- **THEN** the fresh agent MUST be spun up under `project_id` 7
- **AND** the membership MUST be created with `agent_id = null`

#### Scenario: Add member without project_id — uses channel project

- **WHEN** `add_member(slug, persona_slug, caller_persona)` is called without `project_id`
- **THEN** the channel's own `project_id` MUST be used for the spin-up

---

### Requirement: Hook Receiver — Agent Link on Session-Start

The hook receiver SHALL call `link_agent_to_pending_membership()` after an agent is registered on session-start, inside a try/except to prevent blocking.

#### Scenario: New agent registers — pending membership exists

- **WHEN** a session-start hook fires for a new agent whose persona has a pending channel membership
- **THEN** `channel_service.link_agent_to_pending_membership(agent)` MUST be called after the agent is persisted
- **AND** errors from this call MUST NOT prevent the hook from returning a success response

#### Scenario: New agent registers — no pending membership

- **WHEN** a session-start hook fires for an agent with no pending channel memberships
- **THEN** the hook MUST complete normally without error
