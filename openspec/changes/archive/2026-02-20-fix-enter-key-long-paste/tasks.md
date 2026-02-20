## 1. Constants and Retry Count

- [x] 1.1 In `src/claude_headspace/services/tmux_bridge.py`, change `DEFAULT_MAX_ENTER_RETRIES = 1` to `DEFAULT_MAX_ENTER_RETRIES = 3` (line 25)

## 2. Explicit verify_enter at Call Sites

- [x] 2.1 In `src/claude_headspace/routes/respond.py`, add `verify_enter=True` to the text mode `send_text()` call (line ~227-232, inside `if mode == "text":`)
- [x] 2.2 In `src/claude_headspace/routes/respond.py`, add `verify_enter=True` to the other mode `send_text()` call (line ~264-269, inside `elif mode == "other":`, the second `send_text` after the "Other" option is selected)
- [x] 2.3 In `src/claude_headspace/routes/voice_bridge.py`, add `verify_enter=True` to the picker path `send_text()` call (line ~380-385, inside `if has_picker and is_answering:`, the `send_text` after navigating to "Other")
- [x] 2.4 In `src/claude_headspace/routes/voice_bridge.py`, add `verify_enter=True` to the upload path `send_text()` call (line ~623-628, inside `upload_file()` function)

## 3. Adaptive Enter Delay

- [x] 3.1 In `src/claude_headspace/services/tmux_bridge.py` `send_text()`, replace the fixed `time.sleep(text_enter_delay_ms / 1000.0)` (line ~458) with an adaptive delay: `adaptive_delay_ms = text_enter_delay_ms + max(0, len(sanitised) - 200) // 10`. Add a debug log when the adaptive delay differs from the base delay.

## 4. Post-Typing Ghost Text Dismissal

- [x] 4.1 In `src/claude_headspace/services/tmux_bridge.py` `send_text()`, add a second ghost text check AFTER the adaptive delay and BEFORE the pre-Enter baseline capture (between current step 3 and step 4, around line 458-462). When `detect_ghost_text` is True, capture pane with `include_escapes=True`, check `_has_autocomplete_ghost()`, and if detected send `Escape` + `clear_delay_ms` wait. This mirrors the existing step-1 ghost text check but catches NEW autocomplete suggestions triggered by the typed text.

## 5. Verification Snippet Extraction

- [x] 5.1 In `src/claude_headspace/services/tmux_bridge.py`, add `_extract_verification_snippet(text, max_len=60)` function near `_pane_content_changed()` (around line 269-287). It extracts the last non-empty line of the text (truncated to `max_len` from the end). Returns None if text < 40 chars, or if the snippet would be < 15 chars. See design doc and workshop plan for exact implementation.

## 6. Text-Presence Verification

- [x] 6.1 In `src/claude_headspace/services/tmux_bridge.py`, update `_verify_submission()` signature to add `sent_text: str = ""` parameter
- [x] 6.2 In `_verify_submission()`, at the top of the method body (before the retry loop), call `snippet = _extract_verification_snippet(sent_text)`. Then refactor the loop: if `snippet` is not None, use text-presence check (snippet NOT in post_content = Enter accepted; snippet IN post_content = Enter failed). If `snippet` is None, fall back to existing `_pane_content_changed()` logic. Keep the ghost text dismissal and Enter retry logic for both paths.
- [x] 6.3 Update the `_verify_submission()` call in `send_text()` (line ~480) to pass `sent_text=sanitised`

## 7. Unit Tests

- [x] 7.1 In `tests/services/test_tmux_bridge.py`, add `test_extract_verification_snippet_long_text` — verify that text of 40+ chars produces a non-None snippet from the last non-empty line
- [x] 7.2 Add `test_extract_verification_snippet_short_text` — verify that text < 40 chars returns None
- [x] 7.3 Add `test_extract_verification_snippet_empty` — verify that empty/whitespace text returns None
- [x] 7.4 Add `test_extract_verification_snippet_short_last_line` — verify that text where the last non-empty line is < 15 chars returns None
- [x] 7.5 Add `test_verify_submission_text_presence_success` — mock `capture_pane` to return content WITHOUT the snippet; verify `_verify_submission()` returns True
- [x] 7.6 Add `test_verify_submission_text_presence_failure_then_retry` — mock `capture_pane` to return content WITH the snippet on first call, then WITHOUT on retry; verify ghost text check and Enter retry happen
- [x] 7.7 Add `test_verify_submission_short_text_fallback` — verify that short text (< 40 chars) uses `_pane_content_changed` logic instead of snippet check
- [x] 7.8 Add `test_post_typing_ghost_text_dismissed` — mock `capture_pane` to return ghost text ANSI after the text send delay; verify Escape is sent before Enter
- [x] 7.9 Add `test_adaptive_delay_scales_with_length` — verify that `send_text()` uses a longer delay for 2000+ char text than for 50-char text (check via mock `time.sleep` calls)
- [x] 7.10 Update any existing `_verify_submission` tests that break due to the new `sent_text` parameter (add `sent_text=""` to preserve short-text fallback behavior)

## 8. Route Tests

- [x] 8.1 In `tests/routes/test_respond.py`, verify that the text mode path calls `send_text` with `verify_enter=True`
- [x] 8.2 In `tests/routes/test_respond.py`, verify that the other mode path calls `send_text` with `verify_enter=True`

## 9. Run and Verify

- [x] 9.1 Run targeted tests: `pytest tests/services/test_tmux_bridge.py tests/routes/test_respond.py -v`
