# Proposal Summary: e6-s5-file-image-sharing

## Architecture Decisions
- **Single new service**: `FileUploadService` handles all file operations (validation, storage, cleanup) as a standalone service registered in `app.extensions["file_upload"]` — consistent with existing service patterns
- **Reuse voice_bridge blueprint**: Upload and serving endpoints are added to the existing `voice_bridge_bp` blueprint rather than creating a new blueprint — the feature is scoped to the voice bridge chat panel
- **JSONB metadata on Turn**: File info stored as a single `file_metadata` JSONB column on the Turn model (not separate columns) — keeps the schema change minimal while supporting flexible metadata
- **Local filesystem storage**: Files stored in a configurable local directory with UUID-based filenames — no cloud storage (per scope constraints), no database BLOBs
- **Magic bytes validation**: File type validation uses actual file content inspection (not just extension) to prevent disguised file uploads — requires `python-magic` library
- **tmux bridge delivery**: Files are delivered to Claude Code agents by sending the absolute file path via the existing `tmux_bridge.send_text()` — Claude Code already supports image input via file paths

## Implementation Approach
- **Layered approach**: Build backend first (service + endpoints), then frontend (UI enhancements), then connect them
- **Backend pattern**: Follows the same pattern as existing voice bridge routes — validate agent, check tmux pane, perform action, create Turn record, broadcast SSE update
- **Frontend pattern**: Extends existing vanilla JS in `voice-app.js` — no framework dependencies. Drop zone, paste handler, and attachment preview are new DOM event handlers. Chat bubble rendering extended to detect `file_metadata` and render thumbnails or file cards
- **Upload uses FormData**: The JS client uses `XMLHttpRequest` (not fetch) for upload to get progress events — `FormData` multipart encoding for file + optional text

## Files to Modify

### New Files
- `src/claude_headspace/services/file_upload.py` — FileUploadService (core service)
- `migrations/versions/xxxx_add_file_metadata_to_turns.py` — Alembic migration
- `tests/services/test_file_upload.py` — Service unit tests
- `tests/routes/test_voice_bridge_upload.py` — Route tests for upload/serving endpoints
- `tests/integration/test_file_upload_integration.py` — Integration tests

### Modified Files
- **Models**: `src/claude_headspace/models/turn.py` — add `file_metadata` JSONB column
- **Routes**: `src/claude_headspace/routes/voice_bridge.py` — add upload endpoint, file serving endpoint, modify command endpoint for file_path support, include file_metadata in transcript
- **App**: `src/claude_headspace/app.py` — register FileUploadService, schedule cleanup
- **Config**: `src/claude_headspace/config.py` — file_upload config defaults
- **Config YAML**: `config.yaml` — file_upload section
- **Frontend JS**: `static/voice/voice-app.js` — drag-drop, paste, pending preview, send with attachment, image thumbnails, file cards, progress, error feedback
- **Frontend API**: `static/voice/voice-api.js` — uploadFile method
- **Frontend HTML**: `static/voice/voice.html` — drop zone overlay, attachment preview area
- **Frontend CSS**: `static/voice/voice.css` — drop zone, thumbnail, file card, progress, error styles

## Acceptance Criteria
- User can drag an image file into the chat panel and have it delivered to the targeted agent
- User can paste a screenshot from clipboard and send it to an agent
- Uploaded images appear as clickable thumbnails in chat history
- Non-image files appear with file type icon, filename, and size in chat history
- Claude Code agent can read the shared file and respond to its contents
- Invalid file types are rejected with a clear error listing accepted formats
- Oversized files are rejected with a clear error stating the limit
- Existing text-only respond and voice command flows work unchanged
- Files are cleaned up after configured retention period
- Path traversal attacks are prevented

