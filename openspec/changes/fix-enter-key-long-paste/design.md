## Context

The tmux bridge (`tmux_bridge.py`) sends text to Claude Code sessions via `tmux send-keys -l` followed by a separate `send-keys Enter`. For long pasted text (1000+ chars), Enter is frequently swallowed by autocomplete ghost text that appears after the text is typed. The current verification system (`_verify_submission`) was designed to catch this but has a fundamental flaw: it checks if pane content "changed" after Enter, which produces false positives when the Ink UI is still rendering long text.

Seven previous fix attempts addressed symptoms (dismiss pre-existing ghost text, increase delay, add retry, toggle verify flag) but not the structural issues in the verification pipeline.

**Current `send_text()` pipeline:**
1. Dismiss pre-existing ghost text (Escape if detected)
2. `send-keys -l <text>` (literal text)
3. Fixed 120ms delay
4. Capture pre-Enter baseline (5 lines)
5. `send-keys Enter`
6. Wait 200ms, capture post-Enter, compare with baseline → "changed" = success
7. If unchanged: dismiss ghost text + 1 retry

**Failure mode:** Between steps 3-5, the typed text triggers NEW autocomplete suggestions. Enter hits the ghost text (swallowed). Step 6 sees pane content changed (from rendering catch-up or ghost text appearance) → false positive → reports success while text sits in input.

## Goals / Non-Goals

**Goals:**
- Eliminate Enter-key swallowing for text of any length
- Make verification deterministic rather than heuristic
- Scale timing with text length instead of using fixed constants
- Make the fix durable — address root causes so the bug doesn't return

**Non-Goals:**
- Changing the fundamental `send-keys -l` + `send-keys Enter` approach (tmux PTY delivery is sound)
- Adding async/non-blocking alternatives to the sleep-based pipeline
- Modifying Claude Code's input handling (that's upstream)
- Changing the voice chat JavaScript or API contract

## Decisions

### D1: Post-typing ghost text dismissal (proactive prevention)

**Decision:** Add a second ghost text check AFTER text is typed (between steps 3 and 4), before Enter is sent.

**Rationale:** The current ghost text check only handles pre-existing suggestions. Long text triggers NEW autocomplete suggestions that appear after typing. Dismissing these before Enter prevents the swallow in the first place — proactive rather than reactive.

**Alternative considered:** Sending Escape unconditionally before every Enter. Rejected because unconditional Escape was already tried (commit `032b9c0`) and caused TUI mode changes that ALSO prevented Enter from submitting (commit `9d25823` reverted to conditional). The conditional approach only sends Escape when ghost text ANSI markers (`\x1b[2m`, `\x1b[90m`) are detected.

### D2: Text-presence verification (specific over generic)

**Decision:** For long text (40+ chars), verify Enter acceptance by checking if the TAIL of the sent text is still visible in the pane. If the text disappeared (input cleared), Enter worked. If the text is still there, Enter failed.

**Rationale:** The current `_pane_content_changed()` check is ambiguous — any content change counts as "Enter accepted." For long text, content changes from rendering catch-up, ghost text appearance, and status line updates produce false positives. Checking for text persistence is deterministic: the sent text either exists in the pane or it doesn't.

**Alternative considered:** Double-check pattern (verify content change, wait longer, verify again). Rejected because it adds 300ms+ latency to every send and is still fundamentally heuristic-based. Text-presence is O(1) with no extra delay.

**Fallback:** For short text (< 40 chars), the snippet may be too short for reliable matching. Fall back to the existing content-change check, which works well for short text where rendering is fast and false positives are rare.

### D3: Adaptive Enter delay

**Decision:** Scale the delay between text send and Enter send with text length: `delay = base + max(0, len(text) - 200) // 10`.

**Rationale:** 120ms is sufficient for short text but not for 2000+ characters. The Ink UI needs proportional time to process and render. The formula adds ~1ms per 10 characters beyond 200, giving 329ms for a 2291-char blog post while keeping short text at the base 120ms.

**Alternative considered:** Exponential scaling. Rejected as unnecessarily aggressive — the relationship between text length and render time is roughly linear.

### D4: Increase retry count to 3

**Decision:** Change `DEFAULT_MAX_ENTER_RETRIES` from 1 to 3.

**Rationale:** With 1 retry, there are only 2 attempts total. For intermittent issues (autocomplete timing, render races), 2 attempts is insufficient. 3 retries (4 total attempts) provides meaningful resilience. Each retry adds ~400ms worst-case (200ms verify delay + 200ms clear delay), so max overhead is ~1.2s — acceptable given the alternative is a stuck command.

### D5: Explicit `verify_enter=True` everywhere

**Decision:** Add explicit `verify_enter=True` to all 4 `send_text()` call sites that currently rely on the default parameter value.

**Rationale:** The default is `True`, so this is functionally a no-op. But this parameter is critical enough that relying on defaults is dangerous — a default change or refactor could silently break verification. Explicit is always better than implicit for safety-critical parameters.

## Risks / Trade-offs

**[Risk: Snippet false negative]** If the sent text's tail appears in agent output (echoed back), the verification might think Enter failed when it actually succeeded.
→ Mitigation: Agent output appears ABOVE the input area. The verification captures the BOTTOM 5 lines (input area + status). Agent output would need to fill those exact lines with the exact snippet text — very unlikely for a 15+ character tail match. If it occurs, the consequence is a harmless retry (sending Enter to an already-processing agent does nothing).

**[Risk: Increased latency for long text]** Adaptive delay + post-typing ghost check + more retries adds time to the send pipeline.
→ Mitigation: For short text, overhead is zero (same 120ms delay, no extra ghost check if no ghost text, same retry count since retries only fire on failure). For long text, the added latency (200-300ms) is far preferable to a stuck command requiring manual intervention.

**[Risk: Escape dismissing something other than ghost text]** The ghost text detection heuristic (`\x1b[2m`, `\x1b[90m`) could match non-ghost dim text in the pane.
→ Mitigation: The check only examines the last 2-3 lines of the pane (the input area). False matches are limited to dim text in the input zone, which is overwhelmingly autocomplete suggestions. An erroneous Escape is benign — it dismisses whatever overlay is present and the text remains in the input.
