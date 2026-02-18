## Why

Claude Headspace tracks coarse-grained session states via lifecycle hooks but is blind to mid-turn input-needed events (AskUserQuestion, permission dialogs, free-form questions) and captures no agent response content. The dashboard shows status but not substance — summarisation and priority scoring operate on empty text.

This change adds a three-tier content pipeline: (1) Notification hooks for instant input-needed detection, (2) transcript-based content capture for agent response text, and (3) timeout-gated inference for ambiguous question classification. This transforms Headspace from a status monitor into a decision-support tool.

## What Changes

### Hook-Driven State Detection
- Add Notification hook matchers for `elicitation_dialog`, `permission_prompt`, `idle_prompt` to detect input-needed states instantly
- Add PostToolUse hook endpoint as resumption signal (AWAITING_INPUT → PROCESSING)
- Store `message` and `title` from Notification payloads as turn context
- Update hook installer (`bin/install-hooks.sh`) with new Notification matchers and PostToolUse hooks

### Transcript Path & Content Capture
- Add `transcript_path` column to Agent model via Alembic migration
- Capture `transcript_path` from hook event payloads on SessionStart and persist on Agent
- On Stop hook, read agent's transcript `.jsonl` file and extract last response text
- Populate AGENT/COMPLETION turn `text` field with extracted content (truncated to configurable max)

### File Watcher Content Pipeline
- Upgrade file watcher from dormant fallback to active content enrichment
- Monitor registered transcript files for new entries
- Run regex-based question detection immediately on new agent output (via existing intent_detector patterns)
- Implement timeout-gated inference: if no tool activity within `awaiting_input_timeout`, classify via LLM

### Intelligence Integration
- Feed captured agent text through existing summarisation service for real turn/command summaries
- Command summaries from real content feed into priority scoring for meaningful rankings
- Add question classification prompt for inference service

### Configuration
- Add `awaiting_input_timeout` (default 10s) to `file_watcher` section in `config.yaml`

## Impact

- Affected code:
  - **Models:** `models/agent.py` (add transcript_path field)
  - **Routes:** `routes/hooks.py` (new PostToolUse endpoint, enhance Notification endpoint)
  - **Services:**
    - `services/hook_receiver.py` (new event types: POST_TOOL_USE, enhanced NOTIFICATION processing)
    - `services/hook_lifecycle_bridge.py` (AWAITING_INPUT transitions from notifications, PostToolUse resumption)
    - `services/command_lifecycle.py` (turn text population, content-aware transitions)
    - `services/file_watcher.py` (content pipeline upgrade, transcript monitoring, timeout timers)
    - `services/intent_detector.py` (enhanced for transcript content classification)
    - `services/event_writer.py` (new event types for content pipeline)
  - **Scripts:** `bin/install-hooks.sh` (new Notification matchers, PostToolUse hooks)
  - **Config:** `config.yaml` (add `awaiting_input_timeout`)
  - **Migrations:** New Alembic migration for `transcript_path` column
  - **Tests:** New unit, route, and integration tests across all modified services
- Affected specs: Hook processing, state transitions, content pipeline, file watcher behaviour
- No breaking changes to existing API contracts or state machine transitions
