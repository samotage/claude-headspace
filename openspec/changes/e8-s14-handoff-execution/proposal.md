# Proposal: e8-s14-handoff-execution

## Why

When a persona agent's context window fills up, the operator triggers a handoff from the dashboard (S13). Currently, nothing happens after the button click — the execution pipeline doesn't exist yet. This sprint implements the full handoff cycle: instruct outgoing agent to write a handoff document, verify it, record the handoff, shut down the outgoing agent, spin up a successor with the same persona, and deliver handoff context for seamless continuation.

## What Changes

### New Service
- Create `src/claude_headspace/services/handoff_executor.py` — orchestration service for the full handoff cycle
  - Validate preconditions (agent active, has persona, has tmux pane)
  - Generate handoff file path (`data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`)
  - Create handoff directory if needed
  - Compose and send handoff instruction to outgoing agent via tmux bridge
  - Set handoff-in-progress flag on agent
  - After stop hook: verify handoff file exists and is non-empty
  - Create Handoff DB record with injection prompt
  - Shut down outgoing agent
  - Create successor agent with same persona via `create_agent(persona_slug=..., previous_agent_id=...)`
  - After successor registers: wait for skill injection, then send handoff injection prompt

### New Route
- Add `POST /api/agents/<int:agent_id>/handoff` to agents blueprint
  - Accept `{ "reason": "context_limit" }` body
  - Validate preconditions, initiate async handoff, return immediately

### Hook Integration
- Extend `process_stop()` in hook_receiver.py to detect handoff-in-progress flag and trigger handoff continuation (file verification → record creation → successor creation)
- Wire skill injection completion detection for handoff injection prompt sequencing

### Templates for Agent Communication
- Handoff instruction template (sent to outgoing agent)
- Injection prompt template (sent to successor after skill injection)

## Impact

### New Files
- `src/claude_headspace/services/handoff_executor.py` — handoff orchestration service

### Modified Files
- `src/claude_headspace/routes/agents.py` — add handoff endpoint
- `src/claude_headspace/services/hook_receiver.py` — handoff-in-progress detection in stop hook
- `src/claude_headspace/app.py` — register handoff executor service

### Unchanged Files
- `src/claude_headspace/models/handoff.py` — model already exists (S12)
- `src/claude_headspace/models/agent.py` — fields already exist (S4)
- `src/claude_headspace/services/agent_lifecycle.py` — create_agent/shutdown_agent already accept needed params (S7)
- `src/claude_headspace/services/tmux_bridge.py` — send_text already battle-tested
- `src/claude_headspace/services/skill_injector.py` — skill injection already implemented (S9)

### Dependencies
- E8-S12 (Handoff model) — merged
- E8-S13 (Trigger UI) — merged, button POSTs to this sprint's endpoint
- E8-S9 (Skill injection) — merged, successor priming
- E8-S7 (Persona-aware agent creation) — merged, `create_agent(persona_slug=..., previous_agent_id=...)`
- E8-S8 (SessionCorrelator persona) — merged, persona assignment at registration

### Recent OpenSpec History
- e8-s13-handoff-trigger-ui — Handoff trigger button (just completed)
- e8-s12-handoff-model — Handoff database model
- e8-s9-skill-file-injection — Skill injection for persona priming
- e8-s7-persona-aware-agent-creation — create_agent with persona_slug

## Definition of Done

1. `POST /api/agents/<id>/handoff` endpoint validates preconditions and initiates async handoff flow
2. Outgoing agent receives handoff instruction via tmux bridge with correct file path
3. Handoff file path follows convention: `data/personas/{slug}/handoffs/{iso-datetime}-{agent-8digit}.md`
4. After stop hook fires, handoff file existence is verified (non-empty)
5. Hard error raised and reported to operator if file missing or empty
6. Handoff DB record created with agent_id, reason, file_path, injection_prompt
7. Outgoing agent session ends gracefully
8. Successor agent created with same persona and previous_agent_id set
9. Successor receives skill injection before handoff injection prompt
10. Successor receives injection prompt referencing predecessor and handoff file path
11. Full cycle completes without manual intervention after initial trigger
12. All errors surfaced to operator — no silent failures
