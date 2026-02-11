---
validation:
  status: valid
  validated_at: '2026-02-11T17:19:50+11:00'
---

## Product Requirements Document (PRD) — File & Image Sharing in Chat

**Project:** Claude Headspace
**Scope:** Enable file and image sharing through the voice bridge chat interface to Claude Code agents
**Author:** User + PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace's voice bridge chat interface currently only supports text-based communication with Claude Code agents. This limits users' ability to share visual context — screenshots, UI mockups, design references, bug reports — even though Claude Code natively supports image input via file paths. Users must switch to the terminal to share files, breaking the flow the Headspace dashboard is designed to maintain.

This PRD defines the requirements for adding file and image sharing to the voice bridge chat panel. Users will be able to drag-and-drop or paste images into the chat, see them rendered as thumbnails in the conversation history, and have them delivered to Claude Code agents in a format the agent can read and respond to. This builds on the completed voice bridge infrastructure (e6-s1 through s3) and makes agent communication feel like a modern messaging interface.

Success means a user can take a screenshot on their phone, AirDrop it to their Mac, drag it into the Headspace chat panel, and have the targeted Claude Code agent see and respond to it — all without leaving the dashboard.

---

## 1. Context & Purpose

### 1.1 Context

The voice bridge chat interface (Epic 6, Sprints 1-3) provides a text-based conversation view for interacting with Claude Code agents. The tmux bridge delivers text input via `tmux send-keys`. However, many development interactions are inherently visual: reporting UI bugs, sharing design mockups, approving layout changes, referencing error screenshots. The current text-only interface forces users out of the dashboard for these interactions.

Claude Code already supports image input via file paths referenced in user messages. The gap is purely on the Headspace side: there is no mechanism to upload a file, store it on disk, and deliver its path to the agent.

### 1.2 Target User

Developers using the Claude Headspace dashboard to manage multiple Claude Code agents across projects. Specifically, users who want to share visual context with agents without switching to the terminal — including users working from mobile devices who AirDrop screenshots to their Mac.

### 1.3 Success Moment

The user drags a screenshot into the voice bridge chat panel. A thumbnail appears in the chat history. The Claude Code agent receives the image, analyzes it, and responds with relevant feedback — all within the Headspace interface.

---

## 2. Scope

### 2.1 In Scope

- Drag-and-drop image/file input in the voice bridge chat panel
- Clipboard paste of images into the chat input area
- File upload endpoint on the Flask server that persists files to disk
- File type validation for supported formats (PNG, JPG, GIF, WebP, PDF, text files, code files)
- File size limits with clear user feedback when exceeded
- Thumbnail/preview rendering of uploaded images in the chat message history
- Non-image file representation (icon + filename) in the chat message history
- Delivery of the uploaded file's absolute path to the Claude Code agent via tmux bridge
- Optional accompanying text message alongside a file attachment
- File metadata stored on Turn records for transcript API to serve in chat history
- Uploaded file storage with a configurable cleanup/retention policy
- Static file serving endpoint for the chat UI to render thumbnails

### 2.2 Out of Scope

- Remote/network file sharing (Headspace and Claude Code are colocated on the same machine)
- Video or audio file uploads
- Collaborative file annotation or markup
- File sharing in the main dashboard respond modal (voice bridge chat panel only, initially)
- End-to-end encryption of uploaded files
- Cloud storage backends (files are stored locally)
- Direct phone-to-dashboard file transfer (user must first transfer to Mac via AirDrop/iCloud)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A user can drag an image file into the voice bridge chat panel and have it delivered to the targeted Claude Code agent
2. A user can paste a screenshot from their clipboard into the chat panel and have it sent to an agent
3. Uploaded images appear as thumbnails in the chat message history
4. Non-image files appear with a file type icon and filename in the chat history
5. The Claude Code agent can read the shared image/file and respond to its contents
6. Invalid file types are rejected with a clear error message explaining accepted formats
7. Files exceeding the size limit are rejected with a clear error message stating the limit
8. Existing text-only respond and voice command flows continue to work unchanged

### 3.2 Non-Functional Success Criteria

1. Uploaded files are stored securely with path traversal prevention
2. File uploads complete within 2 seconds for files under 10MB on local connections
3. Uploaded files are automatically cleaned up after the configured retention period
4. The upload storage directory does not grow unbounded

---

## 4. Functional Requirements (FRs)

