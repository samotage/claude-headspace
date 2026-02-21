## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [ ] 2.1 Create `src/claude_headspace/services/skill_injector.py` — `inject_persona_skills(agent)` function: check idempotency, verify persona and tmux pane, load skill/experience files via `persona_assets`, compose priming message, send via `tmux_bridge.send_text()`, log outcome
- [ ] 2.2 Add idempotency tracking — in-memory set of agent IDs that have received injection, with clear-on-agent-end cleanup
- [ ] 2.3 Add health check — call `tmux_bridge.check_health(pane_id)` at COMMAND level before sending; skip with warning if unhealthy
- [ ] 2.4 Trigger injection from `process_session_start()` in `hook_receiver.py` — after persona assignment, if agent has persona_id and tmux_pane_id, call `inject_persona_skills(agent)` in a try/except (fault isolation)

## 3. Testing (Phase 3)

- [ ] 3.1 Unit tests for `skill_injector.py` — successful injection with both skill.md and experience.md
- [ ] 3.2 Unit tests for `skill_injector.py` — skill.md only (experience.md missing)
- [ ] 3.3 Unit tests for `skill_injector.py` — missing skill.md skips injection with warning
- [ ] 3.4 Unit tests for `skill_injector.py` — idempotency: second call is no-op
- [ ] 3.5 Unit tests for `skill_injector.py` — unhealthy tmux pane skips injection
- [ ] 3.6 Unit tests for `skill_injector.py` — agent without persona skips injection
- [ ] 3.7 Unit tests for `hook_receiver.py` — injection triggered for persona-backed agent with tmux pane
- [ ] 3.8 Regression: existing hook_receiver and session_correlator tests still pass

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
