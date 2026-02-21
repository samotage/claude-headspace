# agent-info-persona-display Specification

## Purpose
Displays persona identity (name, role, status, slug) in the agent info panel, project page agent summaries, and activity page agent references when the agent has an associated persona. Agents without personas retain their existing UUID display.

## ADDED Requirements

### Requirement: Agent info API includes persona identity data

The agent info API response SHALL include persona identity fields (name, role, status, slug) when the agent has an associated persona. When the agent has no persona, these fields SHALL be absent or null. Existing response fields SHALL remain unchanged.

#### Scenario: Agent with persona
- **WHEN** the agent info API is called for an agent with persona_id set
- **THEN** the response includes persona.name, persona.role, persona.status, persona.slug

#### Scenario: Agent without persona
- **WHEN** the agent info API is called for an agent without a persona_id
- **THEN** the response does not include persona fields; existing identity fields (session_uuid, etc.) are unchanged

### Requirement: Agent info panel displays persona section

When the agent has a persona, the agent info panel SHALL render a persona identity section containing: persona name, role name, persona status, and persona slug. This section SHALL appear above the existing technical details (IDENTITY) section. The panel header SHALL display persona name instead of UUID hero.

#### Scenario: Info panel with persona
- **WHEN** the agent info panel is opened for an agent with persona data
- **THEN** a PERSONA section appears above the IDENTITY section showing name, role, status, slug
- **AND** the header displays the persona name instead of UUID hero_chars + hero_trail

#### Scenario: Info panel without persona
- **WHEN** the agent info panel is opened for an agent without persona data
- **THEN** no PERSONA section is rendered; the panel is identical to the current layout

### Requirement: Agent info panel preserves technical details

The agent info panel SHALL continue to display all existing technical details: session UUID, claude_session_id, iterm_pane_id, tmux_pane_id, tmux_session, bridge status, and transcript_path. These fields SHALL NOT be removed, relocated, or hidden when a persona section is present.

#### Scenario: Technical details with persona present
- **WHEN** the agent info panel is opened for an agent with persona data
- **THEN** the IDENTITY section still displays session UUID, claude_session_id, iterm_pane_id, tmux_pane_id, tmux_session, bridge status, and transcript_path unchanged

### Requirement: Project page agent summaries display persona identity

Agent rows in the project page agents accordion SHALL display persona name and role (e.g., "Con — developer") as the primary agent identifier when the agent has a persona. Anonymous agents SHALL display UUID-based hero unchanged.

#### Scenario: Project page with persona agent
- **WHEN** the project page agents list is rendered for an agent with persona data
- **THEN** the agent row displays "Name — role" instead of UUID hero

#### Scenario: Project page with anonymous agent
- **WHEN** the project page agents list is rendered for an agent without persona data
- **THEN** the agent row displays UUID hero_chars + hero_trail (unchanged)

### Requirement: Activity page agent references display persona identity

Agent rows in the activity page's Projects & Agents section SHALL display persona name and role as the primary agent identifier when the agent has a persona. Anonymous agents SHALL display UUID-based hero unchanged.

#### Scenario: Activity page with persona agent
- **WHEN** the activity page agent metrics are rendered for an agent with persona data
- **THEN** the agent row displays "Name — role" instead of UUID hero

#### Scenario: Activity page with anonymous agent
- **WHEN** the activity page agent metrics are rendered for an agent without persona data
- **THEN** the agent row displays UUID hero_chars + hero_trail (unchanged)

### Requirement: Backward compatibility

All existing views for anonymous agents (no persona) SHALL render identically to their current appearance. No visual changes SHALL occur for agents without personas across any of the three views.

#### Scenario: Mixed dashboard with persona and anonymous agents
- **WHEN** the dashboard displays both persona-backed and anonymous agents simultaneously
- **THEN** persona agents show "Name — role" and anonymous agents show UUID hero across all three views (agent info, project page, activity page) with no interference between them
