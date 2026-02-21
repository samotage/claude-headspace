# Tasks: e8-s14-handoff-execution

## Phase 1: Preparation

- [x] 1.1 Read existing services: agent_lifecycle.py, hook_receiver.py, tmux_bridge.py, skill_injector.py, app.py
- [x] 1.2 Read existing models: handoff.py, agent.py, persona.py
- [x] 1.3 Read existing routes: agents.py (to understand endpoint patterns)
- [x] 1.4 Read proposal.md and spec.md for full requirements

## Phase 2: Implementation

- [ ] 2.1 Create handoff_executor.py service with HandoffExecutor class
- [ ] 2.2 Implement precondition validation (agent active, has persona, has tmux pane, no existing handoff)
- [ ] 2.3 Implement handoff file path generation (`data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`)
- [ ] 2.4 Implement handoff instruction composition (template for outgoing agent)
- [ ] 2.5 Implement handoff instruction delivery via tmux bridge
- [ ] 2.6 Implement handoff-in-progress flag on agent (in-memory tracking)
- [ ] 2.7 Implement stop hook integration: detect handoff-in-progress and trigger continuation
- [ ] 2.8 Implement handoff file verification (exists, non-empty)
- [ ] 2.9 Implement error reporting to operator on verification failure
- [ ] 2.10 Implement Handoff DB record creation with injection prompt
- [ ] 2.11 Implement outgoing agent graceful shutdown
- [ ] 2.12 Implement successor agent creation with same persona and previous_agent_id
- [ ] 2.13 Implement injection prompt composition (template for successor)
- [ ] 2.14 Implement sequenced delivery: wait for skill injection, then send injection prompt
- [ ] 2.15 Add `POST /api/agents/<id>/handoff` endpoint to agents blueprint
- [ ] 2.16 Register HandoffExecutor service in app.py

## Phase 3: Testing

- [ ] 3.1 Unit tests for precondition validation (agent exists, active, has persona, has tmux)
- [ ] 3.2 Unit tests for handoff file path generation
- [ ] 3.3 Unit tests for handoff instruction composition
- [ ] 3.4 Unit tests for handoff file verification (exists/missing/empty)
- [ ] 3.5 Unit tests for Handoff DB record creation
- [ ] 3.6 Unit tests for injection prompt composition
- [ ] 3.7 Route tests for handoff endpoint (validation, success, error cases)
- [ ] 3.8 Run existing agent lifecycle and hook receiver tests for regressions

## Phase 4: Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 Manual verification: endpoint returns correct validation errors
- [ ] 4.3 Final review of changes against Definition of Done
