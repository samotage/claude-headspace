# Fix: Enter-Key Swallowing on Long Text Paste

## Problem

When pasting long text (1000+ chars) into the voice chat message box and pressing Enter, the text arrives in the Claude Code terminal but Enter is never accepted — the command sits in the input awaiting a manual Enter press. This bug has been "fixed" 7 times across 5 days and keeps returning because the fixes address symptoms, not root causes.

## Root Causes

### RC1: No post-typing ghost text dismissal
Ghost text is only dismissed BEFORE sending text (`send_text()` step 1). After typing 2000+ characters, Claude Code's autocomplete triggers NEW suggestions on the typed content. This ghost text appears AFTER the text is sent but BEFORE Enter. Enter arrives and gets swallowed by the autocomplete (accepts the suggestion instead of submitting).

### RC2: False positive in verification
`_verify_submission()` checks if pane content changed after Enter. But for long text, content changes for OTHER reasons: continued rendering (120ms isn't enough for the UI to finish), ghost text appearing, status line updates. The verification sees ANY change as "Enter worked" — a false positive. The API returns 200 but Enter was never accepted.

### RC3: Fixed timing constants
`DEFAULT_TEXT_ENTER_DELAY_MS = 120` is the same for 5 characters or 5000 characters. For 2000+ chars across ~60 terminal lines, the Ink UI needs significantly more time to process and render before Enter can be reliably sent.

### RC4: Only 1 retry
`DEFAULT_MAX_ENTER_RETRIES = 1` means if the first Enter fails AND the single retry fails, the send is reported as failed (or worse, as succeeded via false positive). Long text is more likely to need multiple retries.

### RC5: Missing explicit `verify_enter=True` in secondary paths
`respond.py` text mode, `respond.py` other mode, `voice_bridge.py` picker path, and `voice_bridge.py` upload path all rely on the default parameter value. While the default IS True, explicit is better than implicit for a parameter this critical.

## Implementation Plan

### Change 1: Add post-typing ghost text dismissal in `send_text()`

**File:** `src/claude_headspace/services/tmux_bridge.py`
**Location:** Between step 3 (delay) and step 4 (pre-Enter capture), around line 458

After `time.sleep(text_enter_delay_ms / 1000.0)`, insert a NEW ghost text check:

```python
# Step 3: Delay between text and Enter
time.sleep(text_enter_delay_ms / 1000.0)

# Step 3.5 (NEW): Dismiss ghost text triggered by typed content.
# The step-1 check only handles PRE-EXISTING ghost text. Long text
# often triggers NEW autocomplete suggestions that appear after typing.
# If not dismissed, Enter gets swallowed by the autocomplete.
if detect_ghost_text:
    post_type_content = capture_pane(
        pane_id, lines=3, include_escapes=True, timeout=timeout,
    )
    if _has_autocomplete_ghost(post_type_content):
        logger.debug(
            f"Post-typing ghost text detected in pane {pane_id}, "
            f"dismissing with Escape before Enter"
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane_id, "Escape"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        time.sleep(clear_delay_ms / 1000.0)
```

This is the **most impactful fix** — it prevents Enter from being swallowed in the first place.

### Change 2: Improve verification with text-presence check

**File:** `src/claude_headspace/services/tmux_bridge.py`

#### 2a: Add `_extract_verification_snippet()` helper (new function, place near `_pane_content_changed`)

```python
def _extract_verification_snippet(text: str, max_len: int = 60) -> str | None:
    """Extract a distinctive tail snippet from sent text for verification.

    After Enter is accepted, the input area clears and agent output appears.
    If the tail of the sent text is still visible in the bottom lines of the
    pane, Enter was NOT accepted (text still in input).

    Returns None if the text is too short for reliable snippet matching.

    Args:
        text: The text that was sent to the pane
        max_len: Maximum snippet length

    Returns:
        A snippet string to search for, or None if text is too short
    """
    if not text or len(text) < 40:
        return None

    # Use the last line of meaningful content (skip blank lines at end)
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None

    # Take the last non-empty line, truncated to max_len
    snippet = lines[-1]
    if len(snippet) > max_len:
        snippet = snippet[-max_len:]

    # Must be long enough to avoid spurious matches
    return snippet if len(snippet) >= 15 else None
```

#### 2b: Update `_verify_submission()` signature and logic

Add `sent_text: str = ""` parameter. Update the verification to use text-presence as the primary check for long text, falling back to content-change for short text:

```python
def _verify_submission(
    pane_id: str,
    pre_submit_content: str,
    timeout: float,
    clear_delay_ms: int,
    verify_delay_ms: int = DEFAULT_ENTER_VERIFY_DELAY_MS,
    max_retries: int = DEFAULT_MAX_ENTER_RETRIES,
    sent_text: str = "",
) -> bool:
    """Verify that Enter was accepted by checking pane state.

    Two strategies, chosen based on text length:
    - Long text (40+ chars): check if the tail of the sent text is STILL
      visible in the pane. If gone, input was cleared → Enter accepted.
      More reliable than content-change because it avoids false positives
      from rendering catch-up and ghost text appearance.
    - Short text: fall back to content-change comparison (original logic).

    ...existing docstring...
    """
    snippet = _extract_verification_snippet(sent_text)

    for attempt in range(1, max_retries + 1):
        time.sleep(verify_delay_ms / 1000.0)
        post_content = capture_pane(
            pane_id, lines=DEFAULT_ENTER_VERIFY_LINES, timeout=timeout,
        )

        if snippet:
            # Text-presence check: if snippet is GONE, Enter was accepted
            if snippet not in post_content:
                logger.info(
                    f"Enter confirmed (text cleared) after {attempt} "
                    f"attempt(s) for pane {pane_id}"
                )
                return True
            # Snippet still visible → Enter was NOT accepted
            logger.debug(
                f"Pane {pane_id} still shows sent text after Enter "
                f"(attempt {attempt}/{max_retries})"
            )
        else:
            # Short text fallback: content-change check
            if _pane_content_changed(pre_submit_content, post_content):
                logger.info(
                    f"Enter confirmed after {attempt} attempt(s) "
                    f"for pane {pane_id}"
                )
                return True
            logger.debug(
                f"Pane {pane_id} unchanged after Enter "
                f"(attempt {attempt}/{max_retries})"
            )

        # Enter was lost — try to recover
        # Check for autocomplete ghost text that may have appeared
        ghost_content = capture_pane(
            pane_id, lines=3, include_escapes=True, timeout=timeout,
        )
        if _has_autocomplete_ghost(ghost_content):
            logger.debug(
                f"Ghost text detected during retry for pane {pane_id}, "
                f"dismissing with Escape"
            )
            try:
                subprocess.run(
                    ["tmux", "send-keys", "-t", pane_id, "Escape"],
                    check=True,
                    timeout=timeout,
                    capture_output=True,
                )
                time.sleep(clear_delay_ms / 1000.0)
            except Exception:
                pass

        # Retry Enter
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "Enter"],
                check=True,
                timeout=timeout,
                capture_output=True,
            )
        except Exception as e:
            logger.warning(f"Enter retry failed for pane {pane_id}: {e}")

    # All retries exhausted
    _diagnostic_dump(pane_id, "Enter verification failed after all retries")
    return False
```

#### 2c: Update `_verify_submission()` call in `send_text()` to pass `sent_text`

At line ~480:
```python
if not _verify_submission(
    pane_id,
    pre_enter_content,
    timeout=timeout,
    clear_delay_ms=clear_delay_ms,
    verify_delay_ms=enter_verify_delay_ms,
    max_retries=max_enter_retries,
    sent_text=sanitised,  # NEW
):
```

### Change 3: Scale delay with text length

**File:** `src/claude_headspace/services/tmux_bridge.py`
**Location:** In `send_text()`, around line 458

Replace the fixed delay with an adaptive one:

```python
# Step 3: Delay between text and Enter.
# Scale with text length — Ink needs more time to process and render
# long text before Enter can be reliably accepted.
adaptive_delay_ms = text_enter_delay_ms + max(0, len(sanitised) - 200) // 10
time.sleep(adaptive_delay_ms / 1000.0)
```

This adds ~1ms per 10 characters beyond 200 chars. For the 2291-char blog post: `120 + (2291-200)//10 = 120 + 209 = 329ms`. For short text: unchanged at 120ms.

Add a log line:
```python
if adaptive_delay_ms != text_enter_delay_ms:
    logger.debug(
        f"Adaptive Enter delay for pane {pane_id}: "
        f"{adaptive_delay_ms}ms (text: {len(sanitised)} chars)"
    )
```

### Change 4: Increase default retries

**File:** `src/claude_headspace/services/tmux_bridge.py`
**Location:** Line 25

```python
DEFAULT_MAX_ENTER_RETRIES = 3  # was 1
```

### Change 5: Add explicit `verify_enter=True` to all call sites

**File:** `src/claude_headspace/routes/respond.py`

At line 227-232 (text mode `send_text`), add `verify_enter=True`:
```python
if mode == "text":
    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text=text,
        timeout=subprocess_timeout,
        text_enter_delay_ms=text_enter_delay_ms,
        verify_enter=True,  # ADD THIS
    )
```

At line 264-269 (other mode `send_text`), add `verify_enter=True`:
```python
result = tmux_bridge.send_text(
    pane_id=agent.tmux_pane_id,
    text=text,
    timeout=subprocess_timeout,
    text_enter_delay_ms=text_enter_delay_ms,
    verify_enter=True,  # ADD THIS
)
```

**File:** `src/claude_headspace/routes/voice_bridge.py`

At line 380-385 (picker path `send_text`), add `verify_enter=True`:
```python
result = tmux_bridge.send_text(
    pane_id=agent.tmux_pane_id,
    text=send_text,
    timeout=subprocess_timeout,
    text_enter_delay_ms=text_enter_delay_ms,
    verify_enter=True,  # ADD THIS
)
```

At line 623-628 (upload path `send_text`), add `verify_enter=True`:
```python
result = tmux_bridge.send_text(
    pane_id=agent.tmux_pane_id,
    text=tmux_text,
    timeout=subprocess_timeout,
    text_enter_delay_ms=text_enter_delay_ms,
    verify_enter=True,  # ADD THIS
)
```

## Testing

### Unit tests to update

**File:** `tests/services/test_tmux_bridge.py`

1. Update existing `_verify_submission` tests for the new `sent_text` parameter
2. Add test: `test_verify_submission_text_presence_check` — verify that when a snippet of sent text is still in the pane, verification returns False (Enter not accepted)
3. Add test: `test_verify_submission_text_cleared` — verify that when the snippet is gone from the pane, verification returns True
4. Add test: `test_verify_submission_short_text_fallback` — verify that text < 40 chars uses content-change logic
5. Add test: `test_extract_verification_snippet` — test snippet extraction edge cases
6. Add test: `test_post_typing_ghost_text_dismissal` — verify that ghost text appearing after text send triggers Escape before Enter
7. Add test: `test_adaptive_delay_long_text` — verify delay scales with text length

### Route tests to verify

**File:** `tests/routes/test_respond.py`
- Verify the `verify_enter=True` parameter is passed in text and other mode sends

**File:** `tests/routes/test_voice_bridge.py` (if exists)
- Verify the `verify_enter=True` parameter is passed in picker and upload paths

### Integration verification

After implementation, verify with the existing agent-driven test:
```bash
pytest tests/agent_driven/test_long_paste_input.py -v
```

## Implementation Order

1. **Change 4** (increase retries) — one-line constant change, lowest risk
2. **Change 5** (explicit verify_enter) — add parameters to 4 call sites, low risk
3. **Change 3** (adaptive delay) — small formula change in one location
4. **Change 1** (post-typing ghost text dismissal) — most impactful fix, adds ~10 lines
5. **Change 2** (text-presence verification) — largest change, refactors core verification logic
6. **Tests** — update existing, add new unit tests
7. **Run targeted tests** — `pytest tests/services/test_tmux_bridge.py tests/routes/test_respond.py -v`

## Key Constants Reference

```
File: src/claude_headspace/services/tmux_bridge.py

Line 21: DEFAULT_TEXT_ENTER_DELAY_MS = 120      # base delay, augmented by adaptive formula
Line 22: DEFAULT_CLEAR_DELAY_MS = 200           # delay after Escape dismisses ghost text
Line 23: DEFAULT_SEQUENTIAL_SEND_DELAY_MS = 150 # delay between sequential key sends
Line 24: DEFAULT_ENTER_VERIFY_DELAY_MS = 200    # delay before each verification capture
Line 25: DEFAULT_MAX_ENTER_RETRIES = 1 → 3      # CHANGE THIS
Line 26: DEFAULT_ENTER_VERIFY_LINES = 5         # pane lines to capture for verification
```

## Why This Fix Is Different

Previous fixes all worked at the SYMPTOM level:
- "Dismiss ghost text before sending" → only handles pre-existing ghost text
- "Increase Enter delay" → still fixed, doesn't scale
- "Add verification + retry" → verification has false positives, only 1 retry
- "Always verify (even during PROCESSING)" → verification is there but broken

This fix works at the ROOT CAUSE level:
- **Post-typing ghost dismissal** prevents Enter from being swallowed (proactive, not reactive)
- **Text-presence verification** eliminates false positives (specific check, not generic)
- **Adaptive delay** gives the UI proportional time for long text
- **3 retries** provides real resilience instead of a single second chance
