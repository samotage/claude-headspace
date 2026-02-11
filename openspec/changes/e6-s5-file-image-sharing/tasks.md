## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Configuration & Infrastructure

- [ ] 2.1 Add `file_upload` configuration section to config.yaml with defaults (upload_dir, max_file_size_mb, max_total_storage_mb, retention_days, allowed types)
- [ ] 2.2 Add `file_upload` config defaults to `config.py` so config loads cleanly when section is missing
- [ ] 2.3 Create Alembic migration adding `file_metadata` JSONB column to `turns` table

### Turn Model

- [ ] 2.4 Add `file_metadata` (JSONB, nullable) mapped column to `Turn` model in `turn.py`

### File Upload Service

- [ ] 2.5 Create `src/claude_headspace/services/file_upload.py` with `FileUploadService` class:
  - Initialise with config (upload_dir, max sizes, allowed types, retention)
  - `validate_file(filename, file_size, file_obj)` -- check extension + magic bytes + size + quota
  - `save_file(file_obj, original_filename)` -- generate unique name, write to disk, return metadata dict
  - `get_serving_url(stored_filename)` -- build URL for file serving endpoint
  - `get_absolute_path(stored_filename)` -- return absolute disk path for tmux delivery
  - `get_storage_usage()` -- calculate total bytes used in upload directory
  - `cleanup_expired()` -- delete files older than retention period
  - `startup_sweep()` -- run cleanup on app startup

### App Registration

- [ ] 2.6 Register `FileUploadService` in `app.py` as `app.extensions["file_upload"]`
- [ ] 2.7 Schedule cleanup: call `startup_sweep()` during app init, and register a background timer or hook for periodic cleanup
- [ ] 2.8 Ensure upload directory is created on startup if it doesn't exist

### Voice Bridge Routes — Upload Endpoint

- [ ] 2.9 Add `POST /api/voice/agents/<agent_id>/upload` route to `voice_bridge.py`:
  - Accept multipart form data: `file` (required) + `text` (optional)
  - Validate agent exists and has tmux pane
  - Call FileUploadService.validate_file and save_file
  - Create Turn record with actor=USER, intent=COMMAND or ANSWER (based on agent state), file_metadata populated
  - Deliver file path (and optional text) to agent via tmux bridge
  - Handle state transitions (same logic as voice_command for AWAITING_INPUT vs IDLE)
  - Return file metadata + turn info in response

### Voice Bridge Routes — File Serving Endpoint

- [ ] 2.10 Add `GET /api/voice/uploads/<filename>` route to `voice_bridge.py`:
  - Serve files from the configured upload directory
  - Validate filename (no path traversal — reject if contains `/`, `..`, or null bytes)
  - Use `send_from_directory` for safe file serving
  - Apply same LAN/localhost auth bypass as other voice bridge endpoints

### Voice Bridge Routes — Command Enhancement

- [ ] 2.11 Modify `POST /api/voice/command` to accept optional `file_path` field in JSON body
  - When present, prepend or append the file path reference to the text sent via tmux
  - Format: `[user text]\n\nPlease look at this file: [absolute_path]`

### Transcript API Enhancement

- [ ] 2.12 Include `file_metadata` field in turn dicts returned by `GET /api/voice/agents/<id>/transcript`

### Voice API Client (JavaScript)

- [ ] 2.13 Add `uploadFile(agentId, file, text)` method to `VoiceAPI` in `voice-api.js`:
  - Build FormData with file + optional text
  - Use XMLHttpRequest for upload progress events
  - Return Promise with response data
  - Report progress via callback

### Chat UI — Drop Zone

- [ ] 2.14 Add drop zone overlay HTML to `voice.html` inside `#screen-chat`
- [ ] 2.15 Add dragenter/dragover/dragleave/drop event handlers in `voice-app.js`:
  - Show overlay on dragenter, hide on dragleave/drop
  - On drop: extract file, validate client-side (type + size), show pending preview
- [ ] 2.16 Add drop zone CSS styles in `voice.css` (overlay, border highlight, icon)

### Chat UI — Clipboard Paste

