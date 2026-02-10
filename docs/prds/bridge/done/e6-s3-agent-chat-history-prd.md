---
validation:
  status: valid
  validated_at: '2026-02-10T17:32:20+11:00'
---

## Product Requirements Document (PRD) — Agent Chat History

**Project:** Claude Headspace
**Scope:** Agent-lifetime conversation history with real-time intermediate messages, iMessage-style display, and universal chat links
**Author:** Sam (PRD Workshop)
**Status:** Draft
**Depends on:** e6-s1-voice-bridge-server, e6-s2-voice-bridge-client

---

## Executive Summary

The Voice Bridge chat screen (introduced in e6-s2 and extended through subsequent iterations) currently displays conversation turns scoped to a single task. When a task completes and a new one begins, the previous conversation disappears. This makes the chat feel like a series of disconnected fragments rather than a continuous conversation with the agent.

This PRD transforms the chat into an agent-lifetime conversation view — showing every meaningful exchange across all tasks for the agent's entire session. It adds real-time intermediate message capture so the user sees what the agent is communicating as it works (e.g., "Let me explore the current implementation..." or "I'll check the test coverage next"), not just the final completion summary. Messages appear with iMessage-style timestamps and smart grouping to keep the view clean and natural.

The chat becomes accessible everywhere agents appear — dashboard cards, project pages, and activity views — including for ended/reaped agents whose session has concluded but whose conversation history remains valuable.

---

## 1. Context & Purpose

### 1.1 Context

The Voice Bridge (e6-s1 server, e6-s2 client) was originally designed for hands-free voice interaction with agents. A chat transcript screen was added as a natural UX extension post-implementation, providing a text-based view of the conversation alongside voice capabilities.

The current chat has two limitations:

1. **Task-scoped view:** Turns are loaded for a single task only. When the agent moves to a new task, the previous conversation is no longer visible. Users lose context about what happened earlier in the session.

2. **Batch-only agent text:** The agent's conversational output (intermediate text between tool calls) is only captured as a single blob when the agent's turn completes (via the stop hook). The user doesn't see individual messages like "Let me explore..." or "I'll check that..." appearing in real-time as the agent works. They only see the final summary after everything is done.

The data pipeline has mature building blocks ready to extend: the transcript reader already supports incremental position-based reading (`read_new_entries_from_position`), the PROGRESS turn intent already exists in the data model, and the SSE broadcaster already pushes updates to the chat screen on every hook event.

### 1.2 Target User

The project owner monitoring and interacting with Claude Code agents — whether at their Mac using the dashboard or on a mobile device via the Voice Bridge.

### 1.3 Success Moment

The user opens the chat for an agent and sees the full conversation from session start — their commands, the agent's intermediate messages appearing in real-time as it works, questions asked, answers given, task completions — all in a natural, scrollable iMessage-like flow. They scroll up to review what the agent said 30 minutes ago on a different task. They tap "Chat" on an ended agent from the project page and review what it accomplished across its entire lifetime.

---

## 2. Scope

### 2.1 In Scope

- Agent-lifetime conversation history spanning all tasks for an agent, displayed chronologically
- Real-time capture and display of intermediate agent text messages as the agent works between tool calls
- Paginated scroll-up loading — most recent messages load first, older messages load on scroll
- Subtle visual task separator markers between task boundaries in the conversation flow
- iMessage-style timestamp display (time-only for today, "Yesterday", day-of-week for this week, date for older)
- Smart grouping of rapid consecutive short agent messages into single bubbles
- Chat links on all pages where agents appear (dashboard cards, project show page, activity page)
- Chat history accessible for ended/reaped agents as read-only conversation (no respond capability)
- Deduplication between intermediate PROGRESS turns and the final COMPLETION turn from the stop hook

### 2.2 Out of Scope

- Changes to voice input/output functionality (speech-to-text, TTS remain unchanged)
- Changes to the respond/answer mechanism (tmux bridge, send-keys remain unchanged)
- Changes to the dashboard agent card respond widget (stays task-scoped, quick-action)
- Full-text search within chat history
- Chat history export or sharing
- Multi-agent conversation view (each chat is single-agent)
- Changes to the Turn model schema (PROGRESS intent already exists, no new columns needed)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Opening the chat for an agent shows the complete conversation across all tasks, not just the current task
2. While an agent is actively processing, intermediate text messages appear in the chat within 5 seconds of the agent producing them
3. Scrolling up loads older messages seamlessly without page reload
4. Task transitions are visible as subtle separators showing the task instruction
5. Rapid consecutive short agent messages (within 2 seconds) are grouped into a single bubble
6. Chat history is accessible for ended agents from the project show page and activity page
7. Timestamps follow iMessage conventions (time-only for today, day-of-week for this week, date for older)

### 3.2 Non-Functional Success Criteria

1. Loading the initial page of chat messages (50 most recent turns) completes within 500ms
2. Loading an older page of messages on scroll-up completes within 500ms
3. Intermediate PROGRESS turn capture does not add more than 50ms latency to the post-tool-use hook response
4. The chat view handles agents with 500+ turns without performance degradation

---

## 4. Functional Requirements (FRs)

### Real-Time Intermediate Message Capture

