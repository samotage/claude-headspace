# Bug Fix: Voice Chat Agent Responses Not Rendering

## Problem Statement

In the Claude Headspace voice chat UI (`/voice`), agent (Claude Code) text responses are not appearing as chat bubbles. User messages display correctly as blue COMMAND bubbles, and task separators (gray dividers with task instruction text) appear between turns, but the **agent's actual response text is invisible** — no agent bubble is rendered.

This means the voice chat is unusable for reading agent responses — users can see what they sent but not what the agent replied.

## Affected Files

**Primary investigation targets:**
- `static/voice/voice-app.js` — Main voice chat application (rendering pipeline)
- `static/voice/voice-api.js` — SSE event routing to handlers
- `src/claude_headspace/services/hook_receiver.py` — Server-side stop hook (creates turns, broadcasts SSE)
- `src/claude_headspace/services/hook_deferred_stop.py` — Deferred stop processing
- `src/claude_headspace/services/hook_helpers.py` — `broadcast_turn_created()` helper
- `src/claude_headspace/routes/voice_bridge.py` — `/api/voice/agents/<id>/transcript` endpoint

## Architecture: How Agent Responses Flow to the Voice Chat

### Server Side (Turn Creation & Broadcasting)

1. Claude Code finishes responding → `stop` hook fires → `hook_receiver.py:handle_stop()`
2. Stop handler reads transcript, creates a Turn record (COMPLETION/END_OF_TASK/QUESTION intent)
3. After `db.session.commit()`, three SSE events broadcast in this order:
   - `card_refresh` (line ~724)
   - `state_changed` (line ~728)
   - `turn_created` (line ~756) — contains `{agent_id, text, actor:"agent", intent, task_id, turn_id}`
4. **Deferred stop path** (lines 597-612): If transcript is empty when stop fires, processing defers. The deferred handler (`hook_deferred_stop.py`) eventually creates the turn and broadcasts `card_refresh` + `turn_created` (but NOT `state_changed`).

### Client Side (SSE → Rendering)

Two parallel paths deliver agent turns to the chat:

**Path A: Direct SSE rendering (`turn_created` event)**
```
SSE turn_created → voice-api.js:_onTurnCreated → voice-app.js:_handleTurnCreated()
```
- Guards: must be on chat screen, agent_id must match target, `data.text` must be non-empty
- Builds a turn-like object and calls `_renderChatBubble()` directly
- Adds turn ID to `_chatRenderedTurnIds` (dedup set)

**Path B: Transcript fetch (triggered by state_changed/card_refresh or 8s polling)**
```
SSE state_changed/card_refresh → _handleAgentUpdate() → _handleChatSSE() → _fetchTranscriptForChat()
  → GET /api/voice/agents/<id>/transcript → _groupTurns() → _renderChatBubble()
```
- Also triggered by: 8-second safety-net polling timer, response catch-up timers (1.5s, 3s, 5s, 8s, 12s, 18s, 25s after send)
- Filters turns through `_chatRenderedTurnIds` — skips any already rendered
- Groups consecutive agent turns within 2s into single bubbles
- Inserts task separators at task boundaries (these ARE rendering — confirmed in screenshot)

### Rendering Pipeline (`_renderChatBubble` → `_createBubbleEl`)

1. `_createBubbleEl` checks `_chatRenderedTurnIds` for dedup (returns null if all IDs already rendered)
2. Creates a `div.chat-bubble.agent` element
3. Text display: `displayText = turn.text || turn.summary || ''` — if both empty, no text div is added
4. Intent label rendered (Question/Completed/Command/Working)
5. **Terminal intent collapse**: When COMPLETION/END_OF_TASK arrives, `_collapseProgressBubbles()` removes all PROGRESS bubbles for that task from the DOM

## Suspected Root Causes (Investigate All Three)

### Hypothesis 1: Turn text is empty when fetched

The transcript endpoint (`voice_bridge.py:agent_transcript()`) returns `t.text` directly. If the Turn record has `text=None` or `text=""`, the bubble renders but with no visible content. The bubble div exists but is effectively invisible (no text div, no intent label if intent is 'progress').

