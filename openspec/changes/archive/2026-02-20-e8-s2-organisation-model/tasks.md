## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [x] 2.1 Create `src/claude_headspace/models/organisation.py` — Organisation model with id, name (not null), description (nullable), status (default "active", supports active/dormant/archived), created_at
- [x] 2.2 Register Organisation model in `src/claude_headspace/models/__init__.py` — add import and __all__ entry
- [x] 2.3 Generate Alembic migration — create Organisation table with seed data (name="Development", status="active"); reversible downgrade deletes seed then drops table

## 3. Testing (Phase 3)

- [x] 3.1 Test Organisation model — create record with name, description, status; verify field defaults
- [x] 3.2 Test status field — defaults to "active", accepts "dormant" and "archived"
- [x] 3.3 Test seed data — verify "Development" org exists after migration
- [x] 3.4 Test constraints — name not-null, status not-null
- [x] 3.5 Test migration reversibility — upgrade creates table with seed, downgrade drops cleanly

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Migration reversible (upgrade + downgrade)
- [x] 4.4 Existing tests still pass (no regressions)
