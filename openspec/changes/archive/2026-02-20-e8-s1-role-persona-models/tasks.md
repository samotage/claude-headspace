## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [x] 2.1 Create `src/claude_headspace/models/role.py` — Role model with id, name (unique), description, created_at fields using Mapped/mapped_column patterns
- [x] 2.2 Create `src/claude_headspace/models/persona.py` — Persona model with id, slug (unique), name, description, status, role_id FK, created_at fields; slug generation method; bidirectional relationship with Role
- [x] 2.3 Register both models in `src/claude_headspace/models/__init__.py` — add imports and __all__ entries
- [x] 2.4 Generate Alembic migration — single migration creating Role table first, then Persona table with FK; reversible downgrade drops Persona first then Role

## 3. Testing (Phase 3)

- [x] 3.1 Test Role model — create record with unique name, verify fields and defaults
- [x] 3.2 Test Persona model — create record with role FK, verify slug generation format `{role}-{name}-{id}`
- [x] 3.3 Test slug uniqueness — duplicate persona names with same role produce different slugs via id
- [x] 3.4 Test bidirectional relationships — Role.personas returns list, Persona.role returns Role object
- [x] 3.5 Test status field — defaults to "active", accepts "archived"
- [x] 3.6 Test migration — upgrade creates both tables, downgrade drops both, existing tables unaffected
- [x] 3.7 Test constraints — Role.name unique constraint, Persona.slug unique constraint, Persona.role_id not-null

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Migration reversible (upgrade + downgrade)
- [ ] 4.4 Existing tests still pass (no regressions)
