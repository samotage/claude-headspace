# Adversarial Code Review: Voice Chat → Tmux Pipeline

**Date:** 2026-02-17
**Reviewer:** Claude (adversarial review)
**Scope:** Full voice chat communication chain: JS frontend → voice bridge route → respond route → tmux bridge service → agent interaction
**Period:** ~70 commits over 5 days (Feb 12-17)
**Trigger:** User-reported regressions, flip-flopping fixes, and a live bug where voice chat message failed to reach the target agent

---

## Executive Summary

The voice-to-tmux pipeline has accumulated significant complexity and multiple interacting bugs over rapid iteration. The core issue is that **the pipeline has no single coherent model for how messages flow from the UI to the agent** — instead, there are overlapping paths, race conditions between hooks and route handlers, and a critical missing data field in SSE events that breaks the permission recapture guard.

**Critical findings: 4 | High findings: 4 | Medium findings: 3 | Total: 11**

---

## Critical Findings

### C1: `question_source_type` Missing from ALL SSE `turn_created` Broadcasts

**Impact:** Permission recapture guard is completely broken for SSE-delivered turns. Free-text questions (AskUserQuestion) may get spurious Yes/No permission buttons injected.

**Evidence:**

The frontend guard in `voice-sse-handler.js:196-198`:
```javascript
if (turn.intent === 'question' && !turn.question_options
    && turn.question_source_type === 'permission_request') {
  _scheduleRecapture(...);
}
```

But `question_source_type` is **never included** in any `turn_created` SSE broadcast:
- `hook_receiver.py:_broadcast_turn_created` (line 148-158) — missing
- `hook_deferred_stop.py:_broadcast_turn_created` (line 72-85) — missing
- `transcript_reconciler.py` broadcast (line 139-149) — missing
- `voice_bridge.py` voice_command broadcasts (line 415-427, 522-535) — missing
- `respond.py` `_broadcast_state_change` (line 415-427) — missing

Additionally, `handleTurnCreated` in `voice-sse-handler.js:151-162` builds a turn object that **never extracts** `question_source_type` from the SSE data, even if it were present:
```javascript
var turn = {
  id: data.turn_id, actor: data.actor, intent: data.intent,
  text: data.text, timestamp: data.timestamp,
  tool_input: data.tool_input, question_text: data.text,
  question_options: null, task_id: data.task_id,
  task_instruction: data.task_instruction
  // question_source_type: MISSING
};
```

**Result:** `turn.question_source_type === 'permission_request'` is **always false** for SSE turns. The recapture mechanism only works when the page reloads and turns are fetched via the transcript API (which includes the field).

**Fix:** (1) Add `question_source_type` to all `turn_created` broadcast payloads. (2) Extract it in `handleTurnCreated`.

---

### C2: Voice Chat Sends Literal Text to TUI Picker Prompts (The Bug You Hit)

**Impact:** When an agent is showing an AskUserQuestion picker UI (a TUI select list), voice chat sends literal typed characters into the picker instead of using arrow-key navigation. The text is garbled and the agent doesn't receive the intended message.

**Evidence:**

In `voice-chat-controller.js`, `sendChatCommand(text)` always calls `VoiceAPI.sendCommand(text, agentId)`, which POSTs to `/api/voice/command`. The route at `voice_bridge.py:360-364` calls `tmux_bridge.send_text()`, which types the text literally with `send-keys -l`.

The route is *aware* of picker questions (line 308-325) — it sets a `has_picker` flag and logs a warning — but **still sends the text via `send_text()`**. The warning at line 321-325:
```python
if has_picker:
    logger.warning(
        f"Voice command to agent {agent.id} targeting a picker question "
        f"(has structured options). Free text will be sent as override."
    )
```

This means: if you type "review the last five days of commits" into voice chat while the agent has an AskUserQuestion prompt showing, `send_text` types `r`, `e`, `v`, `i`, `e`, `w`... into the TUI arrow-key picker. The agent gets garbage.

The voice chat **should either**:
1. Route through the select mechanism when a picker is active, or
2. Navigate to "Other" and then type the text, or
3. Reject the send with a user-facing message explaining the agent has a picker prompt

Currently it does none of these — it just warns in the server logs and proceeds to break.

