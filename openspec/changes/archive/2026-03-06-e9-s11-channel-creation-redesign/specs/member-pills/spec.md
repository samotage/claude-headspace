## ADDED Requirements

### Requirement: Per-Member Pills Replace Plain Count — Voice App

The voice app channel chat header SHALL display one pill per channel member instead of a plain member count text.

#### Scenario: Channel opens — pills render

- **WHEN** the operator opens a channel chat in the voice app
- **THEN** `#channel-chat-member-pills` (replacing `#channel-chat-member-count`) MUST render:
  - One pill per non-chair member
  - Connected pills (agent_id set) MUST be visually distinct (e.g. cyan/primary accent)
  - Pending pills (agent_id null) MUST be visually muted/greyed and NOT clickable
  - A count text "X of Y online" MUST appear alongside the pills

#### Scenario: Connected pill clicked (voice app)

- **WHEN** the operator taps a connected member pill in the voice app
- **THEN** `POST /api/focus/<agent_id>` MUST be called for that pill's agent_id

#### Scenario: Pending pill clicked (voice app)

- **WHEN** the operator taps a pending (muted) pill
- **THEN** NO focus API call MUST be made (pending pills are not interactive)

#### Scenario: SSE update — pending to connected (voice app)

- **WHEN** a `channel_member_connected` SSE event is received for a member of the current channel
- **THEN** that member's pill MUST visually transition from pending to connected state
- **AND** the count text MUST update without a page reload

#### Scenario: channel_ready received (voice app)

- **WHEN** a `channel_ready` SSE event is received for the current channel
- **THEN** the chat input MUST become enabled
- **AND** a go-signal system message MUST appear in the message feed

---

### Requirement: Per-Member Pills Replace Plain Count — Dashboard

The dashboard channel chat panel header SHALL display one pill per channel member in `#channel-chat-member-pills`, already present in the HTML.

#### Scenario: Channel opens — pills render (dashboard)

- **WHEN** the operator opens a channel in the dashboard chat panel
- **THEN** `#channel-chat-member-pills` MUST render one pill per non-chair member:
  - Connected pills clickable to focus API
  - Pending pills visually distinct and NOT clickable

#### Scenario: Connected pill clicked (dashboard)

- **WHEN** the operator clicks a connected member pill in the dashboard
- **THEN** `POST /api/focus/<agent_id>` MUST be called

#### Scenario: SSE update — pending to connected (dashboard)

- **WHEN** a `channel_member_connected` SSE event is received for the open channel
- **THEN** the affected pill MUST transition to connected state without a page reload

#### Scenario: channel_ready received (dashboard)

- **WHEN** a `channel_ready` SSE event is received for the open channel
- **THEN** the chat input MUST become enabled
- **AND** a go-signal system message MUST appear in the channel feed

---

### Requirement: Channel Readiness State — Pending Input Lock

Both surfaces SHALL lock the channel chat input while the channel is in `pending` status.

#### Scenario: Channel pending — input locked

- **WHEN** a channel with status `pending` is opened in either surface
- **THEN** the chat input MUST be disabled/greyed (not interactive)
- **AND** the channel MUST be visible with the initiation system message visible

#### Scenario: Channel active — input enabled

- **WHEN** a channel with status `active` is opened in either surface (or transitions to active via channel_ready SSE)
- **THEN** the chat input MUST be enabled and interactive

---

### Requirement: Progressive Pill Appearance During Spin-Up

Pills SHALL appear progressively as agents connect, not all at once.

#### Scenario: Creation — initial pending state

- **WHEN** a channel is created via `create_channel_from_personas()`
- **THEN** on channel open, one pending pill MUST appear per selected persona
- **AND** all pills MUST be in pending (muted) state initially

#### Scenario: Agent connects — pill transitions

- **WHEN** an agent registers (session-start) and is linked to a pending membership
- **THEN** that member's pill MUST transition from pending to connected
- **AND** the count text MUST update (e.g. "2 of 3 online")
- **AND** other pending pills MUST remain unchanged
