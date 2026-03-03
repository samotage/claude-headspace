## Why

The handoff system works but has three gaps in production: handoff filenames are opaque (timestamps + zero-padded IDs reveal nothing about content), new agents have no awareness of prior handoffs for their persona, and the operator has no control over whether an agent rehydrates from a predecessor's context. The operator must manually browse the filesystem to understand what previous agents were working on.

## What Changes

- **Filename format reform**: `generate_handoff_file_path()` changes from `{YYYYMMDDTHHmmss}-{agent-8digit}.md` to `{timestamp}_<insert-summary>_{agent-id:NNN}.md` with ISO 8601 timestamps, underscore separators, and human-readable agent tags
- **Handoff instruction update**: `compose_handoff_instruction()` adds explicit instructions for the departing agent to replace `<insert-summary>` with a kebab-case summary (max 60 chars, no underscores)
- **Polling thread glob fallback**: `_poll_for_handoff_file()` adds glob fallback `{timestamp}_*_{agent_tag}.md` when exact path (with placeholder) does not match
- **New `HandoffDetectionService`**: Scans persona handoff directory on agent creation, emits `synthetic_turn` SSE event with most recent 3 handoff filenames and paths
- **New `synthetic_turn` SSE event type**: Dashboard-only event for displaying system-generated informational turns (not delivered to agent via tmux)
- **Dashboard rendering**: New JS handler renders synthetic turns as visually distinct bubbles with copyable file paths, positioned before the agent's first real turn
- **New CLI command**: `flask persona handoffs <slug>` lists all handoffs for a persona (newest first) with `--limit N` and `--paths` options
- **Legacy compatibility**: Old-format filenames continue to appear in all listings without migration

## Impact

- Affected specs: Handoff lifecycle, persona asset management, SSE event types, dashboard rendering, CLI commands
- Affected code:
  - `src/claude_headspace/services/handoff_executor.py` (3 method modifications)
  - `src/claude_headspace/services/session_correlator.py` (add detection call after persona assignment)
  - `src/claude_headspace/app.py` (register HandoffDetectionService)
  - `src/claude_headspace/services/handoff_detection.py` (new service)
  - `src/claude_headspace/cli/persona_cli.py` (new handoffs command)
  - `static/js/sse-client.js` (add synthetic_turn to commonTypes)
  - Dashboard JS (new synthetic turn rendering handler)
- No database schema changes (NFR2)
- No breaking changes to existing handoff flow (NFR3)