**This is the bug you experienced.** You sent a message from voice chat. The agent (me) had an `AskUserQuestion` picker active. Your text was typed into the picker, which selected "Recent fixes (last 5 commits)" instead of delivering your actual message.

**Fix:** When `has_picker` is detected, route through the "Other" selection path (navigate to last option → Enter → type text → Enter), or return a 409 to the voice chat with a message telling the user to use the option buttons.

---

### C3: Duplicate Turn Race Between Voice Bridge and Hook

**Impact:** Both `voice_bridge.voice_command()` and `hook_receiver.process_user_prompt_submit()` can create a Turn for the same user message, causing duplicate chat bubbles.

**Evidence:**

In `voice_bridge.py`, the idle/processing path:
1. **Line 360:** tmux sends the text → Claude Code receives it
2. **Line 386-403:** Voice bridge creates a Turn via `lifecycle.process_turn()`
3. **Line 403:** `db.session.commit()`
4. **Line 431-432:** `get_agent_hook_state().set_respond_pending(agent.id)` — flag set AFTER commit

Between step 1 and step 4, Claude Code's `user_prompt_submit` hook can fire, hit `hook_receiver.process_user_prompt_submit()`, find no `respond_pending` flag yet, and create its own Turn. The window is ~100-500ms depending on tmux and hook latency.

The `respond_pending` flag is intentionally set after commit to avoid orphaned flags on commit failure. But this creates a race window.

**Fix:** Set a pre-commit "pending" flag (e.g., `set_respond_inflight`) before the tmux send, then upgrade it to `respond_pending` after commit. The hook checks both flags.

---

### C4: `interrupt_and_send_text` Disrupts Agent Work Without User Intent

**Impact:** Any voice chat message to a PROCESSING agent interrupts its work by sending Escape.

**Evidence:**

`voice_bridge.py:351-358`:
```python
if is_processing:
    result = tmux_bridge.interrupt_and_send_text(
        pane_id=agent.tmux_pane_id,
        text=send_text,
        ...
    )
```

`interrupt_and_send_text` in `tmux_bridge.py:549-637` sends `Escape` to halt the agent, waits 500ms, then types the text. This means every voice chat message to a working agent:
1. Halts whatever the agent is doing
2. Waits half a second (agent may or may not be ready)
3. Types the new command

The user may just want to add context ("also check the tests") without interrupting current work. The interrupt-first-ask-questions-later approach is destructive.

Additionally, the 500ms `interrupt_settle_ms` may not be enough for the agent to abort and return to its prompt, especially during mid-tool-use operations.

**Fix:** Add an explicit `interrupt` boolean to the voice command API. Default to non-interrupting (queue the message). Only interrupt when the user explicitly chooses to.

---

## High Findings

### H1: `send_text()` Excessive Complexity — Up to 13+ Subprocess Calls Per Message

**Impact:** High latency (500ms–3s per send), timing-sensitive, fragile.

**Evidence:**

A single `send_text()` call in `tmux_bridge.py:368-546` can execute this sequence:
1. `capture_pane` (lines=3, escapes) — check ghost text
2. `send-keys Escape` (if ghost) + sleep 200ms
3. `send-keys -l <text>` — type literal text
4. sleep 120ms — `text_enter_delay_ms`
5. `capture_pane` (lines=3, escapes) — check post-typing ghost
6. `send-keys Escape` (if ghost) + sleep 200ms
7. `capture_pane` (lines=5) — pre-Enter baseline
8. `send-keys Enter`
9. sleep 200ms — `enter_verify_delay_ms`
10. `capture_pane` (lines=5) — verify
11. `capture_pane` (lines=3, escapes) — check ghost (if unchanged)
12. `send-keys Escape` (if ghost) + sleep 200ms
13. `send-keys Enter` — retry
14. Repeat 10-13 up to 3 times

Minimum: 4 subprocess calls + 120ms delay = ~250ms
Typical with ghost: 8+ calls + 520ms delays = ~1s
Worst case (3 retries): 13+ calls + 1.5s delays = ~3s

This complexity was added iteratively across commits `9d25823`, `49306e4`, `80a5625` to handle autocomplete ghost text and Enter-swallowing. Each fix addressed a narrow symptom without simplifying the overall mechanism.

