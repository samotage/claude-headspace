## ADDED Requirements

### Requirement: Voice App Channel Creation Bottom Sheet — Redesigned

The voice app `#channel-picker` bottom sheet SHALL be redesigned to show a project picker + channel type selector + persona multi-checkbox, replacing the V0 name/type/existing-agents form.

#### Scenario: Bottom sheet opens (create mode)

- **WHEN** the operator taps "+" next to Channels in the sidebar
- **THEN** the `#channel-picker` bottom sheet MUST open with:
  - A project `<select>` populated from `GET /api/projects`
  - A channel type `<select>` (workshop, delegation, review, standup, broadcast) — retained from V0
  - An empty persona list `#channel-persona-list`
  - A CTA button showing "Create Channel (0 selected)"
- **AND** the old name text input MUST NOT be present

#### Scenario: Project selected — persona list populates

- **WHEN** the operator selects a project from the project picker
- **THEN** the persona list MUST populate with active personas from `GET /api/personas/active`
- **AND** each persona MUST be shown as a checkbox with persona name and role label

#### Scenario: Persona checkbox changes — CTA count updates

- **WHEN** the operator checks or unchecks personas
- **THEN** the CTA button text MUST update to reflect selected count (e.g. "Create Channel (3 selected)")

#### Scenario: Submit — persona-based channel creation

- **WHEN** the operator selects a project, at least one persona, and a type, then taps the CTA
- **THEN** `POST /api/channels` MUST be called with `{project_id, channel_type, persona_slugs: [...]}`
- **AND** the bottom sheet MUST close on success
- **AND** the channel name MUST be auto-generated server-side (no client-side name construction required)

#### Scenario: Submit with no personas selected

- **WHEN** the operator taps CTA without selecting any personas
- **THEN** the submission MUST be blocked (CTA disabled or validation error shown)

---

### Requirement: Voice App Add Member — Stub Replaced

The voice app "Add member" action in the channel kebab menu SHALL be wired to the channel picker in single-select add-member mode, replacing the stub message.

#### Scenario: Add member tapped (voice app)

- **WHEN** the operator taps "Add member" in the channel chat kebab menu
- **THEN** the `#channel-picker` bottom sheet MUST open in add-member mode:
  - Project picker present (may select different project from channel's project)
  - Persona list shows as single-select (radio buttons, not checkboxes)
  - CTA reads "Add to Channel"
- **AND** the stub message "Member picker not yet available in voice app..." MUST NOT appear

#### Scenario: Add member submitted

- **WHEN** the operator selects a project and persona and taps "Add to Channel"
- **THEN** `POST /api/channels/<slug>/members` MUST be called with `{persona_slug, project_id}`
- **AND** the bottom sheet MUST close on success

---

### Requirement: VoiceAPI.createChannel Signature Update

The `VoiceAPI.createChannel` function SHALL accept `(projectId, channelType, personaSlugs)` instead of `(name, channelType, memberAgentIds)`.

#### Scenario: createChannel call

- **WHEN** `VoiceAPI.createChannel(projectId, channelType, personaSlugs)` is called
- **THEN** `POST /api/channels` MUST receive body `{project_id, channel_type, persona_slugs}`
- **AND** `member_agents` field MUST NOT be sent

---

### Requirement: VoiceAPI.addChannelMember — New Function

A new `VoiceAPI.addChannelMember(slug, personaSlug, projectId)` function SHALL be available.

#### Scenario: addChannelMember call

- **WHEN** `VoiceAPI.addChannelMember(slug, personaSlug, projectId)` is called
- **THEN** `POST /api/channels/<slug>/members` MUST receive body `{persona_slug, project_id}`
