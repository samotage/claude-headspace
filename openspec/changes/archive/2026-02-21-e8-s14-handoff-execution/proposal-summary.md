# Proposal Summary: e8-s14-handoff-execution

## Architecture Decisions
- Single orchestration service (`HandoffExecutor`) manages the entire handoff lifecycle as a multi-step async flow
- Agent-as-author pattern: outgoing agent writes its own handoff document (not the server), ensuring context fidelity
- In-memory handoff-in-progress flag (not DB column) — lightweight, only needs to survive the handoff duration
- Stop hook as continuation trigger: the outgoing agent's stop event drives the handoff pipeline forward
- Two-phase successor bootstrap: skill injection first (existing S9 mechanism), then handoff injection prompt

## Implementation Approach
- Create `HandoffExecutor` service class registered in `app.extensions["handoff_executor"]`
- The trigger endpoint validates preconditions synchronously, then initiates the async flow and returns 200 immediately
- Handoff instruction sent via `tmux_bridge.send_text()` telling the agent to write a handoff document to a deterministic file path
- When the agent stops (stop hook fires), `hook_receiver.process_stop()` checks the handoff-in-progress flag and delegates to `HandoffExecutor` for continuation
- Continuation: verify file → create Handoff DB record → shutdown outgoing → create successor → wait for skill injection → send injection prompt
- Error surfacing via SSE broadcasts and OS notifications at every failure point

## Files to Modify

### New Files
- `src/claude_headspace/services/handoff_executor.py` — orchestration service (HandoffExecutor class)

### Modified Files
- `src/claude_headspace/routes/agents.py` — add `POST /api/agents/<int:agent_id>/handoff` endpoint
- `src/claude_headspace/services/hook_receiver.py` — detect handoff-in-progress flag in `process_stop()`, trigger continuation
- `src/claude_headspace/app.py` — register HandoffExecutor service in extensions

### Unchanged (Already Implemented)
- `src/claude_headspace/models/handoff.py` — Handoff model (S12)
- `src/claude_headspace/models/agent.py` — persona_id, previous_agent_id fields (S4/S7)
- `src/claude_headspace/services/agent_lifecycle.py` — create_agent(persona_slug, previous_agent_id), shutdown_agent()
- `src/claude_headspace/services/tmux_bridge.py` — send_text() for tmux communication
- `src/claude_headspace/services/skill_injector.py` — skill injection for persona priming (S9)

## Acceptance Criteria
1. `POST /api/agents/<id>/handoff` validates preconditions and initiates async handoff
2. Outgoing agent receives handoff instruction via tmux with correct file path
3. File path follows `data/personas/{slug}/handoffs/{YYYYMMDDTHHmmss}-{agent-8digit}.md`
4. Stop hook verifies handoff file exists and is non-empty
5. Hard error raised on missing/empty file
6. Handoff DB record created with agent_id, reason, file_path, injection_prompt
7. Outgoing agent shuts down gracefully
8. Successor created with same persona and previous_agent_id set
9. Successor receives skill injection before handoff injection prompt
10. Successor receives injection prompt referencing predecessor and file path
11. Full cycle completes without manual intervention
12. All errors surfaced to operator

## Constraints and Gotchas
- The handoff instruction must be sent via tmux bridge — the outgoing agent receives it as if it were user input
- Handoff file verification happens in the stop hook — timing depends on the agent actually stopping after writing
- If the agent crashes without writing the file, the stop hook must detect this and report failure
- Successor creation depends on `create_agent()` which spawns a real Claude Code process — this is an external dependency
- Skill injection completion must be detected before sending the handoff injection prompt (sequencing matters)
- The 409 Conflict case: if a Handoff DB record already exists for the agent, reject the trigger to prevent double-handoffs
- Directory creation (`data/personas/{slug}/handoffs/`) must happen before sending the instruction

## Git Change History

### Related Files
- Services: agent_lifecycle.py, hook_receiver.py, tmux_bridge.py, skill_injector.py, card_state.py
- Models: handoff.py, agent.py, persona.py
- Routes: agents.py
- Frontend: agent-lifecycle.js (handoff button handler already implemented in S13)

### OpenSpec History
- e8-s13-handoff-trigger-ui — Handoff trigger button and context monitoring (just merged)
- e8-s12-handoff-model — Handoff database model with migration
- e8-s9-skill-file-injection — Skill injection for persona priming
- e8-s8-session-correlator-persona — Persona assignment at registration
- e8-s7-persona-aware-agent-creation — create_agent with persona_slug parameter

### Implementation Patterns
- Service class pattern: class with `__init__(self, app)`, registered in `app.extensions`
- Route pattern: blueprint functions calling service methods, returning JSON responses
- Hook integration: extend existing `process_stop()` with conditional logic
- Tmux communication: `tmux_bridge.send_text(pane_id, message)` for agent interaction

## Q&A History
- No clarifications needed — PRD was sufficiently detailed and all dependencies are already merged

## Dependencies
- No new packages needed
- All infrastructure (models, services, tmux bridge) already exists from prior sprints
- Database: Handoff model and migration already exist (S12)

## Testing Strategy
- Unit tests for HandoffExecutor: precondition validation, file path generation, instruction composition, file verification, DB record creation, injection prompt composition
- Route tests for the handoff endpoint: validation errors (no persona, no tmux, already ended, already has handoff), success case
- Regression tests: run existing agent_lifecycle and hook_receiver tests to ensure no breakage
- Mock external dependencies: tmux_bridge, agent_lifecycle (create_agent, shutdown_agent), skill_injector

## OpenSpec References
- proposal.md: openspec/changes/e8-s14-handoff-execution/proposal.md
- tasks.md: openspec/changes/e8-s14-handoff-execution/tasks.md
- spec.md: openspec/changes/e8-s14-handoff-execution/specs/handoff-execution/spec.md
