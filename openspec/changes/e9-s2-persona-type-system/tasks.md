## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Model Layer

- [ ] 2.1 Create `PersonaType` model (`src/claude_headspace/models/persona_type.py`)
  - `persona_types` table: `id` (PK), `type_key` (String(16), NOT NULL), `subtype` (String(16), NOT NULL)
  - `UniqueConstraint("type_key", "subtype")` named `uq_persona_type_key_subtype`
  - `personas` relationship (back_populates="persona_type")
  - `__repr__` method

- [ ] 2.2 Modify `Persona` model (`src/claude_headspace/models/persona.py`)
  - Add `persona_type_id` FK column (NOT NULL, default=1, ondelete RESTRICT)
  - Add `persona_type` relationship (back_populates="personas")
  - Add `PersonaType` to `TYPE_CHECKING` imports
  - Add `can_create_channel` property (True for internal subtypes, False for external)
  - Add `get_operator()` classmethod (query person/internal PersonaType)

- [ ] 2.3 Register `PersonaType` in `models/__init__.py`
  - Add import
  - Add to `__all__`
  - Update module docstring

### Migration

- [ ] 2.4 Create Alembic migration (`migrations/versions/{rev}_add_persona_type_system.py`)
  - Step 1: Create `persona_types` table
  - Step 2: Seed 4 rows with explicit IDs (agent/internal=1, agent/external=2, person/internal=3, person/external=4)
  - Step 3: Add `persona_type_id` column as NULLABLE with FK
  - Step 4: Backfill all existing personas to `persona_type_id = 1`
  - Step 5: Alter column to NOT NULL
  - Step 6: Create "operator" Role (idempotent)
  - Step 7: Create "Sam" operator Persona with persona_type=3 (idempotent)
  - Step 8: Fix operator slug from `_pending_operator` to `operator-sam-{id}`
  - Downgrade: drop FK constraint, drop column, drop table (preserve operator Role/Persona)

## 3. Testing (Phase 3)

- [ ] 3.1 Test PersonaType model creation and constraints
  - Verify 4-row seed data
  - Verify unique constraint on (type_key, subtype) prevents duplicates

- [ ] 3.2 Test Persona FK and backfill
  - Verify all existing personas have persona_type_id = 1 (agent/internal)
  - Verify new personas default to persona_type_id = 1

- [ ] 3.3 Test `can_create_channel` property
  - person/internal returns True
  - agent/internal returns True
  - agent/external returns False
  - person/external returns False
  - No persona_type loaded returns False

- [ ] 3.4 Test `Persona.get_operator()` classmethod
  - Returns Sam persona with person/internal type
  - Returns None when no operator exists

- [ ] 3.5 Test relationship wiring
  - `persona.persona_type` loads PersonaType
  - `persona_type.personas` loads associated Persona records

- [ ] 3.6 Test operator Persona creation
  - Verify name="Sam", role="operator", persona_type=person/internal, status="active"
  - Verify slug format `operator-sam-{id}`

- [ ] 3.7 Test existing persona flows are not broken
  - PersonaRegistration continues to create agent/internal personas by default
  - All existing persona-related tests pass

- [ ] 3.8 Test migration reversibility
  - Downgrade removes persona_type_id column and persona_types table
  - Operator Role and Persona are preserved on downgrade

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Migration runs cleanly (upgrade + downgrade + upgrade)
- [ ] 4.4 PersonaType importable from `claude_headspace.models`
