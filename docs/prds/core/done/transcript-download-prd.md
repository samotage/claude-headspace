---
validation:
  status: valid
  validated_at: '2026-03-05T08:06:58+11:00'
---

## Product Requirements Document (PRD) — Transcript Download

**Project:** Claude Headspace
**Scope:** Export agent and channel conversations as downloadable Markdown transcripts
**Author:** Robbo (architect)
**Status:** Draft
**Depends On:** Voice App Kebab Menus PRD (for voice app menu integration)

---

## Executive Summary

Conversations in Claude Headspace — both 1:1 agent sessions and group channel chats — contain valuable content for debugging, content creation, and external analysis. Currently this content is trapped inside the dashboard with no way to export it.

This PRD introduces a transcript download feature that assembles a complete conversation into a clean, human-readable Markdown file with YAML frontmatter metadata. The transcript is delivered as a browser download and simultaneously saved server-side in `data/transcripts/` for persistent access. The download action is accessible from kebab menus in both the voice app and the dashboard.

---

## 1. Context & Purpose

### 1.1 Context
Agent sessions and channel chats produce rich conversational content — debugging context, architectural decisions, strategic insights, creative output. This content currently lives only within the Claude Headspace interface. Users who want to use conversation content externally (blog posts, market analysis, project documentation, feeding into other tools) have no clean way to extract it.

Raw JSONL transcript files exist on the filesystem but they are machine-format, not human-readable, and lack the metadata context needed to make them useful standalone.

### 1.2 Target User
The operator — someone who has had a valuable conversation with an agent or observed a productive channel discussion and wants to capture that content for use outside Claude Headspace.

### 1.3 Success Moment
The user finishes a productive session with an agent. They tap "Download Transcript" from the kebab menu, and a clean Markdown file appears in their downloads — ready to paste into a blog post, feed into an analysis tool, or file away for future reference. They know a copy is also saved server-side for later retrieval.

---

## 2. Scope

### 2.1 In Scope
- Transcript assembly from agent session conversations (all turns across all commands, full session lifetime)
- Transcript assembly from channel chat conversations (all messages, full channel history)
- Markdown output format with YAML frontmatter containing identifying metadata
- Each message attributed to its actor by display name with timestamp
- Browser download delivering a `.md` file to the user's downloads folder
- Server-side persistent copy saved to `data/transcripts/` with metadata-derived filename
- "Download Transcript" action added to the voice app agent chat kebab menu
- "Download Transcript" action added to the voice app channel chat kebab menu
- "Download Transcript" action added to the existing dashboard agent card kebab menu
- "Download Transcript" action added to the existing dashboard channel chat kebab menu

### 2.2 Out of Scope
- Selective range export (e.g., export only turns 5–20) — always full session/channel
- Alternative output formats (PDF, HTML, JSON) — Markdown only
- Transcript search or browsing UI within the dashboard
- Sharing transcripts with other users
- Automatic or scheduled transcript generation
- Modifying or redesigning existing kebab menu patterns (just adding the action)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. User can download a complete agent session transcript as a `.md` file from the voice app agent chat kebab menu
2. User can download a complete channel chat transcript as a `.md` file from the voice app channel chat kebab menu
3. User can download a complete agent session transcript from the dashboard agent card kebab menu
4. User can download a complete channel chat transcript from the dashboard channel chat kebab menu
5. Downloaded file contains YAML frontmatter with: conversation type, identifier (session UUID or channel slug), project name, persona slug, agent ID, all participants (display names and roles), start time, end time, total message count
6. Every message in the transcript body is attributed to its actor by display name with timestamp
7. A persistent copy is saved server-side in `data/transcripts/` using the metadata-derived filename convention
8. Transcripts are clean, human-readable Markdown suitable for pasting into blog posts or feeding into external tools

---

## 4. Functional Requirements (FRs)

### Transcript Assembly

**FR1:** The system shall assemble a complete transcript from an agent session, including all turns (USER and AGENT) across all commands within the session, ordered chronologically by timestamp.

**FR2:** The system shall assemble a complete transcript from a channel chat, including all messages from all participants, ordered chronologically by timestamp.

**FR3:** Each entry in the transcript body shall include the actor's display name (persona name for agents, "Operator" or user identity for the human participant), the timestamp, and the full message text.

### Metadata & Formatting

**FR4:** The transcript shall be formatted as Markdown with YAML frontmatter. The frontmatter shall include:
- `type`: `chat` (agent session) or `channel` (group chat)
- `identifier`: session UUID (for chat) or channel slug (for channel)
- `project`: project name
- `persona`: persona slug of the agent (for chat) or of the channel chair (for channel)
- `agent_id`: agent ID
- `participants`: list of all participants with display names and roles
- `start_time`: timestamp of the first message
- `end_time`: timestamp of the last message
- `message_count`: total number of messages in the transcript
- `exported_at`: timestamp of when the transcript was generated

**FR5:** The transcript body shall use a consistent, readable format for each message that clearly distinguishes speaker, time, and content.

### File Naming & Storage

**FR6:** The transcript filename shall follow the convention: `{type}-{persona_slug}-{agent_id}-{datetime}.md` where type is `chat` or `channel`, persona_slug is the agent's persona (for chat) or the chair's persona (for channel), agent_id is the agent identifier, and datetime is the export timestamp.

**FR7:** The transcript shall be saved server-side in `data/transcripts/` using the filename from FR6.

**FR8:** The transcript shall be delivered to the user's browser as a file download with appropriate content-disposition headers.

### UI Integration

**FR9:** A "Download Transcript" action shall be added to the voice app agent chat kebab menu.

**FR10:** A "Download Transcript" action shall be added to the voice app channel chat kebab menu.

**FR11:** A "Download Transcript" action shall be added to the existing dashboard agent card kebab menu.

**FR12:** A "Download Transcript" action shall be added to the existing dashboard channel chat kebab menu.

**FR13:** The download action shall provide visual feedback while the transcript is being assembled (e.g., a brief loading state) and confirmation when the download is triggered.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Transcript generation shall complete without timeout for conversations of any realistic size (up to several thousand messages).

**NFR2:** The download shall not block the chat UI — the user can continue interacting while the transcript is being assembled.

---

## 6. UI Overview

The "Download Transcript" action appears as an item in the kebab menu (three-dot menu) in four locations: the voice app agent chat, the voice app channel chat, the dashboard agent card, and the dashboard channel chat panel. Selecting the action triggers transcript assembly and delivers the file as a browser download. A brief visual indicator shows that the transcript is being prepared. No additional UI screens or dialogs are required — it's a single-action flow: tap menu item, get file.
