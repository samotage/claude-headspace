# Proposal Summary: E8-S18 Agent Revival ("Seance")

## Architecture Decisions

1. **CLI transcript as a Flask CLI command (Click)** — The transcript extraction command runs within Flask app context using Click (Flask's built-in CLI framework), giving it direct database access. This follows the existing pattern in `persona_cli.py`. The command is `claude-headspace transcript <agent-id>`.

2. **Revival service as a thin orchestration layer** — A new `revival_service.py` coordinates the flow: validate dead agent -> call `create_agent()` with `previous_agent_id` -> return result. The actual agent creation reuses the existing `agent_lifecycle.create_agent()` function, which already supports `previous_agent_id` and `persona_slug`.

3. **Revival injection via hook_receiver at session_start** — When the successor agent fires its session_start hook, `hook_receiver.process_session_start()` detects that `previous_agent_id` is set and no Handoff record exists for the predecessor. This distinguishes revival from handoff. The revival instruction is injected via `tmux_bridge.send_text()` after skill injection (persona agents) or immediately (anonymous agents).

4. **Reuse of `previous_agent_id` field** — Both handoff (E8-S14) and revival use the same `previous_agent_id` column on the Agent model. Disambiguation is based on whether the predecessor has a Handoff record (handoff flow) or not (revival flow). No schema changes needed.

5. **No DB schema changes** — All required columns already exist: `previous_agent_id`, `persona_id`, `ended_at`, `project_id`, `tmux_pane_id`. No migrations needed.

## Implementation Approach

The implementation is a wiring job connecting existing infrastructure:

1. **CLI layer** — Add a `transcript` subcommand to the existing argparse parser, or better, register a Flask CLI command via Click (since it needs app context). Query `Agent -> Commands -> Turns` and format as markdown.

2. **Service layer** — Create `revival_service.py` with a `revive_agent()` function that validates preconditions and delegates to `create_agent()`.

3. **Route layer** — Add a `POST /api/agents/<id>/revive` endpoint to `routes/agents.py` that calls the revival service.

4. **Hook integration** — Extend `process_session_start()` in `hook_receiver.py` to detect revival-pending successors and inject the revival instruction. This goes in the same block that handles handoff injection (lines ~685-710), with a new branch for revival.

5. **Frontend** — Add a "Revive" button to dead agent cards in the dashboard template, with a JS click handler that calls the API endpoint.

## Files to Modify (organized by type)

### New Files
- `src/claude_headspace/services/revival_service.py` — Revival orchestration service
- `tests/services/test_revival_service.py` — Revival service unit tests
- `tests/cli/test_transcript_cli.py` — Transcript CLI command tests

### Modified Service Files
- `src/claude_headspace/services/hook_receiver.py` — Add revival injection logic in `process_session_start()`

### Modified Route Files
- `src/claude_headspace/routes/agents.py` — Add `POST /api/agents/<id>/revive` endpoint

### Modified CLI Files
- `src/claude_headspace/cli/__init__.py` — Register transcript CLI command
- `src/claude_headspace/cli/launcher.py` — Add transcript subcommand (or new file `transcript_cli.py` if using Flask Click)

### Modified Template/Static Files
- `templates/partials/` — Add revive button to agent card partial
- `static/js/` — Add revive button click handler

### Modified Test Files
- `tests/routes/test_agents.py` — Add revive endpoint tests

## Acceptance Criteria

1. `claude-headspace transcript <agent-id>` outputs the agent's full conversation history as structured markdown (FR1, FR2)
2. `POST /api/agents/<id>/revive` creates a successor agent with matching project and persona config (FR3, FR4)
3. The successor agent receives a revival instruction via tmux bridge at session_start (FR5, FR6)
4. Dead agent cards in the dashboard display a "Revive" button (FR7)
5. Revival works for both persona-based and anonymous agents (FR6, FR7)
6. The `previous_agent_id` chain links successor to predecessor (FR4)
7. Transcript command handles missing agent, no commands, and no turns gracefully (NFR2)

## Constraints and Gotchas

1. **CLI context requirement** — The transcript command needs Flask app context for database access. Using a Flask Click command (like `persona_cli.py`) is the correct approach. Running it as a bare argparse command without app context will fail.

2. **Revival vs handoff disambiguation** — Both flows set `previous_agent_id`. The distinction is: handoff creates a Handoff record on the predecessor; revival does not. The hook_receiver must check for absence of a Handoff record to trigger revival injection instead of handoff injection.

3. **Injection timing** — Revival injection must happen AFTER skill injection for persona agents. The existing code in `process_session_start()` already handles this ordering (skill injection at line ~670, handoff injection at line ~685). Revival injection should go in the same block or immediately after the handoff check.

4. **Idempotency** — The revival instruction should only be injected once. Consider using the existing `prompt_injected_at` mechanism or a similar flag. However, since revival creates a brand new agent with a fresh `prompt_injected_at=None`, and skill injection sets it, we may need a separate flag or simply rely on the fact that `process_session_start` only fires once per agent.

5. **Large transcripts** — Agents with hundreds of turns will produce large markdown output. The v1 approach is "give me everything" (no filtering), which is acceptable per the PRD out-of-scope decisions. The LLM context window of the successor agent is the natural limit.

6. **Dead agent validation** — The revive endpoint must verify `ended_at IS NOT NULL` before proceeding. Attempting to revive a live agent should return 400.

## Git Change History

### Related Files (from git_context)
- **Modules:** Agent model migrations (tmux_session, transcript_path, ended_at, claude_session_id, context columns, priority fields, prompt_injected_at)
- **Routes:** `routes/agents.py`
- **Tests:** `test_agents.py`, `test_agents_persona.py`, `test_voice_bridge_agents.py`

### Recent Relevant Commits
- `762a4931` — Added the E8-S18 agent revival PRD
- `0b75617f` — Orphan cleanup safety guards for agent lifecycle
- `37f2cabb` — DB-level `prompt_injected_at` for skill injection idempotency
- `b3e52b7c` — Agent creation with persona end-to-end
- `64bcbebb` — CASCADE->SET NULL on nullable FKs, CLI count subquery, skill write error handling

### OpenSpec History
- No prior OpenSpec changes for the agents subsystem

### Patterns Detected
- Has modules (migrations), tests — standard structure
- No main modules, templates, static, bin, or config in the agents subsystem specifically (those are project-wide)

## Q&A History

No clarification was needed. The PRD is well-specified with clear requirements and explicit out-of-scope boundaries.

## Dependencies

- **No new packages** — Uses existing Flask, Click, SQLAlchemy, tmux_bridge
- **No new APIs** — Reuses existing create_agent(), tmux_bridge.send_text()
- **No migrations** — All required columns already exist on the Agent model

## Testing Strategy

### Unit Tests (services/)
- `test_revival_service.py` — Test precondition validation (agent not found, agent alive, agent dead), successor creation with correct project/persona/previous_agent_id
- `test_transcript_cli.py` — Test markdown formatting, chronological ordering, empty/null text filtering, edge cases (no commands, no turns, agent not found)

### Route Tests (routes/)
- `test_agents.py` — Test revive endpoint: 201 on success, 404 on not found, 400 on still alive

### Integration Tests
- Full revival flow: create agent, end it, revive it, verify successor has correct attributes

### Manual Verification
- Trigger revival from dashboard, verify new agent appears, verify revival instruction is injected via tmux

## OpenSpec References

- **Proposal:** `openspec/changes/e8-s18-agent-revival/proposal.md`
- **Tasks:** `openspec/changes/e8-s18-agent-revival/tasks.md`
- **Spec:** `openspec/changes/e8-s18-agent-revival/specs/agent-revival/spec.md`
- **PRD:** `docs/prds/agents/e8-s18-agent-revival-prd.md`
