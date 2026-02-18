---
validation:
  status: valid
  validated_at: '2026-02-01T15:52:39+11:00'
---

## Product Requirements Document (PRD) — Content Pipeline & Mid-Turn State Detection

**Project:** Claude Headspace
**Scope:** Hook-driven mid-turn state detection, transcript-based content capture, and inference-powered intelligence pipeline
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace currently tracks coarse-grained session states (PROCESSING, COMPLETE) via lifecycle hooks but is blind to mid-turn events where user input is required (AskUserQuestion, permission dialogs, free-form questions). Additionally, all AGENT/COMPLETION turns store empty text — the system knows *that* the agent responded but not *what* it said.

This PRD defines a three-tier content pipeline that captures full turn text and detects input-needed states: (1) hooks for instant, deterministic state transitions, (2) regex-based transcript analysis for obvious patterns, and (3) timeout-gated LLM inference for ambiguous cases. The captured content feeds into the existing summarisation and priority scoring services, transforming Headspace from a status monitor into a decision-support tool that knows what each agent accomplished and what to focus on next.

---

## 1. Context & Purpose

### 1.1 Context

The existing hook infrastructure reliably detects turn boundaries (UserPromptSubmit → PROCESSING, Stop → COMPLETE) but Claude Code does not fire notification hooks for AskUserQuestion or permission dialogs within the current Headspace hook configuration. Testing confirmed that during an entire turn containing AskUserQuestion, zero notification hooks fired — the dashboard stayed on PROCESSING the entire time.

Meanwhile, AGENT/COMPLETION turns store empty text (`text=""`) because the Stop hook payload contains no response content. The existing summarisation service, priority scoring, and intent detector are all starved of data — they work with whatever text is provided but receive none from agent turns.

The transcript `.jsonl` file contains the full conversation but is only used by a dormant fallback file watcher. The Claude Code hook system provides `transcript_path` on every hook event and supports Notification hooks with matchers for `elicitation_dialog`, `permission_prompt`, and `idle_prompt` — exactly the events needed for input-needed detection.

### 1.2 Target User

Developers running multiple concurrent Claude Code sessions who need a single pane of glass showing what each agent is doing, which ones need attention, and what to focus on next.

### 1.3 Success Moment

The user glances at the Headspace dashboard and sees one agent card showing "Input needed — Which database migration strategy should we use?" while another shows "Processing — Running test suite after refactoring auth module." They click the input-needed card to switch to that terminal, answer the question, and the card immediately returns to "Processing."

---

## 2. Scope

### 2.1 In Scope

- **Hook-driven state detection:** Configure Notification hooks (`elicitation_dialog`, `permission_prompt`, `idle_prompt`) to detect input-needed states; use PostToolUse as resumption signal
- **Transcript path capture:** Store `transcript_path` from hook events on the Agent model; capture on SessionStart
- **Agent response text capture:** On Stop hook, read the transcript `.jsonl` to extract the agent's last response; populate AGENT/COMPLETION turn text
- **Notification text capture:** Store `message` and `title` from Notification hook payloads as turn context
- **File watcher content pipeline:** Upgrade file watcher from dormant fallback to active content enrichment; detect free-form questions via regex on new transcript entries
- **Timeout-gated inference:** When transcript shows new agent content and no tool activity follows within a configurable timeout, send content to inference for question classification
- **Inference-driven intent classification:** Use LLM to determine if stalled agent output contains a question requiring user input
- **Summarisation from real content:** Feed captured agent text through existing summarisation service for accurate turn/command summaries
- **Priority scoring enrichment:** Command summaries generated from actual content feed into priority scoring for meaningful "recommended next" rankings
- **Hook installer update:** Update `bin/install-hooks.sh` to configure new Notification matchers, PostToolUse hooks
- **Configuration:** Add `awaiting_input_timeout` to `file_watcher` section in `config.yaml`

### 2.2 Out of Scope

