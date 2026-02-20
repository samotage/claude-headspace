## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [ ] 2.1 Create `src/claude_headspace/models/position.py` — Position model with id, org_id (FK→Organisation), role_id (FK→Role), title (not null), reports_to_id (self-ref FK, nullable), escalates_to_id (self-ref FK, nullable), level (default 0), is_cross_cutting (default False), created_at; relationships: role, organisation, reports_to, escalates_to, direct_reports
- [ ] 2.2 Add `positions` relationship to `src/claude_headspace/models/organisation.py` — back_populates with Position.organisation
- [ ] 2.3 Add `positions` relationship to `src/claude_headspace/models/role.py` — back_populates with Position.role
- [ ] 2.4 Register Position model in `src/claude_headspace/models/__init__.py` — add import and __all__ entry
- [ ] 2.5 Generate Alembic migration — create Position table with FKs to Organisation, Role, and two self-referential FKs (all ON DELETE CASCADE); reversible downgrade drops table

## 3. Testing (Phase 3)

- [ ] 3.1 Test Position model — create record with org_id, role_id, title; verify field defaults (level=0, is_cross_cutting=False)
- [ ] 3.2 Test self-referential reporting hierarchy — create parent/child positions, verify reports_to and direct_reports relationships
- [ ] 3.3 Test self-referential escalation path — create positions with different reports_to and escalates_to targets, verify both relationships
- [ ] 3.4 Test Position.role and Position.organisation relationships — verify FK references resolve correctly
- [ ] 3.5 Test Organisation.positions and Role.positions backref relationships
- [ ] 3.6 Test constraints — title not-null, org_id not-null, role_id not-null
- [ ] 3.7 Test top-level positions — reports_to_id=NULL, escalates_to_id=NULL
- [ ] 3.8 Test migration reversibility — upgrade creates table, downgrade drops cleanly

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Migration reversible (upgrade + downgrade)
- [ ] 4.4 Existing tests still pass (no regressions)
