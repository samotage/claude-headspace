## Why

The Agent Teams Design Workshop (decision 5.1) established a hybrid handoff approach: database for orchestration metadata, filesystem for rich context content. The existing data model has no concept of handoff. Without this table, Sprint 13 (handoff trigger UI) has nowhere to write handoff metadata, and Sprint 14 (handoff execution) has no record to read the injection prompt from.

## What Changes

- New `Handoff` SQLAlchemy model in `src/claude_headspace/models/handoff.py` with fields: id (int PK), agent_id (FK to Agent, not null, CASCADE), reason (str, not null), file_path (str, nullable), injection_prompt (text, nullable), created_at (datetime)
- `Handoff.agent` relationship navigates to the outgoing Agent
- `Agent.handoff` one-to-one relationship (uselist=False) navigates from Agent to its Handoff record
- Model registered in `models/__init__.py`
- Single additive Alembic migration creating the `handoffs` table
- Integration tests verifying model CRUD, relationships, and cascade behaviour

## Impact

- Affected specs: handoff-model (new capability)
- Affected code:
  - ADDED: `src/claude_headspace/models/handoff.py` — new Handoff model
  - MODIFIED: `src/claude_headspace/models/__init__.py` — register Handoff import/export
  - MODIFIED: `src/claude_headspace/models/agent.py` — add `handoff` relationship with back_populates
  - ADDED: `migrations/versions/xxxx_add_handoff_table.py` — Alembic migration
  - ADDED: `tests/integration/test_handoff_model.py` — integration tests
- Affected tests: None modified (all additive)

## Definition of Done

- [ ] Handoff table exists after running migration
- [ ] Handoff record can be created with agent_id, reason, file_path, injection_prompt
- [ ] Handoff.agent navigates to the outgoing Agent
- [ ] Agent.handoff returns the Handoff record (or None)
- [ ] Multiple handoffs can reference different agents
- [ ] Existing tables unaffected by migration
- [ ] Migration is additive (no destructive changes)
- [ ] Model follows SQLAlchemy 2.0+ Mapped conventions
- [ ] All existing tests pass without modification
