# channel-admin-page Specification

## Purpose
TBD - created by archiving change e9-s9-channel-admin-page. Update Purpose after archive.
## Requirements
### Requirement: Channel Admin Page Route

The system SHALL serve a dedicated channel administration page at `/channels`. The page SHALL extend `base.html`, include the shared header with navigation, and follow the layout pattern established by `/personas` and `/activity`.

#### Scenario: Page loads successfully

- **WHEN** the operator navigates to `/channels`
- **THEN** the page renders with a channel list table, status filter tabs, a search input, and a "New Channel" button

#### Scenario: Navigation link active state

- **WHEN** the operator is on the `/channels` page
- **THEN** the "channels" link in the header navigation SHALL have the `active` class and `aria-current="page"` attribute

---

### Requirement: Channel List Display

The channel list table SHALL display all channels visible to the operator with columns: name (clickable for detail), type (badge), status (colour-coded label), members (count), last activity (relative time), created date, and actions (lifecycle buttons).

#### Scenario: Default sort order

- **WHEN** the channel list renders
- **THEN** active channels SHALL appear first, sorted by last activity descending

#### Scenario: Empty state

- **WHEN** no channels exist
- **THEN** the page SHALL display an empty state message with guidance to create a channel

---

### Requirement: Status Filter

The page SHALL provide filter tabs for channel status: Active (default on page load), Pending, Complete, Archived, All.

#### Scenario: Filter by status

- **WHEN** the operator clicks a filter tab (e.g., "Complete")
- **THEN** only channels with that status SHALL be visible in the table
- **AND** the selected tab SHALL be visually highlighted

#### Scenario: Default filter on page load

- **WHEN** the page loads for the first time
- **THEN** the "Active" filter SHALL be selected by default

#### Scenario: "All" filter

- **WHEN** the operator selects "All"
- **THEN** all channels SHALL be visible, including archived channels

---

### Requirement: Text Search

The page SHALL provide a text input that filters the channel list by name or slug as the operator types (client-side filtering).

#### Scenario: Search matches

- **WHEN** the operator types "api" in the search input
- **THEN** only channels whose name or slug contains "api" (case-insensitive) SHALL be visible

#### Scenario: Search with active filter

- **WHEN** the operator has a status filter active and types a search term
- **THEN** both filters SHALL apply (intersection)

---

### Requirement: Attention Signals

Active channels with no message activity in a configurable time window (default: 2 hours) SHALL display a visual attention indicator (amber dot or pulse).

#### Scenario: Stale active channel

- **WHEN** an active channel has no messages in the last 2 hours AND has at least one active member
- **THEN** an amber attention indicator SHALL be displayed on that channel's row

#### Scenario: Non-active channel

- **WHEN** a channel has status "complete" or "archived"
- **THEN** no attention indicator SHALL be displayed regardless of last activity

---

### Requirement: Channel Detail Panel

Clicking a channel row SHALL expand an inline detail panel showing: name, slug, type, status, description, chair persona, full member list (with membership status), message count, created date, last activity date, and available lifecycle action buttons.

#### Scenario: Expand detail

- **WHEN** the operator clicks a channel row
- **THEN** a detail panel SHALL expand below the row with full channel metadata and member list

#### Scenario: Collapse detail

- **WHEN** the operator clicks the expanded channel row again (or clicks another row)
- **THEN** the detail panel SHALL collapse

---

### Requirement: Create Channel

The page SHALL provide a "New Channel" button that opens a create form with fields: name (required), type (required, dropdown: workshop, delegation, review, standup, broadcast), description (optional), initial members (optional, persona autocomplete picker).

#### Scenario: Successful creation

- **WHEN** the operator fills in the required fields and submits
- **THEN** a `POST /api/channels` request SHALL be sent
- **AND** on success, the new channel SHALL appear in the list without page reload

#### Scenario: Validation error

- **WHEN** the operator submits without a name
- **THEN** a client-side validation error SHALL be displayed

---

### Requirement: Complete Channel

An active channel SHALL have a "Complete" button visible in the detail panel and/or actions column.

#### Scenario: Complete an active channel

