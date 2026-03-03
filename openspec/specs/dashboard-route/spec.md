# dashboard-route Specification

## Purpose
TBD - created by archiving change e9-s7-dashboard-ui. Update Purpose after archive.
## Requirements
### Requirement: Dashboard Route Channel Data
The dashboard route handler SHALL provide a `channel_data` template context variable containing the operator's active channel memberships with channel details and last message previews.

#### Scenario: Operator with active memberships
- **WHEN** the dashboard page loads and the operator has active channel memberships
- **THEN** the template context includes `channel_data` as a list of dicts, each containing: `slug`, `name`, `channel_type`, `status`, `members` (list of persona names), and `last_message` (dict with `persona_name`, `content_preview`, `sent_at` or `None`)

#### Scenario: Operator with no Persona
- **WHEN** the dashboard page loads and the operator has no registered Persona
- **THEN** `channel_data` is an empty list

#### Scenario: Operator with no memberships
- **WHEN** the dashboard page loads and the operator's Persona has no active channel memberships
- **THEN** `channel_data` is an empty list

#### Scenario: Archived channels excluded
- **WHEN** the operator has memberships in archived channels
- **THEN** those channels are excluded from `channel_data`

### Requirement: No New Backend Routes
This sprint SHALL NOT create new backend routes, blueprints, or services. All backend channel logic is handled by S4-S6.

#### Scenario: Existing route modification only
- **WHEN** the implementation is complete
- **THEN** only the existing `routes/dashboard.py` has been modified (to add `get_channel_data_for_operator()`)
- **AND** no new blueprint files exist in `routes/`

