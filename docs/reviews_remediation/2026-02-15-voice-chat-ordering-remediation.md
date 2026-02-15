# Voice Chat Ordering Remediation — Implementation Plan

**Date:** 2026-02-15T09:45:00+13:00
**Status:** Approved for implementation
**Scope:** Event Processing, Database, Front End, Documentation
**Agents:** 4-agent team (event-processing, database, front-end, technical-writer)

---

## Executive Summary

The voice chat (`/voice`) displays conversation turns out of chronological order. Root cause: a dual-path rendering architecture where SSE events and periodic transcript polling race to append turns at the bottom of the DOM, combined with progress collapse that removes DOM elements and triggers re-rendering at wrong positions.

The fix is architectural: make the database the single source of truth with correct conversation timestamps, push all changes via SSE, and have the client render from authoritative data rather than maintaining complex client-side dedup state.

### Core Principle

**The Claude Code JSONL transcript is the ground truth for conversation ordering.** The JSONL entries contain timestamps reflecting when events actually happened. The database must reflect these timestamps. The client must render in timestamp order.

### Three-Phase Event Pipeline

1. **Phase 1 (Immediate):** Hook event arrives → Create Turn with `turn_at=now()` → Broadcast SSE → Client renders immediately
2. **Phase 2 (Reconciliation):** File watcher reads JSONL transcript → Dedup matches entries to existing Turns → UPDATE timestamps to JSONL values, CREATE new Turns for unmatched entries
3. **Phase 3 (Correction):** Broadcast SSE updates with corrected timestamps → Client updates existing bubbles and reorders if needed

---

## Problem Analysis

### Current Architecture (Broken)

```
CLIENT has TWO rendering paths:
  Path 1: SSE turn_created → _handleTurnCreated() → renders AGENT turns directly at bottom
          (ignores USER turns entirely)
  Path 2: Transcript polling (6 triggers) → _fetchTranscriptForChat() → filters "new" turns
          → appends at bottom

Both paths use messagesEl.appendChild() — always at the bottom.
Dedup via _chatRenderedTurnIds Set + DOM resilience check + pending send TTL matching.
Progress collapse removes DOM elements but keeps IDs in dedup set.
DOM resilience check sees missing elements → re-renders collapsed turns at BOTTOM (wrong position).
```

### Specific Bugs Identified

1. **Progress Collapse + DOM Resilience:** When a COMPLETION turn arrives, `_collapseProgressBubbles()` (voice-app.js:1376) removes PROGRESS bubble DOM elements but keeps their IDs in `_chatRenderedTurnIds`. On next transcript fetch, the DOM resilience check (voice-app.js:2669) sees the ID in the set but no DOM element → clears the ID → re-renders the PROGRESS turn at the bottom, AFTER the COMPLETION turn.

2. **SSE Races Transcript Fetch:** SSE delivers turn N+1 directly, rendered at bottom. Transcript fetch discovers turn N (missed by SSE) → appends at bottom AFTER N+1.

3. **User Turns Invisible to SSE:** `_handleTurnCreated` (voice-app.js:2357) returns early for user turns (`if (data.actor === 'user') return`). User turns only appear via transcript polling. If an agent turn arrived via SSE first, the user turn appears after it.

4. **Two Voice Bridge Paths Don't Broadcast:** `send_voice_command()` (voice_bridge.py:393) and `upload_file()` (voice_bridge.py:589) create Turns but only broadcast `card_refresh`, NOT `turn_created`. The client has no choice but to poll.

5. **Hardcoded 8s Polling Interval:** The sync timer (voice-app.js:984) is hardcoded at 8000ms, ignoring the `file_watcher.polling_interval: 2` config value.

6. **Turn.timestamp = Insertion Time, Not Conversation Time:** All Turn creation paths use `datetime.now(UTC)` (the SQLAlchemy default), not the JSONL transcript timestamp. The JSONL parser (`jsonl_parser.py:116`) extracts timestamps from JSONL entries but they're never propagated to Turn records.

### Timestamp Ordering Problem

DB auto-increment ID reflects insertion order, not conversation order:
```
t=0.000s  Claude Code writes response to JSONL (timestamp: 09:30:00.000)
t=0.150s  Claude Code fires stop hook
t=0.200s  Hook receiver creates Turn id=100 (timestamp=now()=09:30:00.200)
t=2.000s  File watcher reads JSONL, finds PROGRESS text (timestamp: 09:29:59.800)
          Creates Turn id=101 (timestamp=now()=09:30:02.000)

DB order: id=100, id=101
Actual conversation order: id=101 happened BEFORE id=100
Both timestamps are wrong — should be JSONL timestamps
```

---

## Implementation Plan

### Agent 1: Database

#### Task DB-1: Add `turn_at` Column to Turn Model

**File:** `src/claude_headspace/models/turn.py`

**Current state (lines 51-55):**
```python
# Temporal validation (turn.timestamp >= task.started_at) is enforced at
# application level — cross-table CHECK constraints are not supported in PostgreSQL.
timestamp: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
)
```

**Change:** The existing `timestamp` column serves as `turn_at`. No new column needed — but its semantics change:
- **Before:** Server insertion time (always `datetime.now()`)
- **After:** Canonical conversation time (from JSONL when available, `datetime.now()` as initial approximation for hook-created turns, updated to JSONL time during reconciliation)

**Action:** No schema change required. The existing `timestamp` column is already `DateTime(timezone=True), nullable=False, index=True`. Its population logic changes in the event processing layer.

#### Task DB-2: Fix Transcript API Ordering

**File:** `src/claude_headspace/routes/voice_bridge.py`

**Current state (line 804):**
```python
query = query.order_by(Turn.id.desc()).limit(limit + 1)
```

**Change to:**
```python
query = query.order_by(Turn.timestamp.desc()).limit(limit + 1)
```

This ensures the transcript API returns turns in conversation-time order, not insertion order. The existing index `ix_turns_task_id_timestamp` (turn.py:83) already covers this.

**Also update** the `before` pagination parameter. Currently (line 800-801):
```python
if before:
    query = query.filter(Turn.id < before)
```

This needs to change to timestamp-based pagination since ID order no longer equals conversation order. The `before` parameter should accept a timestamp or the API should use cursor-based pagination with `(timestamp, id)` composite for deterministic ordering of turns with identical timestamps.

**Recommended approach:** Use `(timestamp, id)` composite ordering:
```python
query = query.order_by(Turn.timestamp.desc(), Turn.id.desc()).limit(limit + 1)
```
And for pagination:
```python
if before_timestamp and before_id:
    query = query.filter(
        db.or_(
            Turn.timestamp < before_timestamp,
            db.and_(Turn.timestamp == before_timestamp, Turn.id < before_id)
        )
    )
```

