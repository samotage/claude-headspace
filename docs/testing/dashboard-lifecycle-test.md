# Dashboard Lifecycle Test

## Purpose

Verify that the dashboard agent card transitions through all states during a full turn:

```
IDLE → PROCESSING → INPUT NEEDED → PROCESSING → COMPLETE → IDLE
```

## Context

Two bugs were fixed in this session:

1. **FK race condition** (`event_writer.py`): EventWriter used its own DB session, causing ForeignKeyViolation when writing events referencing not-yet-committed tasks. Fix: pass caller's session so events join the same transaction.

2. **Notification override** (`hook_receiver.py`): `process_notification()` unconditionally broadcast AWAITING_INPUT even when no task was PROCESSING (e.g., after stop hook already completed the task). Fix: only broadcast when DB state actually changes.

## What Still Fails

The dashboard card does not visually update in real-time. Suspected cause: SSE connection drops after server restarts and doesn't reconnect reliably. The DB state is correct (verified via `psql`) and server-rendered HTML is correct (verified via `curl`), but the browser doesn't reflect changes.

## Pre-Test Setup

1. **Start Chrome with CDP debugging** (if not already running):
   ```
   /otl/util/start-chrome-debug
   ```

2. **Ensure server is running:**
   ```bash
   ./restart_server.sh
   ```

3. **Verify SSE is working** before starting the test:
   ```bash
   curl -s -N --max-time 5 "http://localhost:5055/api/events/stream" 2>&1 | head -5
   ```
   Should show `: heartbeat` lines.

## Test Procedure

### Step 1: Connect agent-browser and verify initial state

```bash
agent-browser --cdp 9222 open "http://localhost:5055/dashboard"
sleep 3
agent-browser --cdp 9222 screenshot
```

- Verify the agent card shows current state
- Verify SSE status (top-right should NOT show "Reconnecting...")
- If "Reconnecting..." appears, the SSE connection is broken — investigate before proceeding

### Step 2: Verify SSE is live in the browser

```bash
agent-browser --cdp 9222 snapshot -i
```

Look for SSE connection indicator. If SSE is not connected, the test cannot verify real-time updates.

### Step 3: Take baseline DB snapshot

```bash
psql -d claude_headspace -c "SELECT id, agent_id, state FROM tasks WHERE agent_id = (SELECT id FROM agents WHERE session_uuid::text LIKE '%SESSION_UUID%') ORDER BY started_at DESC LIMIT 3;"
```

Replace SESSION_UUID with the agent's session UUID from the dashboard.

### Step 4: Use AskUserQuestion to trigger INPUT NEEDED

The agent should call `AskUserQuestion`. This will:
- Fire `notification` hook → AWAITING_INPUT (if task is PROCESSING)
- Dashboard card should show "Input needed" with orange indicator

**Take screenshot immediately after AskUserQuestion is shown.**

### Step 5: User answers the question

After answering, check:
- Dashboard card state (known limitation: no hook fires for inline tool responses, so card stays on "Input needed" until turn ends)

### Step 6: Wait for turn to complete

The `stop` hook fires at end of turn. Check:
- Dashboard card should show COMPLETE (or transition to IDLE if the next prompt is shown)
- Take screenshot after stop hook fires

### Step 7: Verify in DB

```bash
psql -d claude_headspace -c "SELECT id, state, started_at, completed_at FROM tasks WHERE agent_id = <AGENT_ID> ORDER BY started_at DESC LIMIT 3;"
```

### Step 8: Verify in logs

```bash
grep "agent_id=<AGENT_ID>" logs/app.log | tail -20
```

Expected log sequence:
```
user_prompt_submit → new_state=processing
notification → immediate AWAITING_INPUT (or "ignored" if not processing)
stop → task completed
notification → ignored (no active processing task)  ← THIS is the fix
```

## Key Files Changed

| File | Change |
|------|--------|
| `src/claude_headspace/services/event_writer.py` | Added `session` param to `write_event()` + `_write_to_session()` method |
| `src/claude_headspace/services/task_lifecycle.py` | `_write_transition_event()` passes `self._session` to EventWriter |
| `src/claude_headspace/services/hook_receiver.py` | `process_notification()` only broadcasts when DB state actually changes |
| `tests/services/test_event_writer.py` | 4 new tests for session pass-through |
| `tests/services/test_task_lifecycle.py` | 3 new tests for session forwarding |
| `tests/services/test_hook_receiver.py` | 5 updated/new tests for notification guard |

## Known Limitations

1. **AskUserQuestion → no hook on answer**: Claude Code fires `notification` when AskUserQuestion is shown but no hook fires when the user answers. The card stays on "Input needed" until the turn ends (`stop` hook).

2. **SSE after server restart**: SSE connections break on server restart. The JS client shows "Reconnecting..." and may not recover without a hard refresh. This is a separate issue from the state tracking bugs fixed above.