- [ ] 2.17 Add paste event handler on chat text input in `voice-app.js`:
  - Detect image data in clipboard (clipboardData.items with type starting `image/`)
  - Convert to File object
  - Show pending attachment preview

### Chat UI — Pending Attachment Preview

- [ ] 2.18 Add pending attachment preview area in `voice.html` (inside chat-input-bar, above textarea)
- [ ] 2.19 Implement `_showPendingAttachment(file)` in `voice-app.js`:
  - For images: render thumbnail preview using FileReader/URL.createObjectURL
  - For other files: show file icon + filename + size
  - Add remove (X) button to clear attachment
- [ ] 2.20 Add pending attachment CSS styles in `voice.css`

### Chat UI — Send with Attachment

- [ ] 2.21 Modify chat form submit handler in `voice-app.js`:
  - If pending attachment exists, call `VoiceAPI.uploadFile` instead of `sendCommand`
  - Show upload progress indicator
  - On success: clear attachment, add message to chat, scroll to bottom
  - On error: show error toast, keep attachment for retry

### Chat UI — Image Thumbnails in Chat History

- [ ] 2.22 Modify `_createBubbleEl` in `voice-app.js` to check for `file_metadata` on turn:
  - If image type: render clickable thumbnail (`<img>` with max-width/max-height constraints)
  - Clicking thumbnail opens full image in new tab or lightbox overlay
- [ ] 2.23 Add image thumbnail CSS styles in `voice.css`

### Chat UI — Non-Image File Cards

- [ ] 2.24 Modify `_createBubbleEl` to render file card for non-image attachments:
  - Show file type icon (emoji or SVG), filename, file size (human-readable)
  - Clicking card opens/downloads the file
- [ ] 2.25 Add file card CSS styles in `voice.css`

### Chat UI — Upload Progress & Error Feedback

- [ ] 2.26 Add upload progress indicator in chat input area (progress bar or spinner)
- [ ] 2.27 Add error toast/inline message rendering for upload errors:
  - Invalid file type: list accepted formats
  - File too large: show size limit
  - Upload failed: show retry option
- [ ] 2.28 Add progress and error CSS styles in `voice.css`

## 3. Testing (Phase 3)

### Service Tests

- [ ] 3.1 Create `tests/services/test_file_upload.py`:
  - Test file type validation (allowed + rejected extensions)
  - Test magic bytes validation (content vs extension mismatch)
  - Test file size validation (under limit, at limit, over limit)
  - Test storage quota validation
  - Test unique filename generation
  - Test file save and retrieval
  - Test path traversal prevention (filenames with `..`, `/`, null bytes)
  - Test cleanup of expired files
  - Test startup sweep
  - Test get_serving_url and get_absolute_path

### Route Tests

- [ ] 3.2 Create `tests/routes/test_voice_bridge_upload.py`:
  - Test upload endpoint with valid image file
  - Test upload endpoint with valid text file
  - Test upload endpoint with combined text + file
  - Test upload endpoint with invalid file type (rejected)
  - Test upload endpoint with oversized file (rejected)
  - Test upload endpoint with non-existent agent (404)
  - Test upload endpoint with agent without tmux pane (503)
  - Test file serving endpoint with valid filename
  - Test file serving endpoint with path traversal attempt (400)
  - Test file serving endpoint with non-existent file (404)
  - Test transcript endpoint includes file_metadata
  - Test existing text-only command endpoint still works unchanged

### Integration Tests

- [ ] 3.3 Create `tests/integration/test_file_upload_integration.py`:
  - End-to-end: upload file -> verify stored on disk -> verify Turn record -> verify transcript includes metadata
  - Upload + cleanup: upload file -> advance time past retention -> run cleanup -> verify file removed

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: drag-drop image into chat, see thumbnail, agent receives path
- [ ] 4.4 Manual verification: paste screenshot into chat, see preview, send, see thumbnail in history
- [ ] 4.5 Manual verification: upload non-image file, see file card in chat history
- [ ] 4.6 Manual verification: existing text-only respond and voice command flows work unchanged
- [ ] 4.7 Verify file cleanup runs on startup
