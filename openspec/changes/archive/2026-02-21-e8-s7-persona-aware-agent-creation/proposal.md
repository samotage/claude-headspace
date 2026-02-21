## Why

Agent creation currently has no persona awareness — `create_agent()` takes only a `project_id` and the CLI `claude-headspace start` has no persona flag. There is no way to associate a persona with an agent at creation time or carry persona identity through to the hook pipeline. This sprint bridges persona registration (S6) to the hook-driven registration pipeline, enabling the SessionCorrelator (S8) to set `agent.persona_id` at registration time.

## What Changes

- `create_agent()` in `agent_lifecycle.py` gains optional `persona_slug` and `previous_agent_id` parameters with database validation
- `claude-headspace start` gains `--persona <slug>` flag with database validation before session launch
- Persona slug and `previous_agent_id` propagated via environment variables to `notify-headspace.sh`
- `notify-headspace.sh` reads persona slug and `previous_agent_id` from environment and includes them in hook payload when present
- `/hook/session-start` route extracts `persona_slug` and `previous_agent_id` from payload and passes to `process_session_start()`
- `process_session_start()` accepts and passes through persona slug and `previous_agent_id` parameters (S8 will act on them)
- All changes backward compatible — omitting persona preserves existing anonymous behaviour

## Impact

- Affected specs: persona-aware-agent-creation (new capability)
- Affected code:
  - MODIFIED: `src/claude_headspace/services/agent_lifecycle.py` — `create_agent()` gains persona_slug + previous_agent_id params, validation
  - MODIFIED: `src/claude_headspace/cli/launcher.py` — `--persona` flag, validation, env var propagation
  - MODIFIED: `bin/notify-headspace.sh` — reads persona slug + previous_agent_id env vars, includes in payload
  - MODIFIED: `src/claude_headspace/routes/hooks.py` — extracts persona_slug + previous_agent_id from session-start payload
  - MODIFIED: `src/claude_headspace/services/hook_receiver.py` — `process_session_start()` accepts persona_slug + previous_agent_id

## Definition of Done

- [ ] `create_agent(project_id=X, persona_slug="con")` passes persona slug through to tmux session environment
- [ ] `create_agent(project_id=X, persona_slug="nonexistent")` returns failure with clear error
- [ ] `create_agent(project_id=X)` (no persona) works identically to current behaviour
- [ ] `claude-headspace start --persona con` sets persona slug in session environment
- [ ] `claude-headspace start --persona nonexistent` exits with error, does not launch
- [ ] `claude-headspace start` (no flag) works identically to current behaviour
- [ ] `notify-headspace.sh` includes `persona_slug` and `previous_agent_id` in hook payload when env vars are set
- [ ] Hook route extracts `persona_slug` and `previous_agent_id` and passes to downstream processing
- [ ] `previous_agent_id` flows through the same pipeline when provided
- [ ] All existing agent creation tests continue to pass
