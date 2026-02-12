# Bug Investigation: User Command Turns Not Being Persisted to Database

## Problem Statement

User commands typed into the tmux terminal are received by Claude Code agents (agents respond to them), but the corresponding USER COMMAND turns are NOT being written to the `turns` table in the database. This causes:
- Voice chat showing no user messages for some conversations
- Tasks with NULL instructions (summarisation has no user text to summarise)
- Tasks with 0 turns despite having full conversations in the terminal
- Complete data loss of user input for affected tasks

This is a **data integrity bug** — the state machine transitions fire correctly but the turn records are lost.

## Evidence

### Agent 420 (da_be8c67) — Smoking Gun

The tmux terminal shows a full conversation: user typed a long command about voice chat scroll behaviour, agent responded with detailed analysis. But the database tells a different story:

**Task 1880:**
- State: AWAITING_INPUT
- instruction: NULL
- 0 USER turns, 2 AGENT turns only (PROGRESS + QUESTION)

**State transition events (all fired correctly):**
```
Event 6853: trigger="user:command",                    idle -> commanded      (07:41:27.259075)
Event 6854: trigger="hook:post_tool_use:inferred",     commanded -> processing (07:41:27.259761)
Event 6855: trigger="hook:stop:question_detected",     processing -> awaiting_input
```

**Critical clue:** Event 6854's trigger is `hook:post_tool_use:inferred` — this is the code path at `hook_receiver.py:1468` that fires when `post_tool_use` finds NO current task. It creates a new task but **never creates a USER turn**.

Events 6853 and 6854 are 0.7ms apart — near-simultaneous.

### Agent 413 (0a6060bb) — Same Pattern

Task 1874 has 0 turns and no instruction. Same failure mode — task created but user turn lost.

## Relevant Code Paths

### 1. `process_user_prompt_submit` (hook_receiver.py:774-907)

This is where USER COMMAND turns SHOULD be created. Key flow:
1. Checks `_respond_pending_for_agent` — if set, SKIPS turn creation entirely (lines 787-799)
2. Checks for system XML (`<task-notification>`, `<system-reminder>`) — if found, SKIPS (lines 806-819)
3. Calls `lifecycle.process_turn(agent=agent, actor=TurnActor.USER, text=prompt_text)` (line 854)
4. Auto-transitions COMMANDED → PROCESSING (lines 860-864)

**Potential failure points:**
- `prompt_text` could be None/empty if the hook didn't receive the text
- `_respond_pending_for_agent` could be incorrectly set (voice bridge sets this)
- System XML filter could be too aggressive
- `lifecycle.process_turn()` could fail silently

### 2. `process_post_tool_use` — Inferred Task Path (hook_receiver.py:1414-1544)

When `post_tool_use` finds no current task (line 1433: `if not current_task`), it creates one:
```python
new_task = lifecycle.create_task(agent, TaskState.COMMANDED)
lifecycle.update_task_state(task=new_task, to_state=TaskState.PROCESSING, ...)
```
This path **never creates a USER turn**. The task exists, agent turns get added later, but the user's original command is lost forever.

### 3. Race Condition Hypothesis

Events 6853 and 6854 are 0.7ms apart. Possible scenarios:
- `post_tool_use` fires BEFORE `user_prompt_submit` completes its DB commit
- `user_prompt_submit` fires but `prompt_text` is None, so `process_turn` creates a task with state transition but maybe doesn't create a turn?
- The respond-pending flag is incorrectly set, causing `user_prompt_submit` to skip

### 4. `TaskLifecycleManager.process_turn()` (task_lifecycle.py)

This is where the actual Turn record should be created. Need to verify:
- Does it create a Turn when `text` is None?
- Does it handle the case where a task was already created by `post_tool_use:inferred`?
- Are there error paths that skip Turn creation but still transition the task state?

## Investigation Steps

1. **Check task_lifecycle.py `process_turn()`** — trace exactly what happens when `text=None` or when a task already exists in PROCESSING state

2. **Check the hook route** (`routes/hooks.py`) — verify `prompt_text` is being extracted correctly from the hook payload. The `user-prompt-submit` hook payload should contain the user's text.

3. **Add logging** to `process_user_prompt_submit`:
   - Log the value of `prompt_text` (is it None? Empty?)
   - Log whether `_respond_pending_for_agent` matched
   - Log whether the system XML filter matched
   - Log the result of `lifecycle.process_turn()`

4. **Check for race conditions** between `user_prompt_submit` and `post_tool_use`:
   - Flask dev server is single-threaded, so true races shouldn't happen
   - But if hooks fire asynchronously via shell scripts, requests could overlap
   - Check if the hook scripts use `curl` with `&` (background) or synchronous

5. **Check the hook installation** (`bin/install-hooks.sh`) — verify the `user-prompt-submit` hook is correctly installed and fires with the prompt text

6. **Reproduce**: Start a Claude Code session, type a command, and check:
   - Did the user_prompt_submit hook fire? (check Flask logs)
   - Was prompt_text populated?
   - Was a USER turn created in the DB?

## Key Files

- `src/claude_headspace/services/hook_receiver.py` — Main hook processing (all paths above)
- `src/claude_headspace/services/task_lifecycle.py` — TaskLifecycleManager.process_turn()
- `src/claude_headspace/routes/hooks.py` — Hook HTTP endpoints (extracts payload fields)
- `bin/install-hooks.sh` — Hook installation script
- `src/claude_headspace/services/tmux_bridge.py` — Voice bridge respond (sets _respond_pending)

## Database Queries for Verification

```sql
-- Find tasks with 0 user turns (affected tasks)
SELECT t.id, t.agent_id, t.state, t.instruction, t.started_at,
       (SELECT count(*) FROM turns tr WHERE tr.task_id = t.id AND tr.actor = 'user') as user_turns,
       (SELECT count(*) FROM turns tr WHERE tr.task_id = t.id AND tr.actor = 'agent') as agent_turns
FROM tasks t
WHERE t.agent_id IN (
    SELECT id FROM agents WHERE ended_at IS NULL OR ended_at > now() - interval '24 hours'
)
ORDER BY t.id DESC
LIMIT 50;

-- Find inferred tasks (post_tool_use created without user turn)
SELECT e.agent_id, e.task_id, e.payload, e.timestamp
FROM events e
WHERE e.event_type = 'state_transition'
AND e.payload::text LIKE '%post_tool_use:inferred%'
ORDER BY e.timestamp DESC
LIMIT 20;
```

## Expected Fix Direction

The fix likely needs to ensure that:
1. When `post_tool_use:inferred` creates a task, it should attempt to recover the user's command text (from the transcript file or a pending hook payload)
2. OR: the `user_prompt_submit` hook needs to reliably fire and persist the turn BEFORE `post_tool_use` can infer a task
3. OR: `post_tool_use` should detect that `user_prompt_submit` is about to fire and defer task creation

The most robust fix is probably to make `post_tool_use:inferred` task creation also capture the user's command from the transcript, so even if the hook fails, the data isn't lost.
