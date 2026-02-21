## Why

Persona-backed agents have `persona_id` set (S8) and skill files on disk (S5/S6), but the agent itself has no awareness of its identity. Without skill file injection, personas exist as database metadata but never influence agent behaviour. This sprint delivers the "moment of awareness" — the agent receives its skill and experience content as its first user message and responds in character.

## What Changes

- New `SkillInjector` service that reads persona skill/experience files and sends priming message via tmux bridge
- `process_session_start()` in `hook_receiver.py` triggers injection after persona assignment for persona-backed agents with a tmux pane
- Injection tracks idempotency per agent session (in-memory set) to prevent re-injection
- Health check via `tmux_bridge.check_health()` before sending
- Graceful degradation: missing skill file skips injection with warning, tmux failures don't block agent registration

## Impact

- Affected specs: skill-file-injection (new capability)
- Affected code:
  - NEW: `src/claude_headspace/services/skill_injector.py` — injection logic (file loading, message composition, health check, delivery, idempotency)
  - MODIFIED: `src/claude_headspace/services/hook_receiver.py` — trigger injection in `process_session_start()` after persona assignment
- Affected tests:
  - NEW: `tests/services/test_skill_injector.py` — unit tests for injection service
  - MODIFIED: `tests/services/test_hook_receiver.py` — test injection trigger integration

## Definition of Done

- [ ] Persona-backed agent with tmux pane receives skill.md + experience.md as first user message
- [ ] Agent without persona receives no injection (backward compatible)
- [ ] Missing skill.md on disk logs warning and skips injection
- [ ] Missing experience.md proceeds with skill.md only
- [ ] Injection is idempotent — duplicate triggers are no-ops
- [ ] Health check verifies tmux pane before sending
- [ ] Injection failure does not block agent registration or crash server
- [ ] All injection attempts logged with agent ID, persona slug, and outcome
- [ ] Existing hook_receiver tests pass unchanged
