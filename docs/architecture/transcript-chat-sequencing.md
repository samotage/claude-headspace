# Transcript & Chat Sequencing

## Overview

Claude Headspace uses a three-phase pipeline to deliver Claude Code conversation
turns to the voice chat and dashboard in correct chronological order. The Claude
Code JSONL transcript file is the ground truth for conversation timing. The
PostgreSQL database is the single source of truth for display. SSE pushes all
changes to connected clients.

## The Three-Phase Pipeline

### Phase 1: Immediate (Hook Event)

When Claude Code performs an action, it fires a lifecycle hook to the Headspace
server. The hook receiver creates a Turn record in the database with
`timestamp = now()` (server time) as the best available approximation. The turn
is broadcast immediately via SSE `turn_created` event. The voice chat renders
the turn instantly for a snappy experience.

At this point the timestamp is approximate — it reflects when the server
processed the hook, not when the action occurred in the Claude Code conversation.

**Implementation:** `hook_receiver.py` — `process_stop()`, `process_user_prompt_submit()`,
and `_handle_awaiting_input()` all create Turn records with `datetime.now(timezone.utc)`
and broadcast via `_broadcast_turn_created()`.

### Phase 2: Reconciliation (Transcript Read)

The file watcher service reads the Claude Code JSONL transcript file at a
configurable interval (default: 2 seconds via `file_watcher.polling_interval`).
Each JSONL entry contains a timestamp from Claude Code reflecting when the
conversation event actually occurred.

The transcript reconciler matches JSONL entries against existing Turn records
in the database using content-based hashing:

- **Match found:** The Turn's `timestamp` is UPDATED to the JSONL timestamp and
  `timestamp_source` is set to `"jsonl"`. This corrects the Phase 1 approximation
  to the real conversation time.
- **No match:** A new Turn is CREATED with the JSONL timestamp. This captures
  events that hooks missed (hooks can be unreliable).

Content hashing uses the first 200 characters of normalised text combined with
the actor (`user` or `agent`), producing a SHA-256 prefix. Matches are searched
within a 30-second time window to bound the search space.

**Implementation:** `transcript_reconciler.py` — `reconcile_transcript_entries()`
performs matching via `_content_hash()`, updates or creates Turn records, and
commits changes. `transcript_reader.py` — `read_new_entries_from_position()`
provides incremental reading with byte-position tracking. `_parse_jsonl_timestamp()`
handles both ISO string and Unix epoch timestamp formats.

### Phase 3: Correction Broadcast

After reconciliation, the server broadcasts SSE events for all changes:

- `turn_updated` events for turns whose timestamps were corrected (includes
  the Turn's database ID so the client can update the existing bubble)
- `turn_created` events for newly discovered turns (full turn data)

The voice chat receives these events and:
- Updates timestamps on existing bubbles via `data-timestamp` attribute
- Inserts new bubbles at the correct chronological position
- Reorders any bubbles that are now in the wrong position due to timestamp
  corrections

**Implementation:** `transcript_reconciler.py` — `broadcast_reconciliation()`
sends `turn_updated` (with `update_type: "timestamp_correction"`) and
`turn_created` events via the Broadcaster service. On the client,
`voice-app.js` — `_handleTurnUpdated()` updates the `data-timestamp` attribute
and calls `_reorderBubble()`, which checks sibling positions and re-inserts
the bubble at the correct chronological position via `_insertBubbleOrdered()`.

## Ordering Key

**Turn.timestamp** is the canonical ordering field for conversation display.
It is NOT the database insertion time — it is the actual conversation time,
corrected by the JSONL transcript during Phase 2 reconciliation.

The database auto-increment ID (`Turn.id`) reflects insertion order and is used
as a stable identifier for linking SSE events to DOM elements. It is NOT used
for display ordering.

## Timestamp Sources

The `Turn.timestamp_source` column tracks where the timestamp came from:

| Turn Origin | Initial Timestamp | `timestamp_source` | After Reconciliation |
|-------------|-------------------|--------------------|---------------------|
| Hook event (agent action) | `datetime.now()` (server time) | `"server"` | JSONL timestamp → `"jsonl"` |
| Progress capture (transcript read) | JSONL timestamp | `"jsonl"` | Already correct |
| User respond (dashboard/voice) | `datetime.now()` (user action time) | `"server"` | Not reconciled (user actions are real-time) |
| File watcher (new entry, no hook match) | JSONL timestamp | `"jsonl"` | Already correct |

The `Turn.jsonl_entry_hash` column stores the content hash used for deduplication
matching, preventing the same JSONL entry from being processed twice.

## SSE Event Types for Chat

| Event | Purpose | Key Fields |
|-------|---------|------------|
| `turn_created` | New turn available | `turn_id`, `text`, `actor`, `intent`, `timestamp`, `command_id`, `tool_input` |
| `turn_updated` | Timestamp correction | `turn_id`, `timestamp`, `update_type` |
| `state_changed` | Agent state transition | `agent_id`, `new_state` |
| `gap` | Server detected dropped events | `message` |

## Client Rendering

The voice chat (`voice-app.js`) uses a single rendering approach:

1. **Initial load:** Fetch transcript from API → render all turns in timestamp order
2. **SSE `turn_created`:** Insert new bubble at correct chronological position
   via `_insertBubbleOrdered()`, which walks existing bubbles to find the right
   insertion point based on `data-timestamp`
3. **SSE `turn_updated`:** Update existing bubble's `data-timestamp` attribute,
   then call `_reorderBubble()` to check and correct DOM position
4. **SSE `gap` / reconnect:** Re-fetch transcript from API, reconcile DOM
   against returned turns (update timestamps on existing bubbles, insert missing ones)

There is NO periodic polling. SSE is the primary delivery mechanism. Gap
recovery handles missed events.

Progress bubbles are collapsed (hidden via CSS `display:none`) when a terminal
intent (COMPLETION or END_OF_COMMAND) arrives for the same command, rather than being
removed from the DOM. This preserves DOM stability and prevents re-rendering artefacts.

## Diagram

```
Claude Code
  │
  ├──────────────────────────┐
  │                          │
  │  writes to               │  fires hooks
  │                          │
  ▼                          ▼
JSONL File               Hook Endpoint
  │                          │
  │  read by                 │  Phase 1: create Turn
  │                          │  with timestamp=now()
  ▼                          │
File Watcher                 ├──► DB (Turn record)
  │                          │
  │  Phase 2: reconcile      │
  ▼                          │
Transcript Reconciler        │
  │                          │
  │  match content hash      │
  │  correct timestamps      │
  │                          │
  ├──► DB (update Turn)      │
  │                          │
  │  Phase 3: broadcast      │
  │                          │
  ├──► SSE turn_updated ─────┤──► SSE turn_created
  │                          │
  ▼                          ▼
Voice Chat Client (timestamp-ordered DOM)
```