- **WHEN** the operator clicks "Complete" on an active channel
- **THEN** `POST /api/channels/<slug>/complete` SHALL be called
- **AND** the channel's status SHALL update to "complete" in the list

#### Scenario: Button visibility

- **WHEN** a channel is not active (pending, complete, or archived)
- **THEN** the "Complete" button SHALL NOT be visible

---

### Requirement: Archive Channel

A completed channel SHALL have an "Archive" button visible.

#### Scenario: Archive a completed channel

- **WHEN** the operator clicks "Archive" on a completed channel
- **THEN** `POST /api/channels/<slug>/archive` SHALL be called
- **AND** the channel's status SHALL update to "archived" in the list

#### Scenario: Button visibility

- **WHEN** a channel is not completed
- **THEN** the "Archive" button SHALL NOT be visible

---

### Requirement: Delete Channel

An archived channel (or a channel with zero active members) SHALL have a "Delete" button.

#### Scenario: Delete with confirmation

- **WHEN** the operator clicks "Delete"
- **THEN** a confirmation dialog SHALL appear with the message "Are you sure you want to permanently delete channel #[name]? This cannot be undone."
- **AND** on confirmation, `DELETE /api/channels/<slug>` SHALL be called
- **AND** on success, the channel SHALL be removed from the list

#### Scenario: Delete precondition failure

- **WHEN** a channel is active with active members
- **THEN** the "Delete" button SHALL NOT be visible

#### Scenario: API — delete endpoint

- **WHEN** `DELETE /api/channels/<slug>` is called for a channel that is not archived and has active members
- **THEN** a 409 error SHALL be returned with code `channel_not_deletable`

---

### Requirement: Add Member

The channel detail panel SHALL provide an "Add Member" action that opens a persona picker.

#### Scenario: Add member successfully

- **WHEN** the operator selects a persona from the picker
- **THEN** `POST /api/channels/<slug>/members` SHALL be called with the persona slug
- **AND** the member SHALL appear in the detail panel's member list

---

### Requirement: Remove Member

Each member in the detail panel's member list SHALL have a "Remove" action.

#### Scenario: Remove member successfully

- **WHEN** the operator clicks "Remove" on a member
- **THEN** `DELETE /api/channels/<slug>/members/<persona_slug>` SHALL be called
- **AND** the member SHALL be removed from the list

#### Scenario: Sole chair prevention

- **WHEN** the member being removed is the sole chair of the channel
- **THEN** the removal SHALL be rejected with an error message

---

### Requirement: SSE Real-Time Updates

The channel list SHALL subscribe to `channel_message` and `channel_update` SSE events.

#### Scenario: New message updates last activity

- **WHEN** a `channel_message` SSE event arrives for a channel in the list
- **THEN** the "last activity" column for that channel SHALL update to reflect the new time

#### Scenario: Member change updates count

- **WHEN** a `channel_update` SSE event arrives indicating a member join or leave
- **THEN** the "members" column SHALL update its count

#### Scenario: Status change updates display

- **WHEN** a `channel_update` SSE event indicates a status transition (e.g., active -> complete)
- **THEN** the channel row SHALL update its status label and move to the appropriate filter group

---

### Requirement: Modal Deprecation

The existing channel management modal (`_channel_management.html`) SHALL be superseded by the `/channels` page. The "Channel Management" button on the dashboard SHALL be replaced with a link to `/channels`.

#### Scenario: Dashboard button redirect

- **WHEN** the operator clicks the former "Channel Management" button area on the dashboard
- **THEN** they SHALL be navigated to `/channels` instead of opening a modal

---

### Requirement: API — Remove Member Endpoint

A new endpoint `DELETE /api/channels/<slug>/members/<persona_slug>` SHALL be added.

#### Scenario: Successful removal

- **WHEN** the persona is an active member of the channel
- **THEN** the membership SHALL be removed and a 200 response returned

#### Scenario: Not a member

- **WHEN** the persona is not a member of the channel
- **THEN** a 404 error SHALL be returned

#### Scenario: Sole chair

- **WHEN** the persona is the sole chair
- **THEN** a 403 error SHALL be returned with code `sole_chair`