**FR1: File Upload via Drag-and-Drop**
Users can drag one or more files from Finder (or another application) into the voice bridge chat panel's input area. The UI provides a visual drop zone indicator when a file is being dragged over the input area.

**FR2: File Upload via Clipboard Paste**
Users can paste image data from their clipboard into the chat input area. This supports the workflow of taking a screenshot (Cmd+Shift+4 on macOS) and pasting it directly.

**FR3: Supported File Types**
The system accepts the following file types:
- Images: PNG, JPG/JPEG, GIF, WebP
- Documents: PDF
- Text/Code: .txt, .md, .py, .js, .ts, .json, .yaml, .yml, .html, .css, .rb, .sh, .sql, .csv, .log

Other file types are rejected with a message listing accepted formats.

**FR4: File Size Limits**
The system enforces a configurable maximum file size per upload (default: 10MB). Files exceeding the limit are rejected before upload with a clear error message stating the maximum allowed size.

**FR5: Server-Side File Storage**
Uploaded files are persisted to a designated directory on the server's filesystem. Each file is stored with a unique name to prevent collisions. The storage path is configurable.

**FR6: File Serving for Thumbnails**
The server provides an endpoint to serve uploaded files so the chat UI can render image thumbnails. Access is restricted to the same trust boundary as existing dashboard endpoints (localhost/LAN).

**FR7: File Delivery to Agent**
When a file is uploaded and (optionally) paired with a text message, the system delivers the file's absolute path to the Claude Code agent via the tmux bridge. The path is formatted so Claude Code recognises it as a file to read.

**FR8: Combined Text and File Messages**
Users can include both text and a file attachment in a single message. The text and file path are delivered together to the agent.

**FR9: Image Thumbnail in Chat History**
Uploaded image files appear as clickable thumbnails in the chat message history. Clicking a thumbnail opens the full-size image.

**FR10: Non-Image File Display in Chat History**
Non-image files (PDF, text, code) appear in the chat history with a file type icon, filename, and file size. Clicking opens or downloads the file.

**FR11: File Metadata on Turn Records**
File upload information (filename, file type, file size, server path, serving URL) is stored as metadata on the Turn record so the transcript API can include file information when serving chat history.

**FR12: Transcript API File Awareness**
The transcript API endpoint (`/api/voice/agents/<id>/transcript`) includes file attachment metadata in turn records, enabling the chat UI to render thumbnails and file info for historical messages.

**FR13: Upload Progress Feedback**
The UI shows upload progress for files being transferred to the server, providing feedback that the upload is in progress.

**FR14: Upload Error Feedback**
Failed uploads (network error, invalid type, size exceeded, server error) display clear, actionable error messages in the chat UI without disrupting the conversation flow.

**FR15: File Retention and Cleanup**
Uploaded files are automatically removed after a configurable retention period (default: 7 days). A background process or startup sweep handles cleanup.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Path Traversal Prevention**
The file upload and serving endpoints must prevent path traversal attacks. Uploaded files must be stored only within the designated upload directory. Filenames must be sanitised.

**NFR2: File Type Validation**
File type validation must check actual file content (magic bytes), not just the file extension, to prevent disguised file uploads.

**NFR3: Storage Limits**
The system should enforce a configurable maximum total storage size for uploads (default: 500MB) and reject new uploads when the limit is reached, with a clear error message.

**NFR4: No Impact on Existing Flows**
The addition of file upload capabilities must not break or alter the behaviour of existing text-only respond and voice command endpoints.

---

## 6. UI Overview

**Drop Zone:**
When a user drags a file over the chat input area, a visual overlay appears indicating the area accepts file drops. The overlay disappears when the file is dragged away or dropped.

**Paste Handling:**
When a user pastes image data (Cmd+V), a preview of the pasted image appears in the input area as a pending attachment. The user can remove it before sending or add text alongside it.

**Pending Attachment Preview:**
Before sending, the attached file appears as a small preview (thumbnail for images, icon+name for other files) near the text input. The user can remove the attachment or send it.

**Chat History — Image Messages:**
Image attachments appear inline in the conversation as thumbnails (constrained to a reasonable max width/height). Clicking opens the full image.

**Chat History — File Messages:**
Non-image attachments appear as a compact file card showing: file type icon, filename, and file size.

**Error States:**
- Invalid file type: toast/inline message listing accepted formats
- File too large: toast/inline message showing the size limit
- Upload failed: toast/inline message with a retry option