**Fix:** Consider a single tmux command approach: use `send-keys -l` followed by `send-keys Enter` with a simple retry, without the elaborate capture-verify-escape dance. The ghost text detection may be better handled by a one-time setup that disables Claude Code's autocomplete ghost feature.

---

### H2: `verify_enter` Causes False Negatives When Agent is Still Processing

**Impact:** `send_text()` can return `SEND_FAILED` even when the text was delivered correctly, because `_verify_submission()` detects "no change" when the pane was already updating.

**Evidence:**

`_verify_submission()` in `tmux_bridge.py:289-365` compares pre-Enter pane content with post-Enter content. It expects the content to change when Enter is accepted.

But if the agent was already producing output (PROCESSING state), the pane content was ALREADY changing before Enter was sent. The pre-Enter capture might show mid-output content, and the post-Enter capture might show the same mid-output region. The `_pane_content_changed()` comparison strips whitespace and checks for differences — but if the agent is rapidly scrolling output, both captures could show different slices of the same scroll buffer, making the comparison unreliable.

For `interrupt_and_send_text`, this is even worse: after Escape, the agent is printing stop/cleanup output. The pre-Enter capture during cleanup and the post-Enter capture both show volatile content.

**Fix:** When sending to a processing/interrupting agent, skip `verify_enter` entirely — the pane is too volatile for content comparison.

---

### H3: Voice Command Turn Text Mismatch Between DB and Tmux

**Impact:** For `is_idle`/`is_processing` agents, the text sent to tmux differs from the text stored in the Turn record, causing dedup failures.

**Evidence:**

In `voice_bridge.py`:
- Line 341-349: `send_text` is built: `f"{file_path} {text}"` if file_path exists
- Line 360-364: tmux receives `send_text`
- Line 392: Turn creation uses... `text=send_text` ✓ (OK for idle/processing path)

But for the AWAITING_INPUT path:
- Line 483-488: Turn is created with `text=text` (NOT `send_text`)
- Tmux was sent `send_text` (line 360-364, which happens BEFORE the if/else branch split)

Wait — actually, looking at the flow more carefully: the tmux send happens at lines 351-365 (ALL states), then the Turn creation differs by branch. The awaiting_input branch at line 483 creates a Turn with `text=text` while tmux got `send_text`. If `file_path` was set, the Turn shows "hello" but tmux got "uploads/file.txt hello".

This is somewhat intentional (display vs. raw), but the optimistic bubble in the frontend also shows the original text. The SSE `turn_created` broadcast at line 528 uses `text` (matching the optimistic bubble), while the tmux got `send_text`. This is consistent but fragile — the hook's `user_prompt_submit` would capture whatever was in the terminal buffer, which includes the file path.

---

### H4: `fetchTranscriptForChat` Can Race with `handleTurnCreated` Causing Duplicate Bubbles

**Impact:** Under SSE event bursts, the same turn can be rendered twice briefly before dedup kicks in.

**Evidence:**

`handleAgentUpdate` (line 290 in voice-sse-handler.js) can trigger `fetchTranscriptForChat()` when polling detects a state change. Simultaneously, a `turn_created` SSE event triggers `handleTurnCreated()`. Both race to render the same turn.

The dedup at `handleTurnCreated:179`:
```javascript
if (document.querySelector('[data-turn-id="' + turn.id + '"]')) {
  if (!isTerminalIntent) return;
}
```
Only catches the duplicate if the first render already added the element to the DOM. If both are in-flight (Promise resolution + DOM mutation), both could pass the check.

The `fetchInFlight` guard in `fetchTranscriptForChat` helps for sequential fetches but doesn't prevent the SSE `turn_created` → fetch race.

**Fix:** Use a `Set()` to track pending turn IDs being rendered, checked before DOM insertion. This is lightweight and eliminates the race.

---

## Medium Findings

### M1: `_has_autocomplete_ghost` Detection is Brittle

The ghost text detection in `tmux_bridge.py:239-266` checks for ANSI SGR 2 (dim) or SGR 90 (dark gray) escape sequences in the last 2 lines. But:
- Different terminal themes may not use these codes for ghost text
- Claude Code's styling may change across versions
- The capture uses `-e` flag which returns raw escapes, but tmux versions differ in what they emit
- False positives on dim text in agent output could trigger unnecessary Escape sends

