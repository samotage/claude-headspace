## ADDED Requirements

### Requirement: File Upload via Drag-and-Drop (FR1)

The voice bridge chat panel SHALL accept file uploads via drag-and-drop from the user's operating system.

#### Scenario: User drags image file into chat

- **WHEN** a user drags an image file (PNG, JPG, GIF, WebP) over the chat input area
- **THEN** a visual drop zone overlay SHALL appear indicating the area accepts file drops
- **AND** when the file is dropped, a pending attachment preview SHALL appear in the input area

#### Scenario: User drags file away without dropping

- **WHEN** a user drags a file over the chat area and then drags it away
- **THEN** the drop zone overlay SHALL disappear

### Requirement: File Upload via Clipboard Paste (FR2)

The voice bridge chat panel SHALL accept image uploads via clipboard paste (Cmd+V).

#### Scenario: User pastes screenshot from clipboard

- **WHEN** a user pastes image data from their clipboard into the chat input area
- **THEN** a pending attachment preview of the pasted image SHALL appear in the input area
- **AND** the user SHALL be able to add text alongside the pasted image before sending

### Requirement: Supported File Types (FR3)

The system SHALL accept the following file types and reject all others.

#### Scenario: Upload of supported file type

- **WHEN** a user uploads a file with a supported type (PNG, JPG/JPEG, GIF, WebP, PDF, TXT, MD, PY, JS, TS, JSON, YAML, YML, HTML, CSS, RB, SH, SQL, CSV, LOG)
- **THEN** the file SHALL be accepted and stored

#### Scenario: Upload of unsupported file type

- **WHEN** a user uploads a file with an unsupported type (e.g., .exe, .zip, .mp4)
- **THEN** the upload SHALL be rejected
- **AND** an error message SHALL be displayed listing the accepted formats

### Requirement: File Size Limits (FR4)

The system SHALL enforce a configurable maximum file size per upload (default: 10MB).

#### Scenario: File under size limit

- **WHEN** a user uploads a file smaller than the configured maximum
- **THEN** the file SHALL be accepted

#### Scenario: File exceeds size limit

- **WHEN** a user uploads a file larger than the configured maximum
- **THEN** the upload SHALL be rejected before transfer
- **AND** an error message SHALL state the maximum allowed size

### Requirement: Server-Side File Storage (FR5)

Uploaded files SHALL be persisted to a designated directory on the server filesystem with unique names.

#### Scenario: File stored successfully

- **WHEN** a file is uploaded successfully
- **THEN** it SHALL be stored with a UUID-based filename to prevent collisions
- **AND** the storage path SHALL be configurable

### Requirement: File Serving for Thumbnails (FR6)

The server SHALL provide an endpoint to serve uploaded files for chat UI rendering.

#### Scenario: Serve uploaded image

- **WHEN** the chat UI requests a thumbnail for an uploaded image
- **THEN** the server SHALL serve the file from the upload directory
- **AND** access SHALL be restricted to the same trust boundary as other dashboard endpoints (localhost/LAN)

#### Scenario: Path traversal attempt

- **WHEN** a request contains a filename with path traversal characters (`..`, `/`, null bytes)
- **THEN** the request SHALL be rejected with a 400 error

### Requirement: File Delivery to Agent (FR7)

The system SHALL deliver the uploaded file's absolute path to the Claude Code agent via the tmux bridge.

#### Scenario: Image file delivered to agent

- **WHEN** a user uploads an image file in the chat
- **THEN** the file's absolute path SHALL be sent to the agent via tmux send-keys
- **AND** the path SHALL be formatted so Claude Code recognises it as a file to read

#### Scenario: Combined text and file delivery

- **WHEN** a user includes both text and a file attachment
- **THEN** both the text and the file path SHALL be delivered together to the agent

### Requirement: Image Thumbnails in Chat History (FR9)

Uploaded image files SHALL appear as clickable thumbnails in the chat message history.