#### Task DB-3: Add `timestamp_source` Column (Optional but Recommended)

**File:** `src/claude_headspace/models/turn.py`

Add a column to track where the timestamp came from, enabling debugging and audit:

```python
timestamp_source: Mapped[str | None] = mapped_column(
    String(20), nullable=True, default="server"
)
# Values: "server" (datetime.now initial), "jsonl" (reconciled from transcript), "user" (user action)
```

**Migration:** Create via `flask db migrate -m "add turn timestamp_source column"`

#### Task DB-4: Verify Turn Relationship Ordering

**File:** `src/claude_headspace/models/task.py`

**Current state (line 66):**
```python
turns: Mapped[list["Turn"]] = relationship("Turn", ..., order_by="Turn.timestamp")
```

This is already correct — orders by timestamp. Verify it works correctly when timestamps are updated (Phase 2 reconciliation). SQLAlchemy relationship ordering is evaluated at query time, so updated timestamps will be reflected.

#### Task DB-5: Add Transcript Sequence Fields (Recommended)

To support robust dedup between hook-created turns and JSONL entries, add:

```python
jsonl_entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
```

This stores a hash of the JSONL entry content (e.g., SHA-256 of `type + role + text[:200]`) to match hook-created turns against transcript entries during reconciliation. Without this, dedup relies on fuzzy text matching which is fragile.

---

### Agent 2: Event Processing

#### Task EP-1: Extend TranscriptEntry with Timestamp

**File:** `src/claude_headspace/services/transcript_reader.py`

**Current state (lines 19-25):**
```python
@dataclass
class TranscriptEntry:
    type: str
    role: str | None = None
    content: str | None = None
```

**Change to:**
```python
@dataclass
class TranscriptEntry:
    type: str
    role: str | None = None
    content: str | None = None
    timestamp: datetime | None = None  # JSONL entry timestamp
    raw_data: dict | None = None       # Full JSONL entry for dedup hashing
```

**Update `read_new_entries_from_position()`** (lines 215-257) to extract timestamps:

```python
# In the parsing loop (around line 246):
from datetime import datetime, timezone

role, text = _extract_text(data)

# Extract JSONL timestamp
ts = None
ts_raw = data.get("timestamp")
if ts_raw:
    try:
        if isinstance(ts_raw, str):
            if ts_raw.endswith("Z"):
                ts_raw = ts_raw[:-1] + "+00:00"
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        elif isinstance(ts_raw, (int, float)):
            ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
    except (ValueError, OSError):
        pass

entries.append(TranscriptEntry(
    type=data.get("type", ""),
    role=role,
    content=text,
    timestamp=ts,
    raw_data=data,
))
```

**Also update `read_transcript_file()`** (lines 61-144) to return timestamps. This function is used by the stop hook to get agent text. Change the return type to include the timestamp of the last assistant entry:

```python
@dataclass
class TranscriptReadResult:
    success: bool
    text: str = ""
    error: str | None = None
    timestamp: datetime | None = None  # JSONL timestamp of the last entry
```

In the backwards-walking loop, capture the timestamp from the first (most recent) assistant entry found:

```python
# Around line 124-127, when collecting assistant text:
_role, text = _extract_text(data)
if text:
    parts.append(text)
    if result_timestamp is None:  # Capture timestamp from most recent entry
        ts_raw = data.get("timestamp")
        if ts_raw:
            # parse same as above
            result_timestamp = parsed_ts
```

#### Task EP-2: Propagate JSONL Timestamps in Progress Capture

**File:** `src/claude_headspace/services/hook_receiver.py`

**Function:** `_capture_progress_text_impl()` (lines 216-280)

This function reads transcript entries and creates PROGRESS turns. Currently it discards timestamps.

**Current state (lines 252-262):**
```python
for text in new_texts:
    state.append_progress_text(agent.id, text)
    turn = Turn(
        task_id=current_task.id,
        actor=TurnActor.AGENT,
        intent=TurnIntent.PROGRESS,
        text=text,
    )
    db.session.add(turn)
    db.session.flush()
```

**Change:** Store the entries (not just texts) so timestamps are available:

```python
# Change new_texts collection (around line 244-248) to preserve entries:
progress_entries = []
for entry in entries:
    if entry.role == "assistant" and entry.content and len(entry.content.strip()) >= MIN_PROGRESS_LEN:
        progress_entries.append(entry)

# Change turn creation loop:
for entry in progress_entries:
    text = entry.content.strip()
    state.append_progress_text(agent.id, text)
    turn = Turn(
        task_id=current_task.id,
        actor=TurnActor.AGENT,
        intent=TurnIntent.PROGRESS,
        text=text,
        timestamp=entry.timestamp or datetime.now(timezone.utc),  # Use JSONL timestamp
        timestamp_source="jsonl" if entry.timestamp else "server",
    )
    db.session.add(turn)
    db.session.flush()
```

**Also update the broadcast** (lines 264-275) to use the correct timestamp:

```python
get_broadcaster().broadcast("turn_created", {
    ...
    "timestamp": turn.timestamp.isoformat(),  # Use the turn's actual timestamp, not datetime.now()
    ...
})
```

#### Task EP-3: Implement JSONL Reconciliation Pipeline

**New file:** `src/claude_headspace/services/transcript_reconciler.py`

This is the core of Phase 2. When the file watcher reads new JSONL entries, the reconciler:

1. Matches JSONL entries against existing Turns in the DB
2. Updates timestamps on matched Turns (hook-created turns get corrected)
3. Creates new Turns for unmatched entries
4. Broadcasts SSE updates for all changes

**Design:**

