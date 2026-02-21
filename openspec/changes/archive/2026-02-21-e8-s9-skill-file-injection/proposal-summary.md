# Proposal Summary: e8-s9-skill-file-injection

## Architecture Decisions
- New `SkillInjector` service module — keeps injection logic separate from hook_receiver (single responsibility)
- Injection triggered from `process_session_start()` AFTER persona assignment — natural integration point, runs within the same request context
- Idempotency via in-memory set of injected agent IDs — lightweight, no DB overhead, cleared on agent end
- Health check before send — uses existing `tmux_bridge.check_health()` at COMMAND level
- Fault isolation: entire injection wrapped in try/except in hook_receiver — injection failure never blocks agent registration
- Priming uses `tmux_bridge.send_text()` — the existing, battle-tested transport with per-pane locking and Enter verification
- The priming message is NOT a skill expansion (no `**Command name:**` patterns), so `is_skill_expansion()` filter will not suppress it
- The `respond_pending` mechanism is not relevant here — priming is sent during session_start, before any user_prompt_submit hooks fire

## Implementation Approach
- Create `skill_injector.py` with a single public function `inject_persona_skills(agent)` that:
  1. Checks idempotency (skip if already injected)
  2. Verifies agent has persona_id and tmux_pane_id
  3. Loads persona slug from agent.persona relationship
  4. Reads skill.md via `persona_assets.read_skill_file(slug)`
  5. Reads experience.md via `persona_assets.read_experience_file(slug)` (optional)
  6. Checks tmux pane health via `tmux_bridge.check_health(pane_id)`
  7. Composes priming message
  8. Sends via `tmux_bridge.send_text(pane_id, message)`
  9. Records agent ID in injected set
  10. Logs outcome
- In `hook_receiver.py`, add injection trigger after persona assignment block in `process_session_start()` — guarded by `agent.persona_id and agent.tmux_pane_id`

## Files to Modify
- **NEW** `src/claude_headspace/services/skill_injector.py` — injection service
- **MODIFIED** `src/claude_headspace/services/hook_receiver.py` — trigger injection in `process_session_start()`

## Acceptance Criteria
- Persona-backed agent with tmux pane receives skill.md + experience.md as first user message
- Agent without persona receives no injection
- Missing skill.md skips injection with warning log
- Missing experience.md proceeds with skill.md content only
- Injection is idempotent per agent session
- Health check verifies tmux pane before sending
- Injection failure does not block registration or crash server
- All attempts logged with agent ID, persona slug, outcome
- Existing tests pass unchanged

## Constraints and Gotchas
- **Persona relationship must be loaded**: After S8 sets `agent.persona_id`, the `agent.persona` relationship should be navigable to get the slug. Use `Persona.query.get(agent.persona_id)` if the relationship isn't loaded.
- **`send_text()` is synchronous and blocking**: It waits for Enter verification. This is fine for a single priming message but should not be called in a tight loop. One call per session start.
- **Priming message length**: Skill files are short (typically 20-50 lines). No token budget concerns per workshop decision 3.1.
- **project_root for persona_assets**: `persona_assets` functions default to `Path.cwd()` which should work in the Flask request context. If not, the agent's project path can be used.
- **Idempotency set cleanup**: The in-memory set needs cleanup when agents end to prevent memory growth. Hook into `process_session_end()` or the agent reaper.
- **`is_skill_expansion()` interaction**: The priming message content (skill.md + experience.md) does NOT match skill expansion patterns (no `**Command name:**`, `**Goal:**`, `**Input**:` headers). The filter should not suppress it. Verify with a test.
- **Thread safety**: `send_text()` already uses per-pane locks. The idempotency set needs thread-safe access (use a regular set with the GIL protection, or a threading.Lock if needed).

## Git Change History

### Related Files
- Services: `src/claude_headspace/services/persona_assets.py`, `src/claude_headspace/services/tmux_bridge.py`, `src/claude_headspace/services/hook_receiver.py`
- Models: `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/agent.py`
- Tests: `tests/services/test_persona_assets.py`, `tests/services/test_hook_receiver.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) — created Role + Persona models
- `e8-s5-persona-filesystem-assets` (2026-02-21) — persona_assets module with read_skill_file/read_experience_file
- `e8-s6-persona-registration` (2026-02-21) — persona registration service with asset seeding
- `e8-s7-persona-aware-agent-creation` (2026-02-21) — hook payload persona_slug passthrough
- `e8-s8-session-correlator-persona` (2026-02-21) — Persona DB lookup and agent.persona_id assignment

### Implementation Patterns
- Modules + tests only (no templates, static, config, or migration changes)
- Service module pattern: standalone function, imported where needed
- Fault isolation pattern: try/except in caller, log and continue
- Existing infrastructure reuse: persona_assets for file I/O, tmux_bridge for delivery

## Q&A History
- No clarifications needed — PRD is clear, all integration points verified in codebase

## Dependencies
- No new packages needed
- Consumes E8-S5 persona_assets (read_skill_file, read_experience_file)
- Consumes E8-S8 agent.persona_id assignment
- Consumes existing tmux_bridge (send_text, check_health)

## Testing Strategy
- **Unit tests** for `skill_injector.py`: mock persona_assets reads, mock tmux_bridge.send_text and check_health
- Test scenarios: successful injection, skill-only (no experience), missing skill, idempotency, unhealthy pane, no persona, send failure
- **Integration test** in hook_receiver: verify injection is called for persona-backed agents with tmux pane
- **Regression tests**: run existing hook_receiver and session_correlator tests

## OpenSpec References
- proposal.md: openspec/changes/e8-s9-skill-file-injection/proposal.md
- tasks.md: openspec/changes/e8-s9-skill-file-injection/tasks.md
- spec.md: openspec/changes/e8-s9-skill-file-injection/specs/skill-file-injection/spec.md