**Investigate:** Query the database for recent agent turns and check if `text` is populated. Look at the stop handler's text flow — `completion_text` derivation involves progress dedup logic (lines 614-643 of hook_receiver.py) that could produce empty text. Also check if the transcript endpoint's PROGRESS filter (line 782: `if t.intent == TurnIntent.PROGRESS and (not t.text or not t.text.strip()): continue`) is filtering out turns it shouldn't.

### Hypothesis 2: Progress collapse + dedup race condition

Sequence:
1. Agent processing → PROGRESS turns created → `_handleTurnCreated` renders PROGRESS bubbles
2. Agent finishes → COMPLETION turn created → `_handleTurnCreated` fires with COMPLETION intent
3. `_collapseProgressBubbles()` removes all PROGRESS bubbles from DOM
4. COMPLETION bubble should be created by `_createBubbleEl`
5. **BUT**: if `_chatRenderedTurnIds` already has the COMPLETION turn ID (from a prior transcript fetch triggered by `card_refresh`/`state_changed` arriving before `turn_created`), the bubble creation returns null

The dedup at `_createBubbleEl` line 1326 (`if (allRendered && !forceRender) return null`) would block rendering. The `isTerminalIntent` check in `_handleTurnCreated` (line 2269-2274) tries to handle this by checking if the DOM already has the element, but the timing matters:
- `card_refresh` arrives → `_fetchTranscriptForChat()` → renders COMPLETION bubble + adds ID to dedup set
- `turn_created` arrives → `_handleTurnCreated` checks dedup → ID exists → checks DOM → element exists → returns

In this case, the bubble SHOULD be in the DOM. But if the bubble was rendered by the transcript fetch AND THEN a subsequent `_collapseProgressBubbles` call removes it (because it has `data-task-id` and is a PROGRESS intent)... wait, collapse only removes elements with `.progress-intent` class. COMPLETION bubbles have `.bubble-intent` with text "Completed", not `.progress-intent`. So this shouldn't cause the issue.

**Investigate:** Add console.log tracing to `_handleTurnCreated`, `_createBubbleEl`, and `_collapseProgressBubbles` to observe the actual event sequence and dedup decisions.

### Hypothesis 3: Agent ID mismatch in multi-agent scenarios

The user was running a multi-agent team operation. The voice chat connects to a specific `_targetAgentId`. Both `_handleTurnCreated` (line 2234) and `_handleChatSSE` (line 2160) filter by `parseInt(agentId) !== parseInt(_targetAgentId)`.

If the voice chat was connected to the team lead agent but the `turn_created` SSE events carried the sub-agent IDs (db-models, services, security, frontend), ALL agent turn broadcasts would be filtered out. The transcript fetch would also return no turns if querying the wrong agent.

**Investigate:** Check what `_targetAgentId` is set to in the voice chat. Check what `agent_id` values are in the `turn_created` SSE events. In the multi-agent scenario, the team lead agent (the one connected to the terminal) is the one that should be tracked.

## Debugging Approach

### Step 1: Add diagnostic logging

In `static/voice/voice-app.js`, add `console.log` tracing to:

1. `_handleTurnCreated` — log when called and what guards filter it:
   ```javascript
   // At top of function:
   console.log('[TURN_CREATED] received:', data.agent_id, data.intent, 'text_len:', (data.text||'').length, 'target:', _targetAgentId, 'screen:', _currentScreen);
   ```

2. `_fetchTranscriptForChat` — log what the transcript returns:
   ```javascript
   // After var turns = resp.turns || []:
   console.log('[TRANSCRIPT] fetched:', turns.length, 'turns, newTurns:', newTurns.length);
   ```

3. `_createBubbleEl` — log dedup decisions:
   ```javascript
   // After allRendered check:
   if (allRendered && !forceRender) {
     console.log('[BUBBLE] SKIPPED (dedup):', turn.id, turn.intent);
     return null;
   }
   ```