- Streaming mid-turn partial content to the dashboard in real-time
- Replacing existing lifecycle hooks (SessionStart, Stop, UserPromptSubmit)
- SSE reconnection reliability (separate issue)
- Dashboard UI redesign beyond existing card states
- New LLM models or providers
- PreToolUse as a resumption signal (unreliable — fires before input-needed states)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Dashboard shows INPUT NEEDED within 1 second of AskUserQuestion being displayed to the user (via Notification hook)
2. Dashboard shows INPUT NEEDED within 1 second of a permission dialog being shown (via Notification hook)
3. Dashboard returns to PROCESSING within 1 second of the user answering a question or granting permission (via PostToolUse hook)
4. AGENT/COMPLETION turns have non-empty text extracted from the transcript file
5. Free-form agent questions (ending with "?", "would you like", "should I", etc.) detected within the file watcher polling interval via regex
6. Ambiguous agent output classified as question/not-question by inference within `awaiting_input_timeout` seconds when no tool activity follows
7. Command summaries reflect actual agent work content, not empty strings
8. Priority scoring rankings incorporate real command context

### 3.2 Non-Functional Success Criteria

1. Hook-driven state transitions add < 100ms latency to the existing hook processing pipeline
2. Transcript file reads on Stop hook complete within 500ms for typical transcript sizes
3. Inference calls for question classification respect existing rate limits (30 calls/min, 50k tokens/min)
4. File watcher content pipeline does not increase CPU usage by more than 5% during active monitoring

---

## 4. Functional Requirements (FRs)

### Hook-Driven State Detection

**FR1:** The system shall receive Notification hook events with `notification_type` of `elicitation_dialog`, `permission_prompt`, and `idle_prompt`, and transition the associated agent's task to AWAITING_INPUT state.

**FR2:** The system shall receive PostToolUse hook events and, when the associated agent's task is in AWAITING_INPUT state, transition it back to PROCESSING state.

**FR3:** The system shall not treat PreToolUse(AskUserQuestion) or PermissionRequest events as resumption signals, as these precede input-needed states rather than follow them.

**FR4:** The system shall store `message` and `title` fields from Notification payloads as contextual data on the associated turn.

### Transcript Path & Content Capture

**FR5:** The system shall capture `transcript_path` from hook event payloads and persist it on the Agent model.

**FR6:** The system shall add a `transcript_path` column to the Agent database table via Alembic migration.

**FR7:** On receiving a Stop hook event, the system shall read the agent's transcript `.jsonl` file and extract the agent's last response text.

**FR8:** The system shall populate the AGENT/COMPLETION turn's `text` field with the extracted transcript content, truncated to a configurable maximum length.

**FR9:** The system shall handle unreadable or missing transcript files gracefully, falling back to empty text with a warning log.

### File Watcher Content Pipeline

**FR10:** The file watcher shall monitor registered transcript files for new entries and process them through the content pipeline.

**FR11:** On detecting new agent output in the transcript, the file watcher shall immediately run regex-based question detection using the existing intent detector patterns.

**FR12:** If regex detects a question pattern with high confidence, the system shall transition the agent's task to AWAITING_INPUT state.

**FR13:** If regex does not detect a question and no PostToolUse or Stop hook arrives within the `awaiting_input_timeout` period, the system shall send the agent's output to inference for question classification.

**FR14:** If inference classifies the output as a question, the system shall transition the agent's task to AWAITING_INPUT state.

**FR15:** The `awaiting_input_timeout` timer shall be cancelled if any PostToolUse or Stop hook event arrives for that agent before it expires.

**FR16:** The `awaiting_input_timeout` value shall be configurable in `config.yaml` under the `file_watcher` section.

### Inference & Intelligence

**FR17:** The system shall use the existing inference service to classify stalled agent output as question vs. non-question, using a prompt optimised for this classification task.

**FR18:** Captured agent turn text shall be passed to the existing summarisation service for turn-level and command-level summary generation.

**FR19:** Command summaries generated from real content shall feed into the existing priority scoring service for cross-project ranking.

### Hook Configuration

**FR20:** The hook installer shall configure Notification hooks with matchers for `elicitation_dialog`, `permission_prompt`, and `idle_prompt`.

