# Proposal Summary: e3-s6-content-pipeline

## Architecture Decisions
- Three-tier detection strategy: (1) hooks for instant deterministic transitions, (2) regex for obvious patterns, (3) inference for ambiguous cases
- PostToolUse used as resumption signal (not PreToolUse, which fires before input-needed states)
- Incremental transcript parsing (track file position) to avoid re-reading entire files
- Reuse existing intent_detector regex patterns for question detection in file watcher
- Reuse existing inference service infrastructure (rate limiting, caching) for question classification
- `transcript_path` stored on Agent model (not Task) since it persists across tasks within a session

## Implementation Approach
- Extend existing hook infrastructure rather than creating new services — add PostToolUse endpoint, enhance Notification endpoint
- File watcher upgraded from dormant fallback to active content pipeline — monitors transcript files, detects questions via regex + timeout-gated inference
- Agent response text captured on Stop hook by reading transcript `.jsonl` — populates previously-empty AGENT/COMPLETION turn text
- All new functionality follows existing patterns: state machine transitions, event writing, SSE broadcasting

## Files to Modify

### Models
- `src/claude_headspace/models/agent.py` — add `transcript_path: str | None` field

### Database
- New Alembic migration — add `transcript_path` column to agents table

### Routes
- `src/claude_headspace/routes/hooks.py` — add `POST /hook/post-tool-use` endpoint, enhance notification endpoint to extract message/title

### Services
- `src/claude_headspace/services/hook_receiver.py` — add `POST_TOOL_USE` event type, `process_post_tool_use()`, enhance `process_notification()` for message/title, enhance `process_session_start()` for transcript_path
- `src/claude_headspace/services/hook_lifecycle_bridge.py` — add `process_post_tool_use()` for AWAITING_INPUT → PROCESSING resumption
- `src/claude_headspace/services/command_lifecycle.py` — support turn text population from transcript content
- `src/claude_headspace/services/file_watcher.py` — major upgrade: transcript file registration, incremental reading, new entry detection, regex question detection, awaiting_input_timeout timers, inference integration
- `src/claude_headspace/services/intent_detector.py` — potentially enhanced patterns (existing patterns may suffice)
- `src/claude_headspace/services/event_writer.py` — new event types for content pipeline events

### Scripts
- `bin/install-hooks.sh` — add Notification matchers (elicitation_dialog, permission_prompt, idle_prompt), add PostToolUse hooks

### Configuration
- `config.yaml` — add `awaiting_input_timeout: 10` under `file_watcher` section

### New Files (Utilities)
- Transcript reader utility — parse `.jsonl`, extract last agent response, truncate to max length

## Acceptance Criteria
1. Dashboard shows INPUT NEEDED within 1 second of AskUserQuestion/permission dialog (via Notification hook)
2. Dashboard returns to PROCESSING within 1 second of user answering (via PostToolUse hook)
3. AGENT/COMPLETION turns have non-empty text extracted from transcript
4. Free-form questions detected within file watcher polling interval via regex
5. Ambiguous output classified by inference within `awaiting_input_timeout` seconds
6. Command summaries reflect actual agent work content
7. Priority scoring rankings incorporate real command context

## Constraints and Gotchas
- **Dirty working tree:** Current development branch has uncommitted changes in several files that this PRD targets (hook_receiver.py, hook_lifecycle_bridge.py, command_lifecycle.py, event_writer.py, dashboard.py). These should be from the previous sprint (e3-s5) and will be carried forward.
- **Notification hook already exists:** The `/hook/notification` endpoint already exists but processes notifications simply — needs enhancement to extract message/title and handle notification_type matchers
- **State machine already has AWAITING_INPUT:** No new states needed — the transitions already exist (PROCESSING → AWAITING_INPUT via QUESTION intent, AWAITING_INPUT → PROCESSING via ANSWER intent)
- **File watcher is dormant:** Currently only used as fallback when hooks are silent; needs significant upgrade for active content monitoring
- **Transcript `.jsonl` format:** Lines are JSON objects with `type`, `role`, `content` fields — need to handle the specific format Claude Code produces
- **Async hooks:** PostToolUse and Notification hooks should use `async: true` in the hook config to avoid blocking Claude Code agent execution
- **FK race conditions:** Follow the EventWriter pattern of passing caller's DB session for all new database operations
- **Rate limiting:** Question classification inference calls must respect existing 30 calls/min, 50k tokens/min limits

## Git Change History

### Related Files
- Models: (no existing model changes in recent history for this subsystem)
- Services: hook_receiver.py, hook_lifecycle_bridge.py, command_lifecycle.py, event_writer.py, file_watcher.py, intent_detector.py
- Routes: hooks.py, dashboard.py
- Config: config.yaml

### OpenSpec History
- No previous OpenSpec changes for this specific subsystem area (content pipeline is new)
- Related changes: e3-s5-brain-reboot (recent, merged)

### Implementation Patterns
- Typical structure: model → service → route → tests (three-tier)
- Hook processing: route validates → hook_receiver processes → lifecycle_bridge transitions → command_lifecycle manages state
- Event logging: all state transitions logged via EventWriter with caller's DB session
- Broadcasting: SSE events emitted after state changes for dashboard updates
- Async inference: thread pool with Flask app context for LLM calls

## Q&A History
- No clarification questions were needed — the PRD is comprehensive and well-aligned with existing architecture
- Key decision: PostToolUse (not PreToolUse) as resumption signal — PRD explicitly documents this based on testing that PreToolUse fires before input-needed states

## Dependencies
- No new Python packages required — all functionality builds on existing infrastructure
- Claude Code hook system must support Notification matchers and PostToolUse events (confirmed in PRD)
- Existing inference service must be operational (OPENROUTER_API_KEY set) for question classification

## Testing Strategy
- **Unit tests:** Transcript reader, process_post_tool_use, enhanced notification processing, session_start transcript_path capture, PostToolUse resumption bridge, file watcher content pipeline (entry detection, regex, timeout, timer cancellation), inference question classification
- **Route tests:** POST /hook/post-tool-use (valid, missing fields, correlation), enhanced POST /hook/notification (message/title), POST /hook/session-start (transcript_path), POST /hook/stop (content extraction)
- **Integration tests:** Full Notification → AWAITING_INPUT → PostToolUse → PROCESSING flow, transcript capture end-to-end, file watcher → regex → AWAITING_INPUT, file watcher → timeout → inference → classification

## OpenSpec References
- proposal.md: openspec/changes/e3-s6-content-pipeline/proposal.md
- tasks.md: openspec/changes/e3-s6-content-pipeline/tasks.md
- spec.md: openspec/changes/e3-s6-content-pipeline/specs/content-pipeline/spec.md
