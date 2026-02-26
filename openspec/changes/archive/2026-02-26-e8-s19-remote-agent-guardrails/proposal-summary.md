# Proposal Summary: e8-s19-remote-agent-guardrails

## Architecture Decisions

1. **Content-hash versioning over sequential versioning** — Guardrail versions use SHA-256 content hashes rather than sequential version numbers. This means `data/platform-guardrails.md` can be edited freely without requiring DB migrations or version bump ceremonies. The hash changes automatically when content changes.

2. **Pre-creation validation over injection-time-only validation** — `RemoteAgentService.create_blocking()` validates guardrails BEFORE calling `create_agent()`, preventing the creation of orphaned tmux sessions that would need cleanup. The injection layer (`skill_injector.py`) retains its own validation as a defense-in-depth measure.

3. **Error sanitisation at the hook receiver layer** — Error output is sanitised in `hook_receiver.py` during post_tool_use processing, before content reaches the Turn/Command storage. This is the narrowest interception point that catches all tool errors flowing through the hook pipeline.

4. **otageMon reporting via existing ExceptionReporter** — Guardrail failures use the same `ExceptionReporter` service that handles all other exceptions, with source `guardrail_injection` for identification. No new reporting infrastructure needed.

5. **Adversarial tests as unit tests against guardrail content** — The adversarial test suite verifies that the guardrails document contains the required sections and rules, and that the sanitisation layer strips known dangerous patterns. These are deterministic unit tests, not live LLM interaction tests (which are non-deterministic and belong in the agent_driven tier).

## Implementation Approach

The implementation follows a bottom-up dependency order:

1. **Foundation** (2.1): Add versioning infrastructure to `persona_assets.py` — `compute_guardrails_hash()` and `validate_guardrails_content()`. Add `guardrails_version_hash` column to Agent model via Alembic migration.

2. **Enforcement** (2.2): Make `inject_persona_skills()` fail-closed when guardrails are missing/empty. Add pre-creation validation in `RemoteAgentService.create_blocking()`. Wire otageMon reporting through `ExceptionReporter`.

3. **Sanitisation** (2.3): Create `guardrail_sanitiser.py` with regex-based pattern stripping for file paths, stack traces, module names, environment details, and process IDs. Integrate at the post_tool_use hook level.

4. **Detection** (2.4): Add staleness comparison utilities and expose through agent info and alive endpoints.

5. **API Surface** (2.5): Update error codes and response shapes in the remote agents route.

## Files to Modify

### Services (core logic)
- `src/claude_headspace/services/persona_assets.py` — add `compute_guardrails_hash()`, `validate_guardrails_content()`
- `src/claude_headspace/services/skill_injector.py` — fail-closed injection, version hash storage, otageMon reporting
- `src/claude_headspace/services/remote_agent_service.py` — pre-creation guardrail validation
- `src/claude_headspace/services/hook_receiver.py` — error output sanitisation integration
- `src/claude_headspace/services/guardrail_sanitiser.py` — **NEW** error output sanitisation service

### Models
- `src/claude_headspace/models/agent.py` — add `guardrails_version_hash` column

### Routes
- `src/claude_headspace/routes/remote_agents.py` — new error code, version in response

### Migrations
- `migrations/versions/xxxx_add_guardrails_version_hash_to_agents.py` — **NEW** Alembic migration

### Tests
- `tests/services/test_skill_injector.py` — existing file, add fail-closed and version tests
- `tests/services/test_persona_assets.py` — existing file, add hash/validation tests
- `tests/services/test_guardrail_sanitiser.py` — **NEW** sanitisation unit tests
- `tests/services/test_guardrail_adversarial.py` — **NEW** adversarial test suite
- `tests/routes/test_remote_agents.py` — existing file, add guardrail failure route tests

### Agent Info
- `src/claude_headspace/services/agent_lifecycle.py` — include guardrail version in `get_agent_info()`

## Acceptance Criteria