**FR21:** The hook installer shall configure PostToolUse hooks to send tool completion events to the Headspace server.

**FR22:** All hook commands shall send the full stdin JSON payload (including `session_id`, `transcript_path`, `cwd`, and event-specific fields) to the Headspace server via HTTP POST.

**FR23:** Hook commands shall run asynchronously (`async: true`) where they do not need to control Claude Code's behavior, to avoid blocking agent execution.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Hook event processing shall not block Claude Code agent execution. All hooks that POST to Headspace shall use `async: true` or complete within 1 second.

**NFR2:** Transcript file reading shall use incremental parsing (track file position) to avoid re-reading the entire file on each Stop event.

**NFR3:** The inference question classifier shall use the same rate limiting and caching infrastructure as existing inference calls.

**NFR4:** All new database operations shall use the existing session/transaction patterns to avoid FK race conditions (as fixed in the EventWriter).

**NFR5:** All new endpoints and services shall have unit tests, route tests, and integration tests following the existing three-tier test architecture.

---

## 6. UI Overview

No new UI elements required. The existing dashboard card states already support:
- **PROCESSING** — blue indicator, shows activity
- **INPUT NEEDED / AWAITING_INPUT** — orange indicator, shows "Input needed"
- **COMPLETE** — green indicator, shows completion

The change is that these states will now be reached reliably via the new hook and transcript signals, and the card content will show actual agent text and summaries rather than empty placeholders.

---

## 7. Configuration Changes

```yaml
file_watcher:
  polling_interval: 2
  reconciliation_interval: 60
  awaiting_input_timeout: 10    # Seconds before inference check on stalled transcript
```

---

## 8. Technical Context (for implementers)

### Hook Event Flow

```
HOOK-DRIVEN (instant, deterministic):
  Notification(elicitation_dialog)     → AWAITING_INPUT
  Notification(permission_prompt)      → AWAITING_INPUT
  Notification(idle_prompt)            → AWAITING_INPUT
  PostToolUse(AskUserQuestion)         → PROCESSING (user answered)
  PostToolUse(*) when AWAITING_INPUT   → PROCESSING (tool completed)
  Stop                                 → COMPLETE

TRANSCRIPT-DRIVEN (file watcher pipeline):
  New transcript entry detected        → regex check immediately
  Regex matches question pattern       → AWAITING_INPUT (high confidence)
  Regex no match + no activity
    within awaiting_input_timeout      → send to inference
  Inference says "question"            → AWAITING_INPUT
  Inference says "not a question"      → stay PROCESSING
```

### Key Integration Points

- **Hook endpoints:** `routes/hooks.py` — new endpoints for notification and PostToolUse events
- **Hook receiver:** `services/hook_receiver.py` — process new event types
- **Lifecycle bridge:** `services/hook_lifecycle_bridge.py` — AWAITING_INPUT transitions
- **Command lifecycle:** `services/command_lifecycle.py` — state transitions with text content
- **File watcher:** `services/file_watcher.py` — content pipeline upgrade
- **Intent detector:** `services/intent_detector.py` — regex question detection (existing patterns)
- **Inference service:** `services/inference_service.py` — question classification
- **Summarisation:** `services/summarisation_service.py` — summaries from real content
- **Priority scoring:** `services/priority_scoring.py` — rankings from real summaries
- **Agent model:** `models/agent.py` — add transcript_path field

### Existing Patterns to Follow

- Event writing: pass caller's DB session (FK race fix from EventWriter)
- Async inference: thread pool with Flask app context
- SSE broadcasting: emit state change events for dashboard updates
- Hook installer: shell script in `bin/install-hooks.sh`

### Claude Code Hook Payload Reference

All hooks receive via stdin JSON:
- `session_id` — session identifier (for agent correlation)
- `transcript_path` — path to `.jsonl` transcript file
- `cwd` — working directory
- `permission_mode` — current permission mode
- `hook_event_name` — event type

Notification-specific: `message`, `title`, `notification_type`
PostToolUse-specific: `tool_name`, `tool_input`, `tool_response`, `tool_use_id`
