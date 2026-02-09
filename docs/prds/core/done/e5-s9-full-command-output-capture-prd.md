---
validation:
  status: valid
  validated_at: '2026-02-09T18:05:40+11:00'
---

## Product Requirements Document (PRD) — Full Command & Output Capture

**Project:** Claude Headspace
**Scope:** Extend Task model to persist full user command and full agent output, with drill-down UI on dashboard and project view
**Author:** Sam (PRD Workshop)
**Status:** Draft

---

## Executive Summary

Claude Headspace currently stores AI-generated summaries of task instructions and completion results on the Task model. While these summaries are valuable for at-a-glance monitoring, they discard the complete text of what the user commanded and what the agent responded with. This means reviewing the full detail requires going back to the terminal.

This PRD adds two new fields to the Task model to capture the full user command text and the full agent output (final message). The existing summary fields remain unchanged. A drill-down UI is added to the dashboard agent card and the project view transcript, allowing users to view the complete text from any device — including iPad, iPhone, or desktop browser — without needing to be at the desk.

The core value is decoupling detailed review of agent work from the terminal, making the dashboard a complete record of what was asked and what was delivered.

---

## 1. Context & Purpose

### 1.1 Context
The summarisation pipeline already captures the raw command text and final agent message during processing, but only persists condensed AI-generated summaries. The full text is available at capture time but is not stored on the Task model, making it inaccessible through the dashboard or project view.

### 1.2 Target User
The primary user who monitors multiple Claude Code agents across projects and wants to review complete agent responses without being physically at the terminal.

### 1.3 Success Moment
The user is on their iPad, taps a drill-down button on a completed task's summary, and reads the complete agent response — exactly as it appeared in the terminal — without needing to return to their desk.

---

## 2. Scope

### 2.1 In Scope
- Two new text fields on the Task model for full command input and full agent output (final message)
- Capture the complete user command text when a task is created
- Capture the complete agent final message text when a task completes
- Drill-down button on the dashboard agent card for both instruction and completion summary to view the full text
- Full output visible in the project view agent chat transcript details
- Mobile-friendly rendering of full text (readable on iPad/iPhone Safari)

### 2.2 Out of Scope
- Changes to existing summary generation (instruction and completion_summary remain as-is)
- Full text search across stored commands or outputs
- Markdown or rich-text rendering of the full output
- Export or download of full output
- Editing or annotating stored text
- Pagination or streaming of very large outputs
- Capturing intermediate agent messages, tool calls, or reasoning traces — only the final agent message

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. Every task that receives a user command has the full command text persisted
2. Every completed task has the full agent final message text persisted
3. A drill-down button is available on the dashboard agent card tooltip for both the instruction and completion summary
4. Pressing the drill-down button displays the full stored text
5. The full agent output is visible in the project view agent chat transcript details
6. Existing summary display behaviour is unchanged

### 3.2 Non-Functional Success Criteria
1. Full text display is readable and usable on mobile devices (iPad and iPhone Safari)
2. Storing full text does not degrade dashboard or SSE performance (full text is loaded on demand, not broadcast with every card refresh)

---

## 4. Functional Requirements (FRs)

**FR1:** The Task model shall have a field to store the full user command text.

**FR2:** The Task model shall have a field to store the full agent final message text.

**FR3:** When a task is created from a user command, the system shall persist the complete command text to the task's full command field.

**FR4:** When a task transitions to COMPLETE, the system shall persist the final agent message text to the task's full output field.

**FR5:** The dashboard agent card shall display a drill-down button within the expanded tooltip for the instruction line, allowing the user to view the full command text.

**FR6:** The dashboard agent card shall display a drill-down button within the expanded tooltip for the completion summary line, allowing the user to view the full agent output text.

**FR7:** Pressing a drill-down button shall display the full text in a readable overlay or panel.

**FR8:** The project view agent chat transcript shall display the full agent output for each completed task.

**FR9:** The full text display shall be scrollable and readable on mobile viewports (minimum 320px width).

**FR10:** Full text fields shall not be included in SSE card_refresh event payloads. They shall be loaded on demand when the user requests drill-down.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Full text storage shall not impose a hard character limit. The field shall accommodate outputs of any practical length produced by a Claude Code session.

**NFR2:** On-demand loading of full text shall respond within 1 second under normal conditions.

---

## 6. UI Overview

### Dashboard Agent Card
The existing tooltip that appears when hovering/tapping on truncated instruction or completion summary text gains a drill-down button (e.g., "View full"). Pressing it opens an overlay or modal displaying the complete stored text in a scrollable, readable format.

### Project View — Agent Chat Transcript
Completed tasks in the transcript section show the full agent output alongside the existing instruction and completion summary. This may use an accordion or expandable section pattern consistent with the existing Kanban completed task cards.

### Mobile Considerations
Both the drill-down overlay and the project view transcript must be usable on touch devices. Text should wrap naturally, be legible at mobile font sizes, and the overlay should be dismissible with a tap or swipe.