```python
"""Reconcile JSONL transcript entries against database Turn records.

Implements Phase 2 of the three-phase event pipeline:
- Phase 1: Hook creates Turn with timestamp=now() (approximate)
- Phase 2: THIS — reconciles against JSONL entries, corrects timestamps
- Phase 3: Broadcasts SSE updates for corrections
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta

from ..database import db
from ..models.turn import Turn, TurnActor, TurnIntent

logger = logging.getLogger(__name__)

# Maximum time window to search for matching hook-created turns
MATCH_WINDOW_SECONDS = 30


def reconcile_transcript_entries(agent, task, entries):
    """Reconcile JSONL transcript entries against existing Turns.

    Args:
        agent: Agent record
        task: Current Task record
        entries: List of TranscriptEntry objects with timestamps

    Returns:
        dict with keys:
            updated: list of (turn_id, old_timestamp, new_timestamp) tuples
            created: list of turn_id for newly created turns
    """
    result = {"updated": [], "created": []}

    # Get recent turns for this task within the match window
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=MATCH_WINDOW_SECONDS)
    recent_turns = (
        Turn.query
        .filter(Turn.task_id == task.id, Turn.timestamp >= cutoff)
        .order_by(Turn.timestamp.asc())
        .all()
    )

    # Build index of recent turns by content hash for matching
    turn_index = {}
    for turn in recent_turns:
        key = _content_hash(turn.actor.value, turn.text)
        if key not in turn_index:
            turn_index[key] = turn

    for entry in entries:
        if not entry.content or not entry.content.strip():
            continue

        actor = "user" if entry.role == "user" else "agent"
        content_key = _content_hash(actor, entry.content.strip())

        matched_turn = turn_index.pop(content_key, None)

        if matched_turn and entry.timestamp:
            # Phase 2: Update timestamp to JSONL value
            old_ts = matched_turn.timestamp
            if old_ts != entry.timestamp:
                matched_turn.timestamp = entry.timestamp
                matched_turn.timestamp_source = "jsonl"
                result["updated"].append((matched_turn.id, old_ts, entry.timestamp))
        elif not matched_turn:
            # New entry not seen via hooks — create Turn
            turn = Turn(
                task_id=task.id,
                actor=TurnActor.USER if actor == "user" else TurnActor.AGENT,
                intent=_infer_intent(actor, entry),
                text=entry.content.strip(),
                timestamp=entry.timestamp or datetime.now(timezone.utc),
                timestamp_source="jsonl" if entry.timestamp else "server",
            )
            db.session.add(turn)
            db.session.flush()
            result["created"].append(turn.id)

    if result["updated"] or result["created"]:
        db.session.commit()

    return result


def _content_hash(actor, text):
    """Generate a content-based hash for dedup matching."""
    # Use first 200 chars to handle truncation differences
    normalized = f"{actor}:{text[:200].strip().lower()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _infer_intent(actor, entry):
    """Infer turn intent from transcript entry."""
    if actor == "user":
        return TurnIntent.COMMAND
    return TurnIntent.PROGRESS  # Default for unmatched agent entries
```

**Integration point:** This reconciler is called from the file watcher's turn detection callback or from `_capture_progress_text_impl` after reading new entries.

#### Task EP-4: Broadcast Timestamp Corrections (Phase 3)

**File:** `src/claude_headspace/services/hook_receiver.py` (or the new reconciler)

After Phase 2 reconciliation, broadcast SSE events for corrections:

```python
def broadcast_reconciliation(agent, reconciliation_result):
    """Broadcast SSE updates after transcript reconciliation."""
    from .broadcaster import get_broadcaster
    broadcaster = get_broadcaster()

    # Broadcast timestamp corrections for existing turns
    for turn_id, old_ts, new_ts in reconciliation_result["updated"]:
        broadcaster.broadcast("turn_updated", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "turn_id": turn_id,
            "timestamp": new_ts.isoformat(),
            "update_type": "timestamp_correction",
        })

    # Broadcast newly created turns
    for turn_id in reconciliation_result["created"]:
        turn = db.session.get(Turn, turn_id)
        if turn:
            broadcaster.broadcast("turn_created", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "text": turn.text,
                "actor": turn.actor.value,
                "intent": turn.intent.value,
                "task_id": turn.task_id,
                "turn_id": turn.id,
                "timestamp": turn.timestamp.isoformat(),
            })
```

**New SSE event type: `turn_updated`** — used to push timestamp corrections to the client without re-sending the full turn content. The client uses `turn_id` to find the existing bubble and update its timestamp.

#### Task EP-5: Fix Missing SSE Broadcasts

**File:** `src/claude_headspace/routes/voice_bridge.py`

Two turn creation paths don't broadcast `turn_created`:

**Path 1: `send_voice_command()`** (around line 393-427)

After the existing `db.session.commit()` (line 420) and `broadcast_card_refresh` (line 427), add:

```python
# Broadcast turn_created for voice command
from ..services.broadcaster import get_broadcaster
get_broadcaster().broadcast("turn_created", {
    "agent_id": agent.id,
    "project_id": agent.project_id,
    "text": text,
    "actor": "user",
    "intent": "answer",
    "task_id": current_task.id if current_task else None,
    "turn_id": turn.id,
    "timestamp": turn.timestamp.isoformat(),
})
```

**Path 2: `upload_file()`** (around line 589-615)

After the existing `db.session.commit()` (line 610) and `broadcast_card_refresh` (line 615), add similar broadcast.

#### Task EP-6: Include turn_id in ALL SSE Broadcasts

Audit all `_broadcast_turn_created()` calls to ensure `turn_id` is always included. Currently some paths may not include it (e.g., when broadcasting from a deferred path where the turn object is out of scope).

**Files to audit:**
- `src/claude_headspace/services/hook_receiver.py` — `_broadcast_turn_created()` (lines 143-161)
- `src/claude_headspace/services/hook_deferred_stop.py` — `_broadcast_turn_created()` (lines 68-86)
- `src/claude_headspace/routes/respond.py` — `_broadcast_state_change()` (lines 406-431)

Ensure every `turn_created` broadcast includes: `turn_id`, `timestamp`, `actor`, `intent`, `text`, `agent_id`, `project_id`, `task_id`.

---

### Agent 3: Front End

#### Task FE-1: Register New SSE Event Handler for `turn_updated`

**File:** `static/voice/voice-api.js`

Add a new event listener alongside the existing ones (around line 230):

```javascript
// Existing listeners (lines 209-259):
_sse.addEventListener('turn_created', function(e) { ... });
// ADD:
_sse.addEventListener('turn_updated', function(e) {
    var data = JSON.parse(e.data);
    if (_onTurnUpdated) _onTurnUpdated(data);
});
```

Add callback registration (alongside existing pattern around line 280):
```javascript
var _onTurnUpdated = null;
// In the return object:
onTurnUpdated: function(fn) { _onTurnUpdated = fn; },
```

**File:** `static/voice/voice-app.js`

Register the handler (around line 2885):
```javascript
VoiceAPI.onTurnUpdated(_handleTurnUpdated);
```

#### Task FE-2: Implement `_handleTurnUpdated` for Timestamp Corrections

**File:** `static/voice/voice-app.js`

New function:

```javascript
function _handleTurnUpdated(data) {
    if (_currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(_targetAgentId, 10)) return;

    if (data.update_type === 'timestamp_correction' && data.turn_id && data.timestamp) {
        var messagesEl = document.getElementById('chat-messages');
        if (!messagesEl) return;

        var bubble = messagesEl.querySelector('[data-turn-id="' + data.turn_id + '"]');
        if (!bubble) return;

        // Update the stored timestamp on the bubble element
        bubble.setAttribute('data-timestamp', data.timestamp);

        // Reorder: move this bubble to its correct chronological position
        _reorderBubble(messagesEl, bubble, data.timestamp);

        // Update any visible timestamp separator if needed
        _refreshTimestampSeparators(messagesEl);
    }
}
```