#### Scenario: Image message displayed

- **WHEN** a chat message includes an image file attachment
- **THEN** a thumbnail SHALL be rendered inline (constrained to reasonable max width/height)
- **AND** clicking the thumbnail SHALL open the full-size image

### Requirement: Non-Image File Display (FR10)

Non-image files SHALL appear in the chat history with a file type icon, filename, and file size.

#### Scenario: Code file message displayed

- **WHEN** a chat message includes a code file attachment (e.g., .py, .js)
- **THEN** a file card SHALL be rendered showing: file type icon, filename, and human-readable file size
- **AND** clicking the card SHALL open or download the file

### Requirement: File Metadata on Turn Records (FR11)

File upload information SHALL be stored as `file_metadata` (JSONB) on the Turn record.

#### Scenario: Turn created with file attachment

- **WHEN** a file is uploaded as part of a chat message
- **THEN** the Turn record SHALL include `file_metadata` with: original_filename, stored_filename, file_type, mime_type, file_size, server_path, serving_url

### Requirement: Transcript API File Awareness (FR12)

The transcript API SHALL include file attachment metadata in turn records.

#### Scenario: Transcript loaded with file messages

- **WHEN** the chat UI requests the transcript for an agent
- **THEN** turns with file attachments SHALL include the `file_metadata` field
- **AND** the chat UI SHALL use this metadata to render thumbnails and file cards

### Requirement: Upload Progress Feedback (FR13)

The UI SHALL show upload progress for files being transferred to the server.

#### Scenario: Large file upload in progress

- **WHEN** a file upload is in progress
- **THEN** a progress indicator SHALL be visible in the chat input area

### Requirement: Upload Error Feedback (FR14)

Failed uploads SHALL display clear, actionable error messages without disrupting the conversation.

#### Scenario: Network error during upload

- **WHEN** an upload fails due to network error
- **THEN** an error message SHALL be displayed with a retry option

#### Scenario: Server rejects file

- **WHEN** the server rejects a file (invalid type, size exceeded, quota exceeded)
- **THEN** the specific reason SHALL be displayed to the user

### Requirement: File Retention and Cleanup (FR15)

Uploaded files SHALL be automatically removed after a configurable retention period.

#### Scenario: File expires after retention period

- **WHEN** a file's age exceeds the configured retention period (default: 7 days)
- **THEN** the file SHALL be deleted by the background cleanup process

#### Scenario: Cleanup runs on startup

- **WHEN** the Flask application starts
- **THEN** a startup sweep SHALL delete any expired files in the upload directory

## ADDED Non-Functional Requirements

### Requirement: Path Traversal Prevention (NFR1)

The file upload and serving endpoints MUST prevent path traversal attacks.

#### Scenario: Malicious filename upload

- **WHEN** an uploaded file has a filename containing `..`, `/`, or null bytes
- **THEN** the filename SHALL be sanitised and the file stored only within the designated upload directory

### Requirement: Content-Based File Type Validation (NFR2)

File type validation MUST check actual file content (magic bytes), not just the file extension.

#### Scenario: Disguised file upload

- **WHEN** a file has a `.png` extension but its content is not a valid PNG image
- **THEN** the upload SHALL be rejected

### Requirement: Storage Limits (NFR3)

The system SHALL enforce a configurable maximum total storage size for uploads (default: 500MB).

#### Scenario: Storage quota exceeded

- **WHEN** a new upload would cause the total storage to exceed the configured maximum
- **THEN** the upload SHALL be rejected with a clear error message

### Requirement: No Impact on Existing Flows (NFR4)

The addition of file upload capabilities MUST NOT alter the behaviour of existing text-only respond and voice command endpoints.

#### Scenario: Text-only command still works

- **WHEN** a user sends a text-only command via the existing `/api/voice/command` endpoint
- **THEN** the behaviour SHALL be identical to before this feature was added
