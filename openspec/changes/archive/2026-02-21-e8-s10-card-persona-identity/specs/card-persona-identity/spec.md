# card-persona-identity Specification

## Purpose
Displays persona identity (name + role suffix) on dashboard agent cards when the agent has an associated persona, replacing the UUID-based hero text. Agents without personas retain their existing UUID display.

## ADDED Requirements

### Requirement: Card state includes persona identity data

When building card state for an agent with an associated persona, the card state dict SHALL include `persona_name` (the persona's name) and `persona_role` (the persona's role name). When the agent has no persona, these fields SHALL be absent or null.

#### Scenario: Agent with persona
- **WHEN** card state is computed for an agent with persona_id set and persona relationship loaded
- **THEN** the card state dict includes `persona_name` (e.g., "Con") and `persona_role` (e.g., "developer")

#### Scenario: Agent without persona
- **WHEN** card state is computed for an agent without a persona_id
- **THEN** the card state dict does not include `persona_name` or `persona_role`; `hero_chars` and `hero_trail` are still present

### Requirement: SSE card_refresh includes persona identity

The `card_refresh` SSE event payload SHALL include `persona_name` and `persona_role` fields when the agent has a persona. Existing payload fields SHALL remain unchanged.

#### Scenario: SSE event for persona agent
- **WHEN** a card_refresh SSE event is broadcast for an agent with a persona
- **THEN** the event data includes `persona_name` and `persona_role` alongside existing fields

### Requirement: Card hero displays persona name and role

When the agent has a persona, the card hero section SHALL display the persona name as the primary text and the role as a suffix separated by an em dash (e.g., "Con — developer"). The hero section SHALL remain clickable.

#### Scenario: Persona hero display
- **WHEN** a card is rendered for an agent with persona_name "Con" and persona_role "developer"
- **THEN** the hero section displays "Con — developer" instead of UUID hero_chars + hero_trail

#### Scenario: UUID fallback
- **WHEN** a card is rendered for an agent without persona data
- **THEN** the hero section displays the existing UUID-based hero (hero_chars + hero_trail)

### Requirement: Kanban and condensed cards display persona identity

Kanban command cards and condensed completed-command cards SHALL display persona name and role when persona data is available in the SSE event data.

#### Scenario: Kanban card with persona
- **WHEN** a Kanban command card is built for an agent with persona data
- **THEN** the card displays persona name + role instead of UUID hero

#### Scenario: Condensed card with persona
- **WHEN** a condensed completed-command card is built from SSE data containing persona fields
- **THEN** the card displays persona name + role instead of UUID hero

### Requirement: Backward compatibility

All existing agent cards (anonymous, no persona) SHALL render identically to their current appearance. No visual changes SHALL occur for agents without personas.

#### Scenario: Mixed dashboard
- **WHEN** the dashboard displays both persona-backed and anonymous agents simultaneously
- **THEN** persona agents show "Name — role" and anonymous agents show UUID hero, with no interference between them
