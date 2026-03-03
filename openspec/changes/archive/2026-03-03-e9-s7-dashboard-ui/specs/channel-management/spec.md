## ADDED Requirements

### Requirement: Channel Management Access
The dashboard SHALL include a navigation element (button in the header or controls area) to open a channel management modal.

#### Scenario: Open management modal
- **WHEN** the user clicks the "Channels" button in the dashboard header/controls
- **THEN** a modal opens with the channel management interface

### Requirement: Channel List
The management modal SHALL list all channels visible to the operator by calling `GET /api/channels?all=true`.

#### Scenario: Channel list display
- **WHEN** the management modal opens
- **THEN** it displays a table of channels with columns: name, slug, type, status, member count, and created date
- **AND** rows are clickable to open the chat panel for that channel

### Requirement: Create Channel Form
The management modal SHALL provide a "Create Channel" form.

#### Scenario: Successful channel creation
- **WHEN** the user fills in name (required), type (required, dropdown), description (optional), and members (optional, comma-separated persona slugs)
- **AND** submits the form
- **THEN** it calls `POST /api/channels` with the form data
- **AND** the new channel appears in the management list
- **AND** a new channel card appears on the dashboard

#### Scenario: Create form validation
- **WHEN** the user submits without required fields
- **THEN** the form shows validation errors without making an API call

#### Scenario: Create API error
- **WHEN** the API returns an error (e.g., duplicate name, invalid type)
- **THEN** the error message is displayed via the existing toast system

### Requirement: Channel Actions
The management modal SHALL provide action buttons for channel lifecycle transitions.

#### Scenario: Complete channel
- **WHEN** the user clicks "Complete" on an active channel
- **THEN** it calls `POST /api/channels/<slug>/complete`
- **AND** the channel status updates in the list and on the dashboard card

#### Scenario: Archive channel
- **WHEN** the user clicks "Archive" on a completed channel
- **THEN** it calls `POST /api/channels/<slug>/archive`
- **AND** the channel is removed from the dashboard cards
- **AND** the channel status updates in the management list

#### Scenario: View history
- **WHEN** the user clicks "View History" on a channel
- **THEN** the chat panel opens for that channel, showing its complete message history