#### Task FE-3: Implement Ordered Bubble Insertion

**File:** `static/voice/voice-app.js`

Replace the current `messagesEl.appendChild(el)` pattern in `_renderChatBubble` (line 1368) with ordered insertion:

```javascript
function _insertBubbleOrdered(messagesEl, el) {
    // el must have data-timestamp attribute set during creation
    var newTs = el.getAttribute('data-timestamp');
    if (!newTs) {
        // Fallback: append at end if no timestamp
        messagesEl.appendChild(el);
        return;
    }
    var newTime = new Date(newTs).getTime();

    // Walk backwards through existing bubbles to find insertion point
    var bubbles = messagesEl.querySelectorAll('.chat-bubble[data-timestamp]');
    for (var i = bubbles.length - 1; i >= 0; i--) {
        var existingTime = new Date(bubbles[i].getAttribute('data-timestamp')).getTime();
        if (existingTime <= newTime) {
            // Insert after this bubble (and after any following timestamp separator)
            var insertAfter = bubbles[i];
            // Skip past any non-bubble elements (timestamp separators, task separators)
            while (insertAfter.nextElementSibling &&
                   !insertAfter.nextElementSibling.classList.contains('chat-bubble')) {
                insertAfter = insertAfter.nextElementSibling;
            }
            if (insertAfter.nextSibling) {
                messagesEl.insertBefore(el, insertAfter.nextSibling);
            } else {
                messagesEl.appendChild(el);
            }
            return;
        }
    }
    // No existing bubble has earlier timestamp — prepend
    messagesEl.insertBefore(el, messagesEl.firstChild);
}
```

**Update `_renderChatBubble`** (line 1357-1369) to use this:
```javascript
function _renderChatBubble(turn, prevTurn, forceRender) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var isTerminal = (turn.intent === 'completion' || turn.intent === 'end_of_task');
    if (isTerminal && turn.task_id) {
        _collapseProgressBubbles(messagesEl, turn.task_id);
    }
    var el = _createBubbleEl(turn, prevTurn, forceRender);
    if (el) _insertBubbleOrdered(messagesEl, el);
}
```

**Update `_createBubbleEl`** (line 1385) to set `data-timestamp` on the bubble:
```javascript
// Around line 1430, after creating the bubble div:
bubble.setAttribute('data-turn-id', turn.id);
bubble.setAttribute('data-timestamp', turn.timestamp || new Date().toISOString());
```

#### Task FE-4: Implement `_reorderBubble` for Timestamp Corrections

**File:** `static/voice/voice-app.js`

```javascript
function _reorderBubble(messagesEl, bubble, newTimestamp) {
    var newTime = new Date(newTimestamp).getTime();

    // Check if bubble is already in correct position
    var prev = bubble.previousElementSibling;
    var next = bubble.nextElementSibling;

    var prevOk = !prev || !prev.classList.contains('chat-bubble') ||
                 new Date(prev.getAttribute('data-timestamp') || 0).getTime() <= newTime;
    var nextOk = !next || !next.classList.contains('chat-bubble') ||
                 new Date(next.getAttribute('data-timestamp') || Infinity).getTime() >= newTime;

    if (prevOk && nextOk) return; // Already in correct position

    // Remove from current position
    var parent = bubble.parentNode;
    parent.removeChild(bubble);

    // Re-insert at correct position
    _insertBubbleOrdered(parent, bubble);
}
```

#### Task FE-5: Replace Polling with SSE-Primary Architecture

**File:** `static/voice/voice-app.js`

**Remove the 8-second sync timer:**

Current code (lines 974-984):
```javascript
function _startChatSyncTimer() {
    _stopChatSyncTimer();
    _chatSyncTimer = setInterval(function () {
        if (_currentScreen !== 'chat' || !_targetAgentId) {
            _stopChatSyncTimer();
            return;
        }
        _fetchTranscriptForChat();
    }, 8000);
}
```

**Replace with:** No periodic timer. SSE is the primary data delivery. Keep `_fetchTranscriptForChat` for:
- Initial chat load (already in `_showChatScreen`)
- Gap recovery (already in `_handleGap`)
- SSE reconnect (one-time catch-up)

**Remove the response catch-up timers:**

Current code (lines 1005-1023): `_scheduleResponseCatchUp()` with 7 escalating delays.

**Replace with:** Remove entirely. SSE `turn_created` events deliver agent responses. If SSE drops, the gap handler catches up.

**Remove from `_handleChatSSE`** the transcript fetch trigger (line 2289):
```javascript
// REMOVE this line — SSE events handle turns directly now:
_fetchTranscriptForChat();
```

State changes (`state_changed` events) should update the state pill and typing indicator but NOT trigger a transcript fetch. Turn delivery is handled by `turn_created` SSE events.

#### Task FE-6: Simplify `_handleTurnCreated` — Remove User Turn Filter

**File:** `static/voice/voice-app.js`

**Current state (line 2357):**
```javascript
if (data.actor === 'user') return;
```

**Remove this line.** All turns (user AND agent) should be rendered via SSE. User turns are now broadcast by all server paths (after EP-5 fixes).

Also remove the MULTI-Q DEBUG logging added during testing (lines 2342-2351) and elsewhere in the file.

#### Task FE-7: Replace `_chatRenderedTurnIds` with Simple ID Tracking

**File:** `static/voice/voice-app.js`

**Remove:**
- `_chatRenderedTurnIds` Set (line 25)
- All references to `_chatRenderedTurnIds.has()`, `.add()`, `.delete()`, `.clear()`
- The DOM resilience check (lines 2664-2674)
- Pending send TTL matching (lines 2676-2694)
- `PENDING_SEND_TTL_MS` constant
- `_chatPendingUserSends` array and all references

**Replace with:** Simple `_lastSeenTurnId` tracking:

```javascript
var _lastSeenTurnId = 0;  // Highest turn ID seen from transcript fetch
```

In `_handleTurnCreated`:
```javascript
// Skip if already rendered (turn_id based)
var turnId = parseInt(data.turn_id, 10);
if (!isNaN(turnId) && turnId <= _lastSeenTurnId) {
    // Already in DOM from transcript fetch — skip
    var existing = messagesEl.querySelector('[data-turn-id="' + turnId + '"]');
    if (existing) return;
}
```

In `_fetchTranscriptForChat` (for initial load and gap recovery):
```javascript
// After rendering all turns from transcript:
var maxId = 0;
for (var i = 0; i < turns.length; i++) {
    if (turns[i].id > maxId) maxId = turns[i].id;
}
_lastSeenTurnId = maxId;
```

