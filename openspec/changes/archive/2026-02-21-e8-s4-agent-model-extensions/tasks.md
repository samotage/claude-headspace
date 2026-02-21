# Tasks: e8-s4-agent-model-extensions

## Phase 1: Preparation
- [x] 1.1 Read PRD and understand requirements (3 nullable FKs, relationships, migration)
- [x] 1.2 Read existing Agent model (`agent.py`) for current structure
- [x] 1.3 Read Persona model (`persona.py`) for backref integration point
- [x] 1.4 Read Position model (`position.py`) for self-referential FK pattern reference
- [x] 1.5 Identify migration chain dependency (`a3b8c1d2e4f5` Position table)

## Phase 2: Implementation

### Task 2.1: Extend Agent model with FK columns and relationships
**File:** `src/claude_headspace/models/agent.py`
- [x] Add `persona_id` — `Mapped[int | None]`, FK to `personas.id`, ON DELETE CASCADE, nullable
- [x] Add `position_id` — `Mapped[int | None]`, FK to `positions.id`, ON DELETE CASCADE, nullable
- [x] Add `previous_agent_id` — `Mapped[int | None]`, FK to `agents.id` (self-ref), ON DELETE CASCADE, nullable
- [x] Add `persona` relationship — `Mapped["Persona | None"]`, `back_populates="agents"`
- [x] Add `position` relationship — `Mapped["Position | None"]` (no backref needed)
- [x] Add `previous_agent` relationship — `Mapped["Agent | None"]`, self-referential, `remote_side=[id]`, `foreign_keys=[previous_agent_id]`, `back_populates="successor_agents"`
- [x] Add `successor_agents` relationship — `Mapped[list["Agent"]]`, `foreign_keys=[previous_agent_id]`, `back_populates="previous_agent"`
- [x] Add Persona and Position to TYPE_CHECKING imports

### Task 2.2: Add agents backref to Persona model
**File:** `src/claude_headspace/models/persona.py`
- [x] Add `agents` relationship — `Mapped[list["Agent"]]`, `back_populates="persona"`
- [x] Add Agent to TYPE_CHECKING imports

### Task 2.3: Create Alembic migration
**File:** `migrations/versions/b5c9d3e6f7a8_add_agent_persona_position_predecessor.py`
- [x] Depends on `a3b8c1d2e4f5` (Position table migration)
- [x] `upgrade()`: Add three nullable integer columns to `agents` table with FK constraints (all ON DELETE CASCADE)
- [x] `downgrade()`: Remove three columns (drop FK constraints first, then columns)
- [x] No data transformation — all columns default to NULL

### Task 2.4: Write integration tests
**File:** `tests/integration/test_agent_model_extensions.py`
- [x] Test Agent creation with `persona_id` set → `Agent.persona` navigates to Persona
- [x] Test Agent creation with `position_id` set → `Agent.position` navigates to Position
- [x] Test Agent creation with `previous_agent_id` set → `Agent.previous_agent` navigates to predecessor
- [x] Test `Agent.successor_agents` returns agents referencing this agent as predecessor
- [x] Test `Persona.agents` backref returns all agents with that persona_id
- [x] Test multiple agents can share same `persona_id` (no uniqueness constraint)
- [x] Test Agent with all three new fields NULL (backward compatibility)
- [x] Test first agent in chain has `previous_agent_id = NULL`
- [x] Test continuity chain (A → B → C via previous_agent_id)
- [x] Test FK integrity — setting persona_id to non-existent persona raises IntegrityError

## Phase 3: Testing
- [ ] 3.1 Run integration tests for Agent model extensions
- [ ] 3.2 Run existing Agent-related tests to verify no regressions

## Phase 4: Verification
- [ ] 4.1 Verify Agent model has all three FK columns and four relationships
- [ ] 4.2 Verify Persona model has `agents` backref
- [ ] 4.3 Verify migration is reversible
- [ ] 4.4 Verify existing tests pass unchanged