### M2: Polling Fallback in `handleAgentUpdate` Triggers Full Transcript Fetch

In `voice-sse-handler.js:272-295`, when polling data (no agent_id, has .agents array) detects a state change for the target agent, it calls `fetchTranscriptForChat()`. This is an expensive full transcript fetch triggered by a state-polling mechanism that already fires every 5 seconds during reconnects.

During SSE reconnect periods, this means a full transcript fetch every 5 seconds, even if nothing has changed except the agent state label.

### M3: No Timeout/Cancellation on `interrupt_and_send_text` Settle Period

`interrupt_and_send_text` in `tmux_bridge.py:593` does a hard `time.sleep(interrupt_settle_ms / 1000.0)` (500ms). During this sleep:
- The HTTP request is blocked
- The voice chat optimistic bubble is waiting for confirmation
- Another voice command could queue up behind the send lock
- If the Flask worker is single-threaded, all other requests are blocked

---

## Action Items

| # | Severity | File(s) | Description | Effort |
|---|----------|---------|-------------|--------|
| 1 | **CRITICAL** | `hook_receiver.py`, `hook_deferred_stop.py`, `transcript_reconciler.py`, `voice_bridge.py`, `respond.py` | Add `question_source_type` to all `turn_created` SSE broadcast payloads | Small |
| 2 | **CRITICAL** | `voice-sse-handler.js` | Extract `question_source_type` from SSE data into turn object in `handleTurnCreated` | Small |
| 3 | **CRITICAL** | `voice_bridge.py` | When `has_picker` is true, route through "Other" selection or return 409 with user message instead of sending literal text | Medium |
| 4 | **CRITICAL** | `voice_bridge.py`, `hook_agent_state.py` | Fix race: add pre-send `respond_inflight` flag, check in hook | Medium |
| 5 | **CRITICAL** | `voice_bridge.py` | Don't auto-interrupt PROCESSING agents; add explicit interrupt control | Medium |
| 6 | **HIGH** | `tmux_bridge.py` | Skip `verify_enter` when sending to processing/interrupting agents (pane content is volatile) | Small |
| 7 | **HIGH** | `tmux_bridge.py` | Evaluate simplifying `send_text` — consider reducing capture-verify-escape cycles | Large |
| 8 | **HIGH** | `voice-sse-handler.js` | Add pending turn ID set to prevent race between `handleTurnCreated` and `fetchTranscriptForChat` | Small |
| 9 | **HIGH** | `voice_bridge.py` | Ensure consistent `text` vs `send_text` in Turn records and broadcasts across all branches | Small |
| 10 | **MEDIUM** | `tmux_bridge.py` | Make ghost text detection configurable/disableable | Small |
| 11 | **MEDIUM** | `voice-sse-handler.js` | Debounce/skip transcript fetch from polling when SSE turns are the primary delivery mechanism | Small |

---

## Architecture Observation

The root cause of the flip-flopping is that the voice-to-agent pipeline evolved incrementally without a clear contract at each boundary:

1. **Frontend → Route:** The voice chat doesn't know what TUI state the agent's terminal is in (text input vs. picker vs. processing output). It always sends text and hopes for the best.

2. **Route → Tmux:** The voice bridge tries to handle all states (idle, processing, awaiting_input) in one endpoint with branching logic, rather than having the frontend choose the right action based on known agent state.

3. **Tmux → Agent:** The `send_text` function has accumulated defensive measures (ghost detection, enter verification, retry) that each address real problems but together create a fragile timing-sensitive pipeline.

4. **Hook ↔ Route:** Two independent paths (hooks and route handlers) both create Turns and manage state, coordinated only by an in-memory flag that has a race window.

A more robust design would:
- Have the frontend send structured intents ("send text to idle agent", "select option N for awaiting agent", "interrupt and send command") rather than raw text
- Have each intent map to exactly one backend path with no overlap
- Eliminate the hook/route Turn creation race entirely by making one path authoritative

---

_Review complete. 11 findings (4 critical, 4 high, 3 medium). Recommend prioritising C1+C2 immediately as they are active bugs._