4. `_renderChatBubble` — log what's being rendered:
   ```javascript
   console.log('[BUBBLE] rendering:', turn.id, turn.actor, turn.intent, 'text_len:', (turn.text||'').length);
   ```

### Step 2: Check database state

Query recent agent turns to verify text is populated:
```sql
SELECT t.id, t.actor, t.intent, length(t.text) as text_len,
       substring(t.text, 1, 80) as text_preview, t.summary
FROM turns t
JOIN tasks tk ON t.task_id = tk.id
JOIN agents a ON tk.agent_id = a.id
WHERE a.id = <target_agent_id>
ORDER BY t.id DESC
LIMIT 20;
```

### Step 3: Check SSE event flow

Open browser DevTools → Network tab → filter by EventStream. Watch for `turn_created` events and verify they contain `text` and the correct `agent_id`.

## Fix Guidance

Once the root cause is identified:

- **If text is empty**: Fix the turn creation in `hook_receiver.py` or `hook_deferred_stop.py` to ensure `text` is always populated for COMPLETION/END_OF_TASK turns. Consider falling back to `full_agent_text` if `completion_text` is empty after progress dedup.

- **If dedup race**: Modify `_handleTurnCreated` to NOT add the turn ID to `_chatRenderedTurnIds` when the SSE fires, letting the transcript fetch handle it. Or: when `_fetchTranscriptForChat` finds a turn already in the dedup set, verify the DOM element still exists and re-render if missing.

- **If agent ID mismatch**: In multi-agent scenarios, ensure the voice chat tracks the correct agent. The team lead's agent ID should match what the dashboard shows. Consider broadcasting `turn_created` events with both the agent_id and a parent session indicator.

- **General resilience**: The 8-second sync timer (`_startChatSyncTimer`) should be the ultimate fallback. If turns exist in the DB with text, they MUST eventually render. If they don't, the dedup set (`_chatRenderedTurnIds`) is the most likely blocker — turns were added to the set but their DOM elements were removed or never created.

## Key Code Locations (line numbers as of current `development` branch)

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `_handleTurnCreated` | voice-app.js | 2231 | SSE turn_created handler (Path A) |
| `_handleChatSSE` | voice-app.js | 2156 | Triggers transcript fetch (Path B) |
| `_fetchTranscriptForChat` | voice-app.js | 2480 | Fetches & renders new turns |
| `_groupTurns` | voice-app.js | 1209 | Groups consecutive agent turns |
| `_renderChatBubble` | voice-app.js | 1291 | Renders a turn as DOM bubble |
| `_createBubbleEl` | voice-app.js | 1319 | Creates bubble DOM element with dedup |
| `_collapseProgressBubbles` | voice-app.js | 1310 | Removes PROGRESS bubbles on terminal intent |
| `_renderTaskSeparator` | voice-app.js | 1278 | Renders gray task divider (THESE work) |
| `_scheduleResponseCatchUp` | voice-app.js | 939 | Post-send aggressive polling |
| `_startChatSyncTimer` | voice-app.js | 908 | 8s safety-net polling |
| `handle_stop` | hook_receiver.py | ~560 | Server-side stop hook processing |
| `broadcast_turn_created` | hook_helpers.py | 75 | SSE broadcast helper |
| `agent_transcript` | voice_bridge.py | 742 | Transcript API endpoint |

## CRITICAL Rules

- Do NOT restart the server unless absolutely necessary (Flask reloader handles Python changes)
- If restart needed, use `./restart_server.sh` ONLY
- Do NOT switch git branches
- The application URL is `https://smac.griffin-blenny.ts.net:5055` — never use localhost
- Test database is `claude_headspace_test`, production is `claude_headspace`

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
- Progress collapse uses CSS (`display:none`) instead of DOM removal

See `docs/architecture/transcript-chat-sequencing.md` for the full architecture
and `docs/reviews_remediation/2026-02-15-voice-chat-ordering-remediation.md`
for the implementation plan.
