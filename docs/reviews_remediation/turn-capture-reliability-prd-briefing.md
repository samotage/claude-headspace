# CONTEXT BRIEFING: Turn Capture Reliability — PRD Creation

## Your Task

Run `/bmad:bmad-bmm-create-prd` to create a PRD for redesigning the turn capture pipeline.

## Problem Summary

Claude Headspace's voice chat dashboard silently loses agent turns. This has been a recurring bug across multiple commits — "fixed" and broken repeatedly. The root cause is architectural: the system relies on Claude Code hooks as the primary source of truth for creating turns, but hooks are unreliable.

### What Happened Today (2026-02-18)

Agent 583 was running `/bmad-bmm-quick-spec`. A background Task agent (Explore) was scanning the codebase. The sequence:

1. Main agent output its first response (5 questions) — `stop` hook fired, turn created correctly as QUESTION, task → AWAITING_INPUT
2. An automatic empty `user:answer` fired (voice chat), task → PROCESSING
3. 60s later, `notification` hook arrived, task → AWAITING_INPUT
4. Background Explore agent completed — Claude Code injected a `<task-notification>` user message (correctly filtered by `process_user_prompt_submit` at line 734)
5. Main agent output a SECOND response ("background scan complete, waiting on your 5 answers") — `stop` hook fired, HTTP 200
6. **But the turn was silently destroyed**: `process_stop` detected QUESTION intent, created the turn, then called `lifecycle.update_task_state(AWAITING_INPUT → AWAITING_INPUT)`. The state machine had NO entry for `(AWAITING_INPUT, AGENT, QUESTION)`, raised `InvalidTransitionError`, the `except` block called `db.session.rollback()`, and the turn vanished.

**Immediate fix applied** (commit `179f87c`): Added `(AWAITING_INPUT, AGENT, QUESTION) → AWAITING_INPUT` and `(AWAITING_INPUT, AGENT, PROGRESS) → AWAITING_INPUT` to the state machine. This prevents THIS specific failure. But it's a band-aid.

### The Systemic Problem

The system has THREE sources of turn data with different reliability characteristics:

1. **Hooks** — Real-time (<100ms) but unreliable. May not fire (background task completions have edge cases), may arrive late (notification 60s after stop), may arrive out of order. Currently the PRIMARY source of truth for turn creation. When they fail, turns are silently lost.

2. **JSONL Transcripts** — Delayed (file writes are async, file watcher polls every 2s) but AUTHORITATIVE. Every conversation turn is recorded. The `TranscriptReconciler` exists and is documented as the Phase 2 safety net, but it clearly isn't catching missed turns (today's bug proves it).

3. **Tmux Pane** — Near-immediate, shows what's on screen RIGHT NOW. Already captured for commander availability checks. Not used at all for turn verification or recovery.

### Current Architecture (documented but broken)

The three-phase pipeline is documented in `docs/architecture/transcript-chat-sequencing.md`:
- **Phase 1 (Hook):** Create turn with `timestamp=now()`, broadcast SSE immediately
- **Phase 2 (Reconciliation):** File watcher reads JSONL, reconciler matches entries to turns, corrects timestamps, creates missing turns
- **Phase 3 (Broadcast):** SSE events for corrections

Phase 2 is supposed to be the safety net but ISN'T WORKING for this class of bug. The reconciler matches JSONL entries to existing turns via content hashing, but when a turn was rolled back (destroyed by exception), there's nothing to match against — the reconciler should create a NEW turn, but apparently doesn't.

### What the PRD Should Cover

**The reliability inversion:** Hooks should be the fast path for OPTIMISTIC UI updates. The JSONL transcript should be the AUTHORITATIVE source that guarantees completeness. Tmux should be the EARLY WARNING that detects gaps in real-time.

Specific requirements:
1. **Transcript reconciler must actually work** — if a JSONL entry has no matching turn, CREATE one. Period. No edge cases where it silently skips.
2. **Tmux pane monitoring for turn gaps** — if the tmux pane shows agent output that doesn't have a corresponding turn within N seconds, flag it and trigger reconciliation
3. **No silent failures** — every turn creation failure must be logged, retried, or surfaced. No more `except: rollback` swallowing turns.
4. **The state machine must not destroy data** — if a state transition fails, the turn should still be committed (state stays unchanged, turn gets saved)
5. **Hook failures should be recoverable** — if a hook doesn't fire or fails processing, the system must self-heal via transcript reconciliation within seconds, not minutes.

### Key Files

| File | Role | Relevance |
|------|------|-----------|
| `src/claude_headspace/services/hook_receiver.py` | Hook processing, turn creation | Primary turn creation path; `process_stop()` lines 880-1091 |
| `src/claude_headspace/services/transcript_reconciler.py` | JSONL → DB reconciliation | Phase 2 safety net (currently broken for this case) |
| `src/claude_headspace/services/file_watcher.py` | Watches JSONL files, feeds reconciler | Triggers Phase 2 |
| `src/claude_headspace/services/task_lifecycle.py` | State transitions, turn records | `update_task_state()` raises on invalid transitions |
| `src/claude_headspace/services/state_machine.py` | Valid transition definitions | Was missing AWAITING_INPUT agent transitions (fixed) |
| `src/claude_headspace/services/commander_availability.py` | Tmux pane monitoring | Already reads tmux panes; could be extended for turn verification |
| `src/claude_headspace/services/intent_detector.py` | Classifies agent intent | Completion patterns can swallow trailing questions |
| `docs/architecture/transcript-chat-sequencing.md` | Three-phase pipeline doc | Documents what SHOULD work |
| `docs/architecture/claude-code-hooks.md` | Hook architecture doc | Claims "100% accuracy" (wrong) |
| `docs/bugs/voice-chat-agent-response-rendering.md` | Previous bug investigation | 2026-02-15 partial fix |

### Existing PRDs in the System

PRDs are in `docs/prds/{subsystem}/done/`. Relevant completed PRDs:
- `e1-s13-hook-receiver-prd.md` — original hook receiver design
- `e1-s6-state-machine-prd.md` — state machine design
- `e6-s1-voice-bridge-server-prd.md` — voice bridge server
- `e6-s2-voice-bridge-client-prd.md` — voice bridge client
- `e6-s3-agent-chat-history-prd.md` — chat history

### Important Project Rules
- NEVER restart the server unless absolutely necessary (Flask auto-reloads)
- If restart needed: `./restart_server.sh` ONLY
- Application URL: `https://smac.griffin-blenny.ts.net:5055`
- NEVER switch git branches
- Run targeted tests only, not the full suite
- All work on `development` branch, PRs target `development`