1. Creating a remote agent with guardrails file present succeeds and records the guardrails hash on the agent
2. Creating a remote agent with guardrails file missing fails with `guardrails_missing` error code (no tmux session created)
3. Creating a remote agent with empty guardrails file fails identically
4. Guardrail injection failure triggers otageMon exception report with source `guardrail_injection`
5. Error output containing stack traces, file paths, and module names is sanitised before reaching agent context
6. Sanitised errors preserve generic failure messages that allow the agent to retry
7. Agent alive endpoint reports guardrail staleness when the platform guardrails file has changed since injection
8. Guardrail version hash is included in the create response
9. Adversarial test suite passes, covering identity probing, error extraction, system prompt extraction, and prompt injection
10. Guardrail injection adds < 500ms latency to agent creation

## Constraints and Gotchas

1. **No schema migration per content change** — The versioning mechanism uses content hashing, not DB-stored version numbers. This is explicitly required by NFR3.
2. **Existing `prompt_injected_at` column** — The Agent model already has `prompt_injected_at` for injection timing. The new `guardrails_version_hash` column complements it but does not replace it.
3. **Non-remote agents** — The fail-closed logic only applies to agents created via `RemoteAgentService`. Local/dashboard agents continue with the existing behavior (guardrails optional but strongly expected) to avoid breaking the operator's local workflow.
4. **Error sanitisation scope** — Sanitisation only applies to post_tool_use error output. Normal agent output (non-error) is never sanitised to avoid false positives.
5. **ExceptionReporter availability** — The `ExceptionReporter` may not be configured (no webhook URL/secret). In that case, guardrail failures still prevent agent creation but the otageMon report is silently dropped (consistent with ExceptionReporter's existing behavior).
6. **tmux bridge dependency** — Guardrail injection depends on `tmux_bridge.send_text()`. If tmux send fails, the injection fails and is reported to otageMon, consistent with existing skill injection behavior.

## Git Change History

### Related Files (recent commits)
- `src/claude_headspace/routes/remote_agents.py` — modified in `0f1f428a` (API docs) and `1ed10e57` (CLAUDE.md updates)
- `data/platform-guardrails.md` — modified in `1ed10e57` (CLAUDE.md updates, same commit that added guardrails document)
- `src/claude_headspace/services/agent_lifecycle.py` — modified in `1ed10e57`

### OpenSpec History
- No prior OpenSpec changes for the `remote-agents` capability. This is the first change to formalize guardrail enforcement.

### Patterns Detected
- Service pattern: stateless functions in service modules, registered in `app.extensions`
- Testing pattern: unit tests in `tests/services/`, route tests in `tests/routes/`
- Model pattern: Alembic migrations for schema changes, nullable columns with defaults

## Q&A History

No clarification questions were needed. The PRD is internally consistent with clear requirements.

## Dependencies

- **No new Python packages** — Uses existing `hashlib` (stdlib) for SHA-256, existing `re` (stdlib) for sanitisation patterns
- **No new APIs** — Uses existing `ExceptionReporter` for otageMon reporting
- **One Alembic migration** — Adds `guardrails_version_hash` String(64) nullable column to `agents` table

## Testing Strategy

1. **Unit tests** — Cover versioning functions, fail-closed logic, sanitisation patterns, and staleness detection in isolation
2. **Route tests** — Cover HTTP error codes, response shapes, and guardrail pre-validation at the API layer
3. **Adversarial tests** — Verify guardrails document content covers all required adversarial scenarios (deterministic content verification, not live LLM tests)
4. **Integration consideration** — Live LLM adversarial testing (actually sending prompts to an agent and verifying responses) belongs in the `agent_driven` test tier and is out of scope for this change's automated tests

## OpenSpec References

- Proposal: `openspec/changes/e8-s19-remote-agent-guardrails/proposal.md`
- Tasks: `openspec/changes/e8-s19-remote-agent-guardrails/tasks.md`
- Spec: `openspec/changes/e8-s19-remote-agent-guardrails/specs/remote-agents/spec.md`