#### Task FE-8: CSS-Only Progress Collapse

**File:** `static/voice/voice-app.js`

**Current state (lines 1376-1383):**
```javascript
function _collapseProgressBubbles(container, taskId) {
    var bubbles = container.querySelectorAll('.chat-bubble[data-task-id="' + taskId + '"]');
    for (var i = 0; i < bubbles.length; i++) {
        if (bubbles[i].querySelector('.progress-intent')) {
            bubbles[i].remove();  // REMOVES from DOM — causes ordering bugs
        }
    }
}
```

**Change to CSS-only:**
```javascript
function _collapseProgressBubbles(container, taskId) {
    var bubbles = container.querySelectorAll('.chat-bubble[data-task-id="' + taskId + '"]');
    for (var i = 0; i < bubbles.length; i++) {
        if (bubbles[i].querySelector('.progress-intent')) {
            bubbles[i].classList.add('collapsed');  // CSS hide, DOM untouched
        }
    }
}
```

**File:** `static/voice/voice.css` (or `static/css/src/input.css` if Tailwind)

Add:
```css
.chat-bubble.collapsed {
    display: none;
}
```

This preserves DOM structure and ordering. The bubble is hidden but stays in the DOM, so no re-rendering can put it in the wrong position.

#### Task FE-9: Simplify `_fetchTranscriptForChat` for Gap Recovery Only

**File:** `static/voice/voice-app.js`

The current function (lines 2619-2730) is 110 lines of complexity. Simplify it to:

```javascript
function _fetchTranscriptForChat() {
    if (!_targetAgentId) return;
    if (_fetchInFlight) return;
    _fetchInFlight = true;

    var agentId = _targetAgentId;
    VoiceAPI.getTranscript(agentId).then(function (resp) {
        _fetchInFlight = false;
        if (agentId !== _targetAgentId) return;

        var turns = resp.turns || [];
        var messagesEl = document.getElementById('chat-messages');
        if (!messagesEl) return;

        // Reconcile: for each turn from transcript, ensure it's in the DOM
        for (var i = 0; i < turns.length; i++) {
            var turn = turns[i];
            var existing = messagesEl.querySelector('[data-turn-id="' + turn.id + '"]');

            if (existing) {
                // Update timestamp if changed (Phase 2 correction)
                var serverTs = turn.timestamp;
                var domTs = existing.getAttribute('data-timestamp');
                if (serverTs && serverTs !== domTs) {
                    existing.setAttribute('data-timestamp', serverTs);
                    _reorderBubble(messagesEl, existing, serverTs);
                }
            } else {
                // New turn — render at correct position
                var prev = i > 0 ? turns[i - 1] : null;
                _renderChatBubble(turn, prev, false);
            }

            // Track highest seen ID
            if (turn.id > _lastSeenTurnId) _lastSeenTurnId = turn.id;
        }

        // Update agent state
        if (resp.agent_state) {
            _chatAgentState = resp.agent_state;
            _updateTypingIndicator();
            _updateChatStatePill();
        }
        if (resp.agent_ended !== undefined) {
            _chatAgentEnded = !!resp.agent_ended;
            _updateEndedAgentUI();
        }

        _scrollChatToBottomIfNear();
    }).catch(function () {
        _fetchInFlight = false;
    });
}
```

This is ~40 lines replacing ~110 lines. No dedup set, no DOM resilience check, no pending send matching. Just: "for each turn in transcript, ensure it's in the DOM at the right position."

#### Task FE-10: Preserve Optimistic User Send UX

**File:** `static/voice/voice-app.js`

Keep the instant user bubble when sending a message. The flow:

1. User sends message → render provisional bubble with `data-turn-id="pending-{timestamp}"` and `data-timestamp=now()`
2. SSE `turn_created` arrives with real `turn_id` → find the provisional bubble by matching actor=user + recent timestamp → promote: update `data-turn-id` to real ID
3. If no SSE confirmation within 10s → mark bubble as failed (add error class)

```javascript
function _renderOptimisticUserBubble(text) {
    var fakeTurnId = 'pending-' + Date.now();
    var turn = {
        id: fakeTurnId,
        actor: 'user',
        intent: 'answer',
        text: text,
        timestamp: new Date().toISOString(),
        task_id: null,
    };
    _renderChatBubble(turn, null, true);
    _scrollChatToBottomIfNear();

    // Set timeout to mark as failed if not confirmed
    setTimeout(function () {
        var el = document.getElementById('chat-messages');
        if (el) {
            var bubble = el.querySelector('[data-turn-id="' + fakeTurnId + '"]');
            if (bubble) bubble.classList.add('send-failed');
        }
    }, 10000);

    return fakeTurnId;
}
```

In `_handleTurnCreated`, when receiving a user turn:
```javascript
if (data.actor === 'user') {
    // Try to promote a pending optimistic bubble
    var pendingBubbles = messagesEl.querySelectorAll('.chat-bubble[data-turn-id^="pending-"]');
    for (var i = pendingBubbles.length - 1; i >= 0; i--) {
        var pb = pendingBubbles[i];
        // Match by recency (within 10s)
        var pendingTs = new Date(pb.getAttribute('data-timestamp')).getTime();
        if (Date.now() - pendingTs < 10000) {
            pb.setAttribute('data-turn-id', data.turn_id);
            pb.setAttribute('data-timestamp', data.timestamp);
            pb.classList.remove('send-failed');
            return; // Promoted — don't create new bubble
        }
    }
    // No matching pending bubble — render normally
}
```

#### Task FE-11: Remove MULTI-Q DEBUG Instrumentation

**File:** `static/voice/voice-app.js`

Remove all `console.log('[MULTI-Q DEBUG]` statements added during testing. These are at approximately:
- Lines 1510-1519 (question option detection)
- Lines 1522-1526 (toolInput.questions check)
- Lines 1531, 1535 (multi-question/single-question decision)
- Lines 1540 (q_options promotion)
- Lines 1548-1553 (final rendering decision)
- Lines 2342-2351 (_handleTurnCreated SSE)
- Lines 2648-2661 (transcript question turn)

**File:** `src/claude_headspace/routes/respond.py`

Remove `[MULTI-Q DEBUG]` logging at lines 274-278 and 285-288.

**File:** `src/claude_headspace/services/hook_receiver.py`

Remove `[MULTI-Q DEBUG]` logging around line 1183.

---

## Dependency Graph

