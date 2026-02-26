## Why

A live incident demonstrated that prompt-level guardrails alone are insufficient: a remote agent leaked filesystem paths, virtual environment locations, and module error details when a CLI command failed, and further disclosed technical diagnostics under social engineering. The platform guardrails document exists and has been hotfixed into the injection pipeline, but there is no error sanitisation layer, no fail-closed behaviour on missing guardrails, no version tracking, and no exception reporting when injection fails. This change hardens remote agent guardrails ahead of public launch.

## What Changes

- Guardrail injection becomes mandatory and fail-closed: agent creation fails if guardrails are missing, unreadable, or empty
- Error output sanitisation layer intercepts raw errors, stack traces, and system paths before they reach the agent's conversational context
- Guardrail version tracking via content hash stored per agent (no schema migration needed per content change)
- Guardrail staleness detection for running agents whose guardrails have been updated since injection
- otageMon exception reporting on all guardrail injection failure modes
- Adversarial test suite covering identity probing, error extraction, prompt injection, and system prompt extraction

## Impact

- Affected specs: remote-agents, persona-skill-injection, agent-lifecycle
- Affected code:
  - `src/claude_headspace/services/skill_injector.py` — fail-closed logic, version tracking, otageMon reporting
  - `src/claude_headspace/services/persona_assets.py` — guardrail validation (empty/unreadable), version hash computation
  - `src/claude_headspace/services/remote_agent_service.py` — guardrail pre-check before agent creation
  - `src/claude_headspace/models/agent.py` — new columns for guardrail version hash and injection timestamp (already has prompt_injected_at)
  - `src/claude_headspace/services/hook_receiver.py` — error output sanitisation in post_tool_use processing
  - `src/claude_headspace/routes/remote_agents.py` — guardrail failure error codes in create endpoint
  - `tests/services/test_skill_injector.py` — unit tests for fail-closed, version tracking, otageMon reporting
  - `tests/services/test_guardrail_sanitisation.py` — error sanitisation tests
  - `tests/services/test_guardrail_adversarial.py` — adversarial test suite