## Constraints and Gotchas
- **python-magic dependency**: NFR2 requires magic bytes inspection. Need to add `python-magic` to dependencies. On macOS, requires `libmagic` (via `brew install libmagic`). If the dependency is too heavy, can fall back to extension-only validation as a simpler alternative.
- **Upload directory permissions**: The Flask process must have write access to the upload directory. If running under restricted permissions, uploads will fail silently.
- **FormData multipart**: The upload endpoint receives `multipart/form-data`, not JSON. The existing `voice_bridge.before_request` auth check may need adjustment since it currently expects JSON bodies for some paths.
- **tmux text length**: Very long file paths sent via `tmux send-keys -l` could hit tmux's internal buffer limits. Paths should be kept reasonable (< 1000 chars).
- **File serving and CORS**: The file serving endpoint serves from the upload directory. Since the voice bridge chat is served from the same origin (or localhost), CORS should not be an issue. But if accessed from a different LAN device, may need appropriate headers.
- **Cleanup timing**: Cleanup runs on startup and optionally periodically. For the initial implementation, startup sweep is sufficient. A background timer can be added later if needed.
- **Existing voice_command endpoint**: Must NOT break. The `file_path` parameter is optional. Existing callers that don't send it get identical behavior.
- **Turn intent for file uploads**: When agent is AWAITING_INPUT, file upload Turn intent should be ANSWER. When agent is IDLE/COMPLETE, intent should be COMMAND. This matches existing voice_command behavior.
- **Client-side validation**: Validate file type and size on the client side BEFORE uploading to give immediate feedback. Server-side validation is the authoritative check.

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/turn.py`
- Routes: `src/claude_headspace/routes/voice_bridge.py`
- Services: `src/claude_headspace/services/tmux_bridge.py`, `src/claude_headspace/services/hook_lifecycle_bridge.py`
- Static: `static/voice/voice-app.js`, `static/voice/voice-api.js`, `static/voice/voice.html`, `static/voice/voice.css`
- Tests: `tests/routes/test_voice_bridge.py`, `tests/routes/test_voice_bridge_agents.py`, `tests/routes/test_voice_bridge_client.py`, `tests/services/test_tmux_bridge.py`, `tests/services/test_hook_lifecycle_bridge.py`
- Migrations: `migrations/versions/y6z7a8b9c0d1_add_voice_bridge_turn_columns.py`

### OpenSpec History
- e5-s1-input-bridge (2026-02-02) — original input bridge concept
- e5-s4-tmux-bridge (2026-02-04) — tmux bridge for text delivery to agents
- e5-s8-cli-tmux-bridge (2026-02-06) — CLI launcher with tmux bridge
- e6-s1-voice-bridge-server (2026-02-09) — voice bridge API (Turn model columns, 4 endpoints)
- e6-s2-voice-bridge-client (2026-02-09) — voice bridge PWA client
- e6-s4-agent-lifecycle (2026-02-11) — agent lifecycle management

### Implementation Patterns
- Detected structure: modules (services + routes) + tests
- Service registration: `app.extensions["service_name"]` in `create_app()`
- Route pattern: Blueprint with `before_request` auth check, JSON responses, voice-friendly formatting
- Turn creation: actor + intent + text + optional metadata, followed by state transition and SSE broadcast
- JS pattern: IIFE module pattern (`window.VoiceXxx = (function() { ... })()`)
- CSS pattern: Custom CSS in `static/css/src/input.css` (Tailwind source), plus standalone `voice.css` for voice bridge

## Q&A History
- No clarifications were needed. The PRD was comprehensive and consistent with the existing codebase architecture.

## Dependencies
- **New Python package**: `python-magic` for magic bytes file type validation (NFR2). Requires `libmagic` system library on macOS.
- **No new JS packages**: All frontend work uses vanilla JS (FileReader, FormData, XMLHttpRequest, URL.createObjectURL)
- **Database migration**: One new Alembic migration adding `file_metadata` JSONB column to `turns` table

## Testing Strategy
- **Unit tests** (`tests/services/test_file_upload.py`): FileUploadService validation, storage, cleanup, path safety
- **Route tests** (`tests/routes/test_voice_bridge_upload.py`): Upload endpoint, serving endpoint, transcript with file_metadata, error cases
- **Integration tests** (`tests/integration/test_file_upload_integration.py`): End-to-end upload flow, cleanup lifecycle
- **Manual verification**: Drag-drop, paste, thumbnail rendering, file cards, error feedback, existing flows unchanged

## OpenSpec References
- proposal.md: openspec/changes/e6-s5-file-image-sharing/proposal.md
- tasks.md: openspec/changes/e6-s5-file-image-sharing/tasks.md
- spec.md: openspec/changes/e6-s5-file-image-sharing/specs/file-image-sharing/spec.md
