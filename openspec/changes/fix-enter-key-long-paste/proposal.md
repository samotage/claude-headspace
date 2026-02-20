## Why

When pasting long text (1000+ chars) into the voice chat and pressing Enter, the text arrives in the Claude Code terminal but Enter is never accepted — the command sits in the input awaiting a manual Enter press. This has been "fixed" 7 times across 5 days (commits `032b9c0` through `e48f1ef`) and keeps returning because all fixes address symptoms (dismiss ghost text, add retries, toggle verify flag) rather than root causes (verification false positives, no post-typing ghost dismissal, fixed timing).

## What Changes

- Add post-typing ghost text dismissal in `send_text()` — dismisses autocomplete suggestions that appear AFTER text is typed, BEFORE Enter is sent (currently only pre-existing ghost text is handled)
- Replace generic content-change verification (`_pane_content_changed`) with text-presence verification (`_extract_verification_snippet`) for long text — eliminates false positives by checking "is my text still in the input?" instead of "did anything change?"
- Scale `text_enter_delay_ms` with text length — adaptive delay formula adds ~1ms per 10 chars beyond 200 characters
- Increase `DEFAULT_MAX_ENTER_RETRIES` from 1 to 3
- Add explicit `verify_enter=True` to all `send_text()` call sites in `respond.py` and `voice_bridge.py` that currently rely on the default parameter

## Capabilities

### New Capabilities

_(none — all changes are to existing capabilities)_

### Modified Capabilities

- `tmux-bridge`: Enter verification logic and ghost text handling in `send_text()` and `_verify_submission()` are being redesigned; timing constants changed; retry count increased

## Impact

- **Core file**: `src/claude_headspace/services/tmux_bridge.py` — primary changes (new helper, refactored verification, post-typing ghost dismissal, adaptive delay, constant change)
- **Route files**: `src/claude_headspace/routes/respond.py` and `voice_bridge.py` — add explicit `verify_enter=True` to 4 call sites
- **Tests**: `tests/services/test_tmux_bridge.py` — update existing verification tests, add new tests for snippet extraction, text-presence verification, post-typing ghost dismissal, and adaptive delay
- **No API changes**: All changes are internal to the tmux bridge pipeline
- **No migration needed**: No model changes