**FR1:** When the agent produces text output between tool calls during active processing, that text is captured as a PROGRESS turn linked to the current task. This makes the agent's intermediate commentary (e.g., "Let me explore...", "I'll check the test coverage...") available as individual chat messages.

**FR2:** Intermediate text capture reads the transcript incrementally from the last known position, avoiding re-reading content that has already been captured. Each new text block from the agent becomes a separate PROGRESS turn.

**FR3:** When the agent's turn completes (stop hook), the final completion turn does not duplicate text already captured as PROGRESS turns during the same agent response. The system deduplicates between intermediate captures and the final response.

**FR4:** Empty or whitespace-only text blocks from the transcript are not captured as PROGRESS turns.

### Agent-Lifetime Conversation View

**FR5:** The chat transcript endpoint returns turns across all tasks for a given agent, ordered chronologically. The response is no longer scoped to a single task.

**FR6:** Each turn in the response includes the task identifier it belongs to, enabling the client to detect task boundaries and render separators.

**FR7:** Task boundary separators include the task instruction text (what the user asked the agent to do) and the task state (completed, in progress, etc.).

**FR8:** The chat view for an active agent shows the full history from the agent's first task through the current task, with real-time updates for new turns.

### Pagination

**FR9:** The transcript endpoint supports cursor-based pagination. The client requests the most recent N turns (default 50), and can request older turns by specifying a cursor (the oldest turn ID from the previous page).

**FR10:** The client detects when the user scrolls to the top of the chat and automatically requests the next page of older messages. New messages are prepended above the existing content without disrupting the user's scroll position.

**FR11:** The client indicates when all history has been loaded (no more pages available) and when older messages are being fetched (loading indicator at top).

### Timestamps

**FR12:** Each message or message group displays a timestamp. Timestamps appear on the first message and after gaps of 5 or more minutes between messages.

**FR13:** Timestamp format follows iMessage conventions: time-only for today (e.g., "2:30 PM"), "Yesterday 2:30 PM" for yesterday, day-of-week with time for the current week (e.g., "Monday 2:30 PM"), and month/day with time for older messages (e.g., "Feb 3, 2:30 PM").

### Smart Message Grouping

**FR14:** Consecutive agent messages that arrive within 2 seconds of each other are grouped into a single chat bubble, with individual texts separated by line breaks within the bubble.

**FR15:** A change in turn intent (e.g., PROGRESS to QUESTION, PROGRESS to COMPLETION) always breaks a message group, even if within the 2-second window.

**FR16:** User messages (COMMAND, ANSWER) are never grouped — each appears as its own bubble.

### Task Separators

**FR17:** When the conversation transitions from one task to another, a subtle visual separator appears in the chat flow showing the task instruction for the new task.

**FR18:** Task separators are visually distinct from messages (e.g., centered text with horizontal rules) but unobtrusive — they should not dominate the conversation flow.

### Chat Links Everywhere

**FR19:** The project show page includes a chat link for each agent listed (both active and ended agents).

**FR20:** The activity page includes chat links where individual agents are referenced.

**FR21:** Chat links for ended agents open the chat in read-only mode — the full conversation history is displayed, but the input bar is hidden or disabled since the agent is no longer running.

### Ended Agent Support

**FR22:** The chat transcript endpoint works for ended agents, returning all historical turns across all tasks regardless of agent state.

**FR23:** The chat view for an ended agent clearly indicates that the agent has ended (e.g., a banner or footer message) and does not show a typing indicator or input bar.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The intermediate PROGRESS turn capture adds no more than 50ms to the post-tool-use hook response time. Transcript reading and turn creation must not block the hook response.

**NFR2:** The agent-scoped transcript query (all turns across all tasks for an agent) performs efficiently with an index on task_id and timestamp. The query should not require joining through intermediate tables beyond Task.

**NFR3:** Pagination uses cursor-based approach (turn ID) rather than offset-based, ensuring consistent results when new turns are being added concurrently.

**NFR4:** Smart message grouping is performed client-side to avoid server-side complexity and to allow the grouping to adapt to client-side rendering context.

**NFR5:** The chat view does not re-render all messages when new turns arrive — it appends new messages to the existing DOM, preserving scroll position and rendered state.

---

## 6. UI Overview

The chat screen retains its current layout (header, message area, input bar) but with enhanced content and behavior:

### Chat Message Area

Messages flow chronologically from oldest (top) to newest (bottom). The user sees:

- **User messages** (right-aligned, distinct colour): Their commands and answers
- **Agent messages** (left-aligned): The agent's text responses, questions, and completions
- **Smart-grouped bubbles**: Rapid short agent messages combined with line breaks
- **Task separators**: Subtle centered dividers showing "── Fix the login bug ──" between task boundaries
- **Timestamps**: iMessage-style, appearing on first message and after 5+ minute gaps
- **Typing indicator**: Animated dots when the agent is actively processing

### Scroll-Up Loading

When the user scrolls to the top, a small loading spinner appears and older messages load above. The scroll position is preserved so the user doesn't lose their place.

### Ended Agent View

Same layout but with:
- No input bar (or input bar replaced with an "Agent ended" indicator)
- No typing indicator
- A subtle banner indicating the session has concluded

### Chat Entry Points

- Dashboard agent card: "Chat" link (existing, unchanged)
- Project show page: Chat icon/link next to each agent row (active and ended)
- Activity page: Chat link where agents are individually referenced
