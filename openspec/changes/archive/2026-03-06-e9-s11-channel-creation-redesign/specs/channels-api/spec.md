## ADDED Requirements

### Requirement: POST /api/channels — Persona-Based Creation Path

The `POST /api/channels` endpoint SHALL accept a `persona_slugs` array and `project_id` to create a channel by spinning up fresh agents from personas, in addition to the existing name-based legacy path.

#### Scenario: Persona-based channel creation — success

- **WHEN** the operator POSTs `{"channel_type": "workshop", "project_id": 1, "persona_slugs": ["robbo", "con"]}` to `POST /api/channels`
- **THEN** the system MUST return HTTP 201 with a channel object in `pending` status
- **AND** the channel name MUST be auto-generated from the persona names joined by " + " (e.g. "Robbo + Con")
- **AND** one ChannelMembership with `agent_id = null` MUST be created per persona slug
- **AND** one fresh agent spin-up MUST be initiated per persona slug under the given project_id
- **AND** a system message "Channel initiating..." (or implementer-chosen variant) MUST be present in the channel
- **AND** the legacy name-based path MUST remain functional when `name` field is present instead of `persona_slugs`

#### Scenario: Missing persona_slugs

- **WHEN** `persona_slugs` is present but empty (`[]`)
- **THEN** the system MUST return HTTP 400 with error code `missing_fields`

#### Scenario: Invalid project_id with persona_slugs

- **WHEN** `persona_slugs` is present but `project_id` is absent or not an integer
- **THEN** the system MUST return HTTP 400 with error code `invalid_field` or `missing_fields`

#### Scenario: project_id references non-existent project

- **WHEN** `project_id` references a project that does not exist
- **THEN** the system MUST return HTTP 404 with error code `project_not_found`

#### Scenario: Persona slug not found

- **WHEN** any slug in `persona_slugs` does not match an active persona
- **THEN** the system MUST return HTTP 404 with error code `persona_not_found`

---

### Requirement: POST /api/channels/<slug>/members — Project ID Support

The `POST /api/channels/<slug>/members` endpoint SHALL accept an optional `project_id` field to support cross-project member addition.

#### Scenario: Add member with explicit project_id

- **WHEN** the operator POSTs `{"persona_slug": "wado", "project_id": 2}` to `POST /api/channels/<slug>/members`
- **THEN** the system MUST create a membership with `agent_id = null`
- **AND** initiate a fresh agent spin-up under `project_id` 2 (not the channel's original project)
- **AND** return HTTP 201 with the membership object

#### Scenario: Add member without project_id — defaults to channel project

- **WHEN** the operator POSTs `{"persona_slug": "wado"}` without `project_id`
- **THEN** the system MUST use the channel's `project_id` as the spin-up target
- **AND** return HTTP 201 with the membership object

#### Scenario: Invalid project_id type

- **WHEN** `project_id` is present but not an integer
- **THEN** the system MUST return HTTP 400 with error code `invalid_field`
