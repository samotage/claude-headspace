## Why

The voice bridge chat interface (e6-s1 through s3) only supports text-based communication with Claude Code agents. Users cannot share screenshots, UI mockups, or error captures without switching to the terminal — breaking the dashboard-centric workflow Headspace provides. Claude Code already supports image input via file paths, so the gap is entirely on the Headspace side: there is no mechanism to upload a file, store it on disk, and deliver its path to the agent.

## What Changes

### File Upload Service (new)
- New `FileUploadService` for server-side file handling: validation, storage, cleanup
- Configurable upload directory (default: `uploads/` relative to app root)
- File type validation using both extension whitelist and magic bytes content inspection
- Configurable max file size (default: 10MB) and max total storage (default: 500MB)
- Unique filename generation (UUID-based) to prevent collisions
- Path traversal prevention via filename sanitisation
- Background cleanup of expired files (configurable retention, default: 7 days)
- Startup sweep to clean orphaned/expired uploads

### File Upload API Endpoint (new route on voice_bridge blueprint)
- `POST /api/voice/agents/<agent_id>/upload` — multipart file upload with optional text message
- Returns file metadata (filename, type, size, serving URL, absolute path)
- Validates file type, size, and storage quota before accepting
- Returns structured error responses for invalid type, size exceeded, quota exceeded

### File Serving Endpoint (new route on voice_bridge blueprint)
- `GET /api/voice/uploads/<filename>` — serves uploaded files for thumbnail rendering
- Restricted to same trust boundary as existing endpoints (localhost/LAN)
- Path traversal prevention on filename parameter

### File Delivery to Agent (voice_bridge + tmux_bridge enhancement)
- Modify `POST /api/voice/command` to accept optional `file_path` parameter
- When file_path is present, format the tmux message to include the file path so Claude Code reads it
- Combined text + file path messages delivered as a single tmux send

### Turn Model Enhancement
- Add `file_metadata` (JSONB) column to Turn for storing file attachment info
- Schema: `{original_filename, stored_filename, file_type, mime_type, file_size, server_path, serving_url}`
- Alembic migration for new column

### Transcript API Enhancement
- Include `file_metadata` in turn records returned by `GET /api/voice/agents/<id>/transcript`
- Chat UI uses this metadata to render thumbnails and file info for historical messages

### Voice Bridge Chat UI Enhancements (voice-app.js, voice.html, voice.css)
- **Drop zone:** Visual overlay when dragging files over chat input area
- **Paste handler:** Intercept Cmd+V for clipboard image data
- **Pending attachment preview:** Thumbnail (images) or icon+name (other files) in input area before send
- **Attachment removal:** X button to remove pending attachment before sending
- **Image thumbnails in chat history:** Clickable thumbnails for image messages (constrained max width/height)
- **File cards in chat history:** File type icon + filename + size for non-image attachments
- **Upload progress indicator:** Visual feedback during upload
- **Error toasts:** Inline error messages for invalid type, size exceeded, upload failed
- **Combined send:** Text + file attachment sent together in single action

### Voice API Client Enhancement (voice-api.js)
- New `uploadFile(agentId, file, text)` method using `FormData` + `fetch`
- Upload progress tracking via `XMLHttpRequest` for progress events

### Configuration
- New `file_upload` section in config.yaml:
  - `upload_dir` (default: `uploads`)
  - `max_file_size_mb` (default: 10)
  - `max_total_storage_mb` (default: 500)
  - `retention_days` (default: 7)
  - `allowed_image_types` (default: `[png, jpg, jpeg, gif, webp]`)
  - `allowed_document_types` (default: `[pdf]`)
  - `allowed_text_types` (default: `[txt, md, py, js, ts, json, yaml, yml, html, css, rb, sh, sql, csv, log]`)

## Impact

- Affected specs: voice-bridge, turn-model (file_metadata column)
- Affected code:
  - `src/claude_headspace/services/file_upload.py` -- new service (validation, storage, cleanup)
  - `src/claude_headspace/routes/voice_bridge.py` -- new upload + serving endpoints, modify command endpoint
  - `src/claude_headspace/models/turn.py` -- new `file_metadata` JSONB column
  - `src/claude_headspace/app.py` -- register FileUploadService, schedule cleanup
  - `src/claude_headspace/config.py` -- file_upload config defaults
  - `config.yaml` -- file_upload section
  - `migrations/versions/` -- new migration for Turn.file_metadata
  - `static/voice/voice-app.js` -- drag-drop, paste, preview, thumbnails, file cards, progress, errors
  - `static/voice/voice-api.js` -- uploadFile method
  - `static/voice/voice.html` -- drop zone overlay, attachment preview area
  - `static/voice/voice.css` -- drop zone, thumbnail, file card, progress, error styles
- Related OpenSpec history:
  - e6-s1-voice-bridge-server (2026-02-09) -- voice bridge API foundation
  - e6-s2-voice-bridge-client (2026-02-09) -- voice bridge PWA client
  - e5-s4-tmux-bridge (2026-02-04) -- tmux bridge for text delivery