```
DB-1 (timestamp semantics) ──┐
DB-3 (timestamp_source col) ─┤
DB-5 (jsonl_entry_hash col) ─┴── DB migration must run before EP tasks
                                    │
EP-1 (TranscriptEntry + ts) ───────┤
EP-2 (progress capture + ts) ──────┤
EP-3 (reconciliation pipeline) ────┤── All EP tasks depend on DB schema
EP-4 (broadcast corrections) ──────┤
EP-5 (fix missing broadcasts) ─────┤
EP-6 (audit turn_id in SSE) ───────┘
                                    │
                                    ├── FE tasks can start in parallel
FE-1 (turn_updated SSE handler) ───┤   with EP tasks, but need EP-4
FE-2 (_handleTurnUpdated) ─────────┤   and EP-5 for integration testing
FE-3 (ordered insertion) ──────────┤
FE-4 (_reorderBubble) ────────────┤
FE-5 (remove polling) ────────────┤
FE-6 (remove user turn filter) ───┤
FE-7 (replace dedup set) ─────────┤
FE-8 (CSS-only collapse) ─────────┤
FE-9 (simplify fetch) ────────────┤
FE-10 (optimistic sends) ─────────┤
FE-11 (remove debug logging) ─────┘
                                    │
DB-2 (fix API ordering) ──── Can be done independently
DB-4 (verify relationship) ── Can be done independently
                                    │
                                    ├── DOC tasks wait for EP + FE completion
DOC-1 (architecture doc) ──────────┤   Technical writer agent reads final
DOC-2 (config help: file watcher) ─┤   implementation to ensure accuracy
DOC-3 (config help: hooks) ────────┤
DOC-4 (config help: SSE) ──────────┤
DOC-5 (voice bridge help) ─────────┤
DOC-6 (troubleshooting help) ──────┤
DOC-7 (hooks architecture) ────────┤
DOC-8 (bug document) ──────────────┤
DOC-9 (CLAUDE.md) ─────────────────┘
```

## Execution Order

1. **Phase A (Database):** DB-1, DB-2, DB-3, DB-4, DB-5 → run migration
2. **Phase B (Event Processing):** EP-1 through EP-6
3. **Phase C (Front End):** FE-1 through FE-11
4. **Phase D (Integration Testing):** End-to-end verification with real Claude Code sessions
5. **Phase E (Documentation):** DOC-1 through DOC-9

Phases B and C can run in parallel after Phase A completes. Phase E runs after B and C are stable.

## Testing Strategy

### Unit Tests
- EP-3: Test reconciler matching logic (exact match, fuzzy match, no match)
- EP-3: Test timestamp update propagation
- FE-3: Test ordered bubble insertion (before, after, middle)
- FE-4: Test reorder with timestamp corrections

### Integration Tests
- Create turns via hook, verify timestamp=now()
- Read JSONL with known timestamps, verify reconciliation updates Turn.timestamp
- Verify SSE `turn_updated` events fire after reconciliation
- Verify SSE `turn_created` events include turn_id for all paths

### E2E Verification
- Create agent, send prompt, observe turns in correct chronological order
- Verify progress collapse doesn't break ordering
- Verify SSE-delivered turns appear at correct position
- Verify timestamp corrections reorder bubbles correctly
- Test SSE disconnect + reconnect: verify gap recovery restores correct order
- Test with multi-tab AskUserQuestion (the original test scenario)

## Files Modified (Summary)

### Code Changes

| File | Changes |
|------|---------|
| `src/claude_headspace/models/turn.py` | Add `timestamp_source` column, optionally `jsonl_entry_hash` |
| `src/claude_headspace/routes/voice_bridge.py` | Fix ordering (ID→timestamp), add SSE broadcasts, fix pagination |
| `src/claude_headspace/services/transcript_reader.py` | Add timestamp to TranscriptEntry, return timestamp from read_transcript_file |
| `src/claude_headspace/services/hook_receiver.py` | Propagate JSONL timestamps in progress capture, remove debug logging |
| `src/claude_headspace/services/transcript_reconciler.py` | **NEW** — JSONL reconciliation pipeline |
| `src/claude_headspace/routes/respond.py` | Remove debug logging |
| `static/voice/voice-api.js` | Add turn_updated event handler |
| `static/voice/voice-app.js` | Major rewrite: ordered insertion, remove polling/dedup, CSS collapse, optimistic sends, remove debug logging |
| `static/voice/voice.css` | Add `.collapsed` class |
| `migrations/versions/` | New migration for timestamp_source + jsonl_entry_hash columns |

### Documentation Changes

| File | Changes |
|------|---------|
| `docs/architecture/transcript-chat-sequencing.md` | **NEW** — Primary reference for the three-phase pipeline and chat ordering |
| `docs/help/configuration.md` | Update File Watcher, Hooks, and SSE sections to reflect reconciliation role |
| `docs/help/voice-bridge.md` | Add Chat Display & Turn Ordering section, update connection status text |
| `docs/help/troubleshooting.md` | Add Voice Chat Issues section (ordering, missing responses, duplicates) |
| `docs/architecture/claude-code-hooks.md` | Add "Hooks in the Three-Phase Pipeline" section |
| `docs/bugs/voice-chat-agent-response-rendering.md` | Add Resolution section linking to new architecture |
| `CLAUDE.md` | Update Key Services to add TranscriptReconciler, update FileWatcher description |

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| JSONL entries may lack timestamps | Fallback to `datetime.now()` with `timestamp_source="server"` |
| Content-hash dedup may have false matches | Use first 200 chars + actor; 30-second time window bounds search |
| SSE disconnect during reconciliation | Gap handler triggers full transcript fetch — reconciliation recovers |
| Progress collapse CSS may affect layout | Test with `display:none` vs `height:0; overflow:hidden` |
| Pagination change may break infinite scroll | Test with agents that have >50 turns (pagination boundary) |
| Concurrent hook + file watcher for same event | Row-level locking on Turn update; reconciler uses `SELECT FOR UPDATE` |

---

## Documentation Updates

All documentation must be updated to reflect the new architecture. This is a fourth workstream that can be executed after Phases B and C are complete (when the implementation is stable and the architecture is final).

### Agent 4: Technical Writer

All DOC tasks are assigned to the technical writer agent. This agent must read the implementation code and architecture documents to ensure documentation accurately reflects the final system. The technical writer should not start until Phases B and C are complete (or substantially complete), so the documentation reflects the actual implementation rather than the plan.

The technical writer agent needs **read access to all source files** and **write access to `docs/` and `CLAUDE.md`**. It does not need to run tests, execute bash commands, or modify source code.

#### Task DOC-1: New Architecture Document — Transcript & Chat Sequencing

**Create:** `docs/architecture/transcript-chat-sequencing.md`

This is the primary reference document explaining how conversation data flows from Claude Code to the voice chat display. It must be clear, concise, and serve as the authoritative explanation for anyone maintaining or debugging the system.

**Required content:**

