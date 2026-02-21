# Delta Spec: Agent Model Extensions

**Change ID:** e8-s4-agent-model-extensions
**Affects:** `agents` table, Agent model, Persona model

## ADDED Requirements

### Requirement: Agent model gains persona_id foreign key

The Agent model SHALL have a `persona_id` column — an integer FK referencing `personas.id`, nullable, ON DELETE CASCADE. `Agent.persona` returns the associated Persona object. No unique constraint — multiple agents can share the same persona.

#### Scenario: Agent created with persona association
- **WHEN** an Agent is created with `persona_id` set to a valid Persona id
- **THEN** `Agent.persona` returns the associated Persona object
- **AND** `Persona.agents` includes this Agent

#### Scenario: Multiple agents share same persona
- **WHEN** two Agents are created both referencing the same `persona_id`
- **THEN** both Agents have `Agent.persona` pointing to the same Persona
- **AND** `Persona.agents` returns both Agents

---

### Requirement: Agent model gains position_id foreign key

The Agent model SHALL have a `position_id` column — an integer FK referencing `positions.id`, nullable, ON DELETE CASCADE. `Agent.position` returns the associated Position object.

#### Scenario: Agent created with position association
- **WHEN** an Agent is created with `position_id` set to a valid Position id
- **THEN** `Agent.position` returns the associated Position object

---

### Requirement: Agent model gains previous_agent_id self-referential foreign key

The Agent model SHALL have a `previous_agent_id` column — an integer FK referencing `agents.id` (self-referential), nullable, ON DELETE CASCADE. `Agent.previous_agent` returns the predecessor Agent. `Agent.successor_agents` returns all Agents that reference this agent as their predecessor.

#### Scenario: Agent linked in continuity chain
- **WHEN** Agent B is created with `previous_agent_id` set to Agent A's id
- **THEN** `Agent_B.previous_agent` returns Agent A
- **AND** `Agent_A.successor_agents` includes Agent B

#### Scenario: First agent in chain has no predecessor
- **WHEN** an Agent is created without `previous_agent_id`
- **THEN** `Agent.previous_agent_id` is NULL
- **AND** `Agent.previous_agent` is None

---

### Requirement: Persona model gains agents backref

The Persona model SHALL have an `agents` relationship returning all Agent records driven by that persona via `persona_id`.

#### Scenario: Persona lists all associated agents
- **WHEN** a Persona has three Agents referencing it via `persona_id`
- **THEN** `Persona.agents` returns a list of all three Agent records

---

### Requirement: Backward compatibility with existing agents

All three new FK columns SHALL be nullable and default to NULL. Existing Agent records, queries, services, and routes MUST continue working unchanged.

#### Scenario: Existing agent unaffected by migration
- **WHEN** the migration is applied to a database with existing Agent records
- **THEN** all existing records have NULL for `persona_id`, `position_id`, and `previous_agent_id`
- **AND** no data is lost or modified

---

### Requirement: Alembic migration for agent extensions

A single additive migration SHALL add three nullable integer columns (`persona_id`, `position_id`, `previous_agent_id`) with FK constraints to the `agents` table. The migration is reversible.

#### Scenario: Migration upgrade
- **WHEN** the migration is applied
- **THEN** three nullable columns with FK constraints (ON DELETE CASCADE) are added to the `agents` table

#### Scenario: Migration downgrade
- **WHEN** the migration is rolled back
- **THEN** the three columns and their FK constraints are removed from the `agents` table
