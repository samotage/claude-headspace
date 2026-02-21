## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [ ] 2.1 Create `src/claude_headspace/models/handoff.py` — Handoff model with id, agent_id (FK), reason, file_path, injection_prompt, created_at fields and agent relationship
- [ ] 2.2 Modify `src/claude_headspace/models/agent.py` — add `handoff` relationship with back_populates="agent" and uselist=False
- [ ] 2.3 Modify `src/claude_headspace/models/__init__.py` — register Handoff import and add to __all__
- [ ] 2.4 Create Alembic migration for handoffs table — additive migration with all columns and foreign key
- [ ] 2.5 Apply migration and verify server health

## 3. Testing (Phase 3)

- [ ] 3.1 Create integration test — verify Handoff record creation with all fields
- [ ] 3.2 Create integration test — verify Handoff.agent relationship navigates to Agent
- [ ] 3.3 Create integration test — verify Agent.handoff returns Handoff record or None
- [ ] 3.4 Create integration test — verify cascade delete (agent deletion removes handoff)
- [ ] 3.5 Regression — existing model and route tests still pass

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