```markdown
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

### Phase 2: Reconciliation (Transcript Read)

The file watcher service reads the Claude Code JSONL transcript file at a
configurable interval (default: 2 seconds via `file_watcher.polling_interval`).
Each JSONL entry contains a timestamp from Claude Code reflecting when the
conversation event actually occurred.

The transcript reconciler matches JSONL entries against existing Turn records
in the database using content-based hashing:

- **Match found:** The Turn's timestamp is UPDATED to the JSONL timestamp.
  This corrects the Phase 1 approximation to the real conversation time.
- **No match:** A new Turn is CREATED with the JSONL timestamp. This captures
  events that hooks missed (hooks can be unreliable).

### Phase 3: Correction Broadcast

After reconciliation, the server broadcasts SSE events for all changes:

- `turn_updated` events for turns whose timestamps were corrected (includes
  the Turn's database ID so the client can update the existing bubble)
- `turn_created` events for newly discovered turns (full turn data)

The voice chat receives these events and:
- Updates timestamps on existing bubbles
- Inserts new bubbles at the correct chronological position
- Reorders any bubbles that are now in the wrong position due to timestamp
  corrections

## Ordering Key

**Turn.timestamp** is the canonical ordering field for conversation display.
It is NOT the database insertion time — it is the actual conversation time,
corrected by the JSONL transcript during Phase 2 reconciliation.

The database auto-increment ID (Turn.id) reflects insertion order and is used
as a stable identifier for linking SSE events to DOM elements. It is NOT used
for display ordering.

## Timestamp Sources

| Turn Origin | Initial Timestamp | After Reconciliation |
|-------------|-------------------|---------------------|
| Hook event (agent action) | `datetime.now()` (server time) | JSONL timestamp (conversation time) |
| Progress capture (transcript read) | JSONL timestamp | Already correct |
| User respond (dashboard/voice) | `datetime.now()` (user action time) | Not reconciled (user actions are real-time) |
| File watcher (new entry) | JSONL timestamp | Already correct |

## SSE Event Types for Chat

| Event | Purpose | Key Fields |
|-------|---------|------------|
| `turn_created` | New turn available | turn_id, text, actor, intent, timestamp, task_id, tool_input |
| `turn_updated` | Timestamp correction | turn_id, timestamp, update_type |
| `state_changed` | Agent state transition | agent_id, new_state |
| `gap` | Server detected dropped events | message |

## Client Rendering

The voice chat uses a single rendering approach:

1. **Initial load:** Fetch transcript from API → render all turns in timestamp order
2. **SSE turn_created:** Insert new bubble at correct chronological position
3. **SSE turn_updated:** Update existing bubble's timestamp, reorder if needed
4. **SSE gap / reconnect:** Re-fetch transcript from API, reconcile DOM

There is NO periodic polling. SSE is the primary delivery mechanism. Gap
recovery handles missed events.

## Diagram

[Diagram showing: Claude Code → JSONL file → File Watcher → Reconciler → DB → SSE → Client]
[Parallel path: Claude Code → Hook → DB → SSE → Client]
[Reconciler connects the two paths by matching and correcting timestamps]
```

### Task DOC-2: Update Configuration Help — File Watcher Section

**File:** `docs/help/configuration.md` (lines 77-92)

The current File Watcher help text describes it as a "fallback mechanism when hooks are not sending events." This is no longer accurate — the file watcher is now a critical part of the three-phase pipeline, responsible for reading JSONL timestamps and reconciling Turn records.

**Replace lines 77-92 with:**

```markdown
### File Watcher

Controls how Claude Headspace reads Claude Code JSONL transcript files. The file watcher is a critical component of the transcript reconciliation pipeline — it reads the JSONL transcript to extract accurate conversation timestamps and reconcile them against Turn records created by hooks.

Even when hooks are active, the file watcher performs essential functions:
- **Timestamp correction:** Updates Turn timestamps from approximate (server time) to accurate (JSONL conversation time)
- **Gap filling:** Creates Turn records for conversation events that hooks missed
- **Progress capture:** Detects intermediate agent output between hook events

```yaml
file_watcher:
  polling_interval: 2
  reconciliation_interval: 60
  inactivity_timeout: 5400
  debounce_interval: 0.5
```

- `polling_interval` - Seconds between JSONL transcript reads. This directly controls how quickly conversation timestamps are corrected and missed turns are discovered. Lower values (1-2s) mean the voice chat displays correct chronological ordering sooner. Higher values (5-10s) save resources but timestamps may be approximate for longer. Default of 2s provides a good balance between accuracy and performance.
- `reconciliation_interval` - Seconds between full reconciliation scans. This safety net re-reads the entire active portion of the transcript to catch any entries missed by incremental reads. Lower values improve reliability but increase CPU and disk I/O.
- `inactivity_timeout` - Stop watching a session after this much inactivity (default: 90 minutes). Prevents stale watchers from accumulating. Increase for long-running sessions that may pause for extended periods.
- `debounce_interval` - Minimum seconds between processing file change events. Claude Code often writes multiple entries in quick succession — debouncing prevents redundant processing. Too low causes duplicate work, too high delays detection.
```

### Task DOC-3: Update Configuration Help — Hooks Section

**File:** `docs/help/configuration.md` (lines 128-141)

Update the hooks help text to clarify the relationship between hooks and file watcher in the three-phase pipeline.

**Replace the intro text (line 130) with:**

```markdown
Claude Code lifecycle hooks provide real-time session events with low latency (<100ms). Hooks create Turn records immediately with approximate timestamps. The file watcher then reads the JSONL transcript to correct these timestamps to actual conversation time. Together, hooks and the file watcher form the two input paths of the three-phase event pipeline (see [Transcript & Chat Sequencing](../architecture/transcript-chat-sequencing.md)).
```

### Task DOC-4: Update Configuration Help — SSE Section

**File:** `docs/help/configuration.md` (lines 111-126)

Add a note about the new `turn_updated` event type:

After the existing bullet list, add:

```markdown
The SSE stream delivers several event types to connected clients:
- `turn_created` — a new conversation turn is available for display
- `turn_updated` — an existing turn's timestamp has been corrected by the transcript reconciler
- `state_changed` — an agent's state has transitioned
- `card_refresh` — an agent card's display data has changed
- `gap` — the server detected that events were dropped; clients should re-fetch

See [Transcript & Chat Sequencing](../architecture/transcript-chat-sequencing.md) for details on how SSE events drive the voice chat display.
```

### Task DOC-5: Update Voice Bridge Help

**File:** `docs/help/voice-bridge.md`

**Update the "How It Works" section (lines 7-17)** to reflect the new architecture. The current text describes a simple command→response flow. Add a new subsection:

After the existing "How It Works" section, add:

