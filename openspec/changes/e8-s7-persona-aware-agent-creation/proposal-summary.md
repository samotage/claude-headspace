# Proposal Summary: e8-s7-persona-aware-agent-creation

## Architecture Decisions
- Persona slug propagated via environment variables (`CLAUDE_HEADSPACE_PERSONA_SLUG`, `CLAUDE_HEADSPACE_PREVIOUS_AGENT_ID`) — no changes to Claude Code itself needed
- Two creation paths converge to same pipeline: `create_agent()` for programmatic use, `claude-headspace start --persona` for operator ad-hoc sessions (workshop decision 4.1)
- S7 only carries the slug through to the hook pipeline — S8 (SessionCorrelator) will act on it to set `agent.persona_id`
- Validation is fail-fast: invalid slugs return errors before any session is launched
- Persona validation requires Flask app context for DB access — CLI validates via API call or direct DB query

## Implementation Approach
- Extend `create_agent()` with optional params + Persona table validation before tmux launch
- Extend CLI argparse with `--persona <slug>` flag + validation before session launch
- Set env vars in `setup_environment()` for hook script inheritance
- Extend `notify-headspace.sh` jq payload construction with persona_slug and previous_agent_id env vars
- Extract fields from session-start payload in hooks route and pass through to `process_session_start()`
- `process_session_start()` stores values for S8 consumption

## Files to Modify
- **MODIFIED** `src/claude_headspace/services/agent_lifecycle.py` — `create_agent()` gains persona_slug + previous_agent_id params, Persona validation query
- **MODIFIED** `src/claude_headspace/cli/launcher.py` — `--persona <slug>` argparse flag, validation, env var propagation in `setup_environment()` and `_wrap_in_tmux()`
- **MODIFIED** `bin/notify-headspace.sh` — read two new env vars, include in jq payload construction
- **MODIFIED** `src/claude_headspace/routes/hooks.py` — extract persona_slug + previous_agent_id from session-start data, pass to process_session_start()
- **MODIFIED** `src/claude_headspace/services/hook_receiver.py` — process_session_start() accepts persona_slug + previous_agent_id params

## Acceptance Criteria
- `create_agent(project_id=X, persona_slug="con")` passes persona slug through to tmux session environment
- `create_agent(project_id=X, persona_slug="nonexistent")` returns failure with clear error
- `create_agent(project_id=X)` (no persona) works identically to current behaviour
- `claude-headspace start --persona con` sets persona slug in session environment
- `claude-headspace start --persona nonexistent` exits with error, does not launch
- `claude-headspace start` (no flag) works identically
- Hook payload includes persona_slug and previous_agent_id when env vars are set
- Hook route extracts both fields and passes to downstream processing
- All existing tests continue to pass

## Constraints and Gotchas
- **CLI validation requires DB access**: `cli/launcher.py` is a standalone script (not Flask), so persona validation needs either a direct DB connection or an API call to the server. The approach should follow existing patterns in the CLI (it already calls the server's `/api/sessions` endpoint). Consider validating via an API call or by importing the model layer with a minimal Flask app context.
- **Environment variable naming**: Use `CLAUDE_HEADSPACE_PERSONA_SLUG` and `CLAUDE_HEADSPACE_PREVIOUS_AGENT_ID` to match existing `CLAUDE_HEADSPACE_*` convention
- **Backward compatibility is critical**: All existing flows must work unchanged — the persona parameters are strictly optional
- **`_wrap_in_tmux()` must also propagate**: When bridge mode re-execs in tmux, persona flag must be preserved in the re-executed command (it already passes through `sys.argv[1:]`)
- **`create_agent()` passes persona to CLI**: The tmux session launched by `create_agent()` calls `cli_path start` — need to add `--persona <slug>` to this command array
- **`previous_agent_id` is an integer**: Must be converted to/from string for env var propagation
- **notify-headspace.sh uses jq**: Persona fields are just additional conditional fields in the existing jq payload — same pattern as tmux_pane, tmux_session
- **process_session_start currently has no return mechanism for persona**: S7 just needs to pass persona_slug through — S8 will use it. Consider storing on agent as a transient attribute or passing through kwargs.

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/agent_lifecycle.py`, `src/claude_headspace/services/hook_receiver.py`
- CLI: `src/claude_headspace/cli/launcher.py`
- Routes: `src/claude_headspace/routes/hooks.py`
- Bin: `bin/notify-headspace.sh`
- Models: `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/agent.py`
- Tests: `tests/services/test_agent_lifecycle.py`, `tests/routes/test_hooks.py`, `tests/services/test_hook_receiver.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) — created Role + Persona models
- `e8-s5-persona-filesystem-assets` (2026-02-21) — created asset utility functions
- `e8-s6-persona-registration` (2026-02-21) — persona registration service, CLI, API

### Implementation Patterns
- Modules + tests (no templates, static, or config changes)
- Environment variable propagation pattern: CLI sets env vars → Claude Code inherits → hook script reads them
- Existing hook payload extension pattern: conditional jq fields in notify-headspace.sh
- Existing parameter passthrough in hook_receiver.py: tmux_pane_id, tmux_session follow same pattern

## Q&A History
- No clarifications needed — PRD design decisions were pre-resolved in the Agent Teams Design Workshop

## Dependencies
- No new packages needed
- Consumes E8-S1 models (Persona for slug validation)
- Consumes E8-S4 Agent model extensions (persona_id FK exists but S7 doesn't set it — S8 does)
- Consumes E8-S6 persona registration (personas must exist in DB to validate)

## Testing Strategy
- **Unit tests** for `create_agent()`: mock Persona.query, verify validation logic, verify CLI args construction, verify previous_agent_id passthrough
- **Unit tests** for CLI: test argparse --persona flag, test validation flow
- **Route tests** for `/hook/session-start`: test persona_slug and previous_agent_id extraction from payload
- **Unit tests** for `process_session_start()`: test persona_slug and previous_agent_id parameter acceptance
- **Regression tests**: run existing agent lifecycle and hook tests to verify no breakage

## OpenSpec References
- proposal.md: openspec/changes/e8-s7-persona-aware-agent-creation/proposal.md
- tasks.md: openspec/changes/e8-s7-persona-aware-agent-creation/tasks.md
- spec.md: openspec/changes/e8-s7-persona-aware-agent-creation/specs/persona-aware-agent-creation/spec.md
