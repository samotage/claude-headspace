# Proposal Summary: e6-s3-agent-chat-history

## Architecture Decisions
- **Intermediate capture via post-tool-use hook:** Leverage the existing post-tool-use hook to read agent transcript incrementally and create PROGRESS turns. This is non-blocking and adds minimal latency (<50ms).
- **Agent-scoped query through Task join:** Query turns via `Turn → Command → Agent` relationship rather than adding a denormalized `agent_id` to Turn. The existing composite index on `(command_id, timestamp)` provides adequate performance.
- **Cursor-based pagination (turn ID):** Use turn ID as cursor for pagination rather than offset-based, ensuring consistent results when new turns are added concurrently during active agent sessions.
- **Client-side smart grouping:** Perform message grouping on the client to avoid server-side complexity and allow grouping to adapt to rendering context.
- **No schema changes:** PROGRESS intent already exists in TurnIntent enum. No new columns or migrations needed.

## Implementation Approach
- **Backend first:** Implement intermediate capture and modify transcript endpoint before touching frontend, so the API contract is stable for client work.
- **Deduplication via text comparison:** When the stop hook fires, compare the final agent text against PROGRESS turn texts captured during the same response. Strip duplicated portions from the final turn.
- **Transcript position tracking:** Store per-agent file position in a module-level dict (similar to existing `_awaiting_tool_for_agent` pattern in hook_receiver.py). Reset on session start.
- **Frontend pagination:** Infinite scroll with scroll position preservation using `scrollHeight` measurement before/after DOM insertion.

## Files to Modify

### Backend (Python)
- `src/claude_headspace/services/hook_lifecycle_bridge.py` — Add intermediate PROGRESS capture in `process_post_tool_use()`, deduplication in `process_stop()`
- `src/claude_headspace/services/hook_receiver.py` — Add transcript position tracking dict, reset on session start
- `src/claude_headspace/services/transcript_reader.py` — Existing `read_new_entries_from_position()` will be used for incremental reads
- `src/claude_headspace/routes/voice_bridge.py` — Modify transcript endpoint for agent-scoped query, cursor-based pagination, ended agent support

### Frontend (JavaScript/CSS)
- `static/voice/voice-app.js` — Pagination, smart grouping, iMessage timestamps, command separators, ended agent UI
- `static/voice/voice-api.js` — Add pagination params to `getTranscript()` method
- `static/voice/voice.css` — Command separator styles, loading indicator, ended agent banner, grouped bubble styles
- `static/js/project_show.js` — Render chat links in agent rows
- `static/js/activity.js` — Render chat links in agent references

### Templates
- `templates/project_show.html` — No template changes needed (agents rendered by JS)

## Acceptance Criteria
- Opening chat for an agent shows complete conversation across all tasks
- Intermediate agent text messages appear in chat within 5 seconds of production
- Scrolling up loads older messages seamlessly
- Task transitions visible as subtle separators with command instruction
- Rapid consecutive agent messages (within 2s) grouped into single bubbles
- Chat history accessible for ended agents as read-only
- Timestamps follow iMessage conventions
- Initial page load of 50 turns completes within 500ms
- PROGRESS capture adds <50ms to post-tool-use hook response

## Constraints and Gotchas
- **Transcript position reset:** Must reset the file position tracking on session start and when agent is reaped, to prevent stale positions from a previous session.
- **Thread safety:** The `_transcript_positions` dict follows the same pattern as other module-level dicts in hook_receiver.py. Single-worker Flask deployment means no true thread contention, but the agent reaper runs in a background thread — be cautious about cleanup.
- **Deduplication edge cases:** The stop hook's transcript read uses `read_transcript_file()` which reads the last 64KB tail in reverse. The intermediate reads use `read_new_entries_from_position()` which reads forward from a position. The text content should match but may differ in whitespace/truncation — normalize before comparison.
- **SSE chat refresh:** Currently, `_handleChatSSE()` re-fetches the full transcript on every SSE event. With agent-lifetime history this would be wasteful. Should only fetch new turns (using cursor = most recent rendered turn ID) and append.
- **Voice bridge `_respond_pending_for_agent`:** This dict prevents duplicate turn creation after a voice command. Ensure intermediate PROGRESS capture doesn't conflict with this mechanism.
- **Scroll position preservation:** When prepending older messages, must measure `scrollHeight` before insertion and adjust `scrollTop` by the delta after insertion to prevent visual jump.

## Git Change History

### Related Files
- Routes: `src/claude_headspace/routes/voice_bridge.py`
- Services: `src/claude_headspace/services/hook_lifecycle_bridge.py`, `hook_receiver.py`, `transcript_reader.py`
- Models: `src/claude_headspace/models/turn.py` (no changes, reference only), `command.py` (reference only)
- Tests: `tests/routes/test_voice_bridge.py`, `tests/routes/test_voice_bridge_client.py`, `tests/services/test_hook_lifecycle_bridge.py`
- Frontend: `static/voice/voice-app.js`, `static/voice/voice-api.js`, `static/voice/voice.css`
- Dashboard: `static/js/project_show.js`, `static/js/activity.js`

### OpenSpec History
- e6-s1-voice-bridge-server (2026-02-09) — Created transcript endpoint, voice command API
- e6-s2-voice-bridge-client (2026-02-09) — Created PWA client with chat screen, SSE integration
- e5-s8-cli-tmux-bridge (2026-02-06) — CLI launcher with tmux bridge
- e5-s4-tmux-bridge (2026-02-04) — Tmux bridge for agent communication

### Implementation Patterns
- Follows modules + tests pattern (no templates or static changes to main app structure)
- Services accessed via `app.extensions["service_name"]`
- Hook lifecycle bridge pattern: hook event → intent detection → turn creation → state transition → SSE broadcast
- Voice bridge pattern: Flask route → service calls → JSON response with voice-friendly format

## Q&A History
- No clarification questions needed — PRD is comprehensive and internally consistent
- The PRD correctly identifies that PROGRESS intent exists, `read_new_entries_from_position` exists, and no schema changes are needed

## Dependencies
- No new packages or dependencies needed
- No database migrations needed (PROGRESS intent already exists in TurnIntent enum)
- No external services beyond existing OpenRouter for summarisation

## Testing Strategy
- **Unit tests for intermediate capture:** Test `process_post_tool_use()` creates PROGRESS turns from transcript content
- **Unit tests for deduplication:** Test `process_stop()` strips text already captured as PROGRESS turns
- **Unit tests for transcript endpoint:** Test cursor-based pagination, agent-scoped query, has_more flag, ended agent support
- **Unit tests for empty text filtering:** Test that whitespace-only transcript content is not captured
- **Unit tests for transcript position tracking:** Test incremental reads don't re-read content
- **Existing tests must continue to pass:** test_voice_bridge.py, test_voice_bridge_client.py, test_hook_lifecycle_bridge.py

## OpenSpec References
- proposal.md: openspec/changes/e6-s3-agent-chat-history/proposal.md
- tasks.md: openspec/changes/e6-s3-agent-chat-history/tasks.md
- spec.md (voice-bridge): openspec/changes/e6-s3-agent-chat-history/specs/voice-bridge/spec.md
- spec.md (voice-bridge-client): openspec/changes/e6-s3-agent-chat-history/specs/voice-bridge-client/spec.md