```markdown
### Chat Display & Turn Ordering

The voice chat displays conversation turns in chronological order based on
timestamps from the Claude Code JSONL transcript (the ground truth for when
events actually happened in the conversation).

Turns arrive via two paths:
1. **SSE push (immediate):** When hooks fire, turns are created and pushed to
   the chat in real-time. Timestamps are approximate at this stage.
2. **Transcript reconciliation (seconds later):** The file watcher reads the
   JSONL transcript and corrects timestamps to their actual conversation time.
   If turns need reordering, the chat updates automatically.

This means you may occasionally see a turn appear and then shift position
slightly as its timestamp is corrected. This is normal behaviour — it reflects
the system ensuring chronological accuracy.

For technical details, see [Transcript & Chat Sequencing](../architecture/transcript-chat-sequencing.md).
```

**Update the "Connection Status" section (lines 146-153)** to remove the reference to polling fallback:

Replace line 154:
```
If the SSE connection fails repeatedly, the app falls back to polling the agent list every 5 seconds.
```
With:
```
If the SSE connection fails, the app automatically reconnects with exponential backoff (up to 30 seconds between attempts). On reconnect, missed events are replayed from the server's replay buffer.
```

### Task DOC-6: Update Troubleshooting Help

**File:** `docs/help/troubleshooting.md`

Add a new section after "Input Bridge Issues" (line 133):

```markdown
## Voice Chat Issues

### Messages appearing out of chronological order

**Symptoms:** Turns in the voice chat appear in the wrong order — e.g., a response from 10:40am appears before a message from 10:27am.

**Cause:** This was a known architectural issue that has been resolved. The voice chat now uses timestamp-ordered insertion with JSONL transcript reconciliation. If you still see ordering issues:

**Solutions:**
1. Wait a few seconds — the transcript reconciler corrects timestamps within the file watcher polling interval (default: 2 seconds)
2. Reload the chat by navigating away and back to the agent — this re-fetches the full transcript in correct order from the database
3. Check that the file watcher is enabled in `config.yaml` → `file_watcher.enabled: true`
4. Lower `file_watcher.polling_interval` for faster timestamp correction (minimum: 0.5 seconds)

### Agent responses not appearing in chat

**Symptoms:** You send a command but no agent response bubble appears.

**Solutions:**
1. Check the SSE connection indicator (coloured dot in header) — must be green
2. If disconnected, the app will reconnect automatically; missed turns will appear on reconnect
3. Navigate away from the agent and back — this triggers a full transcript fetch
4. Check server logs for hook processing errors

### Duplicate messages in chat

**Symptoms:** The same turn appears twice in the chat.

**Solutions:**
1. This should not occur with the current architecture — each turn has a unique database ID used for deduplication
2. If it does occur, reload the chat by navigating away and back
3. Report as a bug with the turn IDs (visible in browser developer console)
```

### Task DOC-7: Update Architecture — Hooks Document

**File:** `docs/architecture/claude-code-hooks.md`

Add a new section after the existing content that explains how hooks fit into the three-phase pipeline:

```markdown
## Hooks in the Three-Phase Pipeline

Hooks are Phase 1 of the three-phase event pipeline. When a hook fires:

1. The hook receiver creates a Turn record with `timestamp = datetime.now(UTC)`
2. State transitions are applied via the state machine
3. SSE events are broadcast immediately (`turn_created`, `state_changed`)

The Turn's timestamp is approximate at this stage — it reflects server processing
time, not actual conversation time. Phase 2 (file watcher reading the JSONL
transcript) corrects the timestamp to the actual conversation time from the JSONL
entry.

This means hooks are optimised for **speed** (immediate state updates and SSE
delivery) while the file watcher handles **accuracy** (correct timestamps from
the transcript). Together they provide both fast and accurate turn delivery.

See [Transcript & Chat Sequencing](transcript-chat-sequencing.md) for the full
pipeline documentation.
```

### Task DOC-8: Update Bug Document

**File:** `docs/bugs/voice-chat-agent-response-rendering.md`

Add a "Resolution" section at the end of the existing document:

```markdown
## Resolution (2026-02-15)

This bug was part of a broader architectural issue with the voice chat rendering
pipeline. The root cause was a dual-path rendering architecture where SSE events
and periodic transcript polling raced to append turns at the bottom of the DOM,
combined with progress collapse that removed DOM elements and triggered
re-rendering at wrong positions.

The fix replaced the dual-path architecture with a single-source-of-truth model:
- Database stores turns with correct conversation timestamps (from JSONL transcript)
- All turn creation paths broadcast SSE events
- Client renders turns in timestamp order using ordered insertion
- No periodic polling; SSE is the primary delivery mechanism
- Progress collapse uses CSS (display:none) instead of DOM removal

See `docs/architecture/transcript-chat-sequencing.md` for the full architecture
and `docs/reviews_remediation/2026-02-15-voice-chat-ordering-remediation.md`
for the implementation plan.
```

### Task DOC-9: Update CLAUDE.md — Key Services Section

**File:** `CLAUDE.md`

In the "Key Services" → "Hook & State Management" section, add an entry for the new reconciler:

```markdown
- **TranscriptReconciler** (`transcript_reconciler.py`) -- reconciles JSONL transcript entries against database Turn records; corrects Turn timestamps from approximate (server time) to accurate (JSONL conversation time); creates Turns for events missed by hooks; broadcasts SSE corrections
```

Also update the **FileWatcher** description to mention its role in the reconciliation pipeline:

Current:
```markdown
- **FileWatcher** (`file_watcher.py`) -- hybrid watchdog + polling monitor for `.jsonl` and transcript files
```

Change to:
```markdown
- **FileWatcher** (`file_watcher.py`) -- hybrid watchdog + polling monitor for `.jsonl` transcript files; feeds the TranscriptReconciler with JSONL entries containing actual conversation timestamps for Phase 2 reconciliation
```

---

## Documentation Dependency

DOC tasks should be executed **after** Phases B and C are complete, so the documentation reflects the final implemented architecture. DOC-1 (the new architecture document) is the highest priority as it is referenced by all other documentation updates.

```
Phase B (EP) + Phase C (FE) complete
  │
  ├── DOC-1: New architecture document (transcript-chat-sequencing.md)
  │     │
  │     ├── DOC-2: Update config help — file watcher
  │     ├── DOC-3: Update config help — hooks
  │     ├── DOC-4: Update config help — SSE
  │     ├── DOC-5: Update voice bridge help
  │     ├── DOC-6: Update troubleshooting help
  │     ├── DOC-7: Update hooks architecture doc
  │     ├── DOC-8: Update bug document
  │     └── DOC-9: Update CLAUDE.md
  │
  └── Phase D: Integration testing
```
